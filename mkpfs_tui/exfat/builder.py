"""Build an exFAT image from a dump folder: truncate, mkfs, mount, copy, verify.

Mirrors ShadowMountPlus's mkexfat.sh. truncate/mkfs.exfat/fsck.exfat need no root;
mount/umount go through sudo. Commands run through an injectable ``runner`` (default
inherits this process's stdio, so sudo prompts and rsync progress reach the terminal —
the TUI suspends around the call). The mount point is always unmounted and removed.
"""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from mkpfs_tui.exfat.sizing import SizePlan, plan_size

CommandRunner = Callable[[Sequence[str]], int]


@dataclass(frozen=True)
class BuildOptions:
    """Inputs for one exFAT build."""

    dump: Path
    output: Path
    label: str
    cluster_override: int | None = None
    verify: bool = True


@dataclass(frozen=True)
class BuildResult:
    """Outcome of an exFAT build."""

    ok: bool
    output_path: str
    size_mb: int
    cluster_bytes: int
    label: str
    errors: tuple[str, ...] = ()


def _default_runner(cmd: Sequence[str]) -> int:
    """Run a command inheriting this process's stdio; return its exit code."""
    return subprocess.run(list(cmd), check=False).returncode


def _cluster_arg(cluster_bytes: int) -> str:
    """Render a cluster size as an exfatprogs -c argument (e.g. 64K, 1M)."""
    if cluster_bytes % (1024 * 1024) == 0:
        return f"{cluster_bytes // (1024 * 1024)}M"
    if cluster_bytes % 1024 == 0:
        return f"{cluster_bytes // 1024}K"
    return str(cluster_bytes)


def _result(opts: BuildOptions, plan: SizePlan, ok: bool, errors: list[str]) -> BuildResult:
    """Assemble a BuildResult from options + plan + outcome."""
    return BuildResult(
        ok=ok,
        output_path=str(opts.output),
        size_mb=plan.size_mb,
        cluster_bytes=plan.cluster_bytes,
        label=opts.label,
        errors=tuple(errors),
    )


def run_build(
    opts: BuildOptions,
    *,
    runner: CommandRunner = _default_runner,
    mkdtemp: Callable[..., str] = tempfile.mkdtemp,
) -> BuildResult:
    """Build the exFAT image described by ``opts``.

    Args:
        opts: Dump, output path, label, cluster override, and verify flag.
        runner: Command executor returning an exit code (injected in tests).
        mkdtemp: Mount-point factory (injected in tests).

    Returns:
        A BuildResult; ``ok`` is True only if every step (and any verify) succeeded.
        The mount point is always unmounted and removed, even on failure.
    """
    plan = plan_size(opts.dump, opts.cluster_override)
    output = opts.output
    errors: list[str] = []

    if runner(["truncate", "-s", f"{plan.size_mb}M", str(output)]) != 0:
        return _result(opts, plan, False, ["truncate (allocate image) failed"])

    mkfs = ["mkfs.exfat", "-c", _cluster_arg(plan.cluster_bytes)]
    if opts.label:
        mkfs += ["-L", opts.label]
    mkfs.append(str(output))
    if runner(mkfs) != 0:
        return _result(opts, plan, False, ["mkfs.exfat (format) failed"])

    mnt = Path(mkdtemp(prefix="mkpfs-exfat-"))
    try:
        if runner(["sudo", "mount", "-o", "loop", str(output), str(mnt)]) != 0:
            return _result(opts, plan, False, ["mount failed (needs sudo / loop support)"])
        try:
            if runner(["sudo", "rsync", "-r", "--info=progress2", f"{opts.dump}/", f"{mnt}/"]) != 0:
                errors.append("rsync (copy) failed")
        finally:
            if runner(["sudo", "umount", str(mnt)]) != 0:
                errors.append("umount failed")
    finally:
        with suppress(OSError):
            mnt.rmdir()

    if opts.verify and not errors and runner(["fsck.exfat", "-n", str(output)]) != 0:
        errors.append("fsck.exfat verification failed")

    return _result(opts, plan, not errors, errors)
