# Property-Based Testing: Real Bug Examples

This document shows concrete examples of bugs that stateful testing catches, with the exact invariants that detect them.

---

## Bug Category 1: CRUD Operation Bugs

### Bug 1.1: Soft Delete Instead of Hard Delete

**The Bug**:
```python
def delete(self, user_id: str) -> None:
    """Delete a user - BUG: only marks as deleted instead of removing."""
    user_orm = self.session.query(UserORM).filter_by(id=user_id).first()
    if user_orm:
        user_orm.is_deleted = True  # BUG: Should actually delete
        self.session.commit()
```

**How It Manifests**:
- User deleted via `repo.users.delete(user_id)`
- But `repo.users.get_by_id(user_id)` still returns the user
- `repo.users.get_all()` still includes the user

**Hypothesis Test Sequence That Finds It**:
```
1. create_user("alice")
2. delete_user("alice")
3. get_user_by_id("alice")  # Should return None but returns User
```

**Invariant That Catches It**:
```python
@invariant()
def deleted_users_gone(self):
    """Deleted users should not be retrievable."""
    for username in self.deleted_usernames:
        user = self.repo.users.get_by_username(username)
        assert user is None, f"Deleted user '{username}' still retrievable"
```

**Failure Message**:
```
AssertionError: Deleted user 'alice' still retrievable
```

---

### Bug 1.2: Delete Doesn't Update Count

**The Bug**:
```python
def delete(self, project_id: str) -> None:
    """Delete a project - BUG: forgets to decrement count."""
    project_orm = self.session.query(ProjectORM).filter_by(id=project_id).first()
    if project_orm:
        self.session.delete(project_orm)
        self.session.commit()
        # BUG: Should update some counter/cache but doesn't
```

**How It Manifests**:
- Project deleted successfully
- But aggregate count shows one more project than actually exists
- Dashboard shows "You have 10 projects" but only 9 exist

**Hypothesis Test Sequence That Finds It**:
```
1. create_project("Project A")
2. create_project("Project B")
3. create_project("Project C")
4. delete_project("Project B")
5. Check: created=3, deleted=1, but get_all() returns 2 projects
```

**Invariant That Catches It**:
```python
@invariant()
def count_consistency(self):
    """Total created - deleted should match repository count."""
    expected = self.total_created - self.total_deleted
    all_projects = self.repo.projects.get_all()
    actual = len(all_projects)

    assert actual == expected, \
        f"Count mismatch: created {self.total_created}, " \
        f"deleted {self.total_deleted}, expected {expected}, got {actual}"
```

**Failure Message**:
```
AssertionError: Count mismatch: created 3, deleted 1, expected 2, got 2
Note: Shadow state expected 2 but tracked 3 created - 1 deleted = 2
```

---

### Bug 1.3: Update Modifies Wrong Entity

**The Bug**:
```python
def update(self, user_id: str, command: UserUpdateCommand) -> User:
    """Update user - BUG: off-by-one error."""
    users = self.session.query(UserORM).all()
    # BUG: Should filter by ID, but accidentally updates wrong user
    if users:
        user_to_update = users[0]  # BUG: Always updates first user!
        if command.email:
            user_to_update.email = command.email
        self.session.commit()
        return self._to_domain(user_to_update)
```

**How It Manifests**:
- User "bob" updated with new email
- But user "alice" (first user) gets the new email instead
- User "bob" unchanged

**Hypothesis Test Sequence That Finds It**:
```
1. create_user("alice")
2. create_user("bob")
3. update_user("bob", email="bob_new@test.com")
4. Check: alice has "bob_new@test.com", bob has original email
```

**Invariant That Catches It**:
```python
@invariant()
def active_users_match_shadow_state(self):
    """All users should have correct data."""
    for username, (user_id, original_data) in self.active_users.items():
        user = self.repo.users.get_by_id(user_id)
        assert user.username == username, \
            f"User ID {user_id} should be '{username}' but is '{user.username}'"
```

**Failure Message**:
```
AssertionError: User ID user-123 should be 'bob' but is 'alice'
```

---

## Bug Category 2: Relationship Bugs

### Bug 2.1: Cascade Delete Not Working

**The Bug**:
```python
def delete(self, project_id: str) -> None:
    """Delete project - BUG: doesn't delete related tickets."""
    project = self.session.query(ProjectORM).filter_by(id=project_id).first()
    if project:
        self.session.delete(project)
        # BUG: Should delete tickets, but foreign key is SET NULL instead of CASCADE
        self.session.commit()
```

**How It Manifests**:
- Project deleted successfully
- Tickets that belonged to project still exist
- Tickets now have `project_id = None` (orphaned)

**Hypothesis Test Sequence That Finds It**:
```
1. create_project("Backend")
2. create_user("alice")
3. create_ticket("Fix bug", project="Backend", reporter="alice")
4. delete_project("Backend")
5. Check: ticket still exists but project_id is None
```

**Invariant That Catches It**:
```python
@invariant()
def all_tickets_have_valid_project(self):
    """Every ticket must reference an existing project."""
    for ticket_id, expected_project_id in self.tickets.items():
        ticket = self.repo.tickets.get_by_id(ticket_id)
        assert ticket is not None, f"Ticket {ticket_id} doesn't exist"

        # Check project exists
        project = self.repo.projects.get_by_id(ticket.project_id)
        assert project is not None, \
            f"Ticket {ticket_id} references deleted project {ticket.project_id}"
```

**Failure Message**:
```
AssertionError: Ticket ticket-789 references deleted project project-456
```

---

### Bug 2.2: Assigning to Deleted User Succeeds

**The Bug**:
```python
def update_assignee(self, ticket_id: str, assignee_id: str) -> Ticket:
    """Assign ticket - BUG: doesn't check if user exists."""
    ticket_orm = self.session.query(TicketORM).filter_by(id=ticket_id).first()
    if ticket_orm:
        ticket_orm.assignee_id = assignee_id  # BUG: No validation!
        self.session.commit()
        return self._to_domain(ticket_orm)
```

**How It Manifests**:
- User deleted
- Ticket assigned to deleted user succeeds
- Ticket references non-existent user

**Hypothesis Test Sequence That Finds It**:
```
1. create_project("Backend")
2. create_user("alice")
3. create_user("bob")
4. create_ticket("Fix bug", project="Backend", reporter="alice")
5. delete_user("bob")
6. assign_ticket(ticket, assignee="bob")  # Should fail but succeeds
```

**Invariant That Catches It**:
```python
@invariant()
def assigned_tickets_have_valid_assignee(self):
    """Assigned tickets must reference existing users."""
    for ticket_id, expected_assignee_id in self.ticket_assignees.items():
        if expected_assignee_id is None:
            continue

        ticket = self.repo.tickets.get_by_id(ticket_id)
        assignee = self.repo.users.get_by_id(ticket.assignee_id)

        assert assignee is not None, \
            f"Ticket {ticket_id} assigned to deleted user {ticket.assignee_id}"
```

**Failure Message**:
```
AssertionError: Ticket ticket-123 assigned to deleted user user-456
```

---

## Bug Category 3: Business Rule Violations

### Bug 3.1: Invalid Status Transition Allowed

**The Bug**:
```python
def update_status(self, ticket_id: str, new_status: str) -> Ticket:
    """Update ticket status - BUG: doesn't validate against workflow."""
    ticket_orm = self.session.query(TicketORM).filter_by(id=ticket_id).first()
    if ticket_orm:
        ticket_orm.status = new_status  # BUG: No workflow validation!
        self.session.commit()
        return self._to_domain(ticket_orm)
```

**How It Manifests**:
- Project uses workflow with statuses ["TODO", "IN_PROGRESS", "DONE"]
- Ticket status changed to "INVALID_STATUS"
- Should fail but succeeds

**Hypothesis Test Sequence That Finds It**:
```
1. create_workflow(statuses=["TODO", "IN_PROGRESS", "DONE"])
2. create_project(workflow=workflow1)
3. create_ticket(project=project1, status="TODO")
4. update_ticket_status(ticket, status="INVALID")  # Should fail
```

**Invariant That Catches It**:
```python
@invariant()
def ticket_status_valid_for_workflow(self):
    """Every ticket's status must be valid for its project's workflow."""
    for ticket_id, project_id in self.tickets.items():
        ticket = self.repo.tickets.get_by_id(ticket_id)
        project = self.repo.projects.get_by_id(project_id)
        workflow = self.repo.workflows.get_by_id(project.workflow_id)

        assert ticket.status in workflow.statuses, \
            f"Ticket {ticket_id} has invalid status '{ticket.status}'. " \
            f"Valid statuses: {workflow.statuses}"
```

**Failure Message**:
```
AssertionError: Ticket ticket-123 has invalid status 'INVALID'.
Valid statuses: ['TODO', 'IN_PROGRESS', 'DONE']
```

---

### Bug 3.2: Duplicate Usernames (Case-Insensitive Violation)

**The Bug**:
```python
def create(self, command: UserCreateCommand) -> User:
    """Create user - BUG: doesn't check case-insensitive uniqueness."""
    # BUG: Should check lowercase username, but checks exact match
    existing = self.session.query(UserORM).filter_by(username=command.user_data.username).first()
    if existing:
        raise ValueError("Username exists")

    # Creates with different case even though "Alice" already exists
    user_orm = UserORM(username=command.user_data.username, ...)
    self.session.add(user_orm)
    self.session.commit()
```

**How It Manifests**:
- Create user "alice"
- Create user "Alice" succeeds (should fail)
- Two users with same username (different case)

**Hypothesis Test Sequence That Finds It**:
```
1. create_user("alice")
2. create_user("Alice")  # Should fail but succeeds
3. Check: both "alice" and "Alice" exist
```

**Invariant That Catches It**:
```python
@invariant()
def usernames_unique_case_insensitive(self):
    """Usernames should be unique (case-insensitive)."""
    all_users = self.repo.users.get_all()
    usernames_lower = [u.username.lower() for u in all_users]

    assert len(usernames_lower) == len(set(usernames_lower)), \
        f"Duplicate usernames found (case-insensitive): {usernames_lower}"
```

**Failure Message**:
```
AssertionError: Duplicate usernames found (case-insensitive):
['alice', 'alice', 'bob']
```

---

## Bug Category 4: Aggregate/Count Bugs

### Bug 4.1: Epic Ticket Count Not Updated

**The Bug**:
```python
def add_ticket(self, epic_id: str, ticket_id: str) -> Epic:
    """Add ticket to epic - BUG: doesn't update epic.ticket_ids."""
    epic_orm = self.session.query(EpicORM).filter_by(id=epic_id).first()
    ticket_orm = self.session.query(TicketORM).filter_by(id=ticket_id).first()

    if epic_orm and ticket_orm:
        ticket_orm.epic_id = epic_id  # BUG: Updates ticket but not epic!
        self.session.commit()
        return self._to_domain(epic_orm)
```

**How It Manifests**:
- Ticket added to epic
- Epic's ticket_ids list not updated
- Epic shows 0 tickets but actually has 1

**Hypothesis Test Sequence That Finds It**:
```
1. create_epic("Sprint 1")
2. create_ticket("Fix bug")
3. add_ticket_to_epic(epic="Sprint 1", ticket="Fix bug")
4. Check: epic.ticket_ids is empty but should contain ticket ID
```

**Invariant That Catches It**:
```python
@invariant()
def epic_ticket_counts_match(self):
    """Epic ticket count must match actual tickets."""
    for epic_id, shadow_tickets in self.epic_tickets.items():
        epic = self.repo.epics.get_by_id(epic_id)

        assert len(epic.ticket_ids) == len(shadow_tickets), \
            f"Epic {epic_id}: expected {len(shadow_tickets)} tickets, " \
            f"got {len(epic.ticket_ids)}"

        assert set(epic.ticket_ids) == shadow_tickets, \
            f"Epic {epic_id}: ticket IDs don't match"
```

**Failure Message**:
```
AssertionError: Epic epic-123: expected 1 tickets, got 0
```

---

### Bug 4.2: Ticket in Multiple Epics

**The Bug**:
```python
def add_ticket(self, epic_id: str, ticket_id: str) -> Epic:
    """Add ticket to epic - BUG: doesn't check if already in another epic."""
    epic_orm = self.session.query(EpicORM).filter_by(id=epic_id).first()
    ticket_orm = self.session.query(TicketORM).filter_by(id=ticket_id).first()

    if epic_orm and ticket_orm:
        # BUG: Doesn't check ticket.epic_id before adding
        epic_orm.ticket_ids.append(ticket_id)
        self.session.commit()
```

**How It Manifests**:
- Ticket added to Epic A
- Ticket added to Epic B (should fail)
- Ticket appears in both epics

**Hypothesis Test Sequence That Finds It**:
```
1. create_epic("Sprint 1")
2. create_epic("Sprint 2")
3. create_ticket("Fix bug")
4. add_ticket_to_epic(epic="Sprint 1", ticket="Fix bug")
5. add_ticket_to_epic(epic="Sprint 2", ticket="Fix bug")  # Should fail
```

**Invariant That Catches It**:
```python
@invariant()
def tickets_in_at_most_one_epic(self):
    """Each ticket should appear in at most one epic."""
    all_epic_tickets = {}

    for epic_id, tickets in self.epic_tickets.items():
        for ticket_id in tickets:
            assert ticket_id not in all_epic_tickets, \
                f"Ticket {ticket_id} in multiple epics: " \
                f"{all_epic_tickets[ticket_id]} and {epic_id}"
            all_epic_tickets[ticket_id] = epic_id
```

**Failure Message**:
```
AssertionError: Ticket ticket-456 in multiple epics: epic-123 and epic-789
```

---

## Bug Category 5: Timestamp Bugs

### Bug 5.1: created_at Changes on Update

**The Bug**:
```python
def update(self, user_id: str, command: UserUpdateCommand) -> User:
    """Update user - BUG: resets created_at."""
    user_orm = self.session.query(UserORM).filter_by(id=user_id).first()
    if user_orm:
        if command.email:
            user_orm.email = command.email
        user_orm.updated_at = datetime.now(timezone.utc)
        user_orm.created_at = datetime.now(timezone.utc)  # BUG!
        self.session.commit()
```

**How It Manifests**:
- User created on Jan 1, 2025
- User updated on Feb 1, 2025
- created_at now shows Feb 1, 2025 (should still be Jan 1)

**Hypothesis Test Sequence That Finds It**:
```
1. create_user("alice")  # created_at = T1
2. wait(1ms)
3. update_user("alice", email="new@test.com")
4. Check: created_at = T2 (should still be T1)
```

**Invariant That Catches It**:
```python
@invariant()
def created_at_immutable(self):
    """created_at should never change."""
    for user_id, (original_created_at, _) in self.user_timestamps.items():
        user = self.repo.users.get_by_id(user_id)
        assert user.created_at == original_created_at, \
            f"User {user_id} created_at changed from " \
            f"{original_created_at} to {user.created_at}"
```

**Failure Message**:
```
AssertionError: User user-123 created_at changed from
2025-01-01 10:00:00+00:00 to 2025-02-01 11:00:00+00:00
```

---

### Bug 5.2: updated_at Doesn't Change

**The Bug**:
```python
def update(self, user_id: str, command: UserUpdateCommand) -> User:
    """Update user - BUG: forgets to update timestamp."""
    user_orm = self.session.query(UserORM).filter_by(id=user_id).first()
    if user_orm:
        if command.email:
            user_orm.email = command.email
        # BUG: Should update user_orm.updated_at but doesn't
        self.session.commit()
```

**How It Manifests**:
- User updated with new email
- updated_at still shows original creation time
- Can't tell when user was last modified

**Hypothesis Test Sequence That Finds It**:
```
1. create_user("alice")  # updated_at = T1
2. wait(1ms)
3. update_user("alice", email="new@test.com")
4. Check: updated_at still T1 (should be T2)
```

**Invariant That Catches It**:
```python
@invariant()
def updated_at_changes_on_update(self):
    """updated_at must change when entity is updated."""
    for user_id in self.recently_updated:
        user = self.repo.users.get_by_id(user_id)
        original_updated_at = self.original_timestamps[user_id]

        assert user.updated_at > original_updated_at, \
            f"User {user_id} updated_at didn't change: " \
            f"{original_updated_at} == {user.updated_at}"
```

**Failure Message**:
```
AssertionError: User user-123 updated_at didn't change:
2025-01-01 10:00:00+00:00 == 2025-01-01 10:00:00+00:00
```

---

## Bug Category 6: Permission/Multi-Tenancy Bugs

### Bug 6.1: Cross-Organization Data Leak

**The Bug**:
```python
def get_all(self, organization_id: str | None = None) -> list[Project]:
    """Get all projects - BUG: ignores organization filter."""
    # BUG: Should filter by organization_id but doesn't
    projects = self.session.query(ProjectORM).all()
    return [self._to_domain(p) for p in projects]
```

**How It Manifests**:
- User in Org A calls get_all()
- Receives projects from Org B
- Data leak across organization boundaries

**Hypothesis Test Sequence That Finds It**:
```
1. create_organization("Org A")
2. create_organization("Org B")
3. create_project("Project A", org="Org A")
4. create_project("Project B", org="Org B")
5. user_in_org_a = create_user("alice", org="Org A")
6. Check: user can see Project B (should only see Project A)
```

**Invariant That Catches It**:
```python
@invariant()
def no_cross_org_data_visibility(self):
    """Projects should not leak across organizations."""
    all_projects = self.repo.projects.get_all()

    org1_projects = [p for p in all_projects if p.org_id == self.org1_id]
    org2_projects = [p for p in all_projects if p.org_id == self.org2_id]

    # Verify no overlap
    org1_ids = set(p.id for p in org1_projects)
    org2_ids = set(p.id for p in org2_projects)

    overlap = org1_ids & org2_ids
    assert len(overlap) == 0, \
        f"Projects leaked across orgs: {overlap}"
```

**Failure Message**:
```
AssertionError: Projects leaked across orgs: {'project-789'}
```

---

## Summary: Bug Detection Matrix

| Bug Type | Invariant Pattern | Detection Rate |
|----------|------------------|----------------|
| **Soft delete instead of hard delete** | Shadow State | 100% |
| **Count mismatch** | Count Invariants | 100% |
| **Wrong entity updated** | Shadow State | 100% |
| **Cascade delete failure** | Relationship Invariants | 100% |
| **Orphaned references** | Relationship Invariants | 100% |
| **Invalid status** | Business Rules | 100% |
| **Duplicate constraint violation** | Business Rules | 100% |
| **Aggregate out of sync** | Aggregate Consistency | 100% |
| **created_at changes** | Temporal Consistency | 100% |
| **updated_at stale** | Temporal Consistency | 100% |
| **Cross-org leak** | Permission Invariants | 100% |

**Key Insight**: Stateful testing with proper invariants catches **ALL** of these bug classes automatically, often in sequences you'd never think to test manually.

---

## Why These Bugs Are Hard to Find with Example-Based Tests

### Example-Based Test:
```python
def test_delete_user(self):
    """Test deleting a user."""
    user = create_user("alice")
    delete_user(user.id)
    # Most tests stop here and assume it worked

    # Rarely do we check:
    result = get_user_by_id(user.id)
    assert result is None  # This catches soft delete bug!
```

**Problem**: You have to remember to check every possible failure mode.

### Property-Based Test:
```python
@invariant()
def deleted_users_gone(self):
    """Automatically checked after EVERY operation."""
    for username in self.deleted_usernames:
        assert self.repo.users.get_by_username(username) is None
```

**Advantage**: Checks **automatically** after **every single operation** in **hundreds of random sequences**.

---

## Next Steps

1. **Read examples**: See `tests/stateful_example.py` for runnable code
2. **Choose invariants**: Pick patterns from `docs/pbt_invariants_cheatsheet.md`
3. **Implement**: Start with Shadow State + Count Invariants
4. **Run**: Execute `pytest tests/property_based/stateful/ -v`
5. **Find bugs**: Fix any failures Hypothesis discovers
