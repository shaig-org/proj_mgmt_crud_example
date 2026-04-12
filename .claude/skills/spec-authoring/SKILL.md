---
name: spec-authoring
description: How to write behavioral specifications in this project. Product-behavior-primary, REQ-ID format, inline status, main_spec as index only. Used by spec-author agent; also available to the main orchestrator when editing specs directly.
---

# Spec authoring rules

## Core principle: product behavior over technical details

**Product behavior**: what users or external systems can observe and verify.
**Technical detail**: implementation choices users cannot observe — omit these.

✅ GOOD — product behavior:
- "After creating a project, GET /projects/{id} returns that project with all submitted data."
- "When a user submits invalid data, the API returns an error response describing the invalid field."
- "Creating two projects with identical names both succeed."

❌ BAD — technical detail:
- "Project is written to the database."
- "The `projects` table has a row inserted."
- "ProjectORM instance is created."

## The "So what?" test
For every requirement, ask: *how would a user or external system know this happened?*
If there's no observable consequence, the requirement is wrong.

## File structure

### `docs/spec/main_spec.md` — INDEX ONLY
- Feature list, one-sentence rationale each.
- Status rollup (e.g., `🟢 10/10 (100%)`).
- Link to detailed spec.
- No requirement bodies. No detail.

### `docs/spec/detailed/<feature>_detailed_spec.md`
- Requirements with full detail.
- Inline status markers on each REQ.

## Requirement format

```markdown
### REQ-{FEATURE}-{NUMBER}: <short behavior description>
**Status**: 🔴 Not Implemented | ✅ Implemented | ⚠️ Needs Fix
**Type**: Product Behavior   (or: Technical Behavior — only when justified)

**Scenario**:
When <user/system action occurs>

**Observable Behavior**:
<what external systems can verify, high-level>

**Acceptance Criteria**:
- After <action>, <observable consequence>.
- <Another testable criterion>
- ...

**Edge Cases**:
- Minimum / maximum length inputs
- Unicode, special characters
- Optional vs required fields
- Concurrent operations
- Permission boundaries
- Cross-org isolation (where applicable)
- <Other edge cases from the scenario>
```

## REQ-ID discipline
- Format: `REQ-{FEATURE}-{NUMBER}`. Feature is short uppercase (PROJ, AUTH, TICKET, RBAC, ORG, COMMENT, WORKFLOW, EPIC, ACTIVITY, USER).
- Numbers never get reused or renumbered after approval.
- IDs appear in detailed spec, feature plan, and are referenced by tests in docstrings — keep them stable.

## Status markers (inline, no separate tracking file)
- `🔴 Not Implemented`
- `✅ Implemented`
- `⚠️ Needs Fix`
- Feature-level rollup in main_spec: `🟢 N/N (100%)`, `🟡 partial`, `🔴 not started`.

## Good example

```markdown
### REQ-PROJ-001: Project creation and retrieval
**Status**: ✅ Implemented
**Type**: Product Behavior

**Scenario**:
When a user with sufficient permissions creates a project with valid data (name, optional description).

**Observable Behavior**:
User can create a project and subsequently retrieve it via GET with all submitted data preserved.

**Acceptance Criteria**:
- After POST /projects with valid data, response includes a non-empty id and all submitted fields.
- Subsequent GET /projects/{id} returns the same project with matching data.
- Created project appears in GET /projects list for users in the same organization.
- Description is optional; creating without it succeeds.

**Edge Cases**:
- Maximum length name (255 chars) succeeds.
- Unicode characters in name succeed.
- Two projects with identical names both succeed.
- Special characters !@#$%^&*() in name succeed.
```

## What does NOT go in a spec

- ❌ Test code or pytest snippets.
- ❌ File paths or function names.
- ❌ Implementation plans (those belong in `docs/tasks/<feature>/plan.md`).
- ❌ Specific HTTP status codes as the behavior itself ("returns 201") — state the observable consequence instead ("returns a new project ID that can be used to retrieve it"). Status codes ARE acceptable as part of acceptance criteria when they're the externally observable signal (422 on validation, 404 on missing, 403 on forbidden).
- ❌ Reference to specific database tables or ORM classes.

## When technical behavior is acceptable

Rarely. Only for:
- Security properties phrased observably: "Cannot log in using a stored password value" (not "passwords are hashed").
- Performance under observable load: "1000 sequential requests complete without error."
- Resource cleanup with observable consequence.

Always prefer rephrasing to observable behavior.

## Updating statuses
- Simple 🔴 → ✅ flips can be made by an engineer after a requirement is fully tested and passing validation.
- Any content change (new/modified requirement, edge case added, scenario changed) goes through spec-author.
