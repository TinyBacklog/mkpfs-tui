"""Tests for the deploy CLI subcommand and its app.main() dispatch."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pytest import CaptureFixture, MonkeyPatch

import mkpfs_tui.deploy.cli as cli
from mkpfs_tui.deploy.deployer import DeployResult


def test_parser_reads_flags() -> None:
    args = cli.deploy_argv_parser().parse_args(
        ["img.exfat", "--host", "10.0.0.2", "--port", "1337", "--path", "/x/", "--user", "u", "--name", "n.exfat"]
    )
    assert args.file == Path("img.exfat")
    assert args.host == "10.0.0.2"
    assert args.port == 1337
    assert args.path == "/x/"
    assert args.user == "u"
    assert args.name == "n.exfat"


def test_main_success(monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli, "run_deploy", lambda opts, **kw: DeployResult(True, "/x/img.exfat", 10))
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_a: "")
    rc = cli.main(["img.exfat", "--host", "h"])
    assert rc == 0
    assert "Deployed" in capsys.readouterr().out


def test_main_needs_confirm_aborts(monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        cli, "run_deploy", lambda opts, **kw: DeployResult(False, "/x/img.exfat", 0, needs_confirm=True)
    )
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_a: "")
    monkeypatch.setattr("builtins.input", lambda *_a: "n")
    rc = cli.main(["img.exfat", "--host", "h"])
    assert rc == 1
    assert "exists" in capsys.readouterr().out.lower()


def test_main_error(monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        cli, "run_deploy", lambda opts, **kw: DeployResult(False, "/x/img.exfat", 0, errors=("refused",))
    )
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_a: "")
    rc = cli.main(["img.exfat", "--host", "h"])
    assert rc == 1
    assert "refused" in capsys.readouterr().out


def test_app_main_dispatches_deploy(monkeypatch: MonkeyPatch) -> None:
    from mkpfs_tui import app

    captured: dict[str, list[str]] = {}

    def fake_deploy_main(argv: list[str]) -> int:
        captured["argv"] = argv
        return 0

    monkeypatch.setattr("mkpfs_tui.deploy.cli.main", fake_deploy_main)
    monkeypatch.setattr(sys, "argv", ["mkpfs-tui", "deploy", "img.exfat", "--host", "h"])
    monkeypatch.delenv("MKPFS_TUI_EXEC_MKPFS", raising=False)
    with pytest.raises(SystemExit) as exc:
        app.main()
    assert captured["argv"] == ["img.exfat", "--host", "h"]
    assert exc.value.code == 0
