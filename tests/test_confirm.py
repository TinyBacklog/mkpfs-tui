"""Tests for the confirm modal."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Button

from mkpfs_tui.screens.confirm import ConfirmScreen


class _Host(App[None]):
    def __init__(self) -> None:
        super().__init__()
        self.answer: bool | None = None

    def compose(self) -> ComposeResult:
        yield Button("open", id="open")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "open":
            self.push_screen(ConfirmScreen("Overwrite?"), self._got)

    def _got(self, value: bool) -> None:
        self.answer = value


async def test_confirm_yes() -> None:
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.click("#open")
        await pilot.pause()
        await pilot.click("#confirm-yes")
        await pilot.pause()
        assert app.answer is True


async def test_confirm_no() -> None:
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.click("#open")
        await pilot.pause()
        await pilot.click("#confirm-no")
        await pilot.pause()
        assert app.answer is False


async def test_confirm_escape() -> None:
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.click("#open")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert app.answer is False
