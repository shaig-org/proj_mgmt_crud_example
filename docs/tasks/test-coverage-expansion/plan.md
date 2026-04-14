# Test Coverage Expansion

Branch: `test-coverage-expansion`. Goal: 20–30 new E2E scenarios + 50+ new API-level backend tests covering real gaps.

## Context

- Existing scenarios (`frontend/e2e/scenarios/*.scenario.spec.ts`): create-project, create-epic-in-project, create-ticket-and-change-status, _fixture-smoketest. **Huge gap** vs 20–30 target.
- Existing regular E2E (`frontend/e2e/*.spec.ts`): login-flow, navigation, organizations, create-user, create-project, project-details, epic-management, epic-details, epic-progress-tracking, epic-ticket-relationship, ticket-management, ticket-details, ticket-advanced, ticket-filtering-sorting, health-check. Rich — many flows visible here can be promoted to scenarios.
- Existing backend API tests: 12 files, **367 `test_*` methods** already. `test_health_api.py` very thin (1 test). `test_custom_workflow_validation.py` and `test_stub_entity_api.py` thinner. Coverage is dense for core CRUD; gaps tend to be **edge cases, cross-entity consistency, role matrix, and workflow-specific paths**.

## Scenario list (25 new + 3 existing = 28 total)

Authoring rules (see `docs/testing/scenario_walkthroughs.md`):
- 5–8 `step()` calls, imperative labels, one visibly distinct DOM state per step.
- UI-only in test body; API in `beforeAll`.
- Parallel-safe data via `generateTest*Name()`.
- No `waitForTimeout`, no raw `page.screenshot()`.

### Auth & onboarding
1. `login-happy-path.scenario.spec.ts` — super-admin logs in, lands on projects.
2. `logout.scenario.spec.ts` — logged-in user logs out and returns to login.
3. `change-password.scenario.spec.ts` — user changes their own password (if UI surfaces this; else skip, document).
4. `super-admin-onboarding-flow.scenario.spec.ts` — admin creates org → creates PM user → shows generated password.

### Organizations (admin-level)
5. `create-organization.scenario.spec.ts` — super-admin creates an org and sees it in the list.

### Users (admin-level)
6. `create-user-with-role.scenario.spec.ts` — admin creates a user with write_access role, sees generated password modal, then sees user in list.
7. `edit-user-role.scenario.spec.ts` — admin changes a user's role (if UI supports).
8. `deactivate-user.scenario.spec.ts` — admin deactivates a user (if UI supports).

### Projects
9. `edit-project.scenario.spec.ts` — PM edits project name/description from project details.
10. `project-list-overview.scenario.spec.ts` — PM views projects list with multiple projects.
11. `view-project-details.scenario.spec.ts` — open a project, see info/epics/tickets sections.

### Epics
12. `edit-epic.scenario.spec.ts` — PM edits epic name/description from epic details.
13. `epic-progress-updates.scenario.spec.ts` — epic progress bar updates when tickets move to DONE.
14. `epic-ticket-list.scenario.spec.ts` — open epic, see its ticket list.

### Tickets
15. `ticket-details-overview.scenario.spec.ts` — PM opens a ticket and sees full details layout (status, priority, assignee, description).
16. `assign-ticket-to-user.scenario.spec.ts` — PM assigns a ticket to a user.
17. `link-ticket-to-epic.scenario.spec.ts` — PM links an existing ticket to an epic via edit modal.
18. `change-ticket-priority.scenario.spec.ts` — PM changes ticket priority.
19. `filter-tickets-by-status.scenario.spec.ts` — PM filters project tickets by status.
20. `sort-tickets-by-priority.scenario.spec.ts` — PM sorts tickets by priority.

### Comments
21. `add-comment-to-ticket.scenario.spec.ts` — PM adds a comment on a ticket.
22. `edit-own-comment.scenario.spec.ts` — PM edits own comment.
23. `delete-own-comment.scenario.spec.ts` — PM deletes own comment.

### Workflows (V2)
24. `create-custom-workflow.scenario.spec.ts` — admin creates a custom workflow for the org (if UI exposed; else skip).
25. `apply-workflow-to-project.scenario.spec.ts` — PM selects custom workflow on project (if UI exposed; else skip).

### Cross-cutting
26. `read-only-user-view.scenario.spec.ts` — read_access user sees tickets but cannot create (buttons absent/disabled).
27. `permission-restricted-nav.scenario.spec.ts` — PM does NOT see Users/Organizations nav links.

> If a scenario's UI is not implemented, skip it and record that fact in the scenario file as a top-comment reason; don't stub.

### Promote-or-delete list (existing regular e2e → scenarios)
- `create-project.spec.ts` — duplicates `create-project.scenario.spec.ts` happy path. **Trim:** remove any test that only asserts the happy-path create; keep the edge/negative tests (empty name, cancel, etc.). Do NOT delete the whole file — it has assertions the scenario doesn't.
- `login-flow.spec.ts` — "super admin can login" dup'd by new `login-happy-path.scenario.spec.ts`. **Trim that test**, keep logout + protected-route tests.
- `organizations.spec.ts` "super admin can create new organization" → covered by scenario. **Trim** that one test.
- `create-user.spec.ts` "can create a new user successfully" → covered by scenario. **Trim** that one test.

## API test list (50 new)

Gap-focused. File placement matches entity. All are deterministic `TestClient` calls, no PBT.

### `test_auth_api.py` — **6 new**
- A1 `test_login_with_deactivated_user_fails` — deactivated user login returns 401/403.
- A2 `test_login_after_password_change_old_password_fails` — old password invalidated post-change.
- A3 `test_protected_endpoint_with_malformed_bearer_header_401`.
- A4 `test_protected_endpoint_without_bearer_prefix_401`.
- A5 `test_token_for_deleted_user_rejected`.
- A6 `test_change_password_with_wrong_old_password_fails`.

### `test_user_api.py` — **6 new**
- U1 `test_create_user_with_duplicate_username_in_same_org_fails`.
- U2 `test_create_user_with_duplicate_email_in_same_org_fails`.
- U3 `test_create_user_in_nonexistent_org_404`.
- U4 `test_update_user_role_takes_effect_on_next_request`.
- U5 `test_list_users_scoped_to_org_for_admin`.
- U6 `test_read_user_cannot_list_users`.

### `test_organization_api.py` — **5 new**
- O1 `test_create_organization_with_duplicate_name_fails`.
- O2 `test_non_super_admin_cannot_create_organization`.
- O3 `test_list_organizations_only_own_for_non_super_admin`.
- O4 `test_delete_organization_cascades_projects` (or is blocked if has projects — assert whichever is spec).
- O5 `test_update_organization_name_reflected_in_get`.

### `test_project_api.py` — **5 new**
- P1 `test_create_project_in_org_outside_membership_forbidden`.
- P2 `test_list_projects_filters_to_user_org_only`.
- P3 `test_update_project_name_to_duplicate_in_same_org_fails`.
- P4 `test_read_user_can_get_project_but_cannot_update`.
- P5 `test_project_delete_cascades_or_blocks_with_tickets` (per spec).

### `test_ticket_api.py` — **8 new**
- T1 `test_create_ticket_with_assignee_outside_org_fails`.
- T2 `test_create_ticket_with_epic_in_different_project_fails`.
- T3 `test_transition_ticket_to_invalid_status_fails`.
- T4 `test_transition_ticket_follows_default_workflow_TODO_to_IN_PROGRESS_to_DONE`.
- T5 `test_reopen_ticket_from_DONE_to_IN_PROGRESS_allowed_or_blocked` (match spec).
- T6 `test_list_tickets_filters_by_status`.
- T7 `test_list_tickets_filters_by_assignee`.
- T8 `test_list_tickets_filters_by_priority`.

### `test_epic_api.py` — **5 new**
- E1 `test_create_epic_in_nonexistent_project_404`.
- E2 `test_list_epic_tickets_returns_only_tickets_linked_to_epic`.
- E3 `test_epic_progress_counts_reflect_ticket_statuses`.
- E4 `test_delete_epic_unlinks_tickets_or_blocks` (per spec).
- E5 `test_update_epic_name_conflict_in_project_fails` (if unique).

### `test_comment_api.py` — **5 new**
- C1 `test_read_user_can_list_comments_but_cannot_create` (per spec; else adjust).
- C2 `test_update_others_comment_forbidden`.
- C3 `test_delete_others_comment_forbidden`.
- C4 `test_comment_on_ticket_in_other_org_forbidden`.
- C5 `test_list_comments_chronological_order`.

### `test_activity_log_api.py` — **4 new**
- L1 `test_ticket_create_emits_activity_log_entry`.
- L2 `test_ticket_status_change_emits_activity_log_entry`.
- L3 `test_activity_log_filterable_by_entity_id`.
- L4 `test_activity_log_read_requires_appropriate_role`.

### `test_workflow_api.py` — **5 new**
- W1 `test_create_workflow_with_cyclic_transitions_rejected` (or allowed; match spec).
- W2 `test_create_workflow_with_single_status_rejected` (or minimum states per spec).
- W3 `test_assign_workflow_to_project_constrains_ticket_transitions`.
- W4 `test_remove_workflow_from_project_falls_back_to_default_statuses`.
- W5 `test_workflow_scoped_to_org`.

### `test_custom_workflow_validation.py` — **1 new**
- CW1 `test_workflow_with_unreachable_terminal_state_rejected` (or valid per spec — match current validator).

**Total new API tests: 50.**

## Execution

1. Backend-engineer implements 50 API tests. Each new test has `@pytest.mark.scenario` + `@pytest.mark.behavior(...)` where appropriate. Validation: `cd backend && ./devtools/run_all_agent_validations.sh`.
2. Frontend-engineer implements 25 scenarios. Validation: `npm run lint && npm run typecheck && npm run e2e`.
3. For each scenario, if the UI doesn't support the flow (e.g., no change-password UI), skip it and note the gap — do not fabricate UI. Report skipped scenarios back.
4. Trim overlapping existing e2e tests per the list above; keep file-level tests that still carry unique negative-path assertions.
5. Code-reviewer final pass.

## Non-goals
- No property-based tests (per user).
- No repository/domain layer changes.
- No spec edits unless a test uncovers a real spec ambiguity, in which case raise it — do not silently resolve.
