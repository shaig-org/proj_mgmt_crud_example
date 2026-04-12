#!/usr/bin/env zsh
set -x

uv run ruff check . && uv run ruff format --diff .
