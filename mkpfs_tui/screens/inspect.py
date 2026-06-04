"""Inspect view: render a PFS image's header and counts in a table."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Input, Label, Switch

from mkpfs_tui import mkpfs_runner
from mkpfs_tui.format import human_bytes
from mkpfs_tui.messages import OperationFinished
from mkpfs_tui.mkpfs_runner import Inspection
from mkpfs_tui.screens.read_view import ReadView
from mkpfs_tui.widgets.path_field import PathField
from mkpfs_tui.widgets.result_panel import ResultPanel


class InspectView(ReadView):
    """Inspect a PFS image via the mkpfs library and show the summary."""

    VIEW_ID = "inspect"

    def compose(self) -> ComposeResult:
        """Render the image picker, options, run button, table, and result panel."""
        yield PathField("Image", "file", id="inspect-image")
        yield Input(placeholder="EKPFS key — 64 hex, optional", id="inspect-ekpfs")
        with Horizontal(classes="option-row"):
            yield Label("newCrypt")
            yield Switch(id="inspect-new-crypt")
        yield Button("Inspect", id="inspect-run", variant="primary")
        yield DataTable(id="inspect-table")
        yield ResultPanel(id="inspect-result")

    def on_mount(self) -> None:
        """Add the table's columns once."""
        self.query_one("#inspect-table", DataTable).add_columns("Field", "Value")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Start an inspection when the Inspect button is pressed."""
        if event.button.id != "inspect-run":
            return
        event.stop()
        path = self.query_one("#inspect-image", PathField).value
        ekpfs = self.query_one("#inspect-ekpfs", Input).value
        new_crypt = self.query_one("#inspect-new-crypt", Switch).value
        self.run_operation(lambda: mkpfs_runner.inspect_image(Path(path), ekpfs_hex=ekpfs, new_crypt=new_crypt))

    def on_operation_finished(self, event: OperationFinished) -> None:
        """Fill the table and result panel from the inspection."""
        if event.view_id != self.VIEW_ID:
            return
        result = event.result
        if not isinstance(result, Inspection):
            return
        table = self.query_one("#inspect-table", DataTable)
        table.clear()
        block_size = str(result.header.block_size) if result.header else "—"
        rows: list[tuple[str, str]] = [
            ("Image", result.image),
            ("Version", result.version_label or "—"),
            ("Size on disk", human_bytes(result.size_bytes)),
            ("Block size", block_size),
            ("Inodes", str(result.inode_count)),
            ("Directories", str(result.dir_count)),
            ("Files", str(result.file_count)),
            ("Compressed files", str(result.compressed_files)),
            ("Checked files", str(result.checked_files)),
            ("Data CRC32", f"0x{result.data_crc32:08X}"),
            ("Manifest SHA256", result.manifest_sha256 or "—"),
            ("Logical bytes", human_bytes(result.logical_file_bytes)),
            ("Stored bytes", human_bytes(result.stored_file_bytes)),
        ]
        for field_name, field_value in rows:
            table.add_row(field_name, field_value)
        self.query_one("#inspect-result", ResultPanel).show(result.errors, result.warnings)
