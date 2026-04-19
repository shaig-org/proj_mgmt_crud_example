# CLAUDE.md

Orchestrator guidance. Keep short — detailed rules live in `docs/architecture/principles.md` and in agent/skill files.

## Project layout
- `backend/` — Python 3 / FastAPI. Run Python commands from here.
- `frontend/` — React 19 + TypeScript + Vite + Playwright. Run npm commands from here.
- `docs/spec/` — Product specs. `main_spec.md` is an index; detailed specs in `detailed/`.
- `docs/tech_spec/` — Technical architecture.
- `docs/architecture/principles.md` — **Non-negotiable rules. Read this.**
- `docs/tasks/<feature>/plan.md` — Feature plans produced before implementation.

## Per-worktree dev ports
Each worktree's dev-stack ports (frontend / dashboard / backend) are auto-generated
by `githooks/post-checkout` (see `devtools/setup-worktree-ports.sh`). Resolved
values live in `.claude/launch.json`, `frontend/.env.local`,
`tools/dev-dashboard/.env.local`, and `.claude/env.ports` (all gitignored).
The first `npm ci` (in `frontend/` or `tools/dev-dashboard/`) runs both
`devtools/install-git-hooks.sh` (wires `core.hooksPath=githooks`) and the
port generator via postinstall — no manual setup step needed. From then on,
`git worktree add` auto-bootstraps each new worktree. See
`docs/guides/per-worktree-ports-setup.md` to apply this pattern to other repos.

## Routing — which agent does what

| Situation | Agent |
|---|---|
| Any multi-file feature work (new entity, cross-stack change, non-trivial addition) | **feature-planner** FIRST → then engineer(s) |
| Spec edits (`docs/spec/**`) | **spec-author** |
| Backend-only implementation of an approved plan | **backend-engineer** (Sonnet default) |
| Frontend-only implementation of an approved plan | **frontend-engineer** (Sonnet default) |
| Backend implementation escalation — Sonnet run failed, or plan flags architectural difficulty, or change touches migrations/concurrency/auth/cross-org isolation | **backend-engineer-opus** |
| Frontend implementation escalation — Sonnet run failed, or non-trivial state machine / perf-sensitive rendering / accessibility-critical UI | **frontend-engineer-opus** |
| Reviewing completed work before declaring done | **code-reviewer** |
| Open-ended codebase exploration (cross-stack understanding) | **Explore** (built-in) |

**Model assignments**: `feature-planner` runs on Opus (planning rewards strong reasoning). `backend-engineer` and `frontend-engineer` run on Sonnet (fast, cheap, fine for executing an approved plan). `-opus` variants exist for escalation — same rules as their Sonnet counterparts, stronger model. `code-reviewer` and `spec-author` inherit the orchestrator's model.

**Default behavior**: for any feature request, call `feature-planner` first. The planner produces the plan and test matrix. Then dispatch the Sonnet engineer(s) against the plan. Escalate to `-opus` variants only when warranted (see routing table). Finally run `code-reviewer`.

For cross-stack features:
1. `Explore` agent gathers current state across FE + BE.
2. `feature-planner` produces a single plan with BE-contract, FE-contract, and the FE/BE interface (exact request/response shapes).
3. `backend-engineer` implements BE first (contract must exist before FE consumes it).
4. `frontend-engineer` implements FE against the real endpoints.
5. Playwright E2E runs as the integration gate.
6. `code-reviewer` reviews everything.

## Free-form work (no slash command)
If the user asks for something directly without naming an agent, apply the routing table above. Skills (`run-targeted-tests-backend`, `run-targeted-tests-frontend`, `validate-backend`, `validate-frontend`, `write-pbt`, `spec-authoring`, `feature-plan-template`) are available to you as the orchestrator too — use them when appropriate.

## Commits
Commit freely on the current branch/worktree. Natural checkpoints: plan written, tests written, implementation passing, validations green. No approval gate.

## pytest-tracer (test coverage traces)
Backend tests marked with `@pytest.mark.scenario` are indexed into `backend/.trace-index` by pytest-tracer. Query the index with the `trace` CLI to find which tests cover which code **before editing backend code**. Full CLI reference and rebuild steps live in the `trace-analyzer` skill — invoke it when working with traces. Markers (`scenario`, `behavior`, `error`) are registered in `backend/pytest.ini`.

## Validations
Any completed backend work must pass `cd backend && ./devtools/run_all_agent_validations.sh`. Any completed frontend work must pass `npm run lint && npm run typecheck && npm run e2e`. Any completed `tools/dev-dashboard/` work must pass `npm --prefix tools/dev-dashboard run typecheck && npm --prefix tools/dev-dashboard run lint && npm --prefix tools/dev-dashboard run test -- --run && npm --prefix tools/dev-dashboard run smoke`. Zero errors, zero warnings. See principles.md for the full contract.

## Git hooks
Repo-tracked hooks live in `githooks/` (currently `pre-commit` and `post-checkout`). The first `npm ci` auto-runs `./devtools/install-git-hooks.sh` via postinstall, which sets `core.hooksPath=githooks` and sweeps any stale worktree-local `core.hookspath` overrides. Re-running `install-git-hooks.sh` by hand is safe (idempotent) but not required.

- `pre-commit` runs typecheck + lint + unit tests for any module whose files are staged (currently `tools/dev-dashboard/`; extend `githooks/pre-commit` when adding more modules). Playwright/E2E suites are intentionally NOT in the hook — run them manually before declaring work done.
- `post-checkout` runs `devtools/setup-worktree-ports.sh` (see the Per-worktree dev ports section above).

## Dev dashboard (tools/dev-dashboard/)
Standalone Vite + React + TS app that consolidates the Scenarios walkthroughs, Capabilities analyzer report, and pytest-tracer artifacts behind per-aspect tabs. View-only: each panel shows a copyable refresh command, last-generated mtime, and a stale indicator. The aspect-plugin contract (`Aspect<TData>` in `src/aspects/types.ts`) is the extension point — add a new angle on the project by registering a new aspect. Real-producer schemas are locked in by `tests/unit/scenarios.realschema.test.ts`; extend that file whenever a producer's artifact shape changes.

**Refresh all dashboard artifacts (one command):** `./devtools/refresh-dashboard-artifacts.sh` (or `npm --prefix tools/dev-dashboard run dashboard:refresh`). Regenerates every input every tab depends on — capabilities report + baseline, capability git-diff, e2e-traces, walkthrough GIFs/screenshots/manifest, pytest-tracer `.trace-artifacts` (if the plugin is installed), and dashboard staleness. Each step is independent; failures don't abort the rest. See the header of the script for the full artifact → tab map and flags (`--skip-e2e`, `--diff-from REF`). **Use this instead of chasing per-panel refresh commands when the dashboard looks stale or empty.**

## Capability layer
Backend route handlers depend on narrow **Capability** objects, not on the full `Repository`. See `docs/architecture/principles.md` §Capability layer for the rule. When a change alters a route's capability set:
1. Run `cd backend && ./devtools/run_with_env.sh uv run python -m project_management_crud_example.tools.analyze_capabilities` — exit 0 means unchanged/reduced; exit 1 means expansion vs baseline.
2. If the expansion is intentional, run the same command with `--update-baseline` and commit the updated `backend/evidence/capabilities/baseline.json` as part of the change (reviewers see the diff).
3. Read `backend/evidence/capabilities/README.md` for the full workflow and how to open the static viewer.

## Testing layers
Unit / repository / domain / API / PBT tests own correctness. **Scenario tests** (`frontend/e2e/scenarios/*.scenario.spec.ts`) own the visual happy-path tour and double as the source for the local Dev Dashboard walkthroughs. Every major user-facing feature must ship with at least one scenario test. See `docs/testing/scenario_walkthroughs.md`.
