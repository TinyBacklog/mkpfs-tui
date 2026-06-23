"""Push a file to a jailbroken PS5 over plain FTP (stdlib ftplib, passive mode).

The PS5's FTP payload (etaHEN ftpsrv on 2121, alternate 1337) is plain FTP on the
LAN. ``upload`` streams via STOR with a per-block callback so callers can drive a
progress bar, and checks a ``should_cancel`` callback between blocks to abort.
"""

from __future__ import annotations

import ftplib
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

_BLOCK = 64 * 1024
_TIMEOUT = 30

ProgressCb = Callable[[int, int], None]
CancelCb = Callable[[], bool]


@dataclass(frozen=True)
class FtpTarget:
    """Connection + destination for an FTP push (password is never persisted)."""

    host: str
    port: int = 2121
    path: str = "/data/etaHEN/games/"
    user: str = "anonymous"
    password: str = ""


class TransferCancelled(Exception):
    """Raised inside the STOR callback to abort an in-flight upload."""


def _connect(target: FtpTarget) -> ftplib.FTP:
    """Open + log in to an FTP connection (separated out so tests can fake it)."""
    ftp = ftplib.FTP(timeout=_TIMEOUT)
    ftp.connect(target.host, target.port)
    ftp.login(target.user or "anonymous", target.password)
    ftp.set_pasv(True)
    return ftp


class FtpClient:
    """Thin façade over ftplib for connect / list / upload."""

    def test_connect(self, target: FtpTarget) -> str | None:
        """Try to connect + log in. Returns None on success, else an error string."""
        try:
            ftp = _connect(target)
        except ftplib.all_errors as exc:
            return str(exc) or exc.__class__.__name__
        with suppress(ftplib.all_errors):
            ftp.quit()
        return None

    def list_dir(self, target: FtpTarget, path: str) -> list[tuple[str, int]]:
        """List ``path`` as ``(name, size)`` rows (MLSD, falling back to NLST).

        Args:
            target: The connection target.
            path: The remote directory to list.

        Returns:
            One ``(name, size_bytes)`` tuple per entry (size 0 when unknown).
        """
        ftp = _connect(target)
        try:
            rows: list[tuple[str, int]] = []
            try:
                for name, facts in ftp.mlsd(path):
                    if name in (".", ".."):
                        continue
                    rows.append((name, int(facts.get("size", 0) or 0)))
            except ftplib.all_errors:
                rows = [(name, 0) for name in ftp.nlst(path)]
            return rows
        finally:
            with suppress(ftplib.all_errors):
                ftp.quit()

    def upload(
        self,
        target: FtpTarget,
        local: Path,
        remote_name: str,
        progress_cb: ProgressCb,
        should_cancel: CancelCb,
    ) -> int:
        """Upload ``local`` to ``target.path/remote_name`` via STOR.

        Args:
            target: The connection + destination directory.
            local: The local file to send.
            remote_name: The destination basename.
            progress_cb: Called as ``(bytes_sent, total_bytes)`` per block.
            should_cancel: Polled per block; True raises TransferCancelled.

        Returns:
            The total number of bytes sent.

        Raises:
            TransferCancelled: If ``should_cancel()`` returns True mid-transfer.
        """
        total = local.stat().st_size
        sent = 0
        ftp = _connect(target)
        try:
            ftp.cwd(target.path)

            def callback(block: bytes) -> None:
                nonlocal sent
                if should_cancel():
                    raise TransferCancelled
                sent += len(block)
                progress_cb(sent, total)

            with local.open("rb") as handle:
                ftp.storbinary(f"STOR {remote_name}", handle, blocksize=_BLOCK, callback=callback)
        finally:
            with suppress(ftplib.all_errors):
                ftp.quit()
        return sent
