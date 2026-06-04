"""Parse mkpfs's progress-bar stderr output (an f-string format, not a contract)."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TextIO

_PBAR_RE = re.compile(
    r"^\[(?P<bar>[#-]+)\]\s+(?P<pct>\d{1,3})%\s+(?P<phase>\w+)"
    r"(?:\s+@\s+(?P<speed>[\d.]+\s*\S+/s))?"
    r"(?:\s+(?P<items>[\d.]+\s+items/s))?"
    r"(?:\s+ETA\s+(?P<eta>[\d.]+[sm]))?\s*$"
)


@dataclass(frozen=True)
class Progress:
    """A parsed progress-bar line."""

    percent: int
    phase: str
    speed: str | None
    eta: str | None


def parse_progress_line(line: str) -> Progress | None:
    """Parse one stripped stderr line into a Progress, or None if it isn't a bar.

    Args:
        line: A single stripped stderr segment.

    Returns:
        A Progress when the line is a progress bar, else None (a status line).
    """
    match = _PBAR_RE.match(line)
    if match is None:
        return None
    speed = match.group("speed") or match.group("items")
    return Progress(
        percent=int(match.group("pct")),
        phase=match.group("phase"),
        speed=speed.strip() if speed else None,
        eta=match.group("eta"),
    )


def iter_cr_lf(stream: TextIO) -> Iterator[str]:
    r"""Yield segments from a text stream, splitting on both '\r' and '\n'.

    mkpfs rewrites the progress bar in place with '\r' (no newline) and ends a
    phase with '\n', so a normal line iterator would coalesce many updates into
    one. Empty segments (e.g. from a '\r\n' pair) are skipped.

    Args:
        stream: A text-mode readable stream (e.g. a subprocess stderr pipe).

    Yields:
        Each non-empty segment, in order.
    """
    buffer: list[str] = []
    while True:
        char = stream.read(1)
        if not char:
            if buffer:
                yield "".join(buffer)
            return
        if char in ("\r", "\n"):
            if buffer:
                yield "".join(buffer)
                buffer = []
        else:
            buffer.append(char)
