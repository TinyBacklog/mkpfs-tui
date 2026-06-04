"""Tests for the mkpfs anti-corruption boundary (mapping + ekpfs handling).

These use fakes that duck-type PFSImageInspection so the test never imports mkpfs.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from mkpfs_tui import mkpfs_runner


def _fake_raw(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "image": Path("game.pfs"),
        "errors": [],
        "warnings": [],
        "size_bytes": 2048,
        "version_label": "PS5",
        "header": SimpleNamespace(
            block_size=65536,
            nblock=10,
            dinode_count=3,
            ndblock=8,
            dinode_block_count=1,
            readonly=1,
        ),
        "inodes": [1, 2, 3],
        "dir_inodes": {"d": 2},
        "file_inodes": {"a": 4, "b": 5},
        "compressed_files": 1,
        "checked_files": 2,
        "data_crc32": 0xDEADBEEF,
        "manifest_sha256": "abc123",
        "logical_file_bytes": 4096,
        "stored_file_bytes": 2048,
        "uroot_inode": 2,
        "dirents_by_inode": {},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_inspect_image_maps_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mkpfs_runner, "inspect_pfs_image", lambda **kwargs: _fake_raw())
    result = mkpfs_runner.inspect_image(Path("game.pfs"))
    assert result.ok is True
    assert result.version_label == "PS5"
    assert result.size_bytes == 2048
    assert result.inode_count == 3
    assert result.dir_count == 1
    assert result.file_count == 2
    assert result.compressed_files == 1
    assert result.data_crc32 == 0xDEADBEEF
    assert result.manifest_sha256 == "abc123"
    assert result.header is not None
    assert result.header.block_size == 65536
    assert result.errors == ()
    assert result.warnings == ()


def test_inspect_structure_only_gates_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    # A fake inspect that *calls* verify_file_payload_hashes (as the real one does)
    # and records the tuple it got back, so we can prove it was skipped during the call.
    recorded: dict[str, object] = {}

    def fake_inspect(**kwargs: object) -> SimpleNamespace:
        recorded["hashes"] = mkpfs_runner._mkpfs_pfs.verify_file_payload_hashes(None, None, None, None, [])
        return _fake_raw()

    monkeypatch.setattr(mkpfs_runner, "inspect_pfs_image", fake_inspect)
    mkpfs_runner._inspect_structure_only(Path("game.pfs"), None, False)
    # During the call, hashing was skipped to the (0, 0, "") no-op...
    assert recorded["hashes"] == (0, 0, "")
    # ...and the thread-local flag is cleared afterwards, so other threads/ops still hash.
    assert getattr(mkpfs_runner._skip_payload_hashing, "active", False) is False


def test_inspect_image_marks_hashes_not_computed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mkpfs_runner, "inspect_pfs_image", lambda **kwargs: _fake_raw())
    result = mkpfs_runner.inspect_image(Path("game.pfs"))
    assert result.hashes_computed is False


def test_inspect_image_handles_memoryerror(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(**kwargs: object) -> SimpleNamespace:
        raise MemoryError("cannot allocate 29 GiB")

    monkeypatch.setattr(mkpfs_runner, "inspect_pfs_image", boom)
    result = mkpfs_runner.inspect_image(Path("game.pfs"))
    assert result.ok is False
    assert "Out of memory" in result.errors[0]


def test_inspect_image_reports_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mkpfs_runner,
        "inspect_pfs_image",
        lambda **kwargs: _fake_raw(errors=["bad header"], warnings=["odd readonly"]),
    )
    result = mkpfs_runner.inspect_image(Path("game.pfs"))
    assert result.ok is False
    assert result.errors == ("bad header",)
    assert result.warnings == ("odd readonly",)


def test_blank_ekpfs_passes_none(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _capture(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return _fake_raw()

    monkeypatch.setattr(mkpfs_runner, "inspect_pfs_image", _capture)
    mkpfs_runner.inspect_image(Path("game.pfs"), ekpfs_hex="   ")
    assert captured["ekpfs"] is None


def test_bad_ekpfs_hex_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    # Uses the REAL parse_ekpfs_key_hex, which raises BuildError on non-64-hex.
    # inspect_pfs_image is patched to a sentinel that must never be reached.
    monkeypatch.setattr(
        mkpfs_runner,
        "inspect_pfs_image",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not be called")),
    )
    result = mkpfs_runner.inspect_image(Path("game.pfs"), ekpfs_hex="not-hex")
    assert result.ok is False
    assert "64" in result.errors[0]


def test_header_none_maps_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mkpfs_runner, "inspect_pfs_image", lambda **kwargs: _fake_raw(header=None))
    result = mkpfs_runner.inspect_image(Path("game.pfs"))
    assert result.header is None
    assert result.ok is True


def test_new_crypt_is_forwarded(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _capture(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return _fake_raw()

    monkeypatch.setattr(mkpfs_runner, "inspect_pfs_image", _capture)
    mkpfs_runner.inspect_image(Path("game.pfs"), new_crypt=True)
    assert captured["new_crypt"] is True


def test_verify_image_passes_through_and_maps(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _capture(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return _fake_raw()

    monkeypatch.setattr(mkpfs_runner, "verify_pfs_image", _capture)
    result = mkpfs_runner.verify_image(
        Path("game.pfs"),
        source="/src",
        expected_crc32="0x10",
        expected_manifest_sha256="dead",
    )
    assert result.ok is True
    assert captured["expected_crc32"] == 16
    assert str(captured["source"]) == "/src"
    assert captured["expected_manifest_sha256"] == "dead"


def test_verify_image_blank_optionals_become_none(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _capture(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return _fake_raw()

    monkeypatch.setattr(mkpfs_runner, "verify_pfs_image", _capture)
    mkpfs_runner.verify_image(Path("game.pfs"))
    assert captured["source"] is None
    assert captured["expected_crc32"] is None
    assert captured["expected_manifest_sha256"] is None


def test_verify_image_bad_crc_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mkpfs_runner,
        "verify_pfs_image",
        lambda **k: (_ for _ in ()).throw(AssertionError("should not be called")),
    )
    result = mkpfs_runner.verify_image(Path("game.pfs"), expected_crc32="not-a-number")
    assert result.ok is False
    assert result.errors


def _dirent(inode: int, type_code: int, name: str) -> SimpleNamespace:
    return SimpleNamespace(inode_number=inode, type_code=type_code, name=name)


def test_read_tree_builds_sorted_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    dirents = {
        2: [_dirent(5, 2, "eboot.bin"), _dirent(3, 3, "sys"), _dirent(2, 4, "."), _dirent(2, 5, "..")],
        3: [_dirent(4, 2, "config"), _dirent(3, 4, "."), _dirent(2, 5, "..")],
    }
    raw = _fake_raw(uroot_inode=2, dirents_by_inode=dirents)
    monkeypatch.setattr(mkpfs_runner, "inspect_pfs_image", lambda **k: raw)
    result = mkpfs_runner.read_tree(Path("game.pfs"))
    assert result.ok is True
    assert result.root is not None
    names = [c.name for c in result.root.children]
    assert names == ["sys", "eboot.bin"]  # dir first, then file
    sys_node = result.root.children[0]
    assert sys_node.is_dir is True
    assert [c.name for c in sys_node.children] == ["config"]
    assert sys_node.children[0].is_dir is False


def test_read_tree_no_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mkpfs_runner, "inspect_pfs_image", lambda **k: _fake_raw(uroot_inode=-1))
    result = mkpfs_runner.read_tree(Path("game.pfs"))
    assert result.root is None
    assert result.ok is False
    assert result.errors


def test_read_tree_guards_cycles(monkeypatch: pytest.MonkeyPatch) -> None:
    dirents = {2: [_dirent(3, 3, "a")], 3: [_dirent(2, 3, "b")]}
    raw = _fake_raw(uroot_inode=2, dirents_by_inode=dirents)
    monkeypatch.setattr(mkpfs_runner, "inspect_pfs_image", lambda **k: raw)
    result = mkpfs_runner.read_tree(Path("game.pfs"))  # must return, not hang
    assert result.root is not None


def test_read_tree_catches_deep_recursion(monkeypatch: pytest.MonkeyPatch) -> None:
    # A long acyclic chain of nested dirs exceeds Python's recursion limit;
    # read_tree must catch RecursionError and return a failed result, not raise.
    depth = 3000
    dirents = {i: [_dirent(i + 1, 3, f"d{i}")] for i in range(2, depth + 2)}
    raw = _fake_raw(uroot_inode=2, dirents_by_inode=dirents)
    monkeypatch.setattr(mkpfs_runner, "inspect_pfs_image", lambda **k: raw)
    result = mkpfs_runner.read_tree(Path("game.pfs"))
    assert result.root is None
    assert result.ok is False
    assert result.errors


def test_unpack_image_maps_result_and_drives_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    steps: list[tuple[str, int, int]] = []

    def fake_extract(  # type: ignore[return]
        *, image: object, output_path: object, progress: object, ekpfs: object, new_crypt: object
    ) -> SimpleNamespace:
        # the adapter is a real mkpfs.pbar.Progress subclass; drive it like mkpfs would
        progress.step("extract", 1, 2, 0)  # type: ignore[union-attr]
        progress.status("finalizing")  # type: ignore[union-attr]
        progress.step("extract", 2, 2, 0)  # type: ignore[union-attr]
        return SimpleNamespace(
            image=image,
            output_path=output_path,
            errors=[],
            warnings=[],
            files_written=3,
            directories_created=1,
            bytes_written=4096,
        )

    monkeypatch.setattr(mkpfs_runner, "extract_pfs_image", fake_extract)
    result = mkpfs_runner.unpack_image(
        Path("game.pfs"),
        Path("/out"),
        on_step=lambda phase, done, total, b: steps.append((phase, done, total)),
    )
    assert result.ok is True
    assert result.files_written == 3
    assert result.directories_created == 1
    assert result.bytes_written == 4096
    assert steps == [("extract", 1, 2), ("finalizing", 0, 0), ("extract", 2, 2)]


def test_inspect_image_rejects_non_pfs_file(tmp_path: Path) -> None:
    junk = tmp_path / "raw.exfat"
    junk.write_bytes(b"\xeb\x76\x90EXFAT   " + b"\x00" * 1024)  # exfat-ish, not PFS
    result = mkpfs_runner.inspect_image(junk)
    assert result.ok is False
    assert "Not a PFS image" in result.errors[0]


def test_unpack_image_rejects_non_pfs_file(tmp_path: Path) -> None:
    junk = tmp_path / "raw.exfat"
    junk.write_bytes(b"\xeb\x76\x90EXFAT   " + b"\x00" * 1024)
    result = mkpfs_runner.unpack_image(junk, tmp_path / "out")
    assert result.ok is False
    assert "Not a PFS image" in result.errors[0]


def test_read_tree_rejects_non_pfs_file(tmp_path: Path) -> None:
    junk = tmp_path / "raw.exfat"
    junk.write_bytes(b"\xeb\x76\x90EXFAT   " + b"\x00" * 1024)
    result = mkpfs_runner.read_tree(junk)
    assert result.ok is False and result.root is None
    assert "Not a PFS image" in result.errors[0]


def test_unpack_image_reports_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_extract(
        *, image: object, output_path: object, progress: object, ekpfs: object, new_crypt: object
    ) -> SimpleNamespace:
        return SimpleNamespace(
            image=image,
            output_path=output_path,
            errors=["boom"],
            warnings=[],
            files_written=0,
            directories_created=0,
            bytes_written=0,
        )

    monkeypatch.setattr(mkpfs_runner, "extract_pfs_image", fake_extract)
    result = mkpfs_runner.unpack_image(Path("game.pfs"), Path("/out"))
    assert result.ok is False
    assert result.errors == ("boom",)
