"""Build exFAT view: turn a PS5 dump folder into a .exfat image for ShadowMountPlus.

The build needs sudo (mount/umount), which a full-screen TUI can't prompt for, so
the app suspends around run_build: control drops to the real terminal where sudo
prompts and rsync streams, then the TUI resumes and shows the result.
"""

from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Input, Label, ProgressBar, Select, Static, Switch
from textual.worker import get_current_worker

from mkpfs_tui.config import load
from mkpfs_tui.deploy.deployer import DeployOptions, DeployResult, run_deploy
from mkpfs_tui.deploy.ftp import FtpTarget
from mkpfs_tui.exfat.builder import BuildOptions, BuildResult, run_build
from mkpfs_tui.exfat.naming import read_param, suggest_filename, suggest_label
from mkpfs_tui.exfat.sizing import CLUSTER_CHOICES, plan_size
from mkpfs_tui.exfat.tools import preflight
from mkpfs_tui.messages import DeployFinished, DeployProgressed
from mkpfs_tui.screens.confirm import ConfirmScreen
from mkpfs_tui.widgets.path_field import PathField
from mkpfs_tui.widgets.result_panel import ResultPanel

VIEW_ID = "build"

_CLUSTER_OPTIONS = [(key.capitalize() if key == "auto" else key, key) for key in CLUSTER_CHOICES]
_PRESET_OPTIONS = [("PPSA only", "ppsa"), ("PPSA + Title", "title"), ("PPSA + Title (Version)", "version")]


class BuildExfatView(Container):
    """Form + suspend-and-build flow for an exFAT image."""

    def compose(self) -> ComposeResult:
        """Render the dump/output/label/cluster fields, build button, and result panel."""
        yield PathField("Dump folder", "dir", id="build-source")
        yield PathField("Output image", "file", id="build-output")
        with Horizontal(classes="field-row"):
            yield Input(id="build-label", placeholder="volume label (≤ 11 chars)")
            yield Select(_CLUSTER_OPTIONS, value="auto", allow_blank=False, id="build-cluster")
        with Horizontal(classes="field-row"):
            yield Select(_PRESET_OPTIONS, value="version", allow_blank=False, id="build-preset")
        with Horizontal(classes="toggle"):
            yield Label("Lowercase filename")
            yield Switch(value=False, id="build-lower")
        with Horizontal(classes="toggle"):
            yield Label("Verify after (fsck.exfat)")
            yield Switch(value=True, id="build-verify")
        with Horizontal(classes="toggle"):
            yield Label("Deploy to PS5 after build")
            yield Switch(value=False, id="build-deploy-after")
        with Horizontal(classes="field-row"):
            yield Input(id="build-host", placeholder="PS5 IP / host")
            yield Input(id="build-port", placeholder="port")
            yield Input(id="build-user", placeholder="user")
            yield Input(id="build-pass", password=True, placeholder="password")
        yield ProgressBar(total=100, id="build-bar")
        yield Static("", id="build-estimate")
        with Horizontal(classes="option-row"):
            yield Button("Build exFAT", id="build-run", variant="primary")
        yield ResultPanel(id="build-result")

    def on_mount(self) -> None:
        """Initialise auto-fill memory and widget titles."""
        self._auto_output = ""
        self._auto_label = ""
        self.query_one("#build-label", Input).border_title = "Volume label"
        self.query_one("#build-cluster", Select).border_title = "Cluster size"
        cfg = load()
        self.query_one("#build-host", Input).value = cfg.host
        self.query_one("#build-port", Input).value = str(cfg.port)
        self.query_one("#build-user", Input).value = cfg.user
        self.query_one("#build-preset", Select).border_title = "Filename preset"

    def _source_dump(self) -> Path | None:
        """Return the dump folder if the source field points at a real directory."""
        source = self.query_one("#build-source", PathField).value
        dump = Path(source)
        return dump if source.strip() and dump.is_dir() else None

    def _preset(self) -> str:
        """Current filename preset."""
        return str(self.query_one("#build-preset", Select).value)

    def _lower(self) -> bool:
        """Whether the lowercase toggle is on."""
        return self.query_one("#build-lower", Switch).value

    def _refresh_from_source(self) -> None:
        """Auto-fill output + label from param.json and update the size estimate."""
        dump = self._source_dump()
        if dump is None:
            return
        info = read_param(dump)
        out = self.query_one("#build-output", PathField)
        if not out.value or out.value == self._auto_output:
            derived = str(dump.parent / suggest_filename(info, dump, preset=self._preset(), lowercase=self._lower()))
            out.value = derived
            self._auto_output = derived
        label = self.query_one("#build-label", Input)
        if not label.value or label.value == self._auto_label:
            suggested = suggest_label(info, dump)
            label.value = suggested
            self._auto_label = suggested
        self._update_estimate(dump)

    def _update_estimate(self, dump: Path) -> None:
        """Recompute and show the size estimate for the current cluster choice."""
        cluster = CLUSTER_CHOICES[str(self.query_one("#build-cluster", Select).value)]
        plan = plan_size(dump, cluster)
        self.query_one("#build-estimate", Static).update(
            f"≈ {plan.size_mb} MB · cluster {plan.cluster_bytes // 1024}K · {plan.file_count} files"
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        """Refresh auto-fill + estimate when the source path changes."""
        parent = event.input.parent
        if parent is not None and parent.id == "build-source":
            self._refresh_from_source()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Recompute estimate (cluster) or auto-fill (preset) on a Select change."""
        if (dump := self._source_dump()) is None:
            return
        if event.select.id == "build-cluster":
            self._update_estimate(dump)
        elif event.select.id == "build-preset":
            self._refresh_from_source()

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Re-derive the filename when the lowercase toggle flips."""
        if event.switch.id == "build-lower" and self._source_dump() is not None:
            self._refresh_from_source()

    def read_options(self) -> BuildOptions:
        """Read the form into a BuildOptions (call on the main thread)."""
        return BuildOptions(
            dump=Path(self.query_one("#build-source", PathField).value),
            output=Path(self.query_one("#build-output", PathField).value),
            label=self.query_one("#build-label", Input).value.strip(),
            cluster_override=CLUSTER_CHOICES[str(self.query_one("#build-cluster", Select).value)],
            verify=self.query_one("#build-verify", Switch).value,
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Start the build, gating on overwrite if the output already exists."""
        if event.button.id != "build-run":
            return
        event.stop()
        opts = self.read_options()
        if opts.output.exists():
            self.app.push_screen(
                ConfirmScreen(f"{opts.output} exists. Overwrite?"),
                lambda ok: self._run_build(opts) if ok else None,
            )
        else:
            self._run_build(opts)

    def _run_build(self, opts: BuildOptions) -> None:
        """Pre-flight, then suspend the TUI to run the build on the real terminal."""
        result_panel = self.query_one("#build-result", ResultPanel)
        missing = preflight(verify=opts.verify)
        if missing:
            result_panel.show(tuple(missing), ())
            return
        with self.app.suspend():
            print(f"\nBuilding {opts.output} from {opts.dump} …\n")
            result = run_build(opts)
        self._show_result(result)

    def _show_result(self, result: BuildResult) -> None:
        """Render a BuildResult; if deploy-after is on and the build succeeded, push it."""
        panel = self.query_one("#build-result", ResultPanel)
        if not result.ok:
            panel.show(("Build failed.", *result.errors), ())
            return
        note = (
            f"Built {result.output_path} — {result.size_mb} MB, "
            f"cluster {result.cluster_bytes // 1024}K, label {result.label}"
        )
        panel.show((), (), (note,))
        if self.query_one("#build-deploy-after", Switch).value:
            self._deploy_built(Path(result.output_path))

    def _deploy_built(self, output: Path) -> None:
        """Start an FTP upload of the freshly built image (worker + progress bar)."""
        host = self.query_one("#build-host", Input).value.strip()
        if not host:
            self.query_one("#build-result", ResultPanel).show((), ("Built — skipped deploy (no host given).",), ())
            return
        try:
            port = int(self.query_one("#build-port", Input).value)
        except (TypeError, ValueError):
            port = 2121
        target = FtpTarget(
            host=host,
            port=port,
            user=self.query_one("#build-user", Input).value.strip() or "anonymous",
            password=self.query_one("#build-pass", Input).value,
        )
        self.query_one("#build-bar", ProgressBar).update(progress=0)
        self._deploy(DeployOptions(local_file=output, target=target, overwrite=True))

    @work(thread=True, exclusive=True)
    def _deploy(self, opts: DeployOptions) -> None:
        """Upload the built image; stream progress and the final result."""
        worker = get_current_worker()
        result = run_deploy(
            opts,
            progress_cb=lambda sent, total: self.post_message(DeployProgressed(VIEW_ID, sent, total)),
            should_cancel=lambda: worker.is_cancelled,
        )
        self.post_message(DeployFinished(VIEW_ID, result))

    def on_deploy_progressed(self, message: DeployProgressed) -> None:
        """Advance the deploy progress bar during an after-build upload."""
        if message.view_id == VIEW_ID and message.total > 0:
            self.query_one("#build-bar", ProgressBar).update(progress=int(message.sent * 100 / message.total))

    def on_deploy_finished(self, message: DeployFinished) -> None:
        """Append the deploy outcome to the build result panel."""
        if message.view_id != VIEW_ID or not isinstance(message.result, DeployResult):
            return
        result = message.result
        panel = self.query_one("#build-result", ResultPanel)
        if result.ok:
            panel.show((), (), (f"Deployed {result.remote_path} — {result.bytes_sent} bytes",))
        elif result.cancelled:
            panel.show((), ("Deploy cancelled.",), ())
        else:
            panel.show(("Deploy failed.", *result.errors), ())
