"""Shared base for read-only views that run a blocking mkpfs op in a worker."""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from textual import work
from textual.containers import Container
from textual.worker import get_current_worker

from mkpfs_tui.messages import OperationFinished


class ReadView(Container):
    """Base for views that run a blocking mkpfs op off-thread and post the result.

    Subclasses set ``VIEW_ID`` and call ``run_operation`` with a zero-arg callable
    built on the main thread (capturing form values). ``run_operation`` shows the
    ``loading`` spinner on the main thread, then runs ``op()`` in a worker; the result
    arrives as ``OperationFinished(VIEW_ID, result)``. The base ``on_operation_finished``
    clears the spinner and dispatches to the subclass's ``render_result``.
    """

    VIEW_ID: ClassVar[str] = ""

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Require every ReadView subclass to declare a non-empty VIEW_ID."""
        super().__init_subclass__(**kwargs)
        if not cls.VIEW_ID:
            raise TypeError(f"{cls.__name__} must set a non-empty VIEW_ID")

    def _on_operation_start(self) -> None:
        """Called on the main thread just before the worker is launched.

        The default implementation enables the loading spinner.  Subclasses may
        override to replace the spinner with a custom busy indicator.
        """
        self.loading = True

    def _on_operation_end(self) -> None:
        """Called on the main thread when the worker result arrives.

        The default implementation clears the loading spinner.  Subclasses may
        override to tear down a custom busy indicator.
        """
        self.loading = False

    def run_operation(self, op: Callable[[], object]) -> None:
        """Show the spinner (main thread), then run ``op()`` in a worker.

        Args:
            op: Zero-argument callable performing the blocking mkpfs call.
        """
        self._on_operation_start()
        self._run_operation_worker(op)

    @work(thread=True, exclusive=True)
    def _run_operation_worker(self, op: Callable[[], object]) -> None:
        """Run ``op()`` in a worker thread and post the result.

        On cancellation (a newer run replaced this one) the spinner is left to the
        replacement run; otherwise the result is posted and the handler clears it.

        Args:
            op: Zero-argument callable performing the blocking mkpfs call.
        """
        result = op()
        if not get_current_worker().is_cancelled:
            self.post_message(OperationFinished(self.VIEW_ID, result))

    def on_operation_finished(self, event: OperationFinished) -> None:
        """Clear the spinner, then hand the result to the subclass renderer."""
        if event.view_id != self.VIEW_ID:
            return
        self._on_operation_end()
        self.render_result(event.result)

    def render_result(self, result: object) -> None:
        """Render a finished operation's result. Overridden by each subclass."""
        raise NotImplementedError
