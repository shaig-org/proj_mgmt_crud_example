# Frontend — short guide

This file is the index. Detailed rules are in `docs/architecture/principles.md` and the `frontend-engineer` agent's instructions.

## Stack
React 19 + TypeScript (strict) · Vite · Axios · Playwright · ESLint

## Structure
- `src/App.tsx`, `src/main.tsx` — entry.
- `src/services/api.ts` — centralized, typed API client. ALL HTTP goes through here.
- `src/components/`, `src/pages/`, etc.
- `e2e/*.spec.ts` — Playwright E2E tests.
- `playwright.config.ts`, `vite.config.ts`.

## Running tests
- Fast feedback: invoke the `run-targeted-tests-frontend` skill.
- Full validation: invoke the `validate-frontend` skill.

## Non-negotiables (summary)
- Strict TS. No `any`, no `@ts-ignore`.
- E2E is UI-only inside test bodies — API calls allowed ONLY in `beforeAll`/`beforeEach` for fixtures.
- NEVER `waitForTimeout`. Wait on concrete conditions (`toBeVisible`, `toHaveValue`, `not.toBeDisabled`).
- Headless only in automation. `--headed`/`--ui` is for humans, never scripts.
- Parallel-safe (4 workers). Each test creates its own data.
- Tests have descriptive names.

## Scenario tests (evidence visualization)
Scenario tests live in `e2e/scenarios/` and use the `scenarioTest` fixture from `e2e/helpers/scenario.ts`. They run under the `scenarios` Playwright project (video + trace always on) and produce per-scenario evidence under the gitignored `evidence/` tree. Do not put regular specs under `e2e/scenarios/`. To generate the static viewer locally run `npm run e2e:scenarios && npm run evidence:generate && npm run evidence:serve` (requires `ffmpeg` on PATH; dev-only, not part of CI).

## Backend integration
Dev backend runs at `http://localhost:8000`. Playwright starts the backend automatically during `npm run e2e`.

For anything else: `docs/architecture/principles.md` and the `frontend-engineer` agent.
