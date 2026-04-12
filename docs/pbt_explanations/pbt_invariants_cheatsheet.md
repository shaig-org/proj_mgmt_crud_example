# Property-Based Testing: Invariants Cheatsheet

## Quick Reference: 7 Invariant Patterns

### 1. Shadow State Consistency ⭐⭐⭐

**What**: Maintain Python dict/set mirroring what should exist in database.

**When**: All CRUD operations.

**Template**:
```python
class MyStateMachine(RuleBasedStateMachine):
    def __init__(self):
        self.active_entities = {}     # What SHOULD exist
        self.deleted_entities = set() # What SHOULD NOT exist

    @invariant()
    def active_entities_exist(self):
        """Active entities in shadow state must exist in DB."""
        for entity_id, data in self.active_entities.items():
            entity = self.repo.get_by_id(entity_id)
            assert entity is not None
            assert entity.data == data

    @invariant()
    def deleted_entities_gone(self):
        """Deleted entities must not be retrievable."""
        for entity_id in self.deleted_entities:
            entity = self.repo.get_by_id(entity_id)
            assert entity is None
```

**Bugs it finds**:
- Soft delete instead of hard delete
- Deleted entity still retrievable
- Update modifies wrong entity

---

### 2. Count Invariants ⭐⭐

**What**: Track totals and verify arithmetic.

**When**: Add/remove operations, filtering.

**Template**:
```python
class MyStateMachine(RuleBasedStateMachine):
    def __init__(self):
        self.total_created = 0
        self.total_deleted = 0
        self.active_count = 0
        self.archived_count = 0

    @invariant()
    def count_consistency(self):
        """Total - deleted = active + archived."""
        expected = self.total_created - self.total_deleted
        actual = self.active_count + self.archived_count
        assert actual == expected

        # Verify DB matches
        all_entities = self.repo.get_all()
        assert len(all_entities) == expected
```

**Bugs it finds**:
- Archive doesn't update counter
- Delete doesn't actually delete
- Unarchive creates duplicate

---

### 3. Relationship Invariants ⭐⭐⭐

**What**: Verify foreign keys always reference existing entities.

**When**: Entities with relationships (tickets → projects, users → orgs).

**Template**:
```python
@invariant()
def all_tickets_have_valid_project(self):
    """Every ticket must reference an existing project."""
    for ticket_id in self.tickets:
        ticket = self.repo.tickets.get_by_id(ticket_id)
        project = self.repo.projects.get_by_id(ticket.project_id)
        assert project is not None, \
            f"Ticket {ticket_id} references non-existent project"

@invariant()
def all_tickets_have_valid_reporter(self):
    """Every ticket must reference an existing user."""
    for ticket_id in self.tickets:
        ticket = self.repo.tickets.get_by_id(ticket_id)
        reporter = self.repo.users.get_by_id(ticket.reporter_id)
        assert reporter is not None, \
            f"Ticket {ticket_id} references non-existent reporter"
```

**Bugs it finds**:
- Foreign key constraints not enforced
- Cascade delete not working
- Assigning to deleted entity succeeds

---

### 4. Business Rule Invariants ⭐⭐⭐

**What**: Domain-specific rules always hold.

**When**: Workflows, status transitions, validation rules.

**Template**:
```python
@invariant()
def ticket_status_valid_for_workflow(self):
    """Ticket status must be in project's workflow."""
    for ticket_id, project_id in self.tickets.items():
        ticket = self.repo.tickets.get_by_id(ticket_id)
        project = self.repo.projects.get_by_id(project_id)
        workflow = self.repo.workflows.get_by_id(project.workflow_id)

        assert ticket.status in workflow.statuses, \
            f"Ticket has invalid status '{ticket.status}'"

@invariant()
def workflow_statuses_unique(self):
    """Workflow statuses have no duplicates."""
    for workflow_id in self.workflows:
        workflow = self.repo.workflows.get_by_id(workflow_id)
        assert len(workflow.statuses) == len(set(workflow.statuses))
```

**Bugs it finds**:
- Invalid status transitions allowed
- Validation skipped in certain paths
- Business rules not enforced

---

### 5. Aggregate Consistency ⭐⭐

**What**: Computed values match their components.

**When**: Counts, derived data, aggregations.

**Template**:
```python
@invariant()
def epic_ticket_counts_match(self):
    """Epic ticket count must equal actual tickets."""
    for epic_id, shadow_tickets in self.epics.items():
        epic = self.repo.epics.get_by_id(epic_id)

        # Count matches
        assert len(epic.ticket_ids) == len(shadow_tickets)

        # IDs match exactly
        assert set(epic.ticket_ids) == shadow_tickets

@invariant()
def tickets_in_at_most_one_epic(self):
    """Each ticket appears in at most one epic."""
    all_tickets = {}
    for epic_id, tickets in self.epics.items():
        for ticket_id in tickets:
            assert ticket_id not in all_tickets, \
                f"Ticket {ticket_id} in multiple epics"
            all_tickets[ticket_id] = epic_id
```

**Bugs it finds**:
- Count not updated on add/remove
- Entity appears in multiple aggregates
- Computed value out of sync

---

### 6. Temporal Consistency ⭐

**What**: Timestamps and time-based properties correct.

**When**: created_at/updated_at, ordering, audit logs.

**Template**:
```python
@invariant()
def created_before_updated(self):
    """created_at <= updated_at for all entities."""
    for entity_id in self.entities:
        entity = self.repo.get_by_id(entity_id)
        assert entity.created_at <= entity.updated_at

@invariant()
def timestamps_are_utc(self):
    """All timestamps are UTC."""
    for entity_id in self.entities:
        entity = self.repo.get_by_id(entity_id)
        assert entity.created_at.tzinfo == timezone.utc
        assert entity.updated_at.tzinfo == timezone.utc

@invariant()
def update_changes_updated_at(self):
    """Update must change updated_at."""
    for entity_id, (created_at, original_updated_at) in self.timestamps.items():
        entity = self.repo.get_by_id(entity_id)
        # After update, updated_at should be newer
        if self.was_updated[entity_id]:
            assert entity.updated_at > original_updated_at
```

**Bugs it finds**:
- Timestamps not UTC
- created_at changes on update
- updated_at doesn't change
- Time went backwards

---

### 7. Permission Invariants ⭐⭐

**What**: Authorization boundaries enforced.

**When**: Multi-tenant systems, role-based access.

**Template**:
```python
@invariant()
def users_belong_to_one_org(self):
    """Each user belongs to exactly one organization."""
    all_users = set()
    for org_id, users in self.users_by_org.items():
        for user_id in users:
            assert user_id not in all_users
            all_users.add(user_id)

            user = self.repo.users.get_by_id(user_id)
            assert user.organization_id == org_id

@invariant()
def no_cross_org_data_access(self):
    """Users can't access other org's data."""
    all_projects = self.repo.projects.get_all()

    org1_projects = [p for p in all_projects if p.org_id == self.org1_id]
    org2_projects = [p for p in all_projects if p.org_id == self.org2_id]

    # Verify no overlap
    org1_ids = set(p.id for p in org1_projects)
    org2_ids = set(p.id for p in org2_projects)
    assert len(org1_ids & org2_ids) == 0
```

**Bugs it finds**:
- Cross-org data leaks
- User assigned to multiple orgs
- Authorization not enforced

---

## Complete State Machine Template

```python
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, precondition, Bundle
from hypothesis import strategies as st

class EntityStateMachine(RuleBasedStateMachine):
    """State machine for testing Entity operations."""

    def __init__(self):
        super().__init__()
        # 1. Initialize repository
        self.repo = get_test_repository()

        # 2. Setup required entities
        self.org = create_test_org_via_repo(self.repo)

        # 3. Initialize shadow state
        self.active_entities = {}      # Shadow state
        self.deleted_entities = set()

        # 4. Initialize counters
        self.total_created = 0
        self.total_deleted = 0

        # 5. Initialize relationships
        self.entity_relationships = {}

    # =========================================================================
    # OPERATIONS (Rules)
    # =========================================================================

    @rule(name=st.text(min_size=1, max_size=255))
    def create_entity(self, name: str):
        """Create an entity."""
        # Skip if already exists
        assume(name not in self.active_entities)

        # Perform operation
        entity = self.repo.entities.create(...)

        # Update shadow state
        self.active_entities[name] = entity.id
        self.total_created += 1

    @rule()
    @precondition(lambda self: len(self.active_entities) > 0)
    def update_entity(self):
        """Update an entity."""
        name = list(self.active_entities.keys())[0]
        entity_id = self.active_entities[name]

        # Perform operation
        self.repo.entities.update(entity_id, ...)

    @rule()
    @precondition(lambda self: len(self.active_entities) > 0)
    def delete_entity(self):
        """Delete an entity."""
        name = list(self.active_entities.keys())[0]
        entity_id = self.active_entities[name]

        # Perform operation
        self.repo.entities.delete(entity_id)

        # Update shadow state
        del self.active_entities[name]
        self.deleted_entities.add(name)
        self.total_deleted += 1

    @rule()
    @precondition(lambda self: len(self.active_entities) > 0)
    def get_entity(self):
        """Retrieve an entity."""
        name = list(self.active_entities.keys())[0]
        entity_id = self.active_entities[name]

        entity = self.repo.entities.get_by_id(entity_id)
        assert entity is not None

    # =========================================================================
    # INVARIANTS (Checked after every operation)
    # =========================================================================

    @invariant()
    def active_entities_exist(self):
        """Pattern 1: Shadow state - active entities exist."""
        for name, entity_id in self.active_entities.items():
            entity = self.repo.entities.get_by_id(entity_id)
            assert entity is not None, f"Entity '{name}' should exist"

    @invariant()
    def deleted_entities_gone(self):
        """Pattern 1: Shadow state - deleted entities gone."""
        for name in self.deleted_entities:
            entity = self.repo.entities.get_by_name(name)
            assert entity is None, f"Entity '{name}' should be deleted"

    @invariant()
    def count_consistency(self):
        """Pattern 2: Count invariants."""
        expected = self.total_created - self.total_deleted
        actual = len(self.active_entities)
        assert actual == expected, \
            f"Count mismatch: expected {expected}, got {actual}"

    @invariant()
    def entities_have_valid_ids(self):
        """All entities have non-empty IDs."""
        for name, entity_id in self.active_entities.items():
            assert entity_id, f"Entity '{name}' has empty ID"

# Convert to pytest test case
TestEntityCRUD = EntityStateMachine.TestCase
```

---

## Invariant Selection Guide

**Always implement:**
- ✅ Pattern 1: Shadow State (foundation for all tests)
- ✅ Pattern 2: Count Invariants (catches off-by-one errors)

**Implement when applicable:**
- ✅ Pattern 3: Relationships (if foreign keys exist)
- ✅ Pattern 4: Business Rules (if domain-specific logic)
- ✅ Pattern 5: Aggregates (if counts/derived data)
- ✅ Pattern 6: Temporal (if timestamps matter)
- ✅ Pattern 7: Permissions (if multi-tenant/roles)

---

## Common Invariant Anti-Patterns

### ❌ DON'T: Check implementation details

```python
# BAD: Queries database directly
@invariant()
def check_database_table(self):
    rows = self.db.execute("SELECT * FROM users")
    assert len(rows) == self.total_created
```

### ✅ DO: Check observable behavior

```python
# GOOD: Uses repository interface
@invariant()
def count_matches(self):
    all_users = self.repo.users.get_all()
    expected = self.total_created - self.total_deleted
    assert len(all_users) == expected
```

---

### ❌ DON'T: Duplicate operation logic

```python
# BAD: Reimplements business logic
@invariant()
def check_email_format(self):
    for user_id in self.users:
        user = self.repo.users.get_by_id(user_id)
        # Duplicates validation logic from domain models
        assert "@" in user.email
        assert "." in user.email
```

### ✅ DO: Check invariants, not validation

```python
# GOOD: Checks that validation was applied
@invariant()
def all_emails_are_valid(self):
    for user_id in self.users:
        user = self.repo.users.get_by_id(user_id)
        # Just verify email exists and is non-empty
        assert user.email
        # If validation was applied, email should be valid
        # (don't reimplement validation rules)
```

---

### ❌ DON'T: Test single operation in invariant

```python
# BAD: Only relevant right after create
@invariant()
def just_created_user_has_default_role(self):
    if self.last_created_user_id:
        user = self.repo.users.get_by_id(self.last_created_user_id)
        assert user.role == UserRole.ADMIN
```

### ✅ DO: Check properties that always hold

```python
# GOOD: True for ALL users at ALL times
@invariant()
def all_users_have_valid_role(self):
    for user_id in self.active_users:
        user = self.repo.users.get_by_id(user_id)
        assert user.role in [UserRole.ADMIN, UserRole.WRITE, UserRole.READ]
```

---

## Debugging Tips

### 1. Use `note()` for Visibility

```python
from hypothesis import note

@rule(username=usernames())
def create_user(self, username: str):
    note(f"Creating user: {username}")
    user = self.repo.users.create(...)
    note(f"Created with ID: {user.id}")
```

### 2. Add Assertion Messages

```python
@invariant()
def count_matches(self):
    expected = self.total_created - self.total_deleted
    actual = len(self.active_users)
    assert actual == expected, \
        f"Count mismatch: expected {expected} " \
        f"(created: {self.total_created}, deleted: {self.total_deleted}), " \
        f"but have {actual} active users"
```

### 3. Use Preconditions to Skip Invalid States

```python
@rule()
@precondition(lambda self: len(self.active_users) > 0)
def delete_user(self):
    """Only run when there are users to delete."""
    ...
```

### 4. Reproduce Failures

```python
# Hypothesis prints seed on failure
# Rerun with that seed:
pytest test_file.py --hypothesis-seed=12345
```

---

## Quick Start Checklist

**For each entity, implement:**

1. ☐ Shadow State invariants (active exist, deleted gone)
2. ☐ Count invariants (total - deleted = active)
3. ☐ ID validity (all IDs non-empty)
4. ☐ Required fields (all required fields present)

**If entity has relationships:**

5. ☐ Foreign key invariants (all references valid)
6. ☐ Relationship consistency (both sides match)

**If entity has business rules:**

7. ☐ Domain invariants (status in workflow, etc.)
8. ☐ Validation consistency (rules enforced)

**If entity has timestamps:**

9. ☐ Temporal invariants (created <= updated, UTC)

**If multi-tenant:**

10. ☐ Permission invariants (org boundaries enforced)

---

## Examples by Entity

### User CRUD
- Shadow State ✅
- Count Invariants ✅
- Relationship (→ Organization) ✅
- Business Rules (username unique, case-insensitive) ✅
- Temporal (created_at, updated_at) ✅
- Permissions (belongs to one org) ✅

### Project Lifecycle
- Shadow State ✅
- Count Invariants (active + archived = total) ✅
- Relationship (→ Organization, → Workflow) ✅
- Business Rules (is_archived flag consistency) ✅

### Ticket Workflow
- Shadow State ✅
- Relationship (→ Project, → Reporter, → Assignee) ✅
- Business Rules (status in workflow) ✅
- Temporal (timestamps) ✅

### Epic-Ticket Aggregates
- Shadow State ✅
- Count Invariants (epic.ticket_count = len(tickets)) ✅
- Aggregate Consistency (ticket in at most one epic) ✅
- Relationship (all ticket IDs valid) ✅

---

## Further Reading

- Full strategy: `docs/pbt_strategy.md`
- Detailed guide: `docs/pbt_stateful_testing_guide.md`
- Runnable examples: `tests/stateful_example.py`
- Quick reference: `docs/pbt_quick_reference.md`
