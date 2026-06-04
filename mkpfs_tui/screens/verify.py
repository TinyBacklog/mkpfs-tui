"""Verify view: run mkpfs verification and show a PASS/FAIL banner."""

from __future__ import annotations

import time
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.timer import Timer
from textual.widgets import Button, Input, Label, ProgressBar, Static, Switch

from mkpfs_tui import mkpfs_runner
from mkpfs_tui.mkpfs_runner import Inspection
from mkpfs_tui.screens.read_view import ReadView
from mkpfs_tui.widgets.path_field import PathField
from mkpfs_tui.widgets.result_panel import ResultPanel


class VerifyView(ReadView):
    """Verify a PFS image against optional source/hash expectations."""

    VIEW_ID = "verify"

    def compose(self) -> ComposeResult:
        """Render the verify form, run button, progress, banner, and result panel."""
        yield PathField("Image", "file", id="verify-image")
        yield PathField("Source (optional)", "dir", id="verify-source")
        yield Input(placeholder="Expect CRC32 — e.g. 0x1A2B3C4D, optional", id="verify-crc")
        yield Input(placeholder="Expect manifest SHA256, optional", id="verify-manifest")
        yield Input(placeholder="EKPFS key — 64 hex, optional", id="verify-ekpfs")
        with Horizontal(classes="option-row"):
            yield Label("newCrypt")
            yield Switch(id="verify-new-crypt")
        yield Button("Verify", id="verify-run", variant="primary")
        yield ProgressBar(total=None, id="verify-progress")
        yield Static("", id="verify-elapsed")
        yield Static("", id="verify-banner")
        yield ResultPanel(id="verify-result")

    def on_mount(self) -> None:
        """Hide the progress widgets and initialise timer state."""
        self._verify_start: float = 0.0
        self._verify_timer: Timer | None = None
        self.query_one("#verify-progress", ProgressBar).display = False
        self.query_one("#verify-elapsed", Static).display = False

    def _on_operation_start(self) -> None:
        """Show the indeterminate progress bar and start the elapsed timer."""
        self._verify_start = time.monotonic()
        bar = self.query_one("#verify-progress", ProgressBar)
        elapsed = self.query_one("#verify-elapsed", Static)
        bar.display = True
        elapsed.display = True
        elapsed.update("Verifying… 0:00")
        self._verify_timer = self.set_interval(1.0, self._tick_elapsed)

    def _tick_elapsed(self) -> None:
        """Update the elapsed-time Static every second."""
        total_seconds = int(time.monotonic() - self._verify_start)
        minutes, seconds = divmod(total_seconds, 60)
        self.query_one("#verify-elapsed", Static).update(f"Verifying… {minutes}:{seconds:02d}")

    def _on_operation_end(self) -> None:
        """Stop the elapsed timer and hide the progress widgets."""
        if self._verify_timer is not None:
            self._verify_timer.stop()
            self._verify_timer = None
        self.query_one("#verify-progress", ProgressBar).display = False
        self.query_one("#verify-elapsed", Static).display = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Start verification when the Verify button is pressed."""
        if event.button.id != "verify-run":
            return
        event.stop()
        image = self.query_one("#verify-image", PathField).value
        source = self.query_one("#verify-source", PathField).value
        crc = self.query_one("#verify-crc", Input).value
        manifest = self.query_one("#verify-manifest", Input).value
        ekpfs = self.query_one("#verify-ekpfs", Input).value
        new_crypt = self.query_one("#verify-new-crypt", Switch).value
        self.run_operation(
            lambda: mkpfs_runner.verify_image(
                Path(image),
                source=source,
                expected_crc32=crc,
                expected_manifest_sha256=manifest,
                ekpfs_hex=ekpfs,
                new_crypt=new_crypt,
            )
        )

    def render_result(self, result: object) -> None:
        """Render PASS/FAIL and any errors/warnings."""
        if not isinstance(result, Inspection):
            return
        banner = self.query_one("#verify-banner", Static)
        banner.remove_class("banner-pass", "banner-fail")
        if result.ok:
            banner.update("PASS")
            banner.add_class("banner-pass")
        else:
            banner.update("FAIL")
            banner.add_class("banner-fail")
        self.query_one("#verify-result", ResultPanel).show(result.errors, result.warnings)
