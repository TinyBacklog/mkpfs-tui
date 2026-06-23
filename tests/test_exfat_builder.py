"""Tests for the exFAT build pipeline with an injected command runner."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from mkpfs_tui.exfat.builder import BuildOptions, run_build


class _Recorder:
    """Records every command; returns 1 for any command containing a failing token."""

    def __init__(self, fail_on: set[str] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.fail_on = fail_on or set()

    def __call__(self, cmd: Sequence[str]) -> int:
        self.calls.append(list(cmd))
        return 1 if any(token in cmd for token in self.fail_on) else 0

    def tools(self) -> list[str]:
        # First non-"sudo" token of each command (the actual program).
        return [next(arg for arg in call if arg != "sudo") for call in self.calls]


def _mkdtemp_in(tmp_path: Path) -> Callable[..., str]:
    def factory(**_kwargs: object) -> str:
        mnt = tmp_path / "mnt"
        mnt.mkdir(exist_ok=True)
        return str(mnt)

    return factory


def test_happy_path_command_sequence(tmp_path: Path) -> None:
    rec = _Recorder()
    opts = BuildOptions(
        dump=tmp_path,
        output=tmp_path / "out.exfat",
        label="PPSA01234",
        cluster_override=65536,
        verify=True,
    )
    result = run_build(opts, runner=rec, mkdtemp=_mkdtemp_in(tmp_path))
    assert rec.tools() == ["truncate", "mkfs.exfat", "mount", "rsync", "umount", "fsck.exfat"]
    mkfs = next(c for c in rec.calls if c[0] == "mkfs.exfat")
    assert "-c" in mkfs and "64K" in mkfs
    assert "-L" in mkfs and "PPSA01234" in mkfs
    assert result.ok is True
    assert result.cluster_bytes == 65536


def test_umount_runs_even_when_rsync_fails(tmp_path: Path) -> None:
    rec = _Recorder(fail_on={"rsync"})
    opts = BuildOptions(dump=tmp_path, output=tmp_path / "o.exfat", label="L", cluster_override=65536)
    result = run_build(opts, runner=rec, mkdtemp=_mkdtemp_in(tmp_path))
    assert "umount" in rec.tools()  # cleanup still happened
    assert result.ok is False
    assert any("copy" in e or "rsync" in e for e in result.errors)


def test_mount_failure_skips_copy(tmp_path: Path) -> None:
    rec = _Recorder(fail_on={"mount"})
    opts = BuildOptions(dump=tmp_path, output=tmp_path / "o.exfat", label="L", cluster_override=65536)
    result = run_build(opts, runner=rec, mkdtemp=_mkdtemp_in(tmp_path))
    assert "rsync" not in rec.tools()  # never reached the copy
    assert result.ok is False


def test_verify_false_skips_fsck(tmp_path: Path) -> None:
    rec = _Recorder()
    opts = BuildOptions(dump=tmp_path, output=tmp_path / "o.exfat", label="L", cluster_override=65536, verify=False)
    run_build(opts, runner=rec, mkdtemp=_mkdtemp_in(tmp_path))
    assert "fsck.exfat" not in rec.tools()


@pytest.mark.skipif(
    shutil.which("mkfs.exfat") is None or shutil.which("truncate") is None,
    reason="exfatprogs/coreutils not installed",
)
def test_real_mkfs_and_fsck_smoke(tmp_path: Path) -> None:
    # Run truncate/mkfs/fsck for real; fake the privileged mount/rsync/umount.
    def runner(cmd: Sequence[str]) -> int:
        if cmd[0] in ("truncate", "mkfs.exfat", "fsck.exfat"):
            return subprocess.run(list(cmd), capture_output=True).returncode
        return 0

    opts = BuildOptions(
        dump=tmp_path, output=tmp_path / "smoke.exfat", label="SMOKE", cluster_override=65536, verify=True
    )
    result = run_build(opts, runner=runner, mkdtemp=_mkdtemp_in(tmp_path))
    assert result.ok is True, result.errors
    assert (tmp_path / "smoke.exfat").exists()
