"""Tests for the mkpfs progress-bar parser."""

from __future__ import annotations

import io

import pytest

from mkpfs_tui.progress_parser import Progress, parse_progress_line

_BAR = "#" * 16 + "-" * 16


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (f"[{_BAR}] 50% compress @ 142.00 MB/s ETA 31s", Progress(50, "compress", "142.00 MB/s", "31s")),
        (f"[{_BAR}] 50% scan 142.0 items/s ETA 31s", Progress(50, "scan", "142.0 items/s", "31s")),
        (f"[{_BAR}] 50% compress @ 1.50 GB/s", Progress(50, "compress", "1.50 GB/s", None)),
        (f"[{_BAR}] 50% write ETA 2.5m", Progress(50, "write", None, "2.5m")),
        ("[----------------] 0% scan", Progress(0, "scan", None, None)),
        ("[################] 100% write", Progress(100, "write", None, None)),
    ],
)
def test_parse_progress_line_matches(line: str, expected: Progress) -> None:
    assert parse_progress_line(line) == expected


@pytest.mark.parametrize(
    "line",
    [
        "Building image from /tmp/src",
        "Operation cancelled.",
        "",
        "[##] not-a-bar",
    ],
)
def test_parse_progress_line_rejects_non_progress(line: str) -> None:
    assert parse_progress_line(line) is None


def test_iter_cr_lf_splits_on_both() -> None:
    from mkpfs_tui.progress_parser import iter_cr_lf

    # Progress overwrites with \r mid-phase; a phase ends with \n.
    stream = io.StringIO("[--] 0% scan\r[##] 50% scan\rdone scan\nnext line\n")
    assert list(iter_cr_lf(stream)) == ["[--] 0% scan", "[##] 50% scan", "done scan", "next line"]


def test_iter_cr_lf_yields_trailing_unterminated_segment() -> None:
    from mkpfs_tui.progress_parser import iter_cr_lf

    assert list(iter_cr_lf(io.StringIO("partial"))) == ["partial"]


def test_iter_cr_lf_skips_empty_segments() -> None:
    from mkpfs_tui.progress_parser import iter_cr_lf

    assert list(iter_cr_lf(io.StringIO("a\r\nb\n"))) == ["a", "b"]
