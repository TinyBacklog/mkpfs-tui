"""Tests for exFAT image sizing and cluster selection (pure)."""

from __future__ import annotations

from pathlib import Path

from mkpfs_tui.exfat.sizing import CLUSTER_CHOICES, SizePlan, plan_size


def _write(path: Path, size: int) -> None:
    path.write_bytes(b"\0" * size)


def test_single_one_byte_file_known_size(tmp_path: Path) -> None:
    # Hand-computed: cluster 32K (avg<1MB), data=32768, clusters=1,
    # meta=4+1+256+32MB, base=33587461, spare=64MB(floor), total=100696325 -> 97 MB.
    _write(tmp_path / "a.bin", 1)
    plan = plan_size(tmp_path)
    assert plan == SizePlan(cluster_bytes=32768, size_mb=97, file_count=1, dir_count=0, raw_bytes=1)


def test_small_files_pick_32k(tmp_path: Path) -> None:
    for i in range(10):
        _write(tmp_path / f"f{i}.bin", 100 * 1024)  # avg 100KB < 1MB
    assert plan_size(tmp_path).cluster_bytes == 32 * 1024


def test_large_files_pick_64k(tmp_path: Path) -> None:
    for i in range(3):
        _write(tmp_path / f"f{i}.bin", 2 * 1024 * 1024)  # avg 2MB >= 1MB
    assert plan_size(tmp_path).cluster_bytes == 64 * 1024


def test_override_is_honored(tmp_path: Path) -> None:
    _write(tmp_path / "a.bin", 1)
    assert plan_size(tmp_path, cluster_override=128 * 1024).cluster_bytes == 128 * 1024


def test_counts_files_and_dirs(tmp_path: Path) -> None:
    (tmp_path / "sce_sys").mkdir()
    _write(tmp_path / "eboot.bin", 10)
    _write(tmp_path / "sce_sys" / "param.json", 10)
    plan = plan_size(tmp_path)
    assert plan.file_count == 2
    assert plan.dir_count == 1
    assert plan.raw_bytes == 20


def test_size_is_monotonic_for_fixed_cluster(tmp_path: Path) -> None:
    small = tmp_path / "small"
    big = tmp_path / "big"
    small.mkdir()
    big.mkdir()
    _write(small / "a.bin", 1 * 1024 * 1024)
    _write(big / "a.bin", 50 * 1024 * 1024)
    s = plan_size(small, cluster_override=64 * 1024).size_mb
    b = plan_size(big, cluster_override=64 * 1024).size_mb
    assert b >= s


def test_cluster_choices_table() -> None:
    assert CLUSTER_CHOICES["auto"] is None
    assert CLUSTER_CHOICES["64K"] == 64 * 1024
    assert CLUSTER_CHOICES["1M"] == 1024 * 1024
