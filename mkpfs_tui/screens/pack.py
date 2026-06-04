"""Pack view: build a PFS image from a folder/file via a streaming subprocess."""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Input, Label, ProgressBar, RadioButton, RadioSet, Select, Static, Switch
from textual.worker import get_current_worker

from mkpfs_tui import mkpfs_runner
from mkpfs_tui.messages import PackCompleted, PackProgressed, PackStatusLine
from mkpfs_tui.mkpfs_runner import PackFinished, PackProgress, PackStatus
from mkpfs_tui.models import PackOptions, build_pack_argv
from mkpfs_tui.screens.confirm import ConfirmScreen
from mkpfs_tui.widgets.path_field import PathField
from mkpfs_tui.widgets.result_panel import ResultPanel

VIEW_ID = "pack"


def _int(value: str, default: int = 0) -> int:
    """Parse an int from form text, returning default on blank/invalid.

    Args:
        value: The raw string from an Input widget.
        default: Fallback value when parsing fails.

    Returns:
        The parsed integer, or default if the string is blank or not a valid int.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class PackView(Container):
    """Form + live progress for packing a PFS image."""

    def compose(self) -> ComposeResult:
        """Render the pack form, run/cancel buttons, progress, and result panel."""
        with RadioSet(id="pack-mode"):
            yield RadioButton("Folder", value=True, id="pack-mode-folder")
            yield RadioButton("File", id="pack-mode-file")
        yield PathField("Source", "dir", id="pack-source")
        yield PathField("Output image", "file", id="pack-output")
        with Horizontal(classes="field-row"):
            yield Select(
                [("PS4", "PS4"), ("PS5", "PS5")],
                value="PS4",
                allow_blank=False,
                id="pack-version",
            )
            yield Select(
                [("32-bit inodes", 32), ("64-bit inodes", 64)],
                value=32,
                allow_blank=False,
                id="pack-inode-bits",
            )
        with Horizontal(classes="field-row"):
            yield Input(value="auto", id="pack-block-size", placeholder="block size (auto)")
            yield Input(value="0", id="pack-threshold-gain", placeholder="threshold gain %")
            yield Input(value="9", id="pack-compression-level", placeholder="compression level 0-9")
            yield Input(value="0", id="pack-cpu-count", placeholder="cpu count (0=auto)")
            yield Input(value="0", id="pack-min-compress-size", placeholder="min compress size")
        yield Input(id="pack-ekpfs", placeholder="EKPFS key — 64 hex, with --encrypted")
        with Horizontal(id="pack-toggles"):
            for switch_id, label, default in (
                ("pack-compress", "Compress", True),
                ("pack-case-insensitive", "Case-insensitive", True),
                ("pack-signed", "Signed", False),
                ("pack-encrypted", "Encrypted", False),
                ("pack-dry-run", "Dry run", False),
                ("pack-verify", "Verify after", False),
            ):
                with Horizontal(classes="toggle"):
                    yield Label(label)
                    yield Switch(value=default, id=switch_id)
        with Horizontal(classes="option-row"):
            yield Button("Pack", id="pack-run", variant="primary")
            yield Button("Cancel", id="pack-cancel", variant="error")
        yield ProgressBar(total=100, id="pack-bar")
        yield Static("", id="pack-phase")
        yield ResultPanel(id="pack-result")

    def read_options(self) -> PackOptions:
        """Read the form widgets into a PackOptions (call on the main thread).

        Returns:
            A PackOptions built from the current widget values.
        """
        mode = "file" if self.query_one("#pack-mode", RadioSet).pressed_index == 1 else "folder"
        return PackOptions(
            mode=mode,
            source=self.query_one("#pack-source", PathField).value,
            output=self.query_one("#pack-output", PathField).value,
            pfs_version=str(self.query_one("#pack-version", Select).value),
            inode_bits=int(self.query_one("#pack-inode-bits", Select).value),
            block_size=self.query_one("#pack-block-size", Input).value or "auto",
            threshold_gain=_int(self.query_one("#pack-threshold-gain", Input).value),
            compression_level=_int(self.query_one("#pack-compression-level", Input).value, 9),
            cpu_count=_int(self.query_one("#pack-cpu-count", Input).value),
            min_compress_size=_int(self.query_one("#pack-min-compress-size", Input).value),
            ekpfs_key=self.query_one("#pack-ekpfs", Input).value,
            compress=self.query_one("#pack-compress", Switch).value,
            signed=self.query_one("#pack-signed", Switch).value,
            encrypted=self.query_one("#pack-encrypted", Switch).value,
            dry_run=self.query_one("#pack-dry-run", Switch).value,
            verify=self.query_one("#pack-verify", Switch).value,
            case_insensitive=self.query_one("#pack-case-insensitive", Switch).value,
        )

    def on_mount(self) -> None:
        """Set initial inode-bits disabled state and widget labels."""
        self.query_one("#pack-inode-bits", Select).disabled = False
        self._auto_output = ""

        # Border titles for numeric inputs and EKPFS
        titles = {
            "pack-block-size": "Block size",
            "pack-threshold-gain": "Threshold gain %",
            "pack-compression-level": "Compression 0-9",
            "pack-cpu-count": "CPU count (0=auto)",
            "pack-min-compress-size": "Min compress size",
            "pack-ekpfs": "EKPFS key (64 hex, with Encrypted)",
        }
        for wid, title in titles.items():
            self.query_one(f"#{wid}", Input).border_title = title

        # Border titles for the two Selects
        self.query_one("#pack-version", Select).border_title = "PFS version"
        self.query_one("#pack-inode-bits", Select).border_title = "Inode width"

    def _derived_output(self, source: str) -> str:
        """Derive the default output path from the source path.

        Args:
            source: The source path string.

        Returns:
            The suggested output path with appropriate extension.
        """
        compressed = self.query_one("#pack-compress", Switch).value
        ext = ".ffpfsc" if compressed else ".ffpfs"
        return str(Path(source).with_suffix(ext))

    def _maybe_autofill_output(self) -> None:
        """Fill the output field from the source if it hasn't been manually edited."""
        source = self.query_one("#pack-source", PathField).value
        out = self.query_one("#pack-output", PathField)
        if source.strip() and (not out.value or out.value == self._auto_output):
            derived = self._derived_output(source)
            out.value = derived
            self._auto_output = derived

    def on_input_changed(self, event: Input.Changed) -> None:
        """Auto-fill output when the source path changes.

        Args:
            event: The Input.Changed event.
        """
        parent = event.input.parent
        if parent is not None and parent.id == "pack-source":
            self._maybe_autofill_output()

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Update the auto-derived output extension when Compress is toggled.

        Args:
            event: The Switch.Changed event.
        """
        if event.switch.id == "pack-compress":
            self._maybe_autofill_output()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Disable the inode-bits Select when File mode is selected.

        Args:
            event: The RadioSet.Changed event carrying the new pressed index.
        """
        self.query_one("#pack-inode-bits", Select).disabled = event.index == 1

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Pack (with overwrite gate) or cancel.

        Args:
            event: The button-pressed event.
        """
        if event.button.id == "pack-cancel":
            event.stop()
            self.app.workers.cancel_group(self, "default")
            self.query_one("#pack-phase", Static).update("Cancelled.")
            return
        if event.button.id != "pack-run":
            return
        event.stop()
        opts = self.read_options()
        output = Path(opts.output)
        if output.exists():
            self.app.push_screen(
                ConfirmScreen(f"{output} exists. Overwrite?"),
                lambda ok: self._overwrite_then_start(ok, opts, output),
            )
        else:
            self._start(opts)

    def _overwrite_then_start(self, ok: bool, opts: PackOptions, output: Path) -> None:
        """Pre-clean the target and start, or abort, based on the confirm answer.

        Args:
            ok: True if the user confirmed overwrite, False to abort.
            opts: The PackOptions to run if ok.
            output: The output path to unlink before starting.
        """
        if not ok:
            self.query_one("#pack-phase", Static).update("Cancelled — kept existing file.")
            return
        with suppress(OSError):
            output.unlink()
        self._start(opts)

    def _start(self, opts: PackOptions) -> None:
        """Reset the UI and launch the streaming worker.

        Args:
            opts: The PackOptions to run.
        """
        self.query_one("#pack-bar", ProgressBar).update(progress=0)
        self.query_one("#pack-phase", Static).update("")
        self.query_one("#pack-result", ResultPanel).show((), ())
        self._pack(build_pack_argv(opts))

    @work(thread=True, exclusive=True)
    def _pack(self, argv: list[str]) -> None:
        """Stream run_pack events to the UI; close the generator on cancel.

        Args:
            argv: The pack argv from build_pack_argv.
        """
        worker = get_current_worker()
        generator = mkpfs_runner.run_pack(argv)
        try:
            for event in generator:
                if worker.is_cancelled:
                    break
                if isinstance(event, PackProgress):
                    self.post_message(PackProgressed(VIEW_ID, event))
                elif isinstance(event, PackStatus):
                    self.post_message(PackStatusLine(VIEW_ID, event.text))
                elif isinstance(event, PackFinished):
                    self.post_message(PackCompleted(VIEW_ID, event))
        finally:
            generator.close()

    def on_pack_progressed(self, message: PackProgressed) -> None:
        """Advance the bar and update the phase/speed line.

        Args:
            message: The PackProgressed message carrying the progress payload.
        """
        if message.view_id != VIEW_ID:
            return
        progress = message.progress
        if not isinstance(progress, PackProgress):
            return
        self.query_one("#pack-bar", ProgressBar).update(progress=progress.percent)
        speed = f" @ {progress.speed}" if progress.speed else ""
        eta = f" ETA {progress.eta}" if progress.eta else ""
        self.query_one("#pack-phase", Static).update(f"{progress.phase}{speed}{eta}")

    def on_pack_status_line(self, message: PackStatusLine) -> None:
        """Show the latest status line in the phase Static.

        Args:
            message: The PackStatusLine message carrying the status text.
        """
        if message.view_id == VIEW_ID:
            self.query_one("#pack-phase", Static).update(message.text)

    def on_pack_completed(self, message: PackCompleted) -> None:
        """Render the final result (human summary + ok/exit code).

        Args:
            message: The PackCompleted message carrying the PackFinished payload.
        """
        if message.view_id != VIEW_ID:
            return
        result = message.result
        if not isinstance(result, PackFinished):
            return
        lines = tuple(line for line in result.stdout.splitlines() if line.strip())
        if result.ok:
            self.query_one("#pack-result", ResultPanel).show((), (), lines or ("Done.",))
        else:
            self.query_one("#pack-result", ResultPanel).show((f"pack failed (exit {result.exit_code})", *lines), ())
