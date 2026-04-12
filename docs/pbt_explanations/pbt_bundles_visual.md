# Hypothesis Bundles: Visual Guide

## The Problem Bundles Solve

### Scenario: Creating Tickets

**You want to test**: "Create a ticket that references a project and a user"

**The challenge**:
1. First, you need to create a project
2. Then, you need to create a user
3. Only then can you create a ticket

**Without Bundles** (messy manual tracking):
```python
self.created_projects = []  # Track manually
self.created_users = []     # Track manually

# Rule 1: Create project
def create_project():
    project = repo.create_project(...)
    self.created_projects.append(project.id)  # Manual

# Rule 2: Create user
def create_user():
    user = repo.create_user(...)
    self.created_users.append(user.id)  # Manual

# Rule 3: Create ticket - need both!
@precondition(lambda self: len(self.created_projects) > 0 and len(self.created_users) > 0)
def create_ticket():
    project_id = self.created_projects[0]  # Manual selection
    user_id = self.created_users[0]        # Manual selection
    repo.create_ticket(project_id=project_id, reporter_id=user_id)
```

**With Bundles** (clean and automatic):
```python
projects = Bundle("projects")  # Hypothesis tracks
users = Bundle("users")        # Hypothesis tracks

# Rule 1: Create project → add to bundle
@rule(target=projects)
def create_project():
    project = repo.create_project(...)
    return project.id  # Automatically added to projects bundle

# Rule 2: Create user → add to bundle
@rule(target=users)
def create_user():
    user = repo.create_user(...)
    return user.id  # Automatically added to users bundle

# Rule 3: Create ticket - use from bundles!
@rule(project_id=projects, reporter_id=users)  # Hypothesis selects automatically
def create_ticket(project_id, reporter_id):
    repo.create_ticket(project_id=project_id, reporter_id=reporter_id)
```

---

## Visual: How Bundles Work

### Step-by-Step Execution

```
Initial State:
projects bundle: []
users bundle: []

─────────────────────────────────────────────────────

Operation 1: create_project("Backend")
  ↓
projects bundle: [project-123]
users bundle: []

─────────────────────────────────────────────────────

Operation 2: create_user("alice")
  ↓
projects bundle: [project-123]
users bundle: [user-456]

─────────────────────────────────────────────────────

Operation 3: create_project("Frontend")
  ↓
projects bundle: [project-123, project-789]
users bundle: [user-456]

─────────────────────────────────────────────────────

Operation 4: create_user("bob")
  ↓
projects bundle: [project-123, project-789]
users bundle: [user-456, user-999]

─────────────────────────────────────────────────────

Operation 5: create_ticket(project_id=?, reporter_id=?)
             ↓                        ↓
         Hypothesis selects    Hypothesis selects
         from projects         from users
             ↓                        ↓
         project-789              user-456
             ↓                        ↓
         Creates ticket: "Fix bug in Frontend, reported by alice"

─────────────────────────────────────────────────────

Operation 6: create_ticket(project_id=?, reporter_id=?)
             ↓                        ↓
         Hypothesis selects    Hypothesis selects
         from projects         from users
             ↓                        ↓
         project-123              user-999
             ↓                        ↓
         Creates ticket: "Add feature to Backend, reported by bob"
```

**Key insight**: Hypothesis automatically picks **interesting combinations** of projects and users.

---

## Bundle Declaration and Usage

### 1. Declare Bundles (Class Level)

```python
class MyStateMachine(RuleBasedStateMachine):
    # Bundles declared as class attributes
    projects = Bundle("projects")
    users = Bundle("users")
    tickets = Bundle("tickets")

    def __init__(self):
        # Other initialization
        pass
```

**Visual**:
```
┌─────────────────────────────────────┐
│  MyStateMachine                     │
│                                     │
│  [CLASS ATTRIBUTES]                 │
│  projects = Bundle("projects") ◄────┼── Bundle declaration
│  users = Bundle("users")            │
│  tickets = Bundle("tickets")        │
│                                     │
│  [INSTANCE STATE]                   │
│  self.repo = ...                    │
│  self.shadow_state = {}             │
└─────────────────────────────────────┘
```

---

### 2. Add to Bundle (target=)

```python
@rule(target=projects, name=st.text())
def create_project(self, name: str):
    project = self.repo.projects.create(...)
    return project.id  # ← This value added to 'projects' bundle
```

**Visual**:
```
create_project("Backend") called
       │
       ├─→ Creates project in DB
       │
       └─→ Returns project-123
              │
              └─→ Added to projects bundle
                     │
                     ▼
projects bundle: [project-123]
```

---

### 3. Consume from Bundle (param=)

```python
@rule(project_id=projects)  # ← Get value FROM projects bundle
def archive_project(self, project_id: str):
    self.repo.projects.archive(project_id)
```

**Visual**:
```
projects bundle: [project-123, project-456, project-789]
                      │           │           │
                      └──── Hypothesis picks one ────┘
                                  │
                                  ▼
archive_project(project_id="project-456")
```

**Hypothesis selection strategy**:
- Prefers recent values (project-789 most likely)
- Occasionally picks older values for variety
- Smart shrinking (picks simpler examples during minimization)

---

### 4. Multiple Bundle Parameters

```python
@rule(
    target=tickets,
    project_id=projects,  # ← From projects bundle
    reporter_id=users,    # ← From users bundle
    assignee_id=users     # ← Also from users bundle (can be same or different!)
)
def create_ticket(self, project_id: str, reporter_id: str, assignee_id: str):
    ticket = self.repo.tickets.create(
        project_id=project_id,
        reporter_id=reporter_id
    )
    self.repo.tickets.update_assignee(ticket.id, assignee_id)
    return ticket.id  # ← Added to tickets bundle
```

**Visual**:
```
projects bundle: [proj-1, proj-2, proj-3]
                      │       │       │
                      └─── Pick one ──┘
                            │
                            ▼
                        proj-2

users bundle: [user-a, user-b, user-c]
                 │       │       │
                 └─ Pick ┘       │
                    │            │
                    ▼            │
                 user-a          │
                                 │
                 Pick another ───┘
                    │
                    ▼
                 user-c

create_ticket(
    project_id="proj-2",
    reporter_id="user-a",   ← Can be same
    assignee_id="user-c"    ← or different!
)
       │
       └─→ Returns ticket-999
              │
              └─→ Added to tickets bundle

tickets bundle: [ticket-999]
```

---

## Real-World Example: Epic-Ticket Relationships

```python
class EpicTicketStateMachine(RuleBasedStateMachine):
    # Bundle declarations
    epics = Bundle("epics")
    tickets = Bundle("tickets")

    def __init__(self):
        super().__init__()
        self.repo = get_test_repository()
        # Setup...

    @rule(target=epics, name=st.text())
    def create_epic(self, name: str):
        """Create epic and add ID to bundle."""
        epic = self.repo.epics.create(...)
        return epic.id  # → epics bundle

    @rule(target=tickets, title=st.text())
    def create_ticket(self, title: str):
        """Create ticket and add ID to bundle."""
        ticket = self.repo.tickets.create(...)
        return ticket.id  # → tickets bundle

    @rule(epic_id=epics, ticket_id=tickets)
    def add_ticket_to_epic(self, epic_id: str, ticket_id: str):
        """Add ticket to epic - both from bundles."""
        self.repo.epics.add_ticket(epic_id, ticket_id)

    @rule(epic_id=epics, ticket_id=tickets)
    def remove_ticket_from_epic(self, epic_id: str, ticket_id: str):
        """Remove ticket from epic - both from bundles."""
        self.repo.epics.remove_ticket(epic_id, ticket_id)
```

**What Hypothesis generates**:
```
Sequence 1:
  create_epic("Sprint 1")       → epic-1
  create_ticket("Fix bug")      → ticket-1
  create_ticket("Add feature")  → ticket-2
  add_ticket_to_epic(epic-1, ticket-1)
  add_ticket_to_epic(epic-1, ticket-2)
  remove_ticket_from_epic(epic-1, ticket-1)

Sequence 2:
  create_ticket("Bug report")   → ticket-3
  create_epic("Sprint 2")       → epic-2
  create_epic("Sprint 3")       → epic-3
  add_ticket_to_epic(epic-3, ticket-3)
  remove_ticket_from_epic(epic-3, ticket-3)
  add_ticket_to_epic(epic-2, ticket-3)

... hundreds more sequences ...
```

**Key**: Hypothesis explores all interesting combinations automatically!

---

## Bundle Lifecycle

### State Diagram

```
┌─────────────┐
│   EMPTY     │  Initial state
│  Bundle     │
└──────┬──────┘
       │
       │ @rule(target=bundle) returns value
       ▼
┌─────────────┐
│  HAS ONE    │  Bundle: [value1]
│   VALUE     │
└──────┬──────┘
       │
       │ @rule(target=bundle) returns value
       ▼
┌─────────────┐
│  HAS MANY   │  Bundle: [value1, value2, value3, ...]
│   VALUES    │
└──────┬──────┘
       │
       │ Rules with param=bundle can now run
       │
       ├─→ @rule(param=bundle) ──→ Uses value from bundle
       │
       ├─→ @rule(param1=bundle, param2=bundle) ──→ Uses two values
       │
       └─→ @rule(target=bundle, param=bundle) ──→ Consumes and produces
```

**Important**: Bundles **never shrink** - values are never removed.

---

## Bundle Patterns Summary

### Pattern 1: Simple Producer → Consumer

```
create_project()  ──→ [project-1]
                            │
                            └──→ archive_project(project-1)
```

### Pattern 2: Multiple Consumers

```
create_project()  ──→ [project-1, project-2]
                            │         │
                ┌───────────┴─────────┴────────┐
                │                              │
                ▼                              ▼
     list_projects()              delete_project(project-2)
```

### Pattern 3: Producer Uses Another Bundle

```
create_user()     ──→ [user-1, user-2]
                            │      │
create_project()  ──→ [project-1] │
                          │        │
                          │        │
                create_ticket(project-1, user-2)
                          │
                          └──→ [ticket-1]
```

### Pattern 4: Circular (Consume + Produce)

```
create_ticket()   ──→ [ticket-1, ticket-2]
                            │
                            └──→ update_ticket(ticket-1)
                                    │
                                    └──→ [ticket-1]  (re-added)
```

---

## Common Questions

### Q: Can I remove values from a bundle?

**A**: No! Bundles only grow. Use manual tracking for deletions:

```python
users = Bundle("users")  # Never shrinks

def __init__(self):
    self.deleted_users = set()  # Manual tracking

@rule(user_id=users)
def delete_user(self, user_id: str):
    if user_id in self.deleted_users:
        return  # Skip if already deleted

    self.repo.users.delete(user_id)
    self.deleted_users.add(user_id)  # Track manually
```

---

### Q: Can the same value be in a bundle multiple times?

**A**: Yes! If you return it multiple times:

```python
@rule(target=tickets, ticket_id=tickets)
def update_ticket(self, ticket_id: str):
    self.repo.tickets.update(ticket_id, ...)
    return ticket_id  # Re-adds same ticket_id

# After 3 updates: tickets = [ticket-1, ticket-1, ticket-1, ticket-2]
```

This is OK - Hypothesis handles duplicates intelligently.

---

### Q: How does Hypothesis pick values from bundles?

**A**: Smart selection strategy:
1. **Recent bias**: Prefers recently added values
2. **Variety**: Occasionally picks older values
3. **Shrinking**: During minimization, picks simpler examples

You cannot control the selection manually (that's the point!).

---

### Q: Can I have multiple bundles of the same type?

**A**: Yes, useful for subsets:

```python
users = Bundle("users")        # All users
admins = Bundle("admins")      # Subset: admin users

@rule(target=users, role=st.sampled_from([UserRole.ADMIN, UserRole.WRITE]))
def create_user(self, role: UserRole):
    user = self.repo.users.create(..., role=role)
    return user.id  # Added to 'users'

@rule(target=admins)
def create_admin(self):
    user = self.repo.users.create(..., role=UserRole.ADMIN)
    return user.id  # Added to 'admins' (not 'users'!)

@rule(admin_id=admins)  # Only uses admins
def admin_action(self, admin_id: str):
    ...
```

---

## Quick Reference Card

```python
# DECLARE
class MyStateMachine(RuleBasedStateMachine):
    my_bundle = Bundle("my_bundle")

# ADD TO BUNDLE
@rule(target=my_bundle, value=st.text())
def add_value(self, value):
    return value  # Added to bundle

# USE FROM BUNDLE
@rule(value=my_bundle)  # Only runs if bundle non-empty
def use_value(self, value):
    pass  # Use value

# MULTIPLE BUNDLES
@rule(value1=bundle1, value2=bundle2)
def use_both(self, value1, value2):
    pass

# CONSUME AND PRODUCE
@rule(target=my_bundle, old_value=my_bundle)
def transform(self, old_value):
    new_value = transform(old_value)
    return new_value  # Re-added to bundle
```

---

## Next Steps

1. **Read**: [`pbt_bundles_guide.md`](pbt_bundles_guide.md) - Complete guide with patterns
2. **See**: `tests/stateful_example.py` - Example 3 uses Bundles for Epic-Ticket relationships
3. **Try**: Implement your own state machine with Bundles

**Remember**: Bundles are for **passing values between rules**, not for tracking state. Use manual tracking (`self.something = {}`) for state management.
