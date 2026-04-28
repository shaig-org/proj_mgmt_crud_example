# Plan: bind project write capability to a specific project at DI time

## Context

Today, `OrgProjectWriteCapability` is constructed by FastAPI DI with just `(repo, current_user)` and exposes per-verb methods that take `project_id` as an argument: `cap.load_for_update(project_id)`, `cap.update(project_id, cmd)`, etc. The router pattern is "load → check 404 → call verb", with the role / cross-org check happening inside `load_for_*` (raises `CapabilityPermissionError` → 403) and existence check raising 404 in the router.

Two weaknesses:
1. The route handler still has to thread `project_id` through every call. There's no static guarantee the verb is called on the same `project_id` that was checked.
2. The "load_for_X" dance is duplicated in every write route (update, delete, archive, unarchive — four times in `project_api.py` alone).

Goal: have DI produce a `BoundProjectWriteCapability` already scoped to the URL's `{project_id}` — auth and existence resolved before the handler runs. Methods take no `project_id`. The handler literally cannot operate on a different project. "Parse, don't validate" applied to authorization.

This PR is a **proof-of-concept on Project only**. If the shape works, Epic and Workflow (same pattern today) follow in separate PRs. Tickets stay on their `authorize_*` pattern (different shape — out of scope).

---

## Design

### 1. New error type for "not found, capability layer"
File: `backend/project_management_crud_example/capabilities/errors.py`

Add:
```python
class CapabilityNotFoundError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail
```
Mirrors the shape of existing `CapabilityPermissionError`.

### 2. Global exception handler maps it to 404
File: `backend/project_management_crud_example/app.py` (around line 158, beside the existing `CapabilityPermissionError` handler).

Add an `@app.exception_handler(CapabilityNotFoundError)` returning `JSONResponse(status_code=404, content={"detail": exc.detail})`. Keeps capability code framework-agnostic — handlers no longer raise `HTTPException` for these two cases.

### 3. New `BoundProjectWriteCapability` class
File: `backend/project_management_crud_example/capabilities/projects_capability.py`

```python
class BoundProjectWriteCapability:
    """Project write operations scoped to a specific, already-authorized project.

    Verbs and roles (mechanical — surfaced on the dev dashboard, see §8):
      - update:    SUPER_ADMIN, ADMIN, PROJECT_MANAGER
      - archive:   SUPER_ADMIN, ADMIN, PROJECT_MANAGER
      - delete:    SUPER_ADMIN, ADMIN
      - unarchive: SUPER_ADMIN, ADMIN

    Scope: the project passed to bind(); cross-org access is rejected before
    construction (super-admins bypass cross-org).
    """

    def __init__(self, repo: Repository, current_user: User, project: Project) -> None:
        self._repo = repo
        self._user = current_user
        self.current: Project = project   # public, read-only by convention

    def update(self, command: ProjectUpdateCommand) -> Project: ...
    def delete(self) -> bool: ...
    def archive(self) -> Project: ...
    def unarchive(self) -> Project: ...
```

Encapsulation rules (per architectural-memory note in §10):
- **No getter properties.** `current` is a public attribute (the loaded project, used for diff logging / response shape). `_repo` and `_user` are private with **no** accessor — outside code never reaches the repository through the cap. This is the whole point of the pattern; the previous `repo` / `user` getters were a leak.
- **No verb takes `project_id`** — the project is captured at construction.
- **Verbs absorb the post-write side-effects** that the route used to do via `cap.repo` / `cap.user`:
  - `update`: mutate via `_repo`, then call `log_activity(repo=_repo, command=command, entity_id=current.id, actor_id=_user.id, organization_id=updated.organization_id)`, then `log_diff_debug(self.current, updated, "project", "update_project")`. Returns the updated project. Raises `ValueError` (kept) if repo rejects the update — route translates to 400 as today.
  - `delete`: mutate via `_repo.projects.delete(current.id)`, then log activity (entity_id = `current.id`, command = a `ProjectDeleteCommand` if one exists; otherwise pass the same dict shape the existing route built — preserve audit-log fidelity).
  - `archive` / `unarchive`: same shape as `update` (mutation + activity log + diff log).
  - The `_require_write_role` / `_require_delete_role` defensive role re-check still runs at the top of each verb — cheap, preserves defense-in-depth in case `bind()` is ever bypassed in tests.
- The repo race-condition (project deleted between `bind()` and verb call) surfaces as `_repo.projects.update(...)` returning `None` → verb raises `CapabilityNotFoundError("Project not found")`, mapped to 404 by the global handler.

Implication: **the route shrinks dramatically** (see §6) and never imports `log_activity` or `log_diff_debug` itself.

### 4. `bind()` factory on the unbound capability
File: `backend/project_management_crud_example/capabilities/projects_capability.py`

Add to `OrgProjectWriteCapability`:
```python
def bind(self, project_id: str) -> BoundProjectWriteCapability:
    """Resolve auth + existence, return a capability scoped to this project.

    Raises:
        CapabilityPermissionError: role gate or cross-org check fails (-> 403).
        CapabilityNotFoundError: project does not exist (-> 404).
    """
    self._require_write_role("update projects")  # role gate
    project = self._repo.projects.get_by_id(project_id)
    if project is None:
        raise CapabilityNotFoundError("Project not found")
    self._ensure_same_org(project)               # cross-org gate
    return BoundProjectWriteCapability(self._repo, self._user, project)
```

The role detail string is `"update projects"` because that's the broadest verb the bound cap exposes; today the various `load_for_*` methods used different action strings (`"update projects"`, `"delete projects"`, `"archive projects"`, `"unarchive projects"`). **This is a user-visible 403 detail change** for delete/archive/unarchive routes — flagged as a test/spec impact below.

The existing `load_for_update` / `load_for_delete` / `load_for_archive` / `load_for_unarchive` methods become **private** as part of §7 (they're unused by routes once the migration is done; tests that exercised them directly migrate to `bind()` + bound verbs). The cross-org check (`_ensure_same_org`) and role gates (`_require_write_role`, `_require_delete_role`) are reused from `bind()` and the bound class's defensive checks.

### 5. New DI factory
File: `backend/project_management_crud_example/dependencies.py`

```python
def get_bound_project_write_capability(
    project_id: str,
    cap: OrgProjectWriteCapability = Depends(get_org_project_write_capability),
) -> BoundProjectWriteCapability:
    return cap.bind(project_id)
```

`project_id: str` is read from the path automatically (FastAPI matches dep parameter names against path params). No `Path(...)` needed — keeps the codebase free of a new import pattern.

### 6. Migrate the four write routes
File: `backend/project_management_crud_example/routers/project_api.py`

For each of `PUT /{project_id}`, `DELETE /{project_id}`, `PATCH /{project_id}/archive`, `PATCH /{project_id}/unarchive`:

- `project_id: str` is **removed from the handler signature** (the dep consumes it). FastAPI still routes correctly because the dep parameter matches the path variable. This is the strongest "you cannot operate on a different id" guarantee — the handler doesn't even have access to `project_id` as a local.
- Replace `cap: OrgProjectWriteCapability = Depends(get_org_project_write_capability)` with `cap: BoundProjectWriteCapability = Depends(get_bound_project_write_capability)`.
- Remove the `load_for_*` + `if not project: raise 404` block — the dep has already raised.
- Remove the `log_activity(...)` and `log_diff_debug(...)` calls — verbs handle them internally (see §3).
- Verb calls take no arguments other than the command: `cap.update(update_data)`, `cap.delete()`, `cap.archive()`, `cap.unarchive()`.

After migration, `update_project` is roughly:
```python
@router.put("/{project_id}", response_model=Project)
async def update_project(
    update_data: ProjectUpdateCommand,
    cap: BoundProjectWriteCapability = Depends(get_bound_project_write_capability),
) -> Project:
    try:
        return cap.update(update_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
```

`delete_project`, `archive_project`, `unarchive_project` collapse to one or two lines each.

Collection-level routes (`POST /` create, `GET /` list, `GET /{project_id}` read) are **untouched** by the bound-capability migration — read uses `ProjectReadCapability`, create has no `project_id` to bind. **However**, `create_project` today reaches into `cap.repo` and `cap.user.id` for its activity log; that violates the same encapsulation rule we're imposing on the bound class. See §7 for the matching cleanup on `OrgProjectWriteCapability`.

### 7. Encapsulation cleanup on `OrgProjectWriteCapability`
File: `backend/project_management_crud_example/capabilities/projects_capability.py`

Apply the same no-getters / no-`_repo`-leak rule to the unbound class so the architectural rule is uniform across the file (and the bound class isn't the lone island):

- **Remove** the `repo` and `user` `@property` getters from `OrgProjectWriteCapability`. `_repo` and `_user` stay private with no public accessor.
- **Move the activity log into `create()`**: `cap.create(command)` mutates via `_repo.projects.create(command)` and then calls `log_activity(...)` internally with `command`, `entity_id=project.id`, `actor_id=_user.id`, `organization_id=project.organization_id`. Returns the created project.
- `create_project` route loses `log_activity(repo=cap.repo, ...)` and ends with `return cap.create(command)`.
- `build_create_command` stays public (it's pure validation logic the route uses to translate `ProjectData` → `ProjectCreateCommand` before passing to `create`).
- `bind()` stays the public entry point. The internal `load_for_*` methods become **private** (`_load_for_update`, etc.) since they're now implementation detail of `bind` — no external caller after this PR. Tests that exercised them directly are updated to go through `bind()` (see Tests section).

Cross-reference: `ProjectReadCapability` also has `repo` / `user` getters today. **Out of scope** for this PR (no read-side change), but flagged for the same cleanup in a follow-up.

### 8. Capability self-documentation for the dashboard

Goal: each capability class advertises (a) the verbs it exposes, (b) the roles allowed for each verb, (c) the scope (org / bound entity / self / global). Eventually the dev dashboard renders this as a "Capabilities" panel — strict, mechanical, derived from the source of truth (the role-set constants).

POC scope (this PR):
- Add a structured class docstring to `BoundProjectWriteCapability` and `OrgProjectWriteCapability` in the format shown in §3 (Verbs / Roles / Scope sections, simple bullets). This is human-authored and will drift; that's acceptable for a POC.
- Add a tiny generator script `backend/project_management_crud_example/tools/dump_capabilities_doc.py` that imports the capability classes and emits a Markdown file (`backend/evidence/capabilities/verbs.md`) listing each class's verbs + role sets. **For the POC the script can simply concatenate the docstrings** — mechanical extraction from the role-set constants is the eventual target but not blocking.
- The dev dashboard does **not** get a new tab in this PR. The Markdown file is the artifact; consuming it is a follow-up.

Eventual (out of scope) shape for "strict and mechanical":
- A `CapabilitySpec` decorator or class attribute (e.g. `_VERBS = {"update": _WRITE_ROLES, "delete": _DELETE_ROLES, ...}`) that the script reads instead of parsing docstrings. The role constants in `projects_capability.py` (`_WRITE_ROLES`, `_DELETE_ROLES`) become the single source of truth and the docstring is generated from them, not the other way around.
- A new aspect plugin in `tools/dev-dashboard/` reads `verbs.md` (or a JSON sibling) and renders a per-class table with columns: Verb / Roles / Scope / Side-effects.

This split (POC docstring now, mechanical later) avoids gold-plating the proof and lets the bound-cap pattern itself be evaluated first.

### 9. Capability baseline refresh
The static analyzer in `backend/project_management_crud_example/tools/analyze_capabilities` reads route handlers' capability surfaces. The four migrated routes now depend on `BoundProjectWriteCapability` (4 verbs total) instead of `OrgProjectWriteCapability` (8+ methods, including `load_for_*`). Per `backend/evidence/capabilities/README.md`:

```
cd backend && ./devtools/run_with_env.sh uv run python -m project_management_crud_example.tools.analyze_capabilities
```

If exit 1 (expansion), inspect; this refactor should **reduce** surface, so exit 0 is expected. If it reports a reduction, run with `--update-baseline` and commit `backend/evidence/capabilities/baseline.json`.

---

## Files to change

| File | Change |
|---|---|
| `backend/project_management_crud_example/capabilities/errors.py` | Add `CapabilityNotFoundError`. |
| `backend/project_management_crud_example/capabilities/projects_capability.py` | Add `BoundProjectWriteCapability` (no getters; verbs absorb activity/diff logging). Add `bind()` and absorb activity logging into `create()` on `OrgProjectWriteCapability`. Remove `repo` / `user` property getters from `OrgProjectWriteCapability`. Privatise `load_for_*` methods. Add structured class docstrings. |
| `backend/project_management_crud_example/capabilities/__init__.py` | Export `BoundProjectWriteCapability`, `CapabilityNotFoundError`. |
| `backend/project_management_crud_example/app.py` | Register exception handler for `CapabilityNotFoundError` → 404. |
| `backend/project_management_crud_example/dependencies.py` | Add `get_bound_project_write_capability`. |
| `backend/project_management_crud_example/routers/project_api.py` | Migrate 4 write routes to bound cap; drop `load_for_*` + 404 dance + `log_activity` / `log_diff_debug` calls. Drop `log_activity` from `create_project`. |
| `backend/project_management_crud_example/tools/dump_capabilities_doc.py` | New: tiny script that imports capability classes and writes `backend/evidence/capabilities/verbs.md` from class docstrings. |
| `backend/evidence/capabilities/verbs.md` | New artifact: human-readable verb/role table per capability class. |
| `backend/evidence/capabilities/baseline.json` | Regenerate if surface analyzer reports a reduction. |

## Tests

### New
`backend/tests/capabilities/test_projects_capability.py` (extend existing file):
- `test_bind_returns_bound_capability_for_authorized_project` — happy path.
- `test_bind_raises_permission_error_for_wrong_role` — role gate.
- `test_bind_raises_permission_error_for_cross_org_project` — same-org gate.
- `test_bind_raises_not_found_error_for_missing_project` — 404 path now lives in cap, not router.
- `test_bound_write_has_no_project_id_arg` — structural guard via `inspect.signature()`, mirroring the existing `test_own_comment_write_has_no_author_id_or_user_id_arg` (`tests/capabilities/test_comments_capability.py:65`). Asserts no public method on `BoundProjectWriteCapability` accepts a parameter named `project_id`.
- `test_bound_write_has_no_repo_accessor` — structural guard: `BoundProjectWriteCapability` exposes no public `repo` attribute or `repo`-named property. (Pairs with the architectural rule.)
- `test_bound_write_has_no_user_accessor` — same shape, for `user`.
- `test_org_project_write_has_no_repo_accessor` — same guard on the unbound class after the cleanup in §7.
- `test_bind_super_admin_crosses_org` — SA bypass still works.
- `test_bind_loaded_project_on_current` — `cap.current` returns the same instance fetched by `bind`.
- `test_bound_update_emits_activity_log` — call `cap.update(cmd)`, assert an activity log row was inserted via the repo (the route used to do this; verify the cap now does).
- `test_bound_delete_emits_activity_log`, `test_bound_archive_emits_activity_log`, `test_bound_unarchive_emits_activity_log` — same shape.
- `test_org_create_emits_activity_log` — `cap.create(cmd)` on the unbound class also emits the log internally after §7.

### Updated
- `backend/tests/api/test_project_api.py` — most assertions stay (status codes + bodies unchanged). **Audit for 403 detail strings**: today delete returns `"Insufficient permissions to delete projects"`, archive `"... to archive projects"`, unarchive `"... to unarchive projects"`. After the refactor, `bind()` raises with `"... to update projects"` for all four. Either:
  - (a) update those test assertions to expect the new unified string, or
  - (b) preserve the per-verb strings by passing the verb name into `bind(project_id, *, action="delete projects")` (richer API but small extra surface).

  Recommend (a) — simpler, and the action name in the 403 detail was always best-effort. Spec impact in `docs/spec/`: search for those exact strings (none expected, but verify).

### Existing tests that may break
- Tests that called `cap.load_for_update(project_id)` directly: those methods become `_load_for_update` (private, §7). Migrate the assertions to go through `cap.bind(project_id)` and the bound class's verbs. This is part of the work, not optional — privatising the methods is the encapsulation win.
- Tests that read `cap.repo` or `cap.user` on the unbound class: rewrite to use the new public surface (`cap.bind(...)`, `cap.create(...)`, `cap.build_create_command(...)`). If a test needs the underlying repo for assertion, it should use the test fixture's `test_repo` directly, not pull it back through the cap.
- `tests/integration/` cross-org / cross-role suites — should pass unchanged since the gate still raises 403, just from a different call site.

### PBT
None added — the refactor doesn't introduce new property-shaped invariants beyond what is already covered.

## Spec / docs touch-ups

- `docs/architecture/principles.md` §Capability layer — add two sentences:
  1. "Where the route operates on a single resource, prefer a bound capability whose constructor resolves authorization and existence."
  2. "Capability classes do not expose getter properties for their repository or current-user dependencies; those are private. If external code needs them, the capability is missing a verb."
- No `docs/spec/` REQ-IDs are affected (HTTP behavior unchanged: 403/404 surface the same statuses; only one detail-string variant changes).

## Verification

1. **Targeted backend tests during the loop**:
   `cd backend && uv run pytest tests/capabilities/test_projects_capability.py tests/api/test_project_api.py -x` (or via the `run-targeted-tests-backend` skill).

2. **Capability analyzer**:
   ```
   cd backend && ./devtools/run_with_env.sh uv run python -m project_management_crud_example.tools.analyze_capabilities
   ```
   Expect exit 0 (surface unchanged or reduced). If surface reduced, run with `--update-baseline` and commit `backend/evidence/capabilities/baseline.json`.

3. **Full backend validation before declaring done**:
   `cd backend && ./devtools/run_all_agent_validations.sh` (zero errors, zero warnings).

4. **Frontend E2E** — Playwright project-CRUD flow should pass without changes:
   `cd frontend && npm run e2e -- --grep project` (or whatever scenario tag covers project edit/archive/delete).

5. **Manual smoke** in dev dashboard or via curl:
   - PUT a project as authorized user → 200 with updated body.
   - PUT a project as wrong role → 403 with `"Insufficient permissions to update projects"`.
   - PUT a project belonging to another org → 403 with `"Access denied: project belongs to different organization"`.
   - PUT a non-existent project id → 404 with `"Project not found"` (now produced by the dep, not the router — verify body shape unchanged).
   - DELETE / archive / unarchive equivalents.

## Out of scope (explicit follow-ups)

- Apply the same shape (bind + no-getters + side-effects-in-verbs) to `OrgEpicWriteCapability` (`epic_api.py`, 2 routes) and `OrgWorkflowWriteCapability` (`workflow_api.py`, 2 routes). Mechanical copy of this PR.
- Tickets (`ticket_api.py`) currently use a different `authorize_*` + repo pattern; harmonizing with the bound shape is a separate design conversation.
- Sweep `repo` / `user` getter properties off **all** other capability classes (`ProjectReadCapability`, `TicketReadCapability`, `OrgUserWriteCapability`, etc.). One consistent rule across the file.
- Replace the docstring-driven `verbs.md` generator with a strictly-mechanical version that reads from a `_VERBS` mapping on each class (see §8 "Eventual shape"). Add a dev-dashboard aspect plugin to render it.

## Memory to save once plan mode exits

Architectural memory entry for `~/.claude/projects/<this-project>/memory/`:

- **Title**: Getter properties on capability classes are an anti-pattern.
- **Rule**: capability classes do not expose `repo` / `user` getter properties. If an attribute is meant to be public (e.g. the bound entity), make it a plain public attribute. If it is meant to be private (the repository, the current user as captured at construction), there is no public accessor — period. The whole point of the capability layer is to deny external code access to the underlying repository; a getter undoes that guarantee.
- **Why**: the previous shape (`@property def repo(self) -> Repository`) let routes reach back into the unrestricted repo for side-effects like `log_activity`, defeating the layer's purpose. The fix is to absorb those side-effects into the capability's verbs so the repository never leaves the class.
- **How to apply**: when adding or reviewing a capability class, every public method that a route wants to call must be a verb on the capability. If a route needs `cap.repo.something()`, the capability is missing a verb — add the verb, don't expose the repo.
