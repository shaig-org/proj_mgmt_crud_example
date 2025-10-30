# Hypothesis Bundles: Complete Guide

## What Are Bundles?

**Bundles** are Hypothesis's mechanism for passing generated values between rules in stateful testing.

**Without Bundles** (manual tracking):
```python
class MyStateMachine(RuleBasedStateMachine):
    def __init__(self):
        self.created_user_ids = []  # Manual tracking

    @rule(username=st.text())
    def create_user(self, username: str):
        user = self.repo.users.create(...)
        self.created_user_ids.append(user.id)  # Manual append

    @rule()
    @precondition(lambda self: len(self.created_user_ids) > 0)
    def delete_user(self):
        user_id = self.created_user_ids[0]  # Manual selection
        self.repo.users.delete(user_id)
```

**With Bundles** (automatic):
```python
class MyStateMachine(RuleBasedStateMachine):
    users = Bundle("users")  # Hypothesis tracks for you

    @rule(target=users, username=st.text())
    def create_user(self, username: str):
        user = self.repo.users.create(...)
        return user.id  # Automatically added to bundle

    @rule(user_id=users)  # Automatically selects from bundle
    def delete_user(self, user_id: str):
        self.repo.users.delete(user_id)
```

**Benefits**:
- Hypothesis manages the collection
- Automatic selection strategies
- Better shrinking (Hypothesis knows relationships)
- Less boilerplate code

---

## Bundle Syntax

### Declaring Bundles

```python
class MyStateMachine(RuleBasedStateMachine):
    # Bundles are class attributes
    users = Bundle("users")
    projects = Bundle("projects")
    tickets = Bundle("tickets")
```

### Adding to Bundles

```python
@rule(target=users, username=st.text())
def create_user(self, username: str):
    user = self.repo.users.create(...)
    return user.id  # Return value added to 'users' bundle
```

**Key points**:
- Use `target=bundle_name` parameter
- Return the value to add
- Can return any type (IDs, tuples, objects)

### Consuming from Bundles

```python
@rule(user_id=users)  # Parameter gets value from bundle
def get_user(self, user_id: str):
    user = self.repo.users.get_by_id(user_id)
    assert user is not None
```

**Key points**:
- Use `param_name=bundle_name`
- Hypothesis automatically selects value
- Rule only runs if bundle is non-empty

### Multiple Bundles in One Rule

```python
@rule(project_id=projects, reporter_id=users, assignee_id=users)
def create_ticket(self, project_id: str, reporter_id: str, assignee_id: str):
    """Create ticket using project and two users from bundles."""
    ticket_data = TicketData(...)
    ticket = self.repo.tickets.create(TicketCreateCommand(
        ticket_data=ticket_data,
        project_id=project_id,
        reporter_id=reporter_id
    ))
    # Can assign to different user
    self.repo.tickets.update_assignee(ticket.id, assignee_id)
```

**Hypothesis ensures**: `reporter_id` and `assignee_id` can be same or different.

---

## Complete Example: Ticket Management with Bundles

```python
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, Bundle
from hypothesis import strategies as st
from hypothesis import note

class TicketManagementStateMachine(RuleBasedStateMachine):
    """
    Demonstrates Bundles for managing entity relationships.

    Flow: Create orgs → Create projects → Create users → Create tickets → Assign/Update
    """

    def __init__(self):
        super().__init__()
        from tests.conftest import get_test_repository

        self.repo = get_test_repository()

        # Create base organization and workflow
        org_data = OrganizationData(name="Test Org")
        self.org = self.repo.organizations.create(
            OrganizationCreateCommand(organization_data=org_data)
        )
        self.workflow = self.repo.workflows.create_default_workflow()

        # Shadow state for invariants
        self.all_projects = set()    # All created project IDs
        self.all_users = set()        # All created user IDs
        self.all_tickets = {}         # ticket_id -> (project_id, reporter_id, assignee_id)

    # =========================================================================
    # BUNDLES - Declare as class attributes
    # =========================================================================

    projects = Bundle("projects")  # Project IDs
    users = Bundle("users")        # User IDs
    tickets = Bundle("tickets")    # Ticket IDs

    # =========================================================================
    # RULES - Operations that add to or consume from bundles
    # =========================================================================

    @rule(target=projects, name=st.text(min_size=1, max_size=50))
    def create_project(self, name: str):
        """Create a project and add its ID to the projects bundle."""
        note(f"Creating project: {name}")

        project_data = ProjectData(name=name, description=f"Project {name}")
        project = self.repo.projects.create(ProjectCreateCommand(
            project_data=project_data,
            organization_id=self.org.id,
            workflow_id=self.workflow.id
        ))

        # Update shadow state
        self.all_projects.add(project.id)

        note(f"Created project ID: {project.id}")
        return project.id  # Added to 'projects' bundle

    @rule(target=users, username=st.text(min_size=3, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz"))
    def create_user(self, username: str):
        """Create a user and add its ID to the users bundle."""
        note(f"Creating user: {username}")

        user_data = UserData(
            username=username,
            email=f"{username}@test.com",
            full_name=f"User {username}"
        )
        user = self.repo.users.create(UserCreateCommand(
            user_data=user_data,
            password="Pass123!",
            organization_id=self.org.id,
            role=UserRole.ADMIN
        ))

        # Update shadow state
        self.all_users.add(user.id)

        note(f"Created user ID: {user.id}")
        return user.id  # Added to 'users' bundle

    @rule(
        target=tickets,
        title=st.text(min_size=1, max_size=100),
        project_id=projects,  # CONSUME from projects bundle
        reporter_id=users     # CONSUME from users bundle
    )
    def create_ticket(self, title: str, project_id: str, reporter_id: str):
        """
        Create a ticket using project and user from bundles.

        This rule only runs if BOTH projects and users bundles are non-empty.
        """
        note(f"Creating ticket '{title}' in project {project_id} by reporter {reporter_id}")

        ticket_data = TicketData(
            title=title,
            status=self.workflow.statuses[0],
            priority=TicketPriority.MEDIUM,
            description=f"Ticket: {title}"
        )
        ticket = self.repo.tickets.create(TicketCreateCommand(
            ticket_data=ticket_data,
            project_id=project_id,
            reporter_id=reporter_id
        ))

        # Update shadow state
        self.all_tickets[ticket.id] = {
            "project_id": project_id,
            "reporter_id": reporter_id,
            "assignee_id": None
        }

        note(f"Created ticket ID: {ticket.id}")
        return ticket.id  # Added to 'tickets' bundle

    @rule(ticket_id=tickets, assignee_id=users)
    def assign_ticket(self, ticket_id: str, assignee_id: str):
        """
        Assign ticket to a user.

        Both ticket_id and assignee_id come from bundles.
        Hypothesis can pick the same user as reporter or a different one.
        """
        note(f"Assigning ticket {ticket_id} to user {assignee_id}")

        self.repo.tickets.update_assignee(ticket_id, assignee_id)

        # Update shadow state
        self.all_tickets[ticket_id]["assignee_id"] = assignee_id

    @rule(ticket_id=tickets, new_project_id=projects)
    def move_ticket_to_different_project(self, ticket_id: str, new_project_id: str):
        """
        Move ticket to a different project.

        Hypothesis can pick the same project or a different one.
        """
        current_project_id = self.all_tickets[ticket_id]["project_id"]

        # Skip if same project (no-op)
        if current_project_id == new_project_id:
            return

        note(f"Moving ticket {ticket_id} from project {current_project_id} to {new_project_id}")

        self.repo.tickets.update_project(ticket_id, new_project_id)

        # Update shadow state
        self.all_tickets[ticket_id]["project_id"] = new_project_id

    @rule(ticket_id=tickets)
    def get_ticket(self, ticket_id: str):
        """Retrieve a ticket and verify it exists."""
        note(f"Getting ticket {ticket_id}")

        ticket = self.repo.tickets.get_by_id(ticket_id)
        assert ticket is not None, f"Ticket {ticket_id} should exist"

    @rule(project_id=projects)
    def list_tickets_in_project(self, project_id: str):
        """List all tickets in a project."""
        note(f"Listing tickets in project {project_id}")

        tickets = self.repo.tickets.get_all(project_id=project_id)

        # All tickets should belong to this project
        for ticket in tickets:
            assert ticket.project_id == project_id

    # =========================================================================
    # INVARIANTS - Checked after every rule
    # =========================================================================

    @invariant()
    def all_tickets_have_valid_project(self):
        """Every ticket must reference an existing project."""
        for ticket_id, data in self.all_tickets.items():
            ticket = self.repo.tickets.get_by_id(ticket_id)
            assert ticket is not None, f"Ticket {ticket_id} should exist"

            project = self.repo.projects.get_by_id(data["project_id"])
            assert project is not None, \
                f"Ticket {ticket_id} references non-existent project {data['project_id']}"

    @invariant()
    def all_tickets_have_valid_reporter(self):
        """Every ticket must reference an existing reporter."""
        for ticket_id, data in self.all_tickets.items():
            ticket = self.repo.tickets.get_by_id(ticket_id)
            reporter = self.repo.users.get_by_id(data["reporter_id"])
            assert reporter is not None, \
                f"Ticket {ticket_id} references non-existent reporter {data['reporter_id']}"

    @invariant()
    def assigned_tickets_have_valid_assignee(self):
        """Assigned tickets must reference an existing user."""
        for ticket_id, data in self.all_tickets.items():
            if data["assignee_id"] is not None:
                ticket = self.repo.tickets.get_by_id(ticket_id)
                assignee = self.repo.users.get_by_id(data["assignee_id"])
                assert assignee is not None, \
                    f"Ticket {ticket_id} references non-existent assignee {data['assignee_id']}"

    @invariant()
    def ticket_data_matches_shadow_state(self):
        """Ticket data in DB must match shadow state."""
        for ticket_id, expected in self.all_tickets.items():
            ticket = self.repo.tickets.get_by_id(ticket_id)
            assert ticket is not None

            assert ticket.project_id == expected["project_id"], \
                f"Ticket {ticket_id} project mismatch"
            assert ticket.reporter_id == expected["reporter_id"], \
                f"Ticket {ticket_id} reporter mismatch"

            if expected["assignee_id"] is not None:
                assert ticket.assignee_id == expected["assignee_id"], \
                    f"Ticket {ticket_id} assignee mismatch"


TestTicketManagement = TicketManagementStateMachine.TestCase
```

---

## Advanced Bundle Patterns

### Pattern 1: Returning Tuples

```python
@rule(target=users, username=st.text())
def create_user(self, username: str):
    user = self.repo.users.create(...)
    # Return tuple: (id, username) for more context
    return (user.id, username)

@rule(user_data=users)  # user_data is tuple: (id, username)
def delete_user(self, user_data):
    user_id, username = user_data
    note(f"Deleting user {username} (ID: {user_id})")
    self.repo.users.delete(user_id)
```

**Benefit**: Access both ID and metadata in consuming rules.

---

### Pattern 2: Subset Bundles (Multiple Targets)

**Goal**: Create `admins` bundle as a true subset of `users` bundle.

```python
from hypothesis.stateful import multiple

users = Bundle("users")
admins = Bundle("admins")  # Subset of users

@rule(role=st.sampled_from([UserRole.ADMIN, UserRole.WRITE, UserRole.READ]))
def create_user(self, role: UserRole):
    """Create user - add to appropriate bundles."""
    user = self.repo.users.create(..., role=role)

    if role == UserRole.ADMIN:
        # Add to BOTH bundles using multiple()
        return multiple(
            (self.users, user.id),   # Add to 'users'
            (self.admins, user.id)   # Add to 'admins'
        )
    else:
        # Add to 'users' only
        return self.users, user.id  # (bundle, value) tuple

@rule(admin_id=admins)
def admin_only_action(self, admin_id: str):
    """Only admins can perform this action."""
    user = self.repo.users.get_by_id(admin_id)
    assert user.role == UserRole.ADMIN  # Always true!
```

**Note**: See `docs/pbt_bundles_subset_pattern.md` for detailed guide on subset bundles.

**Use case**: Subset bundles for rules that need specific entity types (e.g., admin-only operations).

---

### Pattern 3: Consumes and Produces

```python
@rule(target=tickets, ticket_id=tickets, new_assignee=users)
def reassign_ticket(self, ticket_id: str, new_assignee: str):
    """
    Consume ticket from bundle, update it, and add back to bundle.

    Note: This adds the SAME ticket_id again, creating duplicates in bundle.
    """
    self.repo.tickets.update_assignee(ticket_id, new_assignee)
    return ticket_id  # Re-added to tickets bundle
```

**Effect**: Bundle can contain duplicate values (Hypothesis handles this).

---

### Pattern 4: Conditional Bundle Addition

```python
@rule(target=projects, name=st.text(), is_archived=st.booleans())
def create_project(self, name: st.text(), is_archived: bool):
    project = self.repo.projects.create(...)

    if is_archived:
        self.repo.projects.archive(project.id)
        # Don't add archived projects to bundle
        return multiple()  # Special: adds nothing to bundle
    else:
        return project.id  # Add to bundle

from hypothesis.stateful import multiple

@rule(target=projects)
def create_multiple_projects(self):
    """Add multiple values to bundle from one rule."""
    project1 = self.repo.projects.create(...)
    project2 = self.repo.projects.create(...)
    return multiple(project1.id, project2.id)  # Adds both
```

**Use case**: Conditional addition, or adding multiple values at once.

---

## Bundle vs Manual Tracking: When to Use Each

### Use Bundles When:

✅ **Need automatic selection** - Hypothesis picks interesting values
✅ **Relationships between entities** - Projects, users, tickets
✅ **Don't care about removal** - Bundle values persist (can't remove)
✅ **Want better shrinking** - Hypothesis understands relationships

**Example**: Create tickets using projects and users from bundles.

```python
@rule(target=tickets, project_id=projects, reporter_id=users)
def create_ticket(self, project_id: str, reporter_id: str):
    # Hypothesis automatically picks interesting combinations
    ...
```

---

### Use Manual Tracking When:

✅ **Need to remove values** - Bundles don't support removal
✅ **Need specific selection logic** - "Pick first", "Pick by criteria"
✅ **Track additional state** - Deleted items, counts, metadata

**Example**: Track deleted users (can't use bundles - they don't remove).

```python
class MyStateMachine(RuleBasedStateMachine):
    def __init__(self):
        self.active_users = {}      # Manual: need to remove on delete
        self.deleted_users = set()  # Manual: track deletions

    @rule(username=st.text())
    def create_user(self, username: str):
        user = self.repo.users.create(...)
        self.active_users[username] = user.id

    @rule()
    @precondition(lambda self: len(self.active_users) > 0)
    def delete_user(self):
        username = list(self.active_users.keys())[0]
        user_id = self.active_users[username]
        self.repo.users.delete(user_id)

        # Remove from active, add to deleted
        del self.active_users[username]
        self.deleted_users.add(username)
```

---

### Hybrid Approach (Best Practice)

**Use bundles for creation, manual tracking for state**:

```python
class HybridStateMachine(RuleBasedStateMachine):
    users = Bundle("users")  # For creating/selecting

    def __init__(self):
        self.deleted_user_ids = set()  # Manual: track deletions

    @rule(target=users, username=st.text())
    def create_user(self, username: str):
        user = self.repo.users.create(...)
        return user.id  # Add to bundle

    @rule(user_id=users)  # Consume from bundle
    def delete_user(self, user_id: str):
        # Skip if already deleted
        if user_id in self.deleted_user_ids:
            return

        self.repo.users.delete(user_id)
        self.deleted_user_ids.add(user_id)  # Track deletion

    @invariant()
    def deleted_users_not_retrievable(self):
        for user_id in self.deleted_user_ids:
            user = self.repo.users.get_by_id(user_id)
            assert user is None
```

**Benefits**:
- Bundles: Automatic selection, better shrinking
- Manual tracking: Track deletions, additional state

---

## Bundle Lifecycle and Behavior

### How Bundles Work Internally

```python
# Hypothesis maintains bundles like this (conceptual):
bundles = {
    "users": [user1_id, user2_id, user3_id, ...],
    "projects": [proj1_id, proj2_id, ...],
}

# When you write @rule(user_id=users):
# Hypothesis does: user_id = random.choice(bundles["users"])
```

### Bundle Selection Strategy

Hypothesis uses **smart selection**:
1. **Recent values**: Prefers recently added values
2. **Variety**: Occasionally picks older values
3. **Shrinking-friendly**: During shrinking, picks values that lead to simpler examples

**Example sequence Hypothesis might generate**:
```python
create_user("alice")       # users = [alice_id]
create_user("bob")         # users = [alice_id, bob_id]
delete_user(bob_id)        # Likely picks recently added bob
create_user("carol")       # users = [alice_id, bob_id, carol_id]
assign_ticket(alice_id)    # Might pick alice or carol
```

---

## Common Pitfalls

### Pitfall 1: Bundles Don't Remove Values

```python
# ❌ WRONG: Expecting bundle to remove deleted users
@rule(user_id=users)
def delete_user(self, user_id: str):
    self.repo.users.delete(user_id)
    # Bundle STILL contains user_id!

# Later rule might try to use deleted user
@rule(user_id=users)
def get_user(self, user_id: str):
    user = self.repo.users.get_by_id(user_id)
    # Might be None! (deleted earlier)
```

**Fix**: Track deletions manually
```python
# ✅ CORRECT: Track deletions separately
def __init__(self):
    self.deleted_user_ids = set()

@rule(user_id=users)
def delete_user(self, user_id: str):
    if user_id in self.deleted_user_ids:
        return  # Skip if already deleted

    self.repo.users.delete(user_id)
    self.deleted_user_ids.add(user_id)
```

---

### Pitfall 2: Empty Bundle Preconditions

```python
# ❌ WRONG: Rule runs even if bundle empty (crashes)
@rule(user_id=users)
def delete_user(self, user_id: str):
    # If users bundle is empty, this crashes!
    self.repo.users.delete(user_id)
```

**Fix**: Bundle parameters automatically add precondition
```python
# ✅ CORRECT: Rule only runs if bundle non-empty (automatic)
@rule(user_id=users)  # Hypothesis only runs this if users bundle has values
def delete_user(self, user_id: str):
    self.repo.users.delete(user_id)
```

---

### Pitfall 3: Multiple Bundles Same Type

```python
# ❌ CONFUSING: Which users bundle to use?
users = Bundle("users")
admins = Bundle("admins")

@rule(target=users, ...)
def create_user(...):
    return user.id

@rule(target=admins, ...)
def create_admin(...):
    return admin.id

@rule(user_id=users, admin_id=admins)
def do_something(self, user_id: str, admin_id: str):
    # user_id might be an admin!
    # admin_id might be a regular user!
```

**Fix**: Use clear naming or track membership
```python
# ✅ BETTER: Track which users are admins
def __init__(self):
    self.admin_user_ids = set()

@rule(target=users, role=st.sampled_from([UserRole.ADMIN, UserRole.WRITE]))
def create_user(self, role: UserRole):
    user = self.repo.users.create(..., role=role)
    if role == UserRole.ADMIN:
        self.admin_user_ids.add(user.id)
    return user.id

@rule(user_id=users)
def do_admin_action(self, user_id: str):
    if user_id not in self.admin_user_ids:
        return  # Skip non-admins
    ...
```

---

## Summary: Bundle Patterns

| Pattern | Use Case | Example |
|---------|----------|---------|
| **Basic Bundle** | Create and use entities | `create_user() → delete_user(user_id)` |
| **Multiple Bundles** | Relationships | `create_ticket(project_id, reporter_id)` |
| **Tuple Returns** | Pass metadata | `return (user_id, username)` |
| **Hybrid Tracking** | Deletions + selections | Bundles + manual `deleted_ids` set |
| **Conditional Add** | Filtered bundles | `return multiple()` or conditional return |
| **Consumes + Produces** | Update and re-add | Ticket status changes |

---

## Quick Reference

```python
# DECLARE bundle
users = Bundle("users")

# ADD to bundle
@rule(target=users, ...)
def create(...):
    return value  # Added to bundle

# CONSUME from bundle
@rule(param=users)  # Only runs if bundle non-empty
def use(self, param):
    ...

# MULTIPLE bundles
@rule(project_id=projects, user_id=users)
def use_both(self, project_id, user_id):
    ...

# ADD multiple values
from hypothesis.stateful import multiple
@rule(target=users)
def create_many():
    return multiple(id1, id2, id3)

# ADD nothing (conditional)
@rule(target=users, should_add=st.booleans())
def maybe_create(should_add):
    if not should_add:
        return multiple()  # Adds nothing
    return user_id
```

---

## When to Use Bundles: Decision Tree

```
Does your rule need to use entities created by other rules?
├─ YES → Do you need to remove entities from the pool?
│  ├─ NO → Use Bundles ✅
│  └─ YES → Use Bundles + Manual Tracking (hybrid) ✅
└─ NO → Just use strategies (no bundle needed) ✅
```

**Examples**:
- Create ticket using project → **Bundle** (don't remove projects)
- Delete user and track deletions → **Hybrid** (bundle + manual set)
- Generate random usernames → **Strategy** (no relationship)

---

## Further Reading

- Hypothesis Stateful Testing: https://hypothesis.readthedocs.io/en/latest/stateful.html
- Bundle API Reference: https://hypothesis.readthedocs.io/en/latest/stateful.html#bundles
- Example in `tests/stateful_example.py` - Epic-Ticket state machine uses Bundles
