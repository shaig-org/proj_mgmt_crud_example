---
name: validate-backend
description: Run the full backend validation suite before declaring a task done. Zero tolerance for errors or warnings. Slower than run-targeted-tests-backend — use only when all planned capabilities are implemented.
---

# Validate backend

Run the all-in-one script:

```bash
cd backend && ./devtools/run_all_agent_validations.sh
```

## Acceptance bar
- **ZERO** test failures.
- **ZERO** linting errors (ruff).
- **ZERO** type errors (mypy / pyright).
- **ZERO** warnings.
- **ZERO** skipped tests (except documented flaky infrastructure).

## If it fails

Work the failures in this order:
1. **Type errors first** — a type error often hides the real problem and masks test failures.
2. **Lint errors** — usually mechanical; don't `# noqa` your way out unless documented.
3. **Test failures** — for each:
   - Read the spec. Is the asserted behavior what the spec requires?
   - Code wrong → fix code.
   - Test wrong (misreads spec) → verify against spec, then fix test.
   - **NEVER** change a test just to make it green.

## Individual validation commands (if you need to isolate)
```bash
cd backend && uv run ruff check .                      # lint
cd backend && uv run ruff format --check .             # format
cd backend && ./devtools/run_type_check.sh             # types
cd backend && uv run pytest                            # all tests
cd backend && uv run pytest tests/property_based/      # PBT only (can be slow)
```

## Only two acceptable outcomes
1. All validations pass.
2. You've tried to fix and cannot — report the blocker to the orchestrator explicitly, naming the failure and what you tried.

Do not mark a task ✅ with any red.
