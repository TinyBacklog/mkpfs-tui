"""Tests for the persisted FTP-target config (the app's only on-disk state)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mkpfs_tui.config import FtpConfig, config_path, load, save


def test_defaults_when_no_file(tmp_path: Path) -> None:
    cfg = load(tmp_path / "missing.toml")
    assert cfg == FtpConfig()
    assert cfg.port == 2121
    assert cfg.path == "/data/etaHEN/games/"
    assert cfg.user == "anonymous"


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    save(FtpConfig(host="192.168.1.50", port=1337, path="/mnt/usb0/", user="ps5"), path)
    cfg = load(path)
    assert cfg.host == "192.168.1.50"
    assert cfg.port == 1337
    assert cfg.path == "/mnt/usb0/"
    assert cfg.user == "ps5"


def test_password_is_never_written(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    save(FtpConfig(host="h"), path)
    assert "password" not in path.read_text(encoding="utf-8").lower()


def test_quotes_in_host_are_escaped(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    save(FtpConfig(host='a"b\\c'), path)
    assert load(path).host == 'a"b\\c'


def test_garbage_file_returns_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("{ not toml", encoding="utf-8")
    assert load(path) == FtpConfig()


def test_config_path_honors_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config_path() == tmp_path / "mkpfs-tui" / "config.toml"
