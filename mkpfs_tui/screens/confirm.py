"""A yes/no confirmation modal."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmScreen(ModalScreen[bool]):
    """Modal asking a yes/no question; dismisses with the boolean answer."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "dismiss_false", "Cancel")]

    def __init__(self, question: str) -> None:
        """Store the question text.

        Args:
            question: The prompt shown in the modal.
        """
        super().__init__()
        self._question = question

    def compose(self) -> ComposeResult:
        """Render the question and Yes/No buttons."""
        with Vertical(id="confirm-box"):
            yield Label(self._question)
            with Horizontal():
                yield Button("Yes", id="confirm-yes", variant="error")
                yield Button("No", id="confirm-no", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dismiss with True for Yes, False for No."""
        self.dismiss(event.button.id == "confirm-yes")

    def action_dismiss_false(self) -> None:
        """Escape cancels (answer False)."""
        self.dismiss(False)
