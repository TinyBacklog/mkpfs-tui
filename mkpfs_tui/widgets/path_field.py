"""PathField: a labelled path input paired with a Browse button."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button, Input, Label


class PathField(Horizontal):
    """A labelled path input with a Browse button that requests a picker."""

    DEFAULT_CSS = """
    PathField {
        height: auto;
    }
    PathField Input {
        width: 1fr;
    }
    """

    class BrowseRequested(Message):
        """Posted when the Browse button is pressed (the picker is wired in M5)."""

        def __init__(self, field_id: str, want: str) -> None:
            """Carry which field asked and what kind of path it wants.

            Args:
                field_id: The PathField's id.
                want: Either "file" or "dir".
            """
            self.field_id = field_id
            self.want = want
            super().__init__()

    def __init__(self, label: str, want: str = "file", *, id: str) -> None:
        """Build a path field.

        Args:
            label: Caption shown before the input.
            want: "file" or "dir" — what the Browse picker should select.
            id: Unique id for this field.
        """
        super().__init__(id=id)
        self._label = label
        self.want = want

    def compose(self) -> ComposeResult:
        """Render the caption, input, and Browse button."""
        yield Label(self._label)
        yield Input(id="path")
        yield Button("Browse…", id="browse")

    @property
    def value(self) -> str:
        """Return the current path text."""
        return self.query_one("#path", Input).value

    @value.setter
    def value(self, text: str) -> None:
        """Set the path text programmatically."""
        self.query_one("#path", Input).value = text

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Translate a Browse press into a BrowseRequested message."""
        if event.button.id == "browse":
            event.stop()
            self.post_message(self.BrowseRequested(self.id or "", self.want))
