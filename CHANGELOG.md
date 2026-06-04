# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [0.1.0] — unreleased

First public release — a [Textual](https://textual.textualize.io/) terminal UI over
[mkpfs](https://pypi.org/project/mkpfs/) exposing all five PlayStation PFS operations from one app.

### Added

- Sidebar-driven app shell: header (with clock), a `ContentSwitcher` of five views, and a footer; the
  built-in `tokyo-night` theme and the `Ctrl+P` command palette (theme switching). `Ctrl+Q` quits.
- **Inspect** — show an image's header, inode/dir/file counts, sizes, and checksums in a table.
- **Verify** — PASS/FAIL banner, with optional source-tree / expected-CRC32 / expected-manifest checks.
- **Tree** — browse the file tree stored inside an image (cycle-guarded).
- **Unpack** — extract an image to a directory in-process, with a live progress bar, a files/dirs/bytes
  summary, and a TUI-owned overwrite guard for a non-empty target.
- **Pack** — build an image from a folder or file via a streaming subprocess, with a live progress bar,
  Cancel (which terminates the child process), and an overwrite confirmation.
- A file/directory **picker** modal wired to every Browse button.
- Encryption options (EKPFS key, newCrypt) on every relevant view.

### Internal

- Anti-corruption boundary: all `mkpfs` access is confined to `mkpfs_runner.py`, guarded by a contract test
  that pins the upstream symbols and dataclass fields the adapter relies on.
- Hybrid integration: inspect/verify/tree/unpack call the mkpfs library in-process; pack shells out to a
  subprocess and parses its progress (CR/LF-aware), with the binary self-dispatching as its own mkpfs runtime
  when frozen.
- Distribution: PyPI via Trusted Publishing (OIDC) plus a Linux PyInstaller `--onedir` binary, built by a
  tag-driven release workflow; CI runs lint + tests on every push/PR.

### Requirements

- Python ≥ 3.11. Pins `mkpfs >= 0.0.5, < 0.1.0` and `textual >= 0.86`.
- Licensed GPL-3.0-or-later (it imports mkpfs, which is GPLv3).

[0.1.0]: https://github.com/ClaudioVarandas/mkpfs-tui/releases/tag/v0.1.0
