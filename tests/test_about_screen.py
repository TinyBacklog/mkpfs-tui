"""Tests for the About / welcome screen."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import ContentSwitcher

from mkpfs_tui.app import MkpfsTuiApp
from mkpfs_tui.screens.about import AboutView


class _Host(App[None]):
    """Minimal host that mounts only the AboutView."""

    def compose(self) -> ComposeResult:
        yield AboutView(id="about")


async def test_about_renders_claudio_varandas() -> None:
    app = _Host()
    async with app.run_test(size=(120, 40)):
        statics = app.query_one(AboutView).query("Static")
        combined = " ".join(str(s.content) for s in statics)
        assert "ClaudioVarandas" in combined


async def test_about_renders_playstation_pfs() -> None:
    app = _Host()
    async with app.run_test(size=(120, 40)):
        statics = app.query_one(AboutView).query("Static")
        combined = " ".join(str(s.content) for s in statics)
        assert "PlayStation PFS" in combined


async def test_about_in_full_app_switches_content() -> None:
    """Selecting About in the sidebar switches ContentSwitcher to 'about'."""
    from textual.widgets import ListView

    app = MkpfsTuiApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        switcher = app.query_one("#work", ContentSwitcher)
        # Navigate to About (last sidebar entry)
        from mkpfs_tui.widgets.sidebar import ACTIONS

        about_index = next(i for i, (vid, _) in enumerate(ACTIONS) if vid == "about")
        app.query_one(ListView).index = about_index
        await pilot.pause()
        assert switcher.current == "about"
