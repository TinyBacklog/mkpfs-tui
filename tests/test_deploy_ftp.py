"""Tests for the FTP client using a fake ftplib.FTP (no real network)."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

import mkpfs_tui.deploy.ftp as ftpmod
from mkpfs_tui.deploy.ftp import FtpClient, FtpTarget, TransferCancelled


class _FakeFTP:
    """A minimal stand-in for ftplib.FTP recording calls."""

    def __init__(self) -> None:
        self.pasv: bool | None = None
        self.cwd_to: str | None = None
        self.stored: list[tuple[str, int]] = []
        self.listing = [("a.exfat", 10), ("b.txt", 5)]

    def set_pasv(self, flag: bool) -> None:
        self.pasv = flag

    def cwd(self, path: str) -> None:
        self.cwd_to = path

    def mlsd(self, path: str = "") -> Generator[tuple[str, dict[str, str]], None, None]:
        for name, size in self.listing:
            yield name, {"type": "file", "size": str(size)}

    def storbinary(self, cmd: str, fh: Any, blocksize: int = 8192, callback: Any = None) -> None:
        name = cmd.split(" ", 1)[1]
        total = 0
        while True:
            block = fh.read(blocksize)
            if not block:
                break
            total += len(block)
            if callback is not None:
                callback(block)
        self.stored.append((name, total))

    def quit(self) -> None:
        pass


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> _FakeFTP:
    ftp = _FakeFTP()
    monkeypatch.setattr(ftpmod, "_connect", lambda target: (ftp.set_pasv(True), ftp)[1])
    return ftp


def test_test_connect_ok(fake: _FakeFTP) -> None:
    assert FtpClient().test_connect(FtpTarget(host="h")) is None


def test_test_connect_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(target: FtpTarget) -> None:
        raise OSError("refused")

    monkeypatch.setattr(ftpmod, "_connect", boom)
    msg = FtpClient().test_connect(FtpTarget(host="h"))
    assert msg is not None and "refused" in msg


def test_list_dir_parses_names_and_sizes(fake: _FakeFTP) -> None:
    rows = FtpClient().list_dir(FtpTarget(host="h"), "/data/etaHEN/games/")
    assert ("a.exfat", 10) in rows
    assert fake.pasv is True


def test_upload_streams_and_reports_progress(tmp_path: Path, fake: _FakeFTP) -> None:
    local = tmp_path / "img.exfat"
    local.write_bytes(b"\0" * 200_000)
    seen: list[tuple[int, int]] = []
    sent = FtpClient().upload(
        FtpTarget(host="h"),
        local,
        "img.exfat",
        progress_cb=lambda s, t: seen.append((s, t)),
        should_cancel=lambda: False,
    )
    assert sent == 200_000
    assert fake.stored == [("img.exfat", 200_000)]
    assert seen[-1] == (200_000, 200_000)
    assert fake.cwd_to == "/data/etaHEN/games/"


def test_upload_cancel_raises(tmp_path: Path, fake: _FakeFTP) -> None:
    local = tmp_path / "img.exfat"
    local.write_bytes(b"\0" * 200_000)
    with pytest.raises(TransferCancelled):
        FtpClient().upload(
            FtpTarget(host="h"),
            local,
            "img.exfat",
            progress_cb=lambda s, t: None,
            should_cancel=lambda: True,
        )
