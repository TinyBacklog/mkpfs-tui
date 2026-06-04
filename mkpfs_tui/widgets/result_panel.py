"""ResultPanel: renders operation errors, warnings, and success notes as classed labels."""

from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Label


class ResultPanel(Vertical):
    """Shows operation notes (``.success``), warnings (``.warning``), and errors (``.error``)."""

    def show(self, errors: tuple[str, ...], warnings: tuple[str, ...], notes: tuple[str, ...] = ()) -> None:
        """Replace the panel contents with notes (success), warnings, then errors.

        Args:
            errors: Error lines, rendered with the ``error`` CSS class.
            warnings: Warning lines, rendered with the ``warning`` CSS class.
            notes: Success note lines, rendered with the ``success`` CSS class (shown first).
        """
        self.remove_children()
        for note in notes:
            self.mount(Label(note, classes="success"))
        for warning in warnings:
            self.mount(Label(warning, classes="warning"))
        for err in errors:
            self.mount(Label(err, classes="error"))
