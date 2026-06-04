"""Acceptance tests for the M1 app shell."""

from __future__ import annotations

from textual.widgets import ContentSwitcher, ListView

from mkpfs_tui.app import MkpfsTuiApp


async def test_app_starts_on_tokyo_night() -> None:
    app = MkpfsTuiApp()
    async with app.run_test():
        assert app.theme == "tokyo-night"


def test_command_palette_is_enabled() -> None:
    # Ctrl+P palette (which carries theme switching) is on by default.
    assert MkpfsTuiApp.ENABLE_COMMAND_PALETTE is True


async def test_theme_is_switchable() -> None:
    app = MkpfsTuiApp()
    async with app.run_test():
        app.theme = "nord"  # another built-in theme
        assert app.theme == "nord"


async def test_sidebar_switches_every_view() -> None:
    app = MkpfsTuiApp()
    async with app.run_test() as pilot:
        switcher = app.query_one("#work", ContentSwitcher)
        assert switcher.current == "pack"
        nav = app.query_one(ListView)
        # Setting nav.index fires ListView.Highlighted -> Sidebar.ActionSelected -> ContentSwitcher.current.
        # One pause() drains that two-hop chain because wait_for_idle polls until the app is idle.
        for index, view_id in enumerate(["pack", "inspect", "verify", "tree", "unpack"]):
            nav.index = index
            await pilot.pause()
            assert switcher.current == view_id
