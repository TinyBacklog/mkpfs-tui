# mkpfs-tui — conventions

- **Tooling:** `uv` only. `uv sync`, `uv run ...`, `./run-tests.sh`. Never call `pip` or a global python.
- **Style:** type hints everywhere; Google-style docstrings; prefer `X | None` over `Optional`; ruff is law
  (config mirrors mkpfs). `from __future__ import annotations` at the top of every module.
- **mkpfs is a pinned, read-only dependency.** ALL imports of / calls to `mkpfs.*` live in
  `mkpfs_tui/mkpfs_runner.py` (added in M2). No other module imports mkpfs. Never edit the mkpfs package.
- **Tests:** Textual `App.run_test()` Pilot harness, `pytest-asyncio` auto mode (async tests, no decorator).
- **Updating mkpfs:** `uv lock --upgrade-package mkpfs`, run tests (incl. the contract test), commit.
