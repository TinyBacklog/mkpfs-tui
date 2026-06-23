"""Build exFAT view: turn a PS5 dump folder into a .exfat image for ShadowMountPlus.

The build needs sudo (mount/umount), which a full-screen TUI can't prompt for, so
the app suspends around run_build: control drops to the real terminal where sudo
prompts and rsync streams, then the TUI resumes and shows the result.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Input, Label, Select, Static, Switch

from mkpfs_tui.exfat.builder import BuildOptions, BuildResult, run_build
from mkpfs_tui.exfat.naming import read_param, suggest_filename, suggest_label
from mkpfs_tui.exfat.sizing import CLUSTER_CHOICES, plan_size
from mkpfs_tui.exfat.tools import preflight
from mkpfs_tui.screens.confirm import ConfirmScreen
from mkpfs_tui.widgets.path_field import PathField
from mkpfs_tui.widgets.result_panel import ResultPanel

VIEW_ID = "build"

_CLUSTER_OPTIONS = [(key.capitalize() if key == "auto" else key, key) for key in CLUSTER_CHOICES]


class BuildExfatView(Container):
    """Form + suspend-and-build flow for an exFAT image."""

    def compose(self) -> ComposeResult:
        """Render the dump/output/label/cluster fields, build button, and result panel."""
        yield PathField("Dump folder", "dir", id="build-source")
        yield PathField("Output image", "file", id="build-output")
        with Horizontal(classes="field-row"):
            yield Input(id="build-label", placeholder="volume label (≤ 11 chars)")
            yield Select(_CLUSTER_OPTIONS, value="auto", allow_blank=False, id="build-cluster")
        with Horizontal(classes="toggle"):
            yield Label("Verify after (fsck.exfat)")
            yield Switch(value=True, id="build-verify")
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

    def _source_dump(self) -> Path | None:
        """Return the dump folder if the source field points at a real directory."""
        source = self.query_one("#build-source", PathField).value
        dump = Path(source)
        return dump if source.strip() and dump.is_dir() else None

    def _refresh_from_source(self) -> None:
        """Auto-fill output + label from param.json and update the size estimate."""
        dump = self._source_dump()
        if dump is None:
            return
        info = read_param(dump)
        out = self.query_one("#build-output", PathField)
        if not out.value or out.value == self._auto_output:
            derived = str(dump.parent / suggest_filename(info, dump))
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
        """Recompute the estimate when the cluster choice changes."""
        if event.select.id == "build-cluster" and (dump := self._source_dump()) is not None:
            self._update_estimate(dump)

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
        """Render a BuildResult in the result panel."""
        panel = self.query_one("#build-result", ResultPanel)
        if result.ok:
            note = (
                f"Built {result.output_path} — {result.size_mb} MB, "
                f"cluster {result.cluster_bytes // 1024}K, label {result.label}"
            )
            panel.show((), (), (note,))
        else:
            panel.show(("Build failed.", *result.errors), ())
