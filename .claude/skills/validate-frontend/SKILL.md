---
name: validate-frontend
description: Full frontend validation suite. Run before declaring a task done. Zero tolerance.
---

# Validate frontend

From `frontend/`:

```bash
cd frontend && npm run lint && npm run typecheck && npm test && npm run e2e
```

## Acceptance bar
- `npm run lint` — ZERO errors, ZERO warnings.
- `npm run typecheck` — ZERO TS errors.
- `npm test` — 100% pass (Vitest unit tests).
- `npm run e2e` — 100% pass, ZERO failures, ZERO skips (except documented infra flakes).

## Rules
- Headless only. `npm run e2e` uses `--reporter=list`. Never invoke `e2e:headed` or `e2e:ui` in automation.
- If E2E flakes: inspect trace (`npx playwright show-trace ...`). Don't paper over with `waitForTimeout` — wait on concrete conditions.
- If a test reveals a real bug in the backend contract, hand back to `backend-engineer` with a minimal repro.

## If it fails
1. Type errors → fix types.
2. Lint errors → fix (avoid `eslint-disable` unless documented).
3. E2E failures → inspect trace, fix root cause (UI bug, race, contract mismatch). Never change a test to make it green.

## Only two acceptable outcomes
1. All green.
2. Explicit blockage reported to orchestrator.
