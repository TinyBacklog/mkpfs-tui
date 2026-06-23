"""Tests for the build-exfat CLI subcommand and its app.main() dispatch."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pytest import CaptureFixture, MonkeyPatch

import mkpfs_tui.exfat.cli as cli
from mkpfs_tui.exfat.builder import BuildOptions, BuildResult


def test_parser_reads_all_flags() -> None:
    args = cli.build_argv_parser().parse_args(
        ["dump", "-o", "out.exfat", "--cluster", "64K", "--label", "L", "--no-verify"]
    )
    assert args.dump == Path("dump")
    assert args.output == Path("out.exfat")
    assert args.cluster == "64K"
    assert args.label == "L"
    assert args.verify is False


def test_main_success(monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli, "preflight", lambda *, verify: [])
    monkeypatch.setattr(
        cli,
        "run_build",
        lambda opts: BuildResult(True, str(opts.output), 128, 65536, opts.label, ()),
    )
    rc = cli.main(["dump", "-o", "out.exfat"])
    assert rc == 0
    assert "Built" in capsys.readouterr().out


def test_main_missing_tools(monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli, "preflight", lambda *, verify: ["mkfs.exfat: install exfatprogs"])
    rc = cli.main(["dump", "-o", "out.exfat"])
    assert rc == 1
    assert "mkfs.exfat" in capsys.readouterr().out


def test_main_build_failure(monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli, "preflight", lambda *, verify: [])
    monkeypatch.setattr(
        cli,
        "run_build",
        lambda opts: BuildResult(False, str(opts.output), 128, 65536, opts.label, ("mount failed",)),
    )
    rc = cli.main(["dump", "-o", "out.exfat"])
    assert rc == 1
    assert "mount failed" in capsys.readouterr().out


def test_app_main_dispatches_build_exfat(monkeypatch: MonkeyPatch) -> None:
    from mkpfs_tui import app

    captured: dict[str, list[str]] = {}

    def fake_main(argv: list[str]) -> int:
        captured["argv"] = argv
        return 0

    monkeypatch.setattr("mkpfs_tui.exfat.cli.main", fake_main)
    monkeypatch.setattr(sys, "argv", ["mkpfs-tui", "build-exfat", "dump", "-o", "x.exfat"])
    monkeypatch.delenv("MKPFS_TUI_EXEC_MKPFS", raising=False)
    with pytest.raises(SystemExit) as exc:
        app.main()
    assert captured["argv"] == ["dump", "-o", "x.exfat"]
    assert exc.value.code == 0


def test_build_parser_has_preset_and_lower() -> None:
    args = cli.build_argv_parser().parse_args(["dump", "--preset", "title", "--lower"])
    assert args.output is None  # -o now optional
    assert args.preset == "title"
    assert args.lower is True


def test_build_derives_output_when_omitted(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str], tmp_path: Path
) -> None:
    import json

    dump = tmp_path / "DUMP"
    (dump / "sce_sys").mkdir(parents=True)
    (dump / "sce_sys" / "param.json").write_text(
        json.dumps({"titleId": "PPSA01234", "contentVersion": "01.00", "titleName": "Game"})
    )
    captured: dict[str, object] = {}
    monkeypatch.setattr(cli, "preflight", lambda *, verify: [])

    def fake_run_build(opts: BuildOptions) -> BuildResult:
        captured["output"] = opts.output
        return BuildResult(True, str(opts.output), 100, 65536, opts.label, ())

    monkeypatch.setattr(cli, "run_build", fake_run_build)
    rc = cli.main([str(dump), "--preset", "ppsa"])
    assert rc == 0
    assert str(captured["output"]).endswith("PPSA01234.exfat")
