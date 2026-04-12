# CLAUDE.md

Orchestrator guidance. Keep short — detailed rules live in `docs/architecture/principles.md` and in agent/skill files.

## Project layout
- `backend/` — Python 3 / FastAPI. Run Python commands from here.
- `frontend/` — React 19 + TypeScript + Vite + Playwright. Run npm commands from here.
- `docs/spec/` — Product specs. `main_spec.md` is an index; detailed specs in `detailed/`.
- `docs/tech_spec/` — Technical architecture.
- `docs/architecture/principles.md` — **Non-negotiable rules. Read this.**
- `docs/tasks/<feature>/plan.md` — Feature plans produced before implementation.

## Routing — which agent does what

| Situation | Agent |
|---|---|
| Any multi-file feature work (new entity, cross-stack change, non-trivial addition) | **feature-planner** FIRST → then engineer(s) |
| Spec edits (`docs/spec/**`) | **spec-author** |
| Backend-only implementation of an approved plan | **backend-engineer** |
| Frontend-only implementation of an approved plan | **frontend-engineer** |
| Reviewing completed work before declaring done | **code-reviewer** |
| Open-ended codebase exploration (cross-stack understanding) | **Explore** (built-in) |

**Default behavior**: for any feature request, call `feature-planner` first. The planner produces the plan and test matrix. Then dispatch engineers against the plan. Finally run `code-reviewer`.

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

## Validations
Any completed backend work must pass `cd backend && ./devtools/run_all_agent_validations.sh`. Any completed frontend work must pass `npm run lint && npm run typecheck && npm run e2e`. Zero errors, zero warnings. See principles.md for the full contract.
