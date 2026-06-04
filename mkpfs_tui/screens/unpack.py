"""Unpack view: extract a PFS image to a directory in-process."""

from __future__ import annotations

import shutil
from contextlib import suppress
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Input, Label, ProgressBar, Static, Switch

from mkpfs_tui import mkpfs_runner
from mkpfs_tui.format import human_bytes
from mkpfs_tui.messages import UnpackCompleted, UnpackProgressed
from mkpfs_tui.mkpfs_runner import Extraction
from mkpfs_tui.screens.confirm import ConfirmScreen
from mkpfs_tui.widgets.path_field import PathField
from mkpfs_tui.widgets.result_panel import ResultPanel

VIEW_ID = "unpack"


class UnpackView(Container):
    """Form + live progress for extracting a PFS image to a directory."""

    def compose(self) -> ComposeResult:
        """Render the unpack form, run button, progress, and result panel."""
        yield PathField("Image", "file", id="unpack-image")
        yield PathField("Output directory", "dir", id="unpack-output")
        yield Input(placeholder="EKPFS key — 64 hex, optional", id="unpack-ekpfs")
        with Horizontal(classes="option-row"):
            yield Label("newCrypt")
            yield Switch(id="unpack-new-crypt")
        with Horizontal(classes="option-row"):
            yield Label("Overwrite (clear non-empty output)")
            yield Switch(id="unpack-overwrite")
        yield Button("Unpack", id="unpack-run", variant="primary")
        yield ProgressBar(total=100, id="unpack-bar")
        yield Static("", id="unpack-phase")
        yield ResultPanel(id="unpack-result")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Start an unpack, gating a non-empty output dir on the overwrite switch."""
        if event.button.id != "unpack-run":
            return
        event.stop()
        image = self.query_one("#unpack-image", PathField).value
        output = Path(self.query_one("#unpack-output", PathField).value)
        ekpfs = self.query_one("#unpack-ekpfs", Input).value
        new_crypt = self.query_one("#unpack-new-crypt", Switch).value
        overwrite = self.query_one("#unpack-overwrite", Switch).value
        if overwrite and output.is_dir() and any(output.iterdir()):
            self.app.push_screen(
                ConfirmScreen(f"{output} is not empty. Delete its contents and unpack?"),
                lambda ok: self._clear_then_start(ok, image, output, ekpfs, new_crypt),
            )
        else:
            self._start(image, output, ekpfs, new_crypt)

    def _clear_then_start(self, ok: bool, image: str, output: Path, ekpfs: str, new_crypt: bool) -> None:
        """Pre-clean the output dir on confirm, then start (or abort).

        Args:
            ok: Whether the user confirmed the overwrite.
            image: Path to the PFS image.
            output: Destination directory.
            ekpfs: EKPFS hex key.
            new_crypt: Whether to use the alternate newCrypt derivation.
        """
        if not ok:
            self.query_one("#unpack-phase", Static).update("Cancelled — kept existing files.")
            return
        with suppress(OSError):
            shutil.rmtree(output)
        self._start(image, output, ekpfs, new_crypt)

    def _start(self, image: str, output: Path, ekpfs: str, new_crypt: bool) -> None:
        """Reset the UI and launch the in-process worker.

        Args:
            image: Path to the PFS image.
            output: Destination directory.
            ekpfs: EKPFS hex key.
            new_crypt: Whether to use the alternate newCrypt derivation.
        """
        self.query_one("#unpack-bar", ProgressBar).update(progress=0)
        self.query_one("#unpack-phase", Static).update("")
        self.query_one("#unpack-result", ResultPanel).show((), ())
        self._unpack(image, output, ekpfs, new_crypt)

    @work(thread=True, exclusive=True)
    def _unpack(self, image: str, output: Path, ekpfs: str, new_crypt: bool) -> None:
        """Extract in a worker thread, posting progress + completion.

        Args:
            image: Path to the PFS image.
            output: Destination directory.
            ekpfs: EKPFS hex key.
            new_crypt: Whether to use the alternate newCrypt derivation.
        """

        def on_step(phase: str, done: int, total: int, _bytes: int) -> None:
            self.post_message(UnpackProgressed(VIEW_ID, phase, done, total))

        result = mkpfs_runner.unpack_image(Path(image), output, ekpfs_hex=ekpfs, new_crypt=new_crypt, on_step=on_step)
        self.post_message(UnpackCompleted(VIEW_ID, result))

    def on_unpack_progressed(self, message: UnpackProgressed) -> None:
        """Advance the bar (percent from done/total) and update the phase line.

        When ``total`` is 0 the bar is set to indeterminate (pulse animation).
        When ``total`` is positive the bar is restored to determinate mode.

        Args:
            message: The progress update.
        """
        if message.view_id != VIEW_ID:
            return
        bar = self.query_one("#unpack-bar", ProgressBar)
        if message.total > 0:
            percent = int(message.done * 100 / message.total)
            bar.update(total=100, progress=percent)
        else:
            bar.update(total=None)
        self.query_one("#unpack-phase", Static).update(message.phase)

    def on_unpack_completed(self, message: UnpackCompleted) -> None:
        """Render the extraction summary or errors.

        Args:
            message: The completion message carrying an Extraction.
        """
        if message.view_id != VIEW_ID:
            return
        result = message.result
        if not isinstance(result, Extraction):
            return
        if result.ok:
            self.query_one("#unpack-bar", ProgressBar).update(progress=100)
            summary = (
                f"{result.files_written} files, {result.directories_created} dirs, "
                f"{human_bytes(result.bytes_written)} written to {result.output_path}"
            )
            self.query_one("#unpack-result", ResultPanel).show((), (), (summary, *result.warnings))
        else:
            self.query_one("#unpack-result", ResultPanel).show(result.errors, result.warnings)
