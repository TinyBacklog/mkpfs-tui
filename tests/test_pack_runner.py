"""Tests for run_pack using a fake Popen (no real subprocess)."""

from __future__ import annotations

import io
import subprocess
import sys

from mkpfs_tui import mkpfs_runner
from mkpfs_tui.mkpfs_runner import PackFinished, PackProgress, PackStatus


class _FakePopen:
    """Minimal Popen stand-in driven by scripted stderr/stdout text."""

    def __init__(self, stderr_text: str, stdout_text: str = "", returncode: int = 0) -> None:
        self.stderr = io.StringIO(stderr_text)
        self.stdout = io.StringIO(stdout_text)
        self.returncode = returncode
        self._done = False

    def wait(self, timeout: float | None = None) -> int:
        self._done = True
        return self.returncode

    def poll(self) -> int | None:
        return self.returncode if self._done else None

    def terminate(self) -> None:
        self._done = True

    def kill(self) -> None:
        self._done = True


def test_run_pack_streams_progress_then_finished() -> None:
    stderr = (
        "[----------------] 0% scan\r"
        "[########--------] 50% compress @ 142.00 MB/s ETA 5s\r"
        "[################] 100% compress\n"
        "Built image out.pfs\n"
    )

    def factory(*_args: object, **_kwargs: object) -> _FakePopen:
        return _FakePopen(stderr, stdout_text="Wrote 3 files\n", returncode=0)

    events = list(mkpfs_runner.run_pack(["pack", "folder", "src", "out.pfs"], popen_factory=factory))

    progresses = [e for e in events if isinstance(e, PackProgress)]
    assert progresses[0].percent == 0
    assert progresses[0].phase == "scan"
    assert progresses[1].percent == 50
    assert progresses[1].speed == "142.00 MB/s"
    assert progresses[-1].percent == 100

    statuses = [e for e in events if isinstance(e, PackStatus)]
    assert any("Built image" in s.text for s in statuses)

    finished = events[-1]
    assert isinstance(finished, PackFinished)
    assert finished.ok is True
    assert finished.exit_code == 0
    assert "Wrote 3 files" in finished.stdout


def test_run_pack_reports_failure_exit_code() -> None:
    def factory(*_args: object, **_kwargs: object) -> _FakePopen:
        return _FakePopen("[----------------] 0% scan\n", returncode=2)

    events = list(mkpfs_runner.run_pack(["pack", "folder", "src", "out.pfs"], popen_factory=factory))
    finished = events[-1]
    assert isinstance(finished, PackFinished)
    assert finished.ok is False
    assert finished.exit_code == 2


def test_run_pack_terminates_process_on_early_close() -> None:
    proc = _FakePopen("[----------------] 0% scan\r[####------------] 25% compress\r", returncode=0)

    def factory(*_args: object, **_kwargs: object) -> _FakePopen:
        return proc

    gen = mkpfs_runner.run_pack(["pack", "folder", "src", "out.pfs"], popen_factory=factory)
    next(gen)  # consume the first event, leaving the generator mid-stream
    gen.close()  # simulates a cancel: the finally must terminate the process
    assert proc._done is True


def test_run_pack_kills_unresponsive_process_on_cancel() -> None:
    # If the child ignores SIGTERM (terminate's bounded wait times out), run_pack
    # must SIGKILL it and reap it (no zombie). The fake's wait raises TimeoutExpired
    # only for the bounded call; the post-kill wait() (no timeout) returns.
    proc = _FakePopen("[----------------] 0% scan\r[####------------] 25% compress\r")
    proc._killed = False

    def _wait(timeout: float | None = None) -> int:
        if timeout is not None:
            raise subprocess.TimeoutExpired(cmd="mkpfs", timeout=timeout)
        return 0

    def _kill() -> None:
        proc._killed = True
        proc._done = True

    proc.wait = _wait  # type: ignore[method-assign]
    proc.kill = _kill  # type: ignore[method-assign]

    gen = mkpfs_runner.run_pack(["pack", "folder", "src", "out.pfs"], popen_factory=lambda *a, **k: proc)
    next(gen)
    gen.close()
    assert proc._killed is True


def test_run_pack_with_real_subprocess() -> None:
    # Exercises the REAL pipe + daemon-drain + iter_cr_lf wiring (not the fake) by
    # standing a tiny python program in for mkpfs, run with run_pack's real kwargs.
    script = (
        "import sys\n"
        "sys.stderr.write('[----------------] 0% scan\\r')\n"
        "sys.stderr.write('[################] 100% scan\\n')\n"
        "sys.stderr.flush()\n"
        "print('done writing', flush=True)\n"
    )

    def factory(_cmd: object, **kwargs: object) -> subprocess.Popen[str]:
        return subprocess.Popen([sys.executable, "-c", script], **kwargs)  # type: ignore[call-overload]

    events = list(mkpfs_runner.run_pack(["pack", "folder", "src", "out.pfs"], popen_factory=factory))
    assert any(isinstance(e, PackProgress) and e.percent == 100 for e in events)
    finished = events[-1]
    assert isinstance(finished, PackFinished)
    assert finished.ok is True
    assert "done writing" in finished.stdout
