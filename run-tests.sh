#!/usr/bin/env bash
set -euo pipefail

uv sync
uv run ruff format .
uv run ruff check . --fix
uv run --frozen pytest
