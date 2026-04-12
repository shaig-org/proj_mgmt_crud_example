---
name: run-targeted-tests-backend
description: Fast backend test feedback loop. Pick the smallest test subset that proves a specific capability during development. Use this during the write-test → implement → iterate cycle. Do NOT use this as the final validation — run validate-backend for that.
---

# Running targeted backend tests

Work from `backend/`. All pytest commands go through `uv run pytest` (or whatever the project's runner is — check `pyproject.toml` / `devtools/run_tests.sh` to confirm).

## Decision tree

**Just wrote/changed ONE test** → run that one test:
```bash
cd backend && uv run pytest tests/api/test_projects_api.py::TestProjectsAPI::test_create_project_then_get_returns_it -x
```

**Iterating on ONE file (test or feature)** → run that one file:
```bash
cd backend && uv run pytest tests/api/test_projects_api.py -x
```

**Touching a cross-cutting concern (e.g., "permission tests across all entities")** → use `-k` pattern:
```bash
cd backend && uv run pytest -k "permission and write" -x
```

**A test just failed and you've applied a fix** → rerun only the failures:
```bash
cd backend && uv run pytest --lf -x
```

**Working on a repository** → run the full repository test file:
```bash
cd backend && uv run pytest tests/dal/test_projects_repository.py -x
```

**Working on PBT** → run one strategy/state machine with a seed for determinism:
```bash
cd backend && uv run pytest tests/property_based/stateful/test_user_api.py -x
```

## Useful flags
- `-x` — stop at first failure (always use during iteration).
- `-vv` — verbose assertion diffs when a test fails mysteriously.
- `-k "pattern"` — substring match on test names. Quote it.
- `--lf` — last-failed only.
- `--ff` — failed-first then the rest.
- `-s` — don't capture stdout (useful when you added `print` to debug).
- `--db-mode=memory` — switch to in-memory SQLite when iterating fast (disk is default and catches more real bugs).
- `-n auto` — parallel runners via pytest-xdist (only if installed; don't use with PBT state machines).

## When to escalate
- All targeted tests green for the capability → run `validate-backend` to confirm nothing else regressed.
- A targeted test passes but you suspect cross-feature breakage → run the full layer: `uv run pytest tests/api/` or `uv run pytest tests/dal/`.
- Lint / type errors appear during the cycle → run them locally:
  - `cd backend && uv run ruff check .` (quick)
  - `cd backend && ./devtools/run_type_check.sh`

## Do not
- Don't run the full `run_all_agent_validations.sh` every iteration — it's slow. Use it at the end of the capability.
- Don't skip the targeted run in favor of "I'll just run everything at the end." You'll waste cycles catching errors late.
- Don't silence warnings with `-W ignore`. Zero tolerance.
