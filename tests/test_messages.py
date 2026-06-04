"""Tests for worker→view messages."""

from __future__ import annotations

from mkpfs_tui.messages import OperationFinished


def test_operation_finished_carries_view_id_and_result() -> None:
    payload = {"ok": True}
    msg = OperationFinished("inspect", payload)
    assert msg.view_id == "inspect"
    assert msg.result is payload


def test_pack_messages_carry_payloads() -> None:
    from mkpfs_tui.messages import PackCompleted, PackProgressed, PackStatusLine

    prog = object()
    result = object()
    assert PackProgressed("pack", prog).progress is prog
    assert PackProgressed("pack", prog).view_id == "pack"
    assert PackStatusLine("pack", "hi").text == "hi"
    assert PackCompleted("pack", result).result is result


def test_unpack_messages_carry_payloads() -> None:
    from mkpfs_tui.messages import UnpackCompleted, UnpackProgressed

    msg = UnpackProgressed("unpack", "extract", 3, 10)
    assert msg.view_id == "unpack"
    assert msg.phase == "extract"
    assert msg.done == 3
    assert msg.total == 10
    result = object()
    assert UnpackCompleted("unpack", result).result is result
