---
description: Implement an approved feature plan. Routes to backend-engineer and/or frontend-engineer based on plan scope.
---

Implement the following feature from its approved plan:

$ARGUMENTS

Steps:
1. Locate the plan at `docs/tasks/<feature>/plan.md`. Confirm it is ✅ Approved. If not, STOP and route to `feature-planner`.
2. For backend work: dispatch `backend-engineer`.
3. For frontend work: dispatch `frontend-engineer` AFTER the backend contract exists and its tests pass.
4. When engineers report complete, dispatch `code-reviewer`.
5. On 🔴 review verdict, loop back to the relevant engineer. On ✅, mark the plan Done and update spec statuses.
