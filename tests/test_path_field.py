"""Tests for the PathField widget."""

from __future__ import annotations

from textual.app import App, ComposeResult

from mkpfs_tui.widgets.path_field import PathField


class _Host(App[None]):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[tuple[str, str]] = []

    def compose(self) -> ComposeResult:
        yield PathField("Image", "file", id="image")

    def on_path_field_browse_requested(self, event: PathField.BrowseRequested) -> None:
        self.requests.append((event.field_id, event.want))


async def test_value_roundtrip() -> None:
    app = _Host()
    async with app.run_test():
        field = app.query_one(PathField)
        field.value = "/tmp/x.pfs"
        assert field.value == "/tmp/x.pfs"


async def test_browse_button_posts_request() -> None:
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.click("#browse")
        await pilot.pause()
        assert app.requests == [("image", "file")]


async def test_browse_button_posts_dir_request() -> None:
    class _DirHost(App[None]):
        def __init__(self) -> None:
            super().__init__()
            self.requests: list[tuple[str, str]] = []

        def compose(self) -> ComposeResult:
            yield PathField("Dest", "dir", id="dest")

        def on_path_field_browse_requested(self, event: PathField.BrowseRequested) -> None:
            self.requests.append((event.field_id, event.want))

    app = _DirHost()
    async with app.run_test() as pilot:
        await pilot.click("#browse")
        await pilot.pause()
        assert app.requests == [("dest", "dir")]
