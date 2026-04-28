# Architectural Principles

These rules govern every feature, every plan, every implementation, every review.
Short, non-negotiable. If a change seems to require violating one, surface it and ask.

## Product behavior is primary
- Requirements describe what users/external systems observe.
- Tests verify externally observable behavior through the public API.
- Implementation details (table names, ORM models, internal variables) are NOT specified and NOT tested directly.
- The "So what?" test: if a user cannot observe it, do not specify it.

## Complete capabilities only
- No partial implementations. A task covers ALL its requirements or none.
- No layer-by-layer refactors that ship half a feature. One capability = one cohesive change.
- No speculative abstractions, hooks, flags, or "future-proofing." Build what this feature needs.

## Small, individually testable parts
- Decompose features into parts that each tell a complete story (e.g., "serialize then deserialize returns input").
- Each part has its own tests at the appropriate layer.

## Layered architecture (backend)
```
API (FastAPI routers) → Domain (Pydantic models + commands) → Repository (DAL) → Converters → ORM → SQLite
```
- API layer uses domain models only; never ORM.
- Repository returns domain models only; never ORM leaks to callers.
- Converters are explicit; no implicit `model_validate` between ORM and domain.
- Commands (`XxxCreateCommand`, `XxxUpdateCommand`) encapsulate create/update intent.

## Test layer contract (backend — every feature)
- **API tests** (`tests/api/test_*_api.py`): external behavior, happy paths, errors, complete workflows. REQUIRED.
- **Repository tests** (`tests/dal/test_*_repository.py`): every repository method has a dedicated test. REQUIRED (100% method coverage).
- **Domain/validation tests** (`tests/domain/`): Pydantic rules, command validation. IF APPLICABLE.
- **Utility tests** (`tests/utils/`): converters, helpers. IF APPLICABLE.
- **Property-based tests** (`tests/property_based/`): invariants that hold across inputs. IF APPLICABLE — see `write-pbt` skill.

## Test quality rules
- No mocks. In-memory SQLite simulator is fine.
- Tests are isolated; run in any order, in parallel.
- One fact per test. Descriptive names: `test_after_create_project_get_returns_the_project`.
- Tests never query the database directly or touch ORM in asserts.
- Explicit fixture imports (`from tests.conftest import client  # noqa: F401`).
- Use role-specific helpers (`create_admin_user`, etc.) and repository helpers (`create_test_org_via_repo`) — never inline setup when a helper exists.

## Frontend layer contract
- **E2E tests** (`frontend/e2e/*.spec.ts`): Playwright, UI-only interactions (no direct API calls inside test bodies; API setup only in `beforeAll`/`beforeEach`).
- No `waitForTimeout`. Always wait on concrete conditions (`toBeVisible`, `toHaveValue`).
- Headless only in automation (`npm run e2e`); headed is for humans.
- Parallel-safe (4 workers), each test creates its own data.

## Zero-tolerance validation
- Backend: `cd backend && ./devtools/run_all_agent_validations.sh` — zero errors, zero warnings.
- Frontend: `npm run lint && npm run typecheck && npm test && npm run e2e` — zero errors, zero warnings, zero skips.
- Failing validation is never acceptable at task completion. Two acceptable outcomes: all pass, or you've tried and explicitly reported blockage.
- When tests fail: check spec first. Code wrong → fix code. Test wrong → verify against spec, then fix test. NEVER change tests just to make them green.

## Spec discipline
- Every requirement has a unique ID `REQ-{FEATURE}-{NUM}`.
- Status is inline (🔴 / ✅ / ⚠️). No separate tracking files.
- Main spec is an index; detailed specs live in `docs/spec/detailed/`.
- Requirements describe behavior + acceptance criteria + edge cases. They do NOT contain implementation plans or test code — those belong in the feature plan.

## Scenario coverage for user-facing features
- Every major user-facing feature must have at least one **scenario test** covering the primary happy path (`frontend/e2e/scenarios/*.scenario.spec.ts`, using the `scenarioTest` fixture).
- Scenario tests are a visual happy-path smoke and the source for the local Dev Dashboard walkthroughs. They are **not** a substitute for unit, repository, domain, API, or PBT coverage of business logic — those still own correctness.
- Backend-only features and pure refactors are exempt. See `docs/testing/scenario_walkthroughs.md` for authoring rules and the dashboard workflow.

## Plan-before-implement
- No implementation starts without an approved feature plan in `docs/tasks/<feature>/plan.md`.
- The plan enumerates every test (by name, by layer, by what it verifies) BEFORE code is written.
- The implementer does not invent tests not in the plan. If a gap is found, return to planning.

## Capability layer (backend authorization)
- FastAPI route handlers MUST depend on a narrow capability object (e.g. `ProjectWriteCapability`) — NOT on `Repository` directly. Capabilities live in `backend/project_management_crud_example/capabilities/` and own all role/org authorization.
- On deny, capabilities raise `CapabilityPermissionError`; the handler never raises `HTTPException(403, ...)` for authorization. A single exception handler in `app.py` maps it to HTTP 403 with the standard `{"detail": ...}` envelope.
- Documented exceptions (routes that may still take `Depends(get_repository)`): `POST /auth/login` (no authenticated user at login time), `/health`, `/e2e/**` (test harness). Adding to this list requires a plan update with rationale.
- Every capability-bearing change should be accompanied by a run of the capability analyzer. See `backend/evidence/capabilities/README.md` for the workflow. The analyzer's `baseline.json` is the committed source of truth; the generated `report.json` and `index.html` are gitignored.
- A capability-set *expansion* on any route is a review signal, not a bug. It must be explained in the PR and the updated `baseline.json` committed alongside the code change so reviewers see the diff.
- Where a route operates on a single resource, prefer a **bound capability** whose constructor resolves authorization and existence. The DI factory binds the capability to the URL's path parameter (e.g. `BoundProjectWriteCapability` for `/api/projects/{project_id}` write routes); the handler receives a capability whose verbs cannot be redirected to a different resource. Missing-resource cases raise `CapabilityNotFoundError` (mapped to 404) instead of the route doing its own existence check.
- Capability classes do NOT expose getter properties for their repository or current-user dependencies; those are private. If external code needs them, the capability is missing a verb — add the verb (which performs the side-effect using `_repo` internally). Public attributes are fine when intentionally public (e.g. a bound capability's `current` snapshot). The whole point of the capability layer is to deny external code free access to the underlying repo; getters undo that guarantee.

## Commits
- Commit freely — work happens on branches/worktrees.
- Commit at natural checkpoints (planning done, tests written, implementation complete, validations passing).
- No commit-approval gate.
