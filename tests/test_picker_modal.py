"""Tests for the directory/file picker modal."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Button

from mkpfs_tui.screens.picker import DirectoryPickerScreen


class _Host(App[None]):
    def __init__(self, want: str = "file") -> None:
        super().__init__()
        self._want = want
        self.picked: str | None = "UNSET"

    def compose(self) -> ComposeResult:
        yield Button("open", id="open")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "open":
            self.push_screen(DirectoryPickerScreen(want=self._want), self._got)

    def _got(self, value: str | None) -> None:
        self.picked = value


async def test_choose_returns_selected_path(tmp_path: Path) -> None:
    target = tmp_path / "image.pfs"
    target.write_text("x")
    app = _Host(want="file")
    async with app.run_test() as pilot:
        await pilot.click("#open")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, DirectoryPickerScreen)
        screen.set_selection(str(target))  # simulate a tree file-selection
        await pilot.click("#picker-choose")
        await pilot.pause()
        assert app.picked == str(target)


async def test_cancel_returns_none(tmp_path: Path) -> None:
    app = _Host(want="dir")
    async with app.run_test() as pilot:
        await pilot.click("#open")
        await pilot.pause()
        await pilot.click("#picker-cancel")
        await pilot.pause()
        assert app.picked is None
