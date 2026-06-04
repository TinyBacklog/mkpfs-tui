"""Tests for the ResultPanel widget."""

from __future__ import annotations

from textual.app import App, ComposeResult

from mkpfs_tui.widgets.result_panel import ResultPanel


class _Host(App[None]):
    def compose(self) -> ComposeResult:
        yield ResultPanel()


async def test_shows_errors_and_warnings() -> None:
    app = _Host()
    async with app.run_test() as pilot:
        panel = app.query_one(ResultPanel)
        panel.show(errors=("boom",), warnings=("careful", "watch out"))
        await pilot.pause()
        assert len(panel.query(".error")) == 1
        assert len(panel.query(".warning")) == 2


async def test_show_replaces_previous_contents() -> None:
    app = _Host()
    async with app.run_test() as pilot:
        panel = app.query_one(ResultPanel)
        panel.show(errors=("first",), warnings=())
        await pilot.pause()
        panel.show(errors=(), warnings=("only warning",))
        await pilot.pause()
        assert len(panel.query(".error")) == 0
        assert len(panel.query(".warning")) == 1


async def test_shows_notes() -> None:
    app = _Host()
    async with app.run_test() as pilot:
        panel = app.query_one(ResultPanel)
        panel.show(errors=(), warnings=("w1",), notes=("success line 1", "success line 2"))
        await pilot.pause()
        assert len(panel.query(".success")) == 2
        assert len(panel.query(".warning")) == 1
        assert len(panel.query(".error")) == 0
