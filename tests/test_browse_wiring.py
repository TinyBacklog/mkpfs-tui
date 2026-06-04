"""Browse button → picker → PathField write-back wiring."""

from __future__ import annotations

from mkpfs_tui.app import MkpfsTuiApp
from mkpfs_tui.screens.picker import DirectoryPickerScreen
from mkpfs_tui.widgets.path_field import PathField


async def test_browse_opens_picker_and_writes_back() -> None:
    app = MkpfsTuiApp()
    async with app.run_test(size=(140, 50)) as pilot:
        app.query_one("#work").current = "inspect"
        await pilot.pause()
        # the Inspect image PathField's Browse button
        field = app.query_one("#inspect-image", PathField)
        await pilot.click("#inspect-image #browse")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, DirectoryPickerScreen)
        screen.set_selection("/picked/image.pfs")
        await pilot.click("#picker-choose")
        await pilot.pause()
        assert field.value == "/picked/image.pfs"
