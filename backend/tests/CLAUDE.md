# Backend tests — what lives where

This file is the index. Detailed rules for writing tests are in the architectural principles and the `backend-engineer` agent's instructions. For PBT specifics, invoke the `write-pbt` skill.

## Structure
- `tests/api/` — external HTTP behavior (FastAPI TestClient). One file per entity: `test_<entity>_api.py`.
- `tests/dal/` — repository-layer tests (no HTTP). One file per entity: `test_<entity>_repository.py`. Converter tests: `test_converters.py`.
- `tests/domain/` — Pydantic / command validation.
- `tests/utils/` — helper/utility tests.
- `tests/property_based/` — Hypothesis tests. `dal/` for stateless, `stateful/` for state machines.
- `tests/fixtures/` — shared fixtures (auth tokens per role, etc.).
- `tests/helpers.py` — API helpers (`create_admin_user`, `create_project_manager`, `create_write_user`, `create_read_user`).
- `tests/dal/helpers.py` — repository helpers (`create_test_org_via_repo`, `create_test_project_via_repo`, `create_test_user_via_repo`).
- `tests/conftest.py` — root fixtures (`client`, `test_db`, `test_session`, `test_stub_entity_repo`, `db_path`).

## Running tests
- Fast feedback during development: invoke the `run-targeted-tests-backend` skill.
- Full validation before done: invoke the `validate-backend` skill.

## Non-negotiables (one-line summary — see principles for detail)
- Explicit fixture imports with `# noqa: F401`.
- Use role-specific helpers; use repository helpers; no inline duplication.
- No mocks. No direct DB queries in tests. No ORM access in tests.
- 100% repository method coverage.
- Test names state behavior.
- Shared-org fixtures prefixed `shared_org_`.

For anything else: `docs/architecture/principles.md` and the `backend-engineer` agent.
