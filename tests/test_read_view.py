"""Tests for the shared ReadView worker base."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button

from mkpfs_tui.messages import OperationFinished
from mkpfs_tui.screens.read_view import ReadView


class _Dummy(ReadView):
    VIEW_ID = "dummy"

    def __init__(self) -> None:
        super().__init__()
        self.rendered: list[object] = []

    def compose(self) -> ComposeResult:
        yield Button("go", id="go")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.run_operation(lambda: {"value": 42})

    def render_result(self, result: object) -> None:
        self.rendered.append(result)


class _Host(App[None]):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[tuple[str, object]] = []

    def compose(self) -> ComposeResult:
        yield _Dummy()

    def on_operation_finished(self, event: OperationFinished) -> None:
        self.results.append((event.view_id, event.result))


async def test_read_view_runs_op_and_posts_result() -> None:
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.click("#go")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert app.results == [("dummy", {"value": 42})]


async def test_read_view_sets_loading_then_clears_and_renders() -> None:
    app = _Host()
    async with app.run_test() as pilot:
        view = app.query_one(_Dummy)
        view.run_operation(lambda: {"value": 7})
        # Spinner is shown synchronously, before the worker starts.
        assert view.loading is True
        await app.workers.wait_for_complete()
        await pilot.pause()
        # OperationFinished clears the spinner and routes to render_result.
        assert view.loading is False
        assert view.rendered == [{"value": 7}]


def test_subclass_without_view_id_is_rejected() -> None:
    with pytest.raises(TypeError):

        class _NoId(ReadView):
            pass
