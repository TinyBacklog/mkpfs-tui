"""Tests for the human_bytes formatter."""

from __future__ import annotations

from mkpfs_tui.format import human_bytes


def test_human_bytes_units() -> None:
    assert human_bytes(0) == "0 B"
    assert human_bytes(512) == "512 B"
    assert human_bytes(2048) == "2.00 KiB"
    assert human_bytes(5 * 1024 * 1024) == "5.00 MiB"
    assert human_bytes(3 * 1024**4) == "3.00 TiB"
