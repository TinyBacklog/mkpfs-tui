"""Persisted app settings: the PS5 FTP target — the app's only on-disk state.

Stored at ``$XDG_CONFIG_HOME/mkpfs-tui/config.toml`` (else ``~/.config/…``). Read
with stdlib ``tomllib``; written with a tiny flat ``[ftp]`` emitter (no third-party
TOML writer). The FTP password is never persisted — it is entered each session.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_PORT = 2121
_DEFAULT_PATH = "/data/etaHEN/games/"
_DEFAULT_USER = "anonymous"


@dataclass(frozen=True)
class FtpConfig:
    """The persisted FTP target (never includes a password)."""

    host: str = ""
    port: int = _DEFAULT_PORT
    path: str = _DEFAULT_PATH
    user: str = _DEFAULT_USER


def config_path() -> Path:
    """Return the config file path under XDG_CONFIG_HOME (or ~/.config)."""
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "mkpfs-tui" / "config.toml"


def load(path: Path | None = None) -> FtpConfig:
    """Load the FTP config, returning defaults if absent or unreadable.

    Args:
        path: Override path (defaults to ``config_path()``).

    Returns:
        The parsed FtpConfig, or a default FtpConfig on any error.
    """
    target = path or config_path()
    try:
        data = tomllib.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return FtpConfig()
    ftp = data.get("ftp") if isinstance(data, dict) else None
    if not isinstance(ftp, dict):
        return FtpConfig()
    try:
        port = int(ftp.get("port", _DEFAULT_PORT))
    except (TypeError, ValueError):
        port = _DEFAULT_PORT
    return FtpConfig(
        host=str(ftp.get("host", "")),
        port=port,
        path=str(ftp.get("path", _DEFAULT_PATH)),
        user=str(ftp.get("user", _DEFAULT_USER)),
    )


def _quote(value: str) -> str:
    """Render a string as a TOML basic-string literal."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def save(cfg: FtpConfig, path: Path | None = None) -> None:
    """Write the FTP config (password excluded) as a flat ``[ftp]`` table.

    Args:
        cfg: The config to persist.
        path: Override path (defaults to ``config_path()``).
    """
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "[ftp]",
        f"host = {_quote(cfg.host)}",
        f"port = {cfg.port}",
        f"path = {_quote(cfg.path)}",
        f"user = {_quote(cfg.user)}",
        "",
    ]
    target.write_text("\n".join(lines), encoding="utf-8")
