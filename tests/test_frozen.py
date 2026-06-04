"""Tests for the frozen-binary self-dispatch (M6 packaging)."""

from __future__ import annotations

import sys

import pytest

from mkpfs_tui import app, mkpfs_runner


def test_pack_command_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    cmd = mkpfs_runner._pack_command(["pack", "folder", "s", "o"])
    assert cmd == [sys.executable, "-m", "mkpfs", "pack", "folder", "s", "o"]


def test_pack_command_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    cmd = mkpfs_runner._pack_command(["pack", "folder", "s", "o"])
    assert cmd == [sys.executable, "pack", "folder", "s", "o"]  # no "-m mkpfs"


def test_run_pack_sets_exec_env_only_when_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _Fake:
        def __init__(self) -> None:
            self.stderr = __import__("io").StringIO("")
            self.stdout = __import__("io").StringIO("")
            self.returncode = 0
            self._done = False

        def wait(self, timeout: float | None = None) -> int:
            self._done = True
            return 0

        def poll(self) -> int | None:
            return 0 if self._done else None

        def terminate(self) -> None:
            self._done = True

        def kill(self) -> None:
            self._done = True

    def factory(_cmd: object, **kwargs: object) -> _Fake:
        captured.update(kwargs)
        return _Fake()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    list(mkpfs_runner.run_pack(["pack", "folder", "s", "o"], popen_factory=factory))
    assert captured["env"]["MKPFS_TUI_EXEC_MKPFS"] == "1"

    captured.clear()
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    list(mkpfs_runner.run_pack(["pack", "folder", "s", "o"], popen_factory=factory))
    assert "MKPFS_TUI_EXEC_MKPFS" not in captured["env"]


def test_main_dispatches_to_mkpfs_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MKPFS_TUI_EXEC_MKPFS", "1")
    called: list[bool] = []
    monkeypatch.setattr(mkpfs_runner, "run_mkpfs_cli", lambda: called.append(True) or 0)
    with pytest.raises(SystemExit):
        app.main()
    assert called == [True]


def test_main_runs_tui_when_not_dispatched(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MKPFS_TUI_EXEC_MKPFS", raising=False)
    ran: list[bool] = []
    monkeypatch.setattr(app.MkpfsTuiApp, "run", lambda self: ran.append(True))
    app.main()
    assert ran == [True]
