"""Presentation helpers shared across views."""

from __future__ import annotations

_UNITS = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")


def human_bytes(byte_count: int) -> str:
    """Format a byte count with a binary unit suffix.

    Args:
        byte_count: Number of bytes.

    Returns:
        A string like "0 B", "2.00 KiB", "3.00 TiB".
    """
    size = float(byte_count)
    for unit in _UNITS:
        if size < 1024 or unit == _UNITS[-1]:
            return f"{byte_count} B" if unit == "B" else f"{size:.2f} {unit}"
        size /= 1024
