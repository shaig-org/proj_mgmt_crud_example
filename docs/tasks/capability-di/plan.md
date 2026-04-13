# Feature Plan: Capability-based Dependency Injection + Capability Surface Analyzer

**Status**: Draft
**Date**: 2026-04-12
**Stack**: Backend (+ static HTML tool; no frontend app changes)
**Detailed spec**: docs/spec/detailed/capability_di_detailed_spec.md (to be authored if not present; this plan encodes the agreed design)

## 1. Requirements in scope
- REQ-CAPDI-001: FastAPI route handlers MUST NOT receive `Repository` directly via `Depends(get_repository)` (except the documented exceptions). Instead, they receive narrowly-scoped Capability objects.
- REQ-CAPDI-002: Capability objects own authorization decisions. On deny, they raise `CapabilityPermissionError`; a FastAPI exception handler maps it to HTTP 403 with the existing error envelope.
- REQ-CAPDI-003: Per-entity capability modules live under `backend/project_management_crud_example/capabilities/`. Read/write slicing is applied where endpoints truly differ in permission shape; a single capability class may serve an entity when all access is uniform.
- REQ-CAPDI-004: A static analyzer tool enumerates every FastAPI route, extracts the Capability dependencies it depends on, emits `evidence/capabilities/report.json` and a self-contained `evidence/capabilities/index.html` viewer, and diffs against `evidence/capabilities/baseline.json`.
- REQ-CAPDI-005: Default analyzer invocation fails (exit 1) if any endpoint's capability set *expanded* vs the baseline. `--update-baseline` overwrites the baseline file.
- REQ-CAPDI-006: All existing API permission behaviors are preserved: 403s still occur on the same (role, org, endpoint) combinations as before.

## 2. Out of scope
- No frontend changes. No new roles. No new auth flows. No DB schema migrations.
- No changes to the error envelope shape (we reuse whatever `HTTPException(403, ...)` produced before).
- No refactor of the auth dependencies themselves (`get_current_user`, `get_admin_user`, `get_super_admin_user` remain).
- No capability composition/DSL. A capability is a plain class with methods; no decorators.
- Endpoints intentionally excluded from the rule (keep current wiring, documented below):
  - `POST /auth/login` — runs before a user is known.
  - `GET /health` — no data access.
  - `/e2e/**` test-reset endpoints — intentionally unrestricted in test mode; wrapping them adds no value.

## 3. Architecture

### 3.1 Overview
Introduce an intermediate layer between FastAPI dependencies and the Repository DAL: a **Capability**. A capability is a small object that:
- Holds a reference to the repo it needs (often just one sub-repo) and the authenticated user.
- Exposes verbs that match the endpoint's intent (e.g., `list_projects_in_org`, `create_project`, `delete_project`).
- Enforces authorization before delegating to the repo. Raises `CapabilityPermissionError` on deny.

Routers call capability verbs instead of repo methods and never re-check roles inline.

### 3.2 New modules

```
backend/project_management_crud_example/capabilities/
  __init__.py
  errors.py                        # CapabilityPermissionError
  projects_capability.py           # ProjectReadCapability, ProjectWriteCapability
  users_capability.py              # UserReadCapability, UserWriteCapability
  organizations_capability.py      # OrganizationCapability (single class; super-admin only for writes)
  epics_capability.py              # EpicReadCapability, EpicWriteCapability
  workflows_capability.py          # WorkflowReadCapability, WorkflowWriteCapability
  tickets_capability.py            # TicketReadCapability, TicketWriteCapability
  comments_capability.py           # CommentCapability (single class; author-or-admin policy)
  activity_logs_capability.py      # ActivityLogReadCapability (read-only; writes are internal)
```

**Slicing rationale**:
- Read vs Write is split when deny rules differ (common case: reads allowed to any org member; writes restricted to admins or above).
- Single-class capabilities (Organizations, Comments, ActivityLogs) are used when the per-verb permission set is homogeneous enough that a split adds noise without signal.

### 3.3 Capability class shape

```python
class ProjectReadCapability:
    def __init__(self, repo: Repository, current_user: User):
        self._projects = repo.projects
        self._user = current_user

    def list_projects_in_org(self, org_id: UUID) -> list[Project]:
        if not self._user_can_read_org(org_id):
            raise CapabilityPermissionError("cannot read projects in this organization")
        return self._projects.list_by_org(org_id)
    ...
```

Cross-org isolation, role gating, and "self vs other" checks live inside capability methods. Routers don't know about `UserRole` anymore.

### 3.4 `CapabilityPermissionError` and 403 mapping

`capabilities/errors.py`:
```python
class CapabilityPermissionError(Exception):
    def __init__(self, detail: str, *, code: str = "forbidden"):
        self.detail = detail
        self.code = code
```

In `app.py`:
```python
@app.exception_handler(CapabilityPermissionError)
def _cap_perm_handler(request, exc):
    return JSONResponse(status_code=403, content={"detail": exc.detail})
```

Handlers stop doing `raise HTTPException(403, ...)` for authz. They still raise 404/409/422 themselves — capability only owns 403.

### 3.5 `dependencies.py` additions

Add factories (one per capability class) that build on the existing deps:

```python
def get_project_read_capability(
    repo: Repository = Depends(get_repository),
    user: User = Depends(get_current_user),
) -> ProjectReadCapability:
    return ProjectReadCapability(repo, user)
```

Matching factories for: project_write, user_read, user_write, organization, epic_read, epic_write, workflow_read, workflow_write, ticket_read, ticket_write, comment, activity_log_read.

Factories are the **only** place `get_repository` is still referenced outside the exception list above.

### 3.6 Router migration

For each endpoint (55 total, minus exceptions):
- Remove `repo: Repository = Depends(get_repository)` and any `current_user: User = Depends(get_admin_user)` (role-specific) parameters.
- Add `cap: XxxCapability = Depends(get_xxx_capability)`.
- Replace `repo.foo.bar(...)` with `cap.verb(...)`.
- Remove inline role/org checks that duplicate what the capability now enforces.

### 3.7 Analyzer tool

Location: `backend/project_management_crud_example/tools/analyze_capabilities.py`.
Entry: `python -m project_management_crud_example.tools.analyze_capabilities [--update-baseline]`.

Algorithm:
1. Import the FastAPI `app`.
2. Walk `app.routes` (`APIRoute` instances). Skip exception list.
3. For each route, walk `route.dependant` tree, collect `Depends` callables. A callable qualifies as a capability provider if its return annotation class name ends with `Capability`.
4. Produce `report.json`:
   ```json
   {
     "routes": [
       {"method": "GET", "path": "/projects/{project_id}",
        "handler": "projects_api.get_project",
        "capabilities": ["ProjectReadCapability"]}
     ],
     "summary": {"total": N, "unchanged": X, "expanded": Y, "reduced": Z, "new": W, "removed": V}
   }
   ```
5. Diff against `evidence/capabilities/baseline.json`. Classify each route as `unchanged|expanded|reduced|new|removed`.
6. Render `index.html` (self-contained: inline `<style>`, no external assets). Table of routes; rows tinted red (expanded/new), green (reduced), grey (unchanged), yellow (removed). Banner summarizes counts.
7. Exit code:
   - 0 if no route is expanded *and* no route is new without being intentional (new routes count as expansion for safety).
   - 1 if any route expanded or new.
   - `--update-baseline` always exits 0 after overwriting.

### 3.8 Baseline storage
- `evidence/capabilities/baseline.json` is checked in.
- `evidence/capabilities/report.json` and `index.html` are generated artifacts; add `evidence/capabilities/report.json` and `evidence/capabilities/index.html` to `.gitignore`. Baseline itself is tracked.

### 3.9 FE/BE contract
Not applicable — no endpoint request/response shapes change. The only externally observable change is: endpoints that previously returned 403 continue to return 403 with identical `{detail: "..."}` envelope.

## 4. Test matrix

### 4.1 Capability unit tests — new layer `backend/tests/capabilities/`

Conventions:
- Each capability test file: one test per method covering (a) allow for a permitted user, (b) deny for a disallowed role (raises `CapabilityPermissionError`), (c) deny for a cross-org user where org scoping applies.
- Fixtures: `test_repo` (in-memory `Repository`), helpers from `tests/helpers.py` to create users per role and orgs.

#### `tests/capabilities/test_projects_capability.py`
| Test name | Verifies |
|---|---|
| test_project_read_list_in_org_allows_member | member gets list |
| test_project_read_list_in_org_denies_cross_org_user | raises CapabilityPermissionError |
| test_project_read_get_by_id_allows_member | returns project |
| test_project_read_get_by_id_denies_cross_org_user | raises |
| test_project_write_create_allows_admin | returns created |
| test_project_write_create_denies_regular_user | raises |
| test_project_write_create_denies_cross_org_admin | raises |
| test_project_write_update_allows_admin_same_org | returns updated |
| test_project_write_update_denies_regular_user | raises |
| test_project_write_delete_allows_admin_same_org | deletes |
| test_project_write_delete_denies_regular_user | raises |

#### `tests/capabilities/test_users_capability.py`
| Test name | Verifies |
|---|---|
| test_user_read_get_self_allows_any_role | self read |
| test_user_read_get_other_in_org_allows_admin | admin reads peer |
| test_user_read_get_other_denies_regular_user | raises |
| test_user_read_list_org_users_allows_admin | list |
| test_user_read_list_org_users_denies_regular_user | raises |
| test_user_write_create_allows_admin | returns |
| test_user_write_create_denies_regular_user | raises |
| test_user_write_create_denies_cross_org_admin | raises |
| test_user_write_update_self_allows_any_role | self update |
| test_user_write_update_other_allows_admin | admin updates peer |
| test_user_write_update_other_denies_regular_user | raises |
| test_user_write_delete_allows_admin | deletes |
| test_user_write_delete_denies_regular_user | raises |

#### `tests/capabilities/test_organizations_capability.py`
| Test name | Verifies |
|---|---|
| test_org_get_by_id_allows_member | returns |
| test_org_get_by_id_denies_non_member | raises |
| test_org_list_all_allows_super_admin | returns |
| test_org_list_all_denies_admin | raises |
| test_org_create_allows_super_admin | creates |
| test_org_create_denies_admin | raises |
| test_org_update_allows_super_admin | updates |
| test_org_update_denies_admin | raises |
| test_org_delete_allows_super_admin | deletes |
| test_org_delete_denies_admin | raises |

#### `tests/capabilities/test_epics_capability.py`
| Test name | Verifies |
|---|---|
| test_epic_read_list_in_project_allows_member | list |
| test_epic_read_list_denies_cross_org | raises |
| test_epic_read_get_by_id_allows_member | returns |
| test_epic_read_get_by_id_denies_cross_org | raises |
| test_epic_write_create_allows_admin | creates |
| test_epic_write_create_denies_regular_user | raises |
| test_epic_write_create_denies_cross_org_admin | raises |
| test_epic_write_update_allows_admin | updates |
| test_epic_write_update_denies_regular_user | raises |
| test_epic_write_delete_allows_admin | deletes |
| test_epic_write_delete_denies_regular_user | raises |

#### `tests/capabilities/test_workflows_capability.py`
| Test name | Verifies |
|---|---|
| test_workflow_read_list_allows_member | list |
| test_workflow_read_list_denies_cross_org | raises |
| test_workflow_read_get_allows_member | returns |
| test_workflow_read_get_denies_cross_org | raises |
| test_workflow_write_create_allows_admin | creates |
| test_workflow_write_create_denies_regular_user | raises |
| test_workflow_write_update_allows_admin | updates |
| test_workflow_write_update_denies_regular_user | raises |
| test_workflow_write_delete_allows_admin | deletes |
| test_workflow_write_delete_denies_regular_user | raises |

#### `tests/capabilities/test_tickets_capability.py`
| Test name | Verifies |
|---|---|
| test_ticket_read_list_in_project_allows_member | list |
| test_ticket_read_list_denies_cross_org | raises |
| test_ticket_read_get_allows_member | returns |
| test_ticket_read_get_denies_cross_org | raises |
| test_ticket_write_create_allows_member | creates (regular users can create) |
| test_ticket_write_create_denies_cross_org | raises |
| test_ticket_write_update_allows_assignee_or_admin | updates |
| test_ticket_write_update_denies_unrelated_regular_user | raises |
| test_ticket_write_delete_allows_admin | deletes |
| test_ticket_write_delete_denies_regular_user | raises |

#### `tests/capabilities/test_comments_capability.py`
| Test name | Verifies |
|---|---|
| test_comment_list_on_ticket_allows_member | list |
| test_comment_list_denies_cross_org | raises |
| test_comment_create_allows_member | creates |
| test_comment_create_denies_cross_org | raises |
| test_comment_update_allows_author | updates |
| test_comment_update_denies_non_author_non_admin | raises |
| test_comment_update_allows_admin | admin overrides |
| test_comment_delete_allows_author | deletes |
| test_comment_delete_allows_admin | admin overrides |
| test_comment_delete_denies_non_author_non_admin | raises |

#### `tests/capabilities/test_activity_logs_capability.py`
| Test name | Verifies |
|---|---|
| test_activity_log_list_allows_admin | list |
| test_activity_log_list_denies_regular_user | raises |
| test_activity_log_list_denies_cross_org_admin | raises |
| test_activity_log_get_by_id_allows_admin | returns |
| test_activity_log_get_by_id_denies_regular_user | raises |

### 4.2 Analyzer tests — `backend/tests/tools/test_analyze_capabilities.py`
| Test name | Verifies |
|---|---|
| test_extract_capabilities_from_route_finds_single_capability | given a route depending on one Capability class, extractor returns that name |
| test_extract_capabilities_from_route_finds_multiple | route with multiple Capability deps returns all |
| test_extract_capabilities_from_route_ignores_non_capability_deps | `get_repository`, `get_current_user` not reported |
| test_extract_capabilities_skips_exception_routes | `/auth/login`, `/health`, `/e2e/**` are excluded |
| test_diff_classifies_unchanged_route | same capability set → unchanged |
| test_diff_classifies_expanded_route | added capability → expanded |
| test_diff_classifies_reduced_route | removed capability → reduced |
| test_diff_classifies_new_route | route absent from baseline → new |
| test_diff_classifies_removed_route | route present in baseline, absent now → removed |
| test_render_index_html_contains_all_routes | every route path appears in HTML |
| test_render_index_html_tints_expanded_rows_red | expanded row has red class |
| test_render_index_html_banner_counts_match_summary | banner numbers match summary |
| test_cli_exit_zero_when_no_expansion | unchanged/reduced baseline → exit 0 |
| test_cli_exit_one_when_any_route_expanded | synthesized expansion → exit 1 |
| test_cli_exit_one_when_new_route_without_update_flag | new route → exit 1 |
| test_cli_update_baseline_overwrites_file | `--update-baseline` rewrites baseline.json and exits 0 |

### 4.3 API tests — no new file
Existing `tests/api/test_*_api.py` suites continue to run unchanged. They already assert 403 for disallowed roles and cross-org accesses; those assertions now pass through the capability → `CapabilityPermissionError` → 403 handler path. No new API tests required for this feature; any test that previously passed must continue to pass.

Explicit sanity checks already covered by existing tests (no additions — just documenting that they exercise the new path):
- Project list by cross-org user returns 403.
- Regular user creating a project returns 403.
- Admin deleting another org's resource returns 403.
- Super-admin-only endpoints return 403 for admins.
- Comment update by non-author regular user returns 403.

### 4.4 Domain / validation tests
None. No new domain models.

### 4.5 Utility / converter tests
None. No new converters.

### 4.6 Property-based tests
Not planned. The capability layer is a finite decision table; enumerated unit tests cover it more clearly than hypothesis strategies would. Revisit only if capability composition is introduced (currently out of scope).

### 4.7 Frontend E2E tests
Not applicable — no FE change.

## 5. Test fixtures and helpers

### Existing helpers used
- `tests/helpers.py`: `create_admin_user`, `create_regular_user`, `create_super_admin_user`, `create_test_org_via_repo`.
- `tests/conftest.py`: `test_repo`, `client`.

### New helpers (in `tests/capabilities/helpers.py`)
- `build_project_read_cap(repo, user) -> ProjectReadCapability` — trivial constructor wrapper used for readability; avoids repeating imports across 8 test files.
- `build_project_write_cap(repo, user)` etc. for each capability class.
- `assert_denied(callable_)` — helper that calls and asserts `CapabilityPermissionError` is raised with a non-empty `detail`.

### Fixture types
- `test_repo: Repository`
- `admin_user, regular_user, super_admin_user, cross_org_admin: User`
- `org_id: UUID`, `other_org_id: UUID`

## 6. Edge cases covered

- **Cross-org isolation**: every capability method accepting an org-scoped ID has a deny-for-cross-org test.
- **Self vs other**: user read/update capability tests cover "self allowed", "other requires admin".
- **Role boundaries**: each method tested at its boundary role (e.g., admin allowed, regular denied; super-admin allowed, admin denied for org-level writes).
- **Author-based rules**: comments tested for author-allowed, admin-override, non-author-denied.
- **Internal-write activity logs**: capability only exposes reads; no write verbs tested or offered (writes still happen via repo from within other capabilities / services — not from handlers).
- **Analyzer**: new routes flagged as expansion by default (prevents silent broadening). `--update-baseline` is the explicit opt-in.
- **Analyzer exception list**: login, health, `/e2e/**` explicitly excluded and tested.
- **Error envelope**: `CapabilityPermissionError.detail` is preserved verbatim in the 403 response.

## 7. Implementation order

1. **`CapabilityPermissionError` + exception handler wiring** in `app.py`. No router changes yet.
2. **Per-entity capability modules**, starting with `projects_capability.py`. For each:
   a. Write capability class.
   b. Write matching `tests/capabilities/test_<entity>_capability.py` (all tests from section 4.1).
   c. Add DI factory in `dependencies.py`.
   d. Migrate that entity's router to use the capability. Run existing API tests for that router — must stay green.
   e. Commit.
3. Repeat step 2 for users, organizations, epics, workflows, tickets, comments, activity_logs.
4. **Analyzer tool** (`tools/analyze_capabilities.py`):
   a. Implement `extract_capabilities_from_route` and diff logic.
   b. Implement HTML renderer.
   c. Implement CLI entry with `--update-baseline` flag.
   d. Write `tests/tools/test_analyze_capabilities.py` (all tests from section 4.2).
5. **Baseline creation**: run `python -m ...analyze_capabilities --update-baseline`, commit `evidence/capabilities/baseline.json`. Add generated `report.json`/`index.html` to `.gitignore`.
6. **Final sweep**: grep `backend/project_management_crud_example/routers/` for `Depends(get_repository)` — must return only the documented exception endpoints. Grep for `HTTPException(status_code=403` / `HTTPException(403` in routers — must return zero.
7. **Full validation**: `cd backend && ./devtools/run_all_agent_validations.sh` green.
8. **Analyzer clean run**: `python -m project_management_crud_example.tools.analyze_capabilities` exits 0 (no diff vs committed baseline).

## 8. Risks / open questions

- **Risk**: a router currently performs subtle data-filtering that masquerades as authz (e.g., "admin sees all, regular sees only own"). Moving to capability may flip a filter into a deny. Mitigation: for each router, read the existing handler carefully during migration; if behavior is "filter, don't deny", capability verb returns a filtered list rather than raising.
- **Risk**: `route.dependant` walking may miss capabilities behind nested `Depends`. Mitigation: walk recursively; analyzer test `test_extract_capabilities_from_route_finds_multiple` covers nested cases. If introspection proves flaky, fall back to scanning the handler signature's annotations.
- **Open question**: should `/e2e/**` endpoints be allowed through without any capability, or wrapped in a permissive "E2eResetCapability" so the analyzer surface is fully uniform? Current plan: exclude. Revisit only if the exception list grows.
- **Open question**: do we need per-capability logging on deny? Not in scope; existing access logs are untouched.

## 9. Sign-off
- [ ] User approved plan — date/note
- [ ] Backend implementation complete (all BE tests green, validations clean)
- [ ] Analyzer baseline committed; clean run with zero diff
- [ ] code-reviewer sign-off
