"""Anti-corruption boundary: the ONLY module that imports mkpfs.

Exposes the TUI's own frozen value types and blocking operation functions. Every
other module in the app imports from here, never from ``mkpfs.*``. An upstream
mkpfs rename therefore breaks only this file, caught by ``test_mkpfs_contract``.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mkpfs import consts
from mkpfs.pbar import Progress
from mkpfs.pfs import (
    BuildError,
    PFSImageInspection,
    extract_pfs_image,
    inspect_pfs_image,
    parse_ekpfs_key_hex,
    verify_pfs_image,
)

from mkpfs_tui.progress_parser import iter_cr_lf, parse_progress_line


@dataclass(frozen=True)
class HeaderInfo:
    """Selected numeric fields from a parsed PFS header."""

    block_size: int
    nblock: int
    dinode_count: int
    ndblock: int
    dinode_block_count: int
    readonly: int


@dataclass(frozen=True)
class Inspection:
    """TUI-facing summary of a PFS image inspection."""

    image: str
    ok: bool
    size_bytes: int
    version_label: str
    header: HeaderInfo | None
    inode_count: int
    dir_count: int
    file_count: int
    compressed_files: int
    checked_files: int
    data_crc32: int
    manifest_sha256: str
    logical_file_bytes: int
    stored_file_bytes: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class TreeNode:
    """A node in the PFS filesystem tree."""

    name: str
    inode: int
    is_dir: bool
    children: tuple[TreeNode, ...]


@dataclass(frozen=True)
class TreeResult:
    """TUI-facing result of building a PFS filesystem tree."""

    image: str
    ok: bool
    root: TreeNode | None
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def _ekpfs_bytes(ekpfs_hex: str) -> bytes | None:
    """Convert an EKPFS hex string to bytes, or None when blank.

    Args:
        ekpfs_hex: 64-hex-character key, or blank for none.

    Returns:
        Parsed key bytes, or None when the input is blank/whitespace.

    Raises:
        BuildError: If the text is non-blank and not valid 64-character hex.
    """
    if not ekpfs_hex.strip():
        return None
    return parse_ekpfs_key_hex(ekpfs_hex)


def _to_inspection(raw: PFSImageInspection) -> Inspection:
    """Map an mkpfs PFSImageInspection into the TUI Inspection value type."""
    header: HeaderInfo | None = None
    if raw.header is not None:
        header = HeaderInfo(
            block_size=raw.header.block_size,
            nblock=raw.header.nblock,
            dinode_count=raw.header.dinode_count,
            ndblock=raw.header.ndblock,
            dinode_block_count=raw.header.dinode_block_count,
            readonly=raw.header.readonly,
        )
    return Inspection(
        image=str(raw.image),
        ok=not raw.errors,
        size_bytes=raw.size_bytes,
        version_label=raw.version_label,
        header=header,
        inode_count=len(raw.inodes),
        dir_count=len(raw.dir_inodes),
        file_count=len(raw.file_inodes),
        compressed_files=raw.compressed_files,
        checked_files=raw.checked_files,
        data_crc32=raw.data_crc32,
        manifest_sha256=raw.manifest_sha256,
        logical_file_bytes=raw.logical_file_bytes,
        stored_file_bytes=raw.stored_file_bytes,
        errors=tuple(raw.errors),
        warnings=tuple(raw.warnings),
    )


def _error_inspection(image: Path, message: str) -> Inspection:
    """Build a failed Inspection carrying a single error message."""
    return Inspection(
        image=str(image),
        ok=False,
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
        errors=(message,),
        warnings=(),
    )


def inspect_image(image: Path, ekpfs_hex: str = "", new_crypt: bool = False) -> Inspection:
    """Inspect a PFS image and return a TUI-facing summary.

    Args:
        image: Path to the PFS image.
        ekpfs_hex: Optional 64-hex EKPFS key for encrypted images.
        new_crypt: Use the alternate newCrypt key derivation.

    Returns:
        An Inspection; on a bad key or read error, one with ``ok=False`` and the
        error message instead of raising.
    """
    try:
        ekpfs = _ekpfs_bytes(ekpfs_hex)
        raw = inspect_pfs_image(image=image, ekpfs=ekpfs, new_crypt=new_crypt)
    except (OSError, ValueError, BuildError) as exc:
        return _error_inspection(image, f"{type(exc).__name__}: {exc}")
    return _to_inspection(raw)


def verify_image(
    image: Path,
    source: str = "",
    expected_crc32: str = "",
    expected_manifest_sha256: str = "",
    ekpfs_hex: str = "",
    new_crypt: bool = False,
) -> Inspection:
    """Verify a PFS image against optional source and hash expectations.

    Args:
        image: Path to the PFS image.
        source: Optional source tree path (blank = none).
        expected_crc32: Optional expected CRC32 as text (hex "0x.." or decimal; blank = none).
        expected_manifest_sha256: Optional expected manifest digest (blank = none).
        ekpfs_hex: Optional 64-hex EKPFS key.
        new_crypt: Use the alternate newCrypt key derivation.

    Returns:
        An Inspection; PASS is ``result.ok``. On a bad key/crc or read error,
        ``ok=False`` with the error message instead of raising.
    """
    try:
        ekpfs = _ekpfs_bytes(ekpfs_hex)
        crc = int(expected_crc32, 0) if expected_crc32.strip() else None
        src = Path(source) if source.strip() else None
        manifest = expected_manifest_sha256.strip() or None
        raw = verify_pfs_image(
            image=image,
            source=src,
            expected_crc32=crc,
            expected_manifest_sha256=manifest,
            ekpfs=ekpfs,
            new_crypt=new_crypt,
        )
    except (OSError, ValueError, BuildError) as exc:
        return _error_inspection(image, f"{type(exc).__name__}: {exc}")
    return _to_inspection(raw)


def _build_tree_node(
    name: str,
    inode: int,
    dirents_by_inode: dict[int, list[object]],
    is_dir: bool,
    seen: frozenset[int],
) -> TreeNode:
    """Recursively build a TreeNode, skipping '.'/'..' and guarding cycles."""
    children: list[TreeNode] = []
    if is_dir and inode not in seen:
        seen = seen | {inode}
        entries = [e for e in dirents_by_inode.get(inode, []) if e.name not in (".", "..")]
        entries.sort(key=lambda e: (e.type_code != consts.DIRENT_TYPE_DIRECTORY, e.name.lower(), e.name))
        for ent in entries:
            child_is_dir = ent.type_code == consts.DIRENT_TYPE_DIRECTORY
            children.append(_build_tree_node(ent.name, ent.inode_number, dirents_by_inode, child_is_dir, seen))
    return TreeNode(name=name, inode=inode, is_dir=is_dir, children=tuple(children))


def read_tree(image: Path, ekpfs_hex: str = "", new_crypt: bool = False) -> TreeResult:
    """Inspect a PFS image and build its filesystem tree from the root inode.

    Args:
        image: Path to the PFS image.
        ekpfs_hex: Optional 64-hex EKPFS key for encrypted images.
        new_crypt: Use the alternate newCrypt key derivation.

    Returns:
        A TreeResult; ``root`` is None when the image has no parsable root.

    Note: a pathologically deep tree raises RecursionError internally, which is caught
        and returned as a failed TreeResult.
    """
    try:
        ekpfs = _ekpfs_bytes(ekpfs_hex)
        raw = inspect_pfs_image(image=image, ekpfs=ekpfs, new_crypt=new_crypt)
        if raw.uroot_inode < 0:
            return TreeResult(
                image=str(image),
                ok=False,
                root=None,
                errors=tuple(raw.errors) or ("no filesystem root found",),
                warnings=tuple(raw.warnings),
            )
        root = _build_tree_node("/", raw.uroot_inode, raw.dirents_by_inode, is_dir=True, seen=frozenset())
    except (OSError, ValueError, BuildError, RecursionError) as exc:
        return TreeResult(
            image=str(image),
            ok=False,
            root=None,
            errors=(f"{type(exc).__name__}: {exc}",),
            warnings=(),
        )
    return TreeResult(
        image=str(image),
        ok=not raw.errors,
        root=root,
        errors=tuple(raw.errors),
        warnings=tuple(raw.warnings),
    )


@dataclass(frozen=True)
class PackProgress:
    """A progress update emitted by run_pack."""

    percent: int
    phase: str
    speed: str | None
    eta: str | None


@dataclass(frozen=True)
class PackStatus:
    """A non-progress status line emitted by run_pack."""

    text: str


@dataclass(frozen=True)
class PackFinished:
    """The terminal event emitted by run_pack when the process exits."""

    exit_code: int
    ok: bool
    stdout: str


def run_mkpfs_cli() -> int:
    """Run the bundled mkpfs CLI (the frozen binary's self-dispatch target).

    Houses the ``mkpfs.cli`` import so the boundary stays in this one module.

    Returns:
        The CLI exit code (0 on success).
    """
    from mkpfs.cli import main as _cli_main

    return int(_cli_main() or 0)


def _pack_command(argv: list[str]) -> list[str]:
    """Build the subprocess command for the pack argv.

    In a PyInstaller binary ``sys.executable`` is the frozen exe (not Python), so we
    re-invoke it with ``MKPFS_TUI_EXEC_MKPFS=1`` (set by run_pack) to route into the
    bundled mkpfs CLI. In dev we run ``python -m mkpfs``.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, *argv]
    return [sys.executable, "-m", "mkpfs", *argv]


def run_pack(
    argv: list[str], *, popen_factory: Callable[..., Any] = subprocess.Popen
) -> Iterator[PackProgress | PackStatus | PackFinished]:
    """Run ``mkpfs pack`` as a subprocess, yielding progress/status/finished events.

    Drains stdout in a daemon thread (avoids a pipe-fill deadlock while reading
    stderr) and splits stderr on both CR and LF to capture in-place bar rewrites.
    Closing the generator (e.g. on cancel) terminates the child process.

    Args:
        argv: The pack argv from build_pack_argv (starting with "pack").
        popen_factory: Injectable Popen constructor (tests pass a fake).

    Yields:
        PackProgress / PackStatus events while running, then one PackFinished.
    """
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "MKPFS_NO_UTF8": "1"}
    if getattr(sys, "frozen", False):
        env["MKPFS_TUI_EXEC_MKPFS"] = "1"
    proc = popen_factory(
        _pack_command(argv),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
    )
    stdout_parts: list[str] = []

    def _drain() -> None:
        if proc.stdout is not None:
            for line in proc.stdout:
                stdout_parts.append(line)

    drainer = threading.Thread(target=_drain, daemon=True)
    drainer.start()
    try:
        if proc.stderr is not None:
            for segment in iter_cr_lf(proc.stderr):
                stripped = segment.strip()
                if not stripped:
                    continue
                progress = parse_progress_line(stripped)
                if progress is not None:
                    yield PackProgress(progress.percent, progress.phase, progress.speed, progress.eta)
                else:
                    yield PackStatus(stripped)
        proc.wait()
        drainer.join(timeout=2)
        if drainer.is_alive():
            logging.getLogger(__name__).warning("pack stdout drain timed out; captured output may be truncated")
        yield PackFinished(proc.returncode, proc.returncode == 0, "".join(stdout_parts))
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


@dataclass(frozen=True)
class Extraction:
    """TUI-facing result of extracting a PFS image."""

    output_path: str
    ok: bool
    files_written: int
    directories_created: int
    bytes_written: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


class _UiProgress(Progress):
    """mkpfs Progress adapter that forwards step/status to a callback (no stderr)."""

    def __init__(self, on_step: Callable[[str, int, int, int], None]) -> None:
        """Wrap a callback ``on_step(phase, done, total, bytes_processed)``."""
        super().__init__(enabled=True)
        self._on_step = on_step

    def step(self, phase: str, done: int, total: int, bytes_processed: int = 0) -> None:
        """Forward a progress step to the callback (does not call super)."""
        self._on_step(phase, done, total, bytes_processed)

    def status(self, message: str) -> None:
        """Forward a status message as an indeterminate step (does not call super)."""
        self._on_step(message, 0, 0, 0)


def _error_extraction(output_path: Path, message: str) -> Extraction:
    """Build a failed Extraction carrying a single error message."""
    return Extraction(
        output_path=str(output_path),
        ok=False,
        files_written=0,
        directories_created=0,
        bytes_written=0,
        errors=(message,),
        warnings=(),
    )


def unpack_image(
    image: Path,
    output_path: Path,
    *,
    ekpfs_hex: str = "",
    new_crypt: bool = False,
    on_step: Callable[[str, int, int, int], None] | None = None,
) -> Extraction:
    """Extract a PFS image to a directory, forwarding progress to on_step.

    Args:
        image: Path to the PFS image.
        output_path: Destination directory.
        ekpfs_hex: Optional 64-hex EKPFS key.
        new_crypt: Use the alternate newCrypt key derivation.
        on_step: Optional callable ``(phase, done, total, bytes_processed)`` for progress.

    Returns:
        An Extraction; on a bad key or extraction error, one with ``ok=False``.
    """
    try:
        ekpfs = _ekpfs_bytes(ekpfs_hex)
        progress = _UiProgress(on_step) if on_step is not None else None
        raw = extract_pfs_image(
            image=image, output_path=output_path, progress=progress, ekpfs=ekpfs, new_crypt=new_crypt
        )
    except (OSError, ValueError, BuildError) as exc:
        return _error_extraction(output_path, f"{type(exc).__name__}: {exc}")
    return Extraction(
        output_path=str(raw.output_path),
        ok=not raw.errors,
        files_written=raw.files_written,
        directories_created=raw.directories_created,
        bytes_written=raw.bytes_written,
        errors=tuple(raw.errors),
        warnings=tuple(raw.warnings),
    )
