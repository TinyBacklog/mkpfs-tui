"""Custom messages posted by background workers back to the UI thread."""

from __future__ import annotations

from textual.message import Message


class OperationFinished(Message):
    """Posted when a background operation completes."""

    def __init__(self, view_id: str, result: object) -> None:
        """Carry the originating view and its result value object.

        Args:
            view_id: Id of the view that started the operation.
            result: The TUI value object produced by the operation.
        """
        self.view_id = view_id
        self.result = result
        super().__init__()


class PackProgressed(Message):
    """A pack progress update (drives the bar + phase/speed line)."""

    def __init__(self, view_id: str, progress: object) -> None:
        """Carry the originating view and a PackProgress payload.

        Args:
            view_id: Id of the view that started the pack.
            progress: A mkpfs_runner.PackProgress.
        """
        self.view_id = view_id
        self.progress = progress
        super().__init__()


class PackStatusLine(Message):
    """A non-progress status line from the pack subprocess."""

    def __init__(self, view_id: str, text: str) -> None:
        """Carry the originating view and the status text.

        Args:
            view_id: Id of the view that started the pack.
            text: The status line.
        """
        self.view_id = view_id
        self.text = text
        super().__init__()


class PackCompleted(Message):
    """The terminal pack message (drives the result panel)."""

    def __init__(self, view_id: str, result: object) -> None:
        """Carry the originating view and a PackFinished payload.

        Args:
            view_id: Id of the view that started the pack.
            result: A mkpfs_runner.PackFinished.
        """
        self.view_id = view_id
        self.result = result
        super().__init__()


class UnpackProgressed(Message):
    """An unpack progress update (the adapter computes percent from done/total)."""

    def __init__(self, view_id: str, phase: str, done: int, total: int) -> None:
        """Carry the view id and the raw progress counters.

        Args:
            view_id: Id of the view that started the unpack.
            phase: The current extraction phase.
            done: Units completed.
            total: Total units (0 when indeterminate).
        """
        self.view_id = view_id
        self.phase = phase
        self.done = done
        self.total = total
        super().__init__()


class UnpackCompleted(Message):
    """The terminal unpack message (drives the result panel)."""

    def __init__(self, view_id: str, result: object) -> None:
        """Carry the view id and an Extraction payload.

        Args:
            view_id: Id of the view that started the unpack.
            result: A mkpfs_runner.Extraction.
        """
        self.view_id = view_id
        self.result = result
        super().__init__()


class DeployProgressed(Message):
    """An FTP-upload progress update (drives the deploy bar)."""

    def __init__(self, view_id: str, sent: int, total: int) -> None:
        """Carry the view id and byte counters.

        Args:
            view_id: Id of the view that started the deploy.
            sent: Bytes uploaded so far.
            total: Total bytes (0 when unknown).
        """
        self.view_id = view_id
        self.sent = sent
        self.total = total
        super().__init__()


class DeployFinished(Message):
    """The terminal deploy message (drives the result panel / confirm retry)."""

    def __init__(self, view_id: str, result: object) -> None:
        """Carry the view id and a DeployResult payload.

        Args:
            view_id: Id of the view that started the deploy.
            result: A deploy.deployer.DeployResult.
        """
        self.view_id = view_id
        self.result = result
        super().__init__()


class DeployListing(Message):
    """A remote directory listing (or an error) for the Deploy view's table."""

    def __init__(self, view_id: str, rows: tuple[tuple[str, int], ...], error: str | None) -> None:
        """Carry the view id, the (name, size) rows, and any error.

        Args:
            view_id: Id of the view that requested the listing.
            rows: One (name, size_bytes) tuple per remote entry.
            error: An error message, or None on success.
        """
        self.view_id = view_id
        self.rows = rows
        self.error = error
        super().__init__()
