"""About / welcome screen shown by default when the app launches."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static

_BANNER = r"""           _           __           _         _
 _ __ ___ | | ___ __  / _|___      | |_ _   _(_)
| '_ ` _ \| |/ / '_ \| |_/ __|_____| __| | | | |
| | | | | |   <| |_) |  _\__ \_____| |_| |_| | |
|_| |_| |_|_|\_\ .__/|_| |___/      \__|\__,_|_|
               |_|                              """

_DESCRIPTION = "A terminal UI for packing, inspecting, verifying PlayStation PFS; build exFAT, and deploy to PS5."
_BY = "by ClaudioVarandas"


def _app_version() -> str:
    """Return the installed package version, or 'dev' when not installed.

    Returns:
        The version string from importlib.metadata, or 'dev' as fallback.
    """
    try:
        return version("mkpfs-tui")
    except PackageNotFoundError:
        return "dev"


class AboutView(Container):
    """Welcome / landing screen shown when the app first opens."""

    VIEW_ID: ClassVar[str] = "about"

    def compose(self) -> ComposeResult:
        """Render the ASCII banner, description, author, and footer."""
        ver = _app_version()
        yield Static(_BANNER, id="about-banner")
        yield Static(_DESCRIPTION, id="about-description")
        yield Static(_BY, id="about-by")
        yield Static(
            f"v{ver} · GPL-3.0-or-later · github.com/TinyBacklog/mkpfs-tui",
            id="about-footer",
        )
