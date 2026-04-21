---
name: run-targeted-tests-frontend
description: Fast frontend test feedback loop for Playwright E2E. Pick the smallest test subset during development. Do NOT use as final validation — run validate-frontend for that.
---

# Running targeted frontend tests

Work from `frontend/`. Headless only.

## Decision tree

**One spec** → run that spec:
```bash
cd frontend && npx playwright test e2e/projects.spec.ts --reporter=line
```

**One test by name** → grep on title:
```bash
cd frontend && npx playwright test --grep "creates project via form" --reporter=line
```

**One browser** (faster than all three):
```bash
cd frontend && npx playwright test e2e/projects.spec.ts --project=chromium --reporter=line
```

**Quick iteration on a test you just wrote** → same file, chromium only, one worker:
```bash
cd frontend && npx playwright test e2e/projects.spec.ts --project=chromium --workers=1 --reporter=line
```

**Type-check only** (no browser run) — fast:
```bash
cd frontend && npm run typecheck
```

**Lint only** — fast:
```bash
cd frontend && npm run lint
```

## Rules
- Always `--reporter=line`. Never let the HTML reporter serve — it blocks.
- NEVER `--headed` or `--ui` in scripted runs. Those are for humans debugging.
- Keep tests parallel-safe; running with `--workers=1` is for iteration only, not a fix for flakiness.

## Debugging a flaky/failing test (still headless)
```bash
cd frontend && npx playwright test e2e/projects.spec.ts --project=chromium --workers=1 --reporter=line --trace=on
```
Then inspect traces: `npx playwright show-trace test-results/<path>/trace.zip`.

## When to escalate
- Targeted spec green → `validate-frontend` (lint + typecheck + full E2E).
- Multiple specs touch the same component and one fails → run all `e2e/*.spec.ts` for that feature.

## Do not
- Don't use `waitForTimeout` to make a test pass. Wait on a concrete condition.
- Don't `test.skip` around a failure. Fix it or escalate.
- Don't run `npm run e2e:headed` in scripts.
