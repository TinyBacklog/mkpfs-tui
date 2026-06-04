"""Tests for the Unpack view."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.widgets import ProgressBar, Switch

from mkpfs_tui import mkpfs_runner
from mkpfs_tui.mkpfs_runner import Extraction
from mkpfs_tui.screens.unpack import UnpackView
from mkpfs_tui.widgets.path_field import PathField
from mkpfs_tui.widgets.result_panel import ResultPanel


class _Host(App[None]):
    def compose(self) -> ComposeResult:
        """Yield the view under test."""
        yield UnpackView()


async def test_unpack_streams_progress_and_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_unpack(
        image: Path,
        output_path: Path,
        *,
        ekpfs_hex: str = "",
        new_crypt: bool = False,
        on_step: Callable[[str, int, int, int], None] | None = None,
    ) -> Extraction:
        if on_step is not None:
            on_step("extract", 1, 2, 0)
            on_step("extract", 2, 2, 0)
        return Extraction(
            output_path=str(output_path),
            ok=True,
            files_written=3,
            directories_created=1,
            bytes_written=4096,
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(mkpfs_runner, "unpack_image", fake_unpack)
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        view = app.query_one(UnpackView)
        view.query_one("#unpack-image", PathField).value = "game.pfs"
        view.query_one("#unpack-output", PathField).value = "/out"
        await pilot.click("#unpack-run")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert view.query_one("#unpack-bar", ProgressBar).progress == 100
        # success summary renders (3 files / 1 dir / 4096 bytes) as success lines
        assert len(view.query_one("#unpack-result", ResultPanel).query(".success")) >= 1


async def test_unpack_error_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_unpack(
        image: Path,
        output_path: Path,
        *,
        ekpfs_hex: str = "",
        new_crypt: bool = False,
        on_step: Callable[[str, int, int, int], None] | None = None,
    ) -> Extraction:
        return Extraction(
            output_path=str(output_path),
            ok=False,
            files_written=0,
            directories_created=0,
            bytes_written=0,
            errors=("output exists",),
            warnings=(),
        )

    monkeypatch.setattr(mkpfs_runner, "unpack_image", fake_unpack)
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        view = app.query_one(UnpackView)
        view.query_one("#unpack-image", PathField).value = "game.pfs"
        view.query_one("#unpack-output", PathField).value = "/out"
        await pilot.click("#unpack-run")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert len(view.query_one("#unpack-result", ResultPanel).query(".error")) == 1


async def test_overwrite_no_keeps_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from mkpfs_tui import mkpfs_runner

    started = False

    def fake_unpack(  # pragma: no cover
        image: Path,
        output_path: Path,
        *,
        ekpfs_hex: str = "",
        new_crypt: bool = False,
        on_step: Callable[[str, int, int, int], None] | None = None,
    ) -> Extraction:
        nonlocal started
        started = True
        return Extraction(
            output_path=str(output_path),
            ok=True,
            files_written=0,
            directories_created=0,
            bytes_written=0,
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(mkpfs_runner, "unpack_image", fake_unpack)
    out = tmp_path / "out"
    out.mkdir()
    (out / "keep.txt").write_text("precious")
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        view = app.query_one(UnpackView)
        view.query_one("#unpack-image", PathField).value = "game.pfs"
        view.query_one("#unpack-output", PathField).value = str(out)
        view.query_one("#unpack-overwrite", Switch).value = True
        await pilot.pause()
        await pilot.click("#unpack-run")
        await pilot.pause()
        await pilot.click("#confirm-no")  # decline
        await pilot.pause()
        assert (out / "keep.txt").read_text() == "precious"  # NOT deleted
        assert started is False  # worker never launched


async def test_indeterminate_progress_then_determinate(monkeypatch: pytest.MonkeyPatch) -> None:
    """A total=0 step makes the bar indeterminate; a positive-total step restores it."""

    def fake_unpack(
        image: Path,
        output_path: Path,
        *,
        ekpfs_hex: str = "",
        new_crypt: bool = False,
        on_step: Callable[[str, int, int, int], None] | None = None,
    ) -> Extraction:
        if on_step is not None:
            on_step("scan", 0, 0, 0)  # total=0 → indeterminate
            on_step("extract", 1, 2, 0)  # total>0 → determinate
        return Extraction(
            output_path=str(output_path),
            ok=True,
            files_written=1,
            directories_created=0,
            bytes_written=0,
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(mkpfs_runner, "unpack_image", fake_unpack)
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        view = app.query_one(UnpackView)
        view.query_one("#unpack-image", PathField).value = "game.pfs"
        view.query_one("#unpack-output", PathField).value = "/out"
        await pilot.click("#unpack-run")
        await app.workers.wait_for_complete()
        await pilot.pause()
        # After all steps, total should be 100 (determinate was restored)
        bar = view.query_one("#unpack-bar", ProgressBar)
        assert bar.total == 100


async def test_cancel_kept_files_message(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Declining overwrite shows the harmonized cancel message."""
    from mkpfs_tui import mkpfs_runner

    def fake_unpack(  # pragma: no cover
        image: Path,
        output_path: Path,
        *,
        ekpfs_hex: str = "",
        new_crypt: bool = False,
        on_step: Callable[[str, int, int, int], None] | None = None,
    ) -> Extraction:  # pragma: no cover
        return Extraction(
            output_path=str(output_path),
            ok=True,
            files_written=0,
            directories_created=0,
            bytes_written=0,
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(mkpfs_runner, "unpack_image", fake_unpack)
    out = tmp_path / "out"
    out.mkdir()
    (out / "keep.txt").write_text("precious")
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        view = app.query_one(UnpackView)
        view.query_one("#unpack-image", PathField).value = "game.pfs"
        view.query_one("#unpack-output", PathField).value = str(out)
        view.query_one("#unpack-overwrite", Switch).value = True
        await pilot.pause()
        await pilot.click("#unpack-run")
        await pilot.pause()
        await pilot.click("#confirm-no")
        await pilot.pause()
        from textual.widgets import Static

        phase_text = str(view.query_one("#unpack-phase", Static).render())
        assert "Cancelled" in phase_text
        assert "kept existing files" in phase_text


async def test_overwrite_yes_precleans_and_runs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from mkpfs_tui import mkpfs_runner

    def fake_unpack(
        image: Path,
        output_path: Path,
        *,
        ekpfs_hex: str = "",
        new_crypt: bool = False,
        on_step: Callable[[str, int, int, int], None] | None = None,
    ) -> Extraction:
        return Extraction(
            output_path=str(output_path),
            ok=True,
            files_written=2,
            directories_created=1,
            bytes_written=10,
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(mkpfs_runner, "unpack_image", fake_unpack)
    out = tmp_path / "out"
    out.mkdir()
    (out / "stale.txt").write_text("old")
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        view = app.query_one(UnpackView)
        view.query_one("#unpack-image", PathField).value = "game.pfs"
        view.query_one("#unpack-output", PathField).value = str(out)
        view.query_one("#unpack-overwrite", Switch).value = True
        await pilot.pause()
        await pilot.click("#unpack-run")
        await pilot.pause()
        await pilot.click("#confirm-yes")  # confirm overwrite
        await app.workers.wait_for_complete()
        await pilot.pause()
        # rmtree ran before the (fake, non-recreating) worker, so the dir is gone
        assert not out.exists()
