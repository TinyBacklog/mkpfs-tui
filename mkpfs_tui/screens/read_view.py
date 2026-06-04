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
    built on the main thread (capturing form values). The result is posted as an
    ``OperationFinished(VIEW_ID, result)`` unless the worker was cancelled.
    """

    VIEW_ID: ClassVar[str] = ""

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Require every ReadView subclass to declare a non-empty VIEW_ID."""
        super().__init_subclass__(**kwargs)
        if not cls.VIEW_ID:
            raise TypeError(f"{cls.__name__} must set a non-empty VIEW_ID")

    @work(thread=True, exclusive=True)
    def run_operation(self, op: Callable[[], object]) -> None:
        """Run ``op()`` in a worker thread and post the result unless cancelled.

        Args:
            op: Zero-argument callable performing the blocking mkpfs call.
        """
        result = op()
        if not get_current_worker().is_cancelled:
            self.post_message(OperationFinished(self.VIEW_ID, result))
