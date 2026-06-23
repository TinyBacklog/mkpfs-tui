"""Compute the exFAT image size (MB) and cluster choice for a dump folder.

Mirrors ShadowMountPlus's mkexfat.sh sizing: each file is rounded up to a whole
cluster, then FAT + allocation-bitmap + directory-entry + fixed (boot/upcase/root)
overhead is added, plus a clamped 0.5% spare, then rounded up to a whole megabyte.
Pure: reads only file sizes via os.walk/stat.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_KB = 1024
_MB = 1024 * 1024
_FIXED_OVERHEAD = 32 * _MB
_SPARE_FRACTION = 0.005
_SPARE_MIN = 64 * _MB
_SPARE_MAX = 512 * _MB
_MIN_FREE = 64 * _MB
_AVG_THRESHOLD = _MB  # avg file < 1MB -> 32K cluster, else 64K

CLUSTER_CHOICES: dict[str, int | None] = {
    "auto": None,
    "32K": 32 * _KB,
    "64K": 64 * _KB,
    "128K": 128 * _KB,
    "256K": 256 * _KB,
    "512K": 512 * _KB,
    "1M": 1024 * _KB,
}


@dataclass(frozen=True)
class SizePlan:
    """A sizing decision for one dump folder."""

    cluster_bytes: int
    size_mb: int
    file_count: int
    dir_count: int
    raw_bytes: int


def _scan(dump: Path) -> tuple[list[int], int]:
    """Return (file sizes, subdirectory count) for the dump tree.

    Args:
        dump: The dump folder root.

    Returns:
        A list of every file's byte size and the number of subdirectories
        (each directory counted once; the root itself is not counted).
    """
    sizes: list[int] = []
    dir_count = 0
    for root, dirs, files in os.walk(dump):
        dir_count += len(dirs)
        for name in files:
            try:
                sizes.append((Path(root) / name).stat().st_size)
            except OSError:
                sizes.append(0)
    return sizes, dir_count


def _pick_cluster(sizes: list[int], override: int | None) -> int:
    """Choose the cluster size in bytes (override wins; else adaptive)."""
    if override is not None:
        return override
    avg = (sum(sizes) / len(sizes)) if sizes else 0
    return 64 * _KB if avg >= _AVG_THRESHOLD else 32 * _KB


def plan_size(dump: Path, cluster_override: int | None = None) -> SizePlan:
    """Compute the exFAT image size and cluster for a dump folder.

    Args:
        dump: The dump folder to size.
        cluster_override: Cluster size in bytes, or None for the adaptive choice.

    Returns:
        A SizePlan with the chosen cluster, the rounded-up megabyte size, and
        the file/dir/raw-byte counts (the latter three drive the size estimate UI).
    """
    sizes, dir_count = _scan(dump)
    cluster = _pick_cluster(sizes, cluster_override)
    data = sum(((size + cluster - 1) // cluster) * cluster for size in sizes)
    clusters = data // cluster
    meta = clusters * 4 + (clusters + 7) // 8 + (len(sizes) + dir_count) * 256 + _FIXED_OVERHEAD
    base = data + meta
    spare = min(max(int(base * _SPARE_FRACTION), _SPARE_MIN), _SPARE_MAX)
    raw = sum(sizes)
    total = max(base + spare, raw + _MIN_FREE)
    size_mb = (total + _MB - 1) // _MB
    return SizePlan(
        cluster_bytes=cluster,
        size_mb=size_mb,
        file_count=len(sizes),
        dir_count=dir_count,
        raw_bytes=raw,
    )
