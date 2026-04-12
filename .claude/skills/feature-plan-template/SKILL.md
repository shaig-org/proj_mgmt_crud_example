---
name: feature-plan-template
description: The canonical feature plan template used by feature-planner. Also useful to the orchestrator or engineers when reading an existing plan to understand what each section means.
---

# Feature Plan Template

Write the plan to `docs/tasks/<feature>/plan.md`. Every section must be filled; an empty section means the plan is not yet complete.

```markdown
# Feature Plan: <Feature Name>

**Status**: 🟡 Draft | ✅ Approved | 🔄 Implementing | ✅ Done
**Date**: YYYY-MM-DD
**Stack**: Backend | Frontend | Full-stack
**Detailed spec**: docs/spec/detailed/<feature>_detailed_spec.md

## 1. Requirements in scope
- REQ-XXX-001: <title>
- REQ-XXX-002: <title>
(Link each to its spec section.)

## 2. Out of scope
Explicit list of things this plan does NOT address (future REQs, deferred decisions).

## 3. Architecture

### Backend changes
- **Domain** (`domain_models.py`): new models / field changes — list each with types.
- **ORM** (`dal/sqlite/orm_data_models.py`): new tables / columns / constraints.
- **Converters** (`dal/sqlite/converters.py`): ORM ↔ domain functions to add.
- **Repository** (`dal/sqlite/repository.py`): methods to add/modify — list signatures.
- **API** (`routers/<feature>_api.py`): endpoints with method, path, request body type, response type, status codes.
- **Dependencies** (`dependencies.py`): new DI wiring.
- **Schema/migration** notes.

### Frontend changes (if applicable)
- **Components**: new or modified components, their props.
- **Services** (`src/services/api.ts`): API client methods to add.
- **Routes / navigation**.
- **State management** changes.

### FE/BE contract (cross-stack only)
For each endpoint, specify exact shapes:
- `POST /api/<resource>` — request body `{...}`, success `201 {...}`, errors `422 {detail: ...}`, `403 {detail: ...}`.

## 4. Test matrix

### 4.1 API tests — `tests/api/test_<feature>_api.py`
| Test name | Verifies | Preconditions |
|---|---|---|
| test_create_<entity>_then_get_returns_it | Created entity is retrievable via GET | admin token, org |
| test_create_<entity>_without_required_field_returns_422 | Validation error on missing field | admin token |
| ... | ... | ... |

### 4.2 Repository tests — `tests/dal/test_<feature>_repository.py`
ONE TEST PER REPOSITORY METHOD (100% method coverage):
| Method | Test name | Verifies |
|---|---|---|
| create | test_create_<entity>_returns_domain_model | returns domain type, id populated |
| get_by_id | test_get_by_id_returns_created_<entity> | roundtrip |
| get_by_id | test_get_by_id_non_existent_returns_none | None path |
| ... | ... | ... |

### 4.3 Domain / validation tests (if applicable) — `tests/domain/`
| Test name | Verifies |
|---|---|
| test_<entity>_data_rejects_empty_name | Pydantic validation |

### 4.4 Utility / converter tests (if applicable)

### 4.5 Property-based tests (if applicable) — `tests/property_based/`
Consult the `write-pbt` skill. List invariants:
- **Invariant**: "for any valid <entity> input, create-then-get returns the same data"
- **Strategy**: hypothesis strategies to generate inputs (name, email, etc.).
- **Scope**: stateless (single op) or stateful (state machine).

### 4.6 Frontend E2E tests (if applicable) — `frontend/e2e/<feature>.spec.ts`
| Test name | Verifies | UI steps |
|---|---|---|
| creates_<entity>_via_form_and_shows_in_list | Full user flow | fill form → submit → see in list |
| shows_error_on_validation_failure | Error UX | submit empty → see error message |

## 5. Test fixtures and helpers
- Existing helpers used: `create_admin_user`, `create_test_org_via_repo`, ...
- New helpers needed (define in `tests/helpers.py` or `tests/dal/helpers.py`):
  - `create_<entity>_via_api(client, token, org_id, ...) -> tuple[str, dict]`
- Fixture types (explicit): `test_repo: Repository`, `client: TestClient`, `<feature>_token: tuple[str, str]`.

## 6. Edge cases covered
- Boundary: min/max lengths, empty optional fields
- Unicode, special characters
- Concurrent operations
- Cross-org isolation (other org cannot see this entity)
- Permission boundaries (each role's expected outcome)
- Not-found, already-exists, deleted-then-accessed

## 7. Implementation order
1. Domain models (+ domain tests)
2. ORM + converters (+ converter tests)
3. Repository methods (+ repository tests) — MUST pass before API work
4. API endpoints (+ API tests)
5. PBT (if planned)
6. FE API client (+ unit tests if any)
7. FE components
8. FE E2E tests
9. Full validation suite (BE + FE) green

## 8. Risks / open questions
- Anything that could force plan revision during implementation.

## 9. Sign-off
- [ ] User approved plan — date/note
- [ ] Backend implementation complete (all BE tests green)
- [ ] Frontend implementation complete (E2E green)
- [ ] code-reviewer sign-off
```

## Quality bar for the plan itself
- Every test row names a specific behavior — no "test X works."
- Every architecture change names the file it touches.
- Every edge case is present or explicitly excluded with reason.
- The test matrix is complete BEFORE implementation begins. Adding tests later is acceptable only if the plan is updated first.
