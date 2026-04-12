#!/usr/bin/env zsh
set -x

uv run ruff check --fix . && uv run ruff format .
