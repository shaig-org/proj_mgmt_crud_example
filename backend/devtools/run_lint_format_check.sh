#!/usr/bin/env zsh

uv run ruff check . && uv run ruff format --diff .
