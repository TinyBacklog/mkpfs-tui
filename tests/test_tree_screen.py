"""Tests for the Tree view (runner monkeypatched)."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Tree

from mkpfs_tui import mkpfs_runner
from mkpfs_tui.mkpfs_runner import TreeNode, TreeResult
from mkpfs_tui.screens.tree import TreeView
from mkpfs_tui.widgets.path_field import PathField
from mkpfs_tui.widgets.result_panel import ResultPanel


class _Host(App[None]):
    def compose(self) -> ComposeResult:
        yield TreeView()


def _canned() -> TreeResult:
    return TreeResult(
        image="game.pfs",
        ok=True,
        root=TreeNode(
            "/",
            2,
            True,
            (
                TreeNode("sys", 3, True, (TreeNode("config", 4, False, ()),)),
                TreeNode("eboot.bin", 5, False, ()),
            ),
        ),
        errors=(),
        warnings=(),
    )


async def test_tree_populates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mkpfs_runner, "read_tree", lambda *a, **k: _canned())
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        app.query_one("#tree-image", PathField).value = "game.pfs"
        await pilot.click("#tree-run")
        await app.workers.wait_for_complete()
        await pilot.pause()
        tree = app.query_one("#tree-widget", Tree)
        top = [str(node.label) for node in tree.root.children]
        assert top == ["sys", "eboot.bin"]
        sys_node = tree.root.children[0]
        assert [str(n.label) for n in sys_node.children] == ["config"]


async def test_tree_rebuild_replaces(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mkpfs_runner, "read_tree", lambda *a, **k: _canned())
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        app.query_one("#tree-image", PathField).value = "game.pfs"
        await pilot.click("#tree-run")
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.click("#tree-run")
        await app.workers.wait_for_complete()
        await pilot.pause()
        tree = app.query_one("#tree-widget", Tree)
        assert len(tree.root.children) == 2  # rebuild clears first, not 4


async def test_tree_no_root_hides_tree_and_shows_error(monkeypatch: pytest.MonkeyPatch) -> None:
    failed = TreeResult(image="game.pfs", ok=False, root=None, errors=("bad image",), warnings=())
    monkeypatch.setattr(mkpfs_runner, "read_tree", lambda *a, **k: failed)
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        app.query_one("#tree-image", PathField).value = "game.pfs"
        await pilot.click("#tree-run")
        await app.workers.wait_for_complete()
        await pilot.pause()
        tree = app.query_one("#tree-widget", Tree)
        assert tree.display is False
        assert len(app.query_one(ResultPanel).query(".error")) == 1
