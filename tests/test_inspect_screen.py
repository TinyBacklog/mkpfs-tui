"""Tests for the Inspect view (runner is monkeypatched — no real image)."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from mkpfs_tui import mkpfs_runner
from mkpfs_tui.mkpfs_runner import HeaderInfo, Inspection
from mkpfs_tui.screens.inspect import InspectView
from mkpfs_tui.widgets.path_field import PathField
from mkpfs_tui.widgets.result_panel import ResultPanel


class _Host(App[None]):
    def compose(self) -> ComposeResult:
        yield InspectView()


def _canned(
    *,
    ok: bool = True,
    errors: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
    hashes_computed: bool = False,
) -> Inspection:
    return Inspection(
        image="game.pfs",
        ok=ok,
        size_bytes=2048,
        version_label="PS5",
        header=HeaderInfo(block_size=65536, nblock=10, dinode_count=3, ndblock=8, dinode_block_count=1, readonly=1),
        inode_count=3,
        dir_count=1,
        file_count=2,
        compressed_files=1,
        checked_files=2,
        data_crc32=0xDEADBEEF,
        manifest_sha256="abc",
        logical_file_bytes=4096,
        stored_file_bytes=2048,
        errors=errors,
        warnings=warnings,
        hashes_computed=hashes_computed,
    )


async def test_inspect_populates_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mkpfs_runner, "inspect_image", lambda *a, **k: _canned())
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        app.query_one(PathField).value = "game.pfs"
        await pilot.click("#inspect-run")
        await app.workers.wait_for_complete()
        await pilot.pause()
        table = app.query_one("#inspect-table", DataTable)
        assert table.row_count == 13
        assert table.get_row_at(0)[1] == "game.pfs"
        assert table.get_row_at(1)[1] == "PS5"


async def test_inspect_shows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mkpfs_runner,
        "inspect_image",
        lambda *a, **k: _canned(ok=False, errors=("bad header",)),
    )
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        app.query_one(PathField).value = "game.pfs"
        await pilot.click("#inspect-run")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert len(app.query_one(ResultPanel).query(".error")) == 1


async def test_inspect_dashes_for_missing_header_and_version(monkeypatch: pytest.MonkeyPatch) -> None:
    blank = Inspection(
        image="x",
        ok=True,
        size_bytes=0,
        version_label="",
        header=None,
        inode_count=0,
        dir_count=0,
        file_count=0,
        compressed_files=0,
        checked_files=0,
        data_crc32=0,
        manifest_sha256="",
        logical_file_bytes=0,
        stored_file_bytes=0,
        errors=(),
        warnings=(),
    )
    monkeypatch.setattr(mkpfs_runner, "inspect_image", lambda *a, **k: blank)
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        app.query_one(PathField).value = "x"
        await pilot.click("#inspect-run")
        await app.workers.wait_for_complete()
        await pilot.pause()
        table = app.query_one("#inspect-table", DataTable)
        assert table.get_row_at(1)[1] == "—"  # Version fallback
        assert table.get_row_at(3)[1] == "—"  # Block size fallback


async def test_inspect_shows_checksums_as_not_computed(monkeypatch: pytest.MonkeyPatch) -> None:
    # Inspect skips hashing, so the CRC32/manifest rows must say "run Verify",
    # not 0xDEADBEEF / abc, even though the value type still carries those fields.
    monkeypatch.setattr(mkpfs_runner, "inspect_image", lambda *a, **k: _canned(hashes_computed=False))
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        app.query_one(PathField).value = "game.pfs"
        await pilot.click("#inspect-run")
        await app.workers.wait_for_complete()
        await pilot.pause()
        table = app.query_one("#inspect-table", DataTable)
        assert table.get_row_at(9)[1] == "— (run Verify)"  # Data CRC32
        assert table.get_row_at(10)[1] == "— (run Verify)"  # Manifest SHA256


async def test_inspect_shows_real_checksums_when_computed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mkpfs_runner, "inspect_image", lambda *a, **k: _canned(hashes_computed=True))
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        app.query_one(PathField).value = "game.pfs"
        await pilot.click("#inspect-run")
        await app.workers.wait_for_complete()
        await pilot.pause()
        table = app.query_one("#inspect-table", DataTable)
        assert table.get_row_at(9)[1] == "0xDEADBEEF"
        assert table.get_row_at(10)[1] == "abc"


async def test_inspect_rerun_replaces_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mkpfs_runner, "inspect_image", lambda *a, **k: _canned())
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        app.query_one(PathField).value = "game.pfs"
        await pilot.click("#inspect-run")
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.click("#inspect-run")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert app.query_one("#inspect-table", DataTable).row_count == 13
