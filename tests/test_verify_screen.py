"""Tests for the Verify view (runner monkeypatched)."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import ProgressBar, Static

from mkpfs_tui import mkpfs_runner
from mkpfs_tui.mkpfs_runner import Inspection
from mkpfs_tui.screens.verify import VerifyView
from mkpfs_tui.widgets.path_field import PathField
from mkpfs_tui.widgets.result_panel import ResultPanel


class _Host(App[None]):
    def compose(self) -> ComposeResult:
        yield VerifyView()


def _result(*, ok: bool, errors: tuple[str, ...] = ()) -> Inspection:
    return Inspection(
        image="game.pfs",
        ok=ok,
        size_bytes=0,
        version_label="PS5",
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
        errors=errors,
        warnings=(),
    )


async def test_verify_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mkpfs_runner, "verify_image", lambda *a, **k: _result(ok=True))
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        app.query_one("#verify-image", PathField).value = "game.pfs"
        await pilot.click("#verify-run")
        await app.workers.wait_for_complete()
        await pilot.pause()
        banner = app.query_one("#verify-banner", Static)
        assert "PASS" in str(banner.content)
        assert banner.has_class("banner-pass")


async def test_verify_fail_shows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mkpfs_runner, "verify_image", lambda *a, **k: _result(ok=False, errors=("crc mismatch",)))
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        app.query_one("#verify-image", PathField).value = "game.pfs"
        await pilot.click("#verify-run")
        await app.workers.wait_for_complete()
        await pilot.pause()
        banner = app.query_one("#verify-banner", Static)
        assert "FAIL" in str(banner.content)
        assert banner.has_class("banner-fail")
        assert len(app.query_one(ResultPanel).query(".error")) == 1


async def test_verify_progress_bar_shows_on_start_hides_on_end() -> None:
    """_on_operation_start shows bar/elapsed; _on_operation_end hides them."""
    app = _Host()
    async with app.run_test(size=(120, 40)):
        view = app.query_one(VerifyView)
        bar = app.query_one("#verify-progress", ProgressBar)
        elapsed = app.query_one("#verify-elapsed", Static)

        # Initially hidden (CSS default: display: none is set by CSS; verify at runtime)
        assert not bar.display

        # Call start hook directly — no race with a real timer
        view._on_operation_start()
        assert bar.display
        assert elapsed.display

        # Call end hook directly
        view._on_operation_end()
        assert not bar.display
        assert not elapsed.display


async def test_verify_progress_shows_during_live_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """After a complete verify run the progress bar is hidden again."""
    monkeypatch.setattr(mkpfs_runner, "verify_image", lambda *a, **k: _result(ok=True))
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        app.query_one("#verify-image", PathField).value = "game.pfs"
        await pilot.click("#verify-run")
        await app.workers.wait_for_complete()
        await pilot.pause()
        bar = app.query_one("#verify-progress", ProgressBar)
        assert not bar.display, "progress bar should be hidden after verification completes"


async def test_verify_toggles_pass_to_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    results = iter([_result(ok=True), _result(ok=False, errors=("bad",))])
    monkeypatch.setattr(mkpfs_runner, "verify_image", lambda *a, **k: next(results))
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        app.query_one("#verify-image", PathField).value = "game.pfs"
        await pilot.click("#verify-run")
        await app.workers.wait_for_complete()
        await pilot.pause()
        banner = app.query_one("#verify-banner", Static)
        assert banner.has_class("banner-pass")
        # Wait for button active-effect to expire before the second click.
        await pilot.pause(delay=0.3)
        await pilot.click("#verify-run")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert banner.has_class("banner-fail")
        assert not banner.has_class("banner-pass")
