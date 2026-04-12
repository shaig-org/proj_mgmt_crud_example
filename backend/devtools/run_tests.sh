#!/usr/bin/env zsh
set -x

# -rP - display extra information on all non-passing tests. See:
#   https://docs.pytest.org/en/6.2.x/reference.html#command-line-flags

uv run pytest -rP
