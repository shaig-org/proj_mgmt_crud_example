# Main Specification — Multi-Tenant Project Management System

Index of features. Each links to a detailed spec. Full requirements live in `detailed/`.
For spec authoring rules, invoke the `spec-authoring` skill (or see `.claude/skills/spec-authoring/SKILL.md`).

## Overview
Multi-tenant project management backend:
- Organizations (tenants) with isolated data
- Role-based access (Super Admin, Admin, Project Manager, Write, Read)
- Projects, Tickets, Epics, Comments
- Activity logs with permission-based access
- Custom per-project workflows

## Features

| Feature | Status | Version | Rationale (one line) | Spec |
|---|---|---|---|---|
| Stub Entity Template | 🟢 4/4 | scaffolding | Template for new entities showing every layer | (in-code) |
| User Authentication | 🟢 6/6 | V1 | Secure login with bearer tokens and password change | [auth](detailed/auth_detailed_spec.md) |
| User Management | 🟢 8/8 | V1 | Admin CRUD for users with generated passwords and roles | [users](detailed/users_detailed_spec.md) |
| Multi-Tenancy (Organizations) | 🟢 6/6 | V1 | Tenant isolation — each org has its own data, no cross-access | [organizations](detailed/organizations_detailed_spec.md) |
| Role-Based Access Control | 🟢 10/10 | V1 | Five roles govern what users can do and see | [rbac](detailed/rbac_detailed_spec.md) |
| Projects | 🟢 11/11 | V1 | Containers for tickets within an organization | [projects](detailed/projects_detailed_spec.md) |
| Tickets | 🟢 17/17 | V1 | Core work items with status, assignees, workflow validation | [tickets](detailed/tickets_detailed_spec.md) |
| Epics | 🟢 10/10 | V1 | Group related tickets across projects | [epics](detailed/epics_detailed_spec.md) |
| Comments | 🟢 8/8 | V1 | Threaded discussion on tickets (no attachments in V1) | [comments](detailed/comments_detailed_spec.md) |
| Activity Logs & Audit Trails | 🟢 7/7 | V1 | Immutable audit log with permission-filtered reads | [activity](detailed/activity_logs_detailed_spec.md) |
| Custom Workflows | 🟢 10/10 | V2 | Per-org ticket status sets beyond TODO/IN_PROGRESS/DONE | [workflows](detailed/workflows_detailed_spec.md) |

## Future (not yet planned)
- **Custom Fields** (V2) — user-defined fields on tickets
- **Attachments** (V2) — file upload on tickets and comments

## Status legend
- 🔴 Not started · 🟡 Partial · 🟢 Fully implemented
- Requirement-level: 🔴 Not Implemented · ✅ Implemented · ⚠️ Needs Fix

## Related
- Architecture: [`docs/tech_spec/high_level_architecture.md`](../tech_spec/high_level_architecture.md)
- Principles: [`docs/architecture/principles.md`](../architecture/principles.md)
- Spec authoring rules: `.claude/skills/spec-authoring/SKILL.md`
