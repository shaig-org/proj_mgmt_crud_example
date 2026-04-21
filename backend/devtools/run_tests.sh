#!/usr/bin/env zsh

# Full test suite, parallel. See pytest.ini for why xdist isn't the pytest default.
# -rP — extra info on non-passing tests. See pytest docs.
# -n auto --dist loadfile — xdist parallelism, grouped by file (safe for PBT state machines).

uv run pytest -rP -n auto --dist loadfile "$@"
