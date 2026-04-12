#!/usr/bin/env zsh
# set -x

echo "== 🔍 Running Ruff linter...==========" && uv run ruff check . && echo "== ✨ Checking code formatting ============" && uv run ruff format --diff . && echo "== 🧪 Running tests ============" && uv run pytest && echo "==🔧 Running type checker ============" && uv run ty check
