"""A modal directory/file picker wrapping Textual's DirectoryTree."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Label


class DirectoryPickerScreen(ModalScreen[str | None]):
    """Pick a file or directory; dismisses with the path string, or None on cancel."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "cancel", "Cancel")]

    def __init__(self, want: str = "file", root: str | None = None) -> None:
        """Build the picker.

        Args:
            want: "file" or "dir" — which selections are accepted.
            root: Starting directory (defaults to the current working directory).
        """
        super().__init__()
        self.want = want
        self._root = root or str(Path.cwd())
        self._selection: str | None = None

    def compose(self) -> ComposeResult:
        """Render the tree and Choose/Cancel buttons."""
        with Vertical(id="picker-box"):
            yield Label(f"Select a {self.want}")
            yield DirectoryTree(self._root, id="picker-tree")
            with Horizontal(id="picker-buttons"):
                yield Button("Choose", id="picker-choose", variant="primary")
                yield Button("Cancel", id="picker-cancel")

    def set_selection(self, path: str) -> None:
        """Set the current selection (used by the tree handlers and tests)."""
        self._selection = path

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Record a file selection when picking a file."""
        if self.want == "file":
            self.set_selection(str(event.path))

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """Record a directory selection when picking a directory."""
        if self.want == "dir":
            self.set_selection(str(event.path))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Choose dismisses with the selection; Cancel dismisses with None."""
        if event.button.id == "picker-choose":
            self.dismiss(self._selection)
        elif event.button.id == "picker-cancel":
            self.dismiss(None)

    def action_cancel(self) -> None:
        """Escape cancels."""
        self.dismiss(None)
