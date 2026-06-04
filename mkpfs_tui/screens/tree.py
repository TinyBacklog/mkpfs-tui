"""Tree view: render a PFS image's filesystem tree."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, Label, Switch, Tree
from textual.widgets.tree import TreeNode as WidgetTreeNode

from mkpfs_tui import mkpfs_runner
from mkpfs_tui.mkpfs_runner import TreeNode, TreeResult
from mkpfs_tui.screens.read_view import ReadView
from mkpfs_tui.widgets.path_field import PathField
from mkpfs_tui.widgets.result_panel import ResultPanel


class TreeView(ReadView):
    """Build and display a PFS image's filesystem tree."""

    VIEW_ID = "tree"

    def compose(self) -> ComposeResult:
        """Render the image picker, options, run button, tree, and result panel."""
        yield PathField("Image", "file", id="tree-image")
        yield Input(placeholder="EKPFS key — 64 hex, optional", id="tree-ekpfs")
        with Horizontal(classes="option-row"):
            yield Label("newCrypt")
            yield Switch(id="tree-new-crypt")
        yield Button("Build tree", id="tree-run", variant="primary")
        yield Tree("/", id="tree-widget")
        yield ResultPanel(id="tree-result")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Start building the tree when the button is pressed."""
        if event.button.id != "tree-run":
            return
        event.stop()
        image = self.query_one("#tree-image", PathField).value
        ekpfs = self.query_one("#tree-ekpfs", Input).value
        new_crypt = self.query_one("#tree-new-crypt", Switch).value
        self.run_operation(lambda: mkpfs_runner.read_tree(Path(image), ekpfs_hex=ekpfs, new_crypt=new_crypt))

    def render_result(self, result: object) -> None:
        """Populate the Tree widget and result panel from the TreeResult."""
        if not isinstance(result, TreeResult):
            return
        tree = self.query_one("#tree-widget", Tree)
        tree.clear()
        tree.display = result.root is not None
        if result.root is not None:
            tree.root.set_label(result.root.name)
            self._populate(tree.root, result.root)
            tree.root.expand()
        self.query_one("#tree-result", ResultPanel).show(result.errors, result.warnings)

    def _populate(self, widget_node: WidgetTreeNode, node: TreeNode) -> None:
        """Recursively add a TreeNode's children to a Textual tree node.

        Args:
            widget_node: The Textual tree node to add children to.
            node: The mkpfs_runner TreeNode whose children to recurse over.
        """
        for child in node.children:
            if child.is_dir:
                self._populate(widget_node.add(child.name), child)
            else:
                widget_node.add_leaf(child.name)
