# Bundle Conditional Addition: Complete Guide

## Problem: How to Skip Adding to Bundles

**Question**: How do I conditionally add (or not add) values to bundles?

**Answer**: Use `multiple()` with no arguments to skip addition.

---

## The `multiple()` Function

```python
from hypothesis.stateful import multiple

# Add nothing
multiple()

# Add to one bundle
multiple((bundle, value))

# Add to multiple bundles
multiple((bundle1, value1), (bundle2, value2), ...)
```

---

## Pattern 1: Skip Addition Based on Condition

```python
from hypothesis.stateful import multiple

class MyStateMachine(RuleBasedStateMachine):
    users = Bundle("users")

    def __init__(self):
        super().__init__()
        self.max_users = 50
        self.user_count = 0

    @rule(username=st.text())
    def create_user(self, username: str):
        """Create user, but only if under limit."""

        # Skip if at limit
        if self.user_count >= self.max_users:
            return multiple()  # ✅ Add NOTHING to bundle

        user = self.repo.users.create(...)
        self.user_count += 1

        return self.users, user.id  # Add to bundle
```

**Why this matters**: Without this, you'd need separate rules or complex preconditions.

---

## Pattern 2: Conditional Bundle Selection

```python
users = Bundle("users")
admins = Bundle("admins")
managers = Bundle("managers")

@rule(role=st.sampled_from([UserRole.ADMIN, UserRole.MANAGER, UserRole.WRITE, UserRole.READ]))
def create_user(self, role: UserRole):
    """Create user - add to appropriate bundles based on role."""

    user = self.repo.users.create(..., role=role)

    # Always add to users
    bundles_to_add = [(self.users, user.id)]

    # Conditionally add to role-specific bundles
    if role == UserRole.ADMIN:
        bundles_to_add.append((self.admins, user.id))
    elif role == UserRole.MANAGER:
        bundles_to_add.append((self.managers, user.id))
    # WRITE and READ users only in 'users' bundle

    # Return appropriate bundles
    if len(bundles_to_add) == 1:
        return bundles_to_add[0]  # (bundle, value) tuple
    else:
        return multiple(*bundles_to_add)  # Unpack list
```

**Result**:
- ADMIN: in `users` + `admins`
- MANAGER: in `users` + `managers`
- WRITE/READ: in `users` only

---

## Pattern 3: Skip on Duplicate

```python
users = Bundle("users")

def __init__(self):
    self.created_usernames = set()

@rule(username=st.text(min_size=3, max_size=20))
def create_user(self, username: str):
    """Create user - skip if username already exists."""

    # Skip if duplicate
    if username in self.created_usernames:
        return multiple()  # Don't add to bundle

    user = self.repo.users.create(...)
    self.created_usernames.add(username)

    return self.users, user.id
```

**Alternative using `assume()`**:
```python
from hypothesis import assume

@rule(username=st.text(min_size=3, max_size=20))
def create_user(self, username: str):
    """Create user - skip if username already exists."""

    # Tell Hypothesis to skip this example
    assume(username not in self.created_usernames)

    user = self.repo.users.create(...)
    self.created_usernames.add(username)

    return self.users, user.id
```

**Difference**:
- `return multiple()`: Rule executes but adds nothing
- `assume()`: Rule doesn't execute at all (Hypothesis generates different value)

**Generally prefer `assume()`** for filtering inputs.

---

## Pattern 4: Skip on Error

```python
@rule(project_name=st.text())
def create_project(self, project_name: str):
    """Create project - skip if creation fails."""

    try:
        project = self.repo.projects.create(...)
        return self.projects, project.id
    except ValueError as e:
        # Invalid name or other validation error
        note(f"Project creation failed: {e}")
        return multiple()  # Skip adding to bundle
```

**Use case**: When operation might legitimately fail and you want to continue.

---

## Complete Example: User Roles with Limits

```python
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, Bundle, multiple
from hypothesis import strategies as st, note

class UserLimitsStateMachine(RuleBasedStateMachine):
    """
    Demonstrates conditional bundle addition with limits.

    Limits:
    - Max 50 total users
    - Max 5 admins
    - Max 10 managers
    """

    users = Bundle("users")
    admins = Bundle("admins")
    managers = Bundle("managers")

    def __init__(self):
        super().__init__()
        from tests.conftest import get_test_repository

        self.repo = get_test_repository()

        org_data = OrganizationData(name="Test Org")
        self.org = self.repo.organizations.create(
            OrganizationCreateCommand(organization_data=org_data)
        )

        # Limits
        self.max_users = 50
        self.max_admins = 5
        self.max_managers = 10

        # Tracking
        self.all_user_ids = set()
        self.admin_user_ids = set()
        self.manager_user_ids = set()
        self.regular_user_ids = set()

        self.user_counter = 0

    @rule(role=st.sampled_from([UserRole.ADMIN, UserRole.MANAGER, UserRole.WRITE, UserRole.READ]))
    def create_user(self, role: UserRole):
        """Create user - conditionally add to bundles based on limits."""

        # Check total user limit
        if len(self.all_user_ids) >= self.max_users:
            note(f"Skipping: at user limit ({self.max_users})")
            return multiple()  # Skip - at limit

        # Check role-specific limits
        if role == UserRole.ADMIN and len(self.admin_user_ids) >= self.max_admins:
            note(f"Skipping: at admin limit ({self.max_admins})")
            return multiple()  # Skip - at admin limit

        if role == UserRole.MANAGER and len(self.manager_user_ids) >= self.max_managers:
            note(f"Skipping: at manager limit ({self.max_managers})")
            return multiple()  # Skip - at manager limit

        # Create user
        self.user_counter += 1
        username = f"user{self.user_counter}_{role.value}"

        note(f"Creating {role.value} user: {username}")

        user_data = UserData(
            username=username,
            email=f"{username}@test.com",
            full_name=f"User {self.user_counter}"
        )
        user = self.repo.users.create(UserCreateCommand(
            user_data=user_data,
            password="Pass123!",
            organization_id=self.org.id,
            role=role
        ))

        # Update tracking
        self.all_user_ids.add(user.id)

        # Determine which bundles to add to
        bundles_to_add = [(self.users, user.id)]  # Always add to users

        if role == UserRole.ADMIN:
            self.admin_user_ids.add(user.id)
            bundles_to_add.append((self.admins, user.id))
            note(f"  → Added to users + admins bundles")

        elif role == UserRole.MANAGER:
            self.manager_user_ids.add(user.id)
            bundles_to_add.append((self.managers, user.id))
            note(f"  → Added to users + managers bundles")

        else:
            self.regular_user_ids.add(user.id)
            note(f"  → Added to users bundle only")

        # Return appropriate bundle(s)
        if len(bundles_to_add) == 1:
            return bundles_to_add[0]  # Single tuple
        else:
            return multiple(*bundles_to_add)  # Multiple tuples

    @rule(user_id=users)
    def get_any_user(self, user_id: str):
        """Get any user."""
        note(f"Getting user: {user_id}")
        user = self.repo.users.get_by_id(user_id)
        assert user is not None

    @rule(admin_id=admins)
    def admin_action(self, admin_id: str):
        """Admin-only action."""
        note(f"Admin action by: {admin_id}")
        user = self.repo.users.get_by_id(admin_id)
        assert user.role == UserRole.ADMIN

    @rule(manager_id=managers)
    def manager_action(self, manager_id: str):
        """Manager-only action."""
        note(f"Manager action by: {manager_id}")
        user = self.repo.users.get_by_id(manager_id)
        assert user.role == UserRole.MANAGER

    @invariant()
    def user_counts_within_limits(self):
        """Verify all counts are within limits."""
        assert len(self.all_user_ids) <= self.max_users, \
            f"Total users {len(self.all_user_ids)} exceeds limit {self.max_users}"

        assert len(self.admin_user_ids) <= self.max_admins, \
            f"Admins {len(self.admin_user_ids)} exceeds limit {self.max_admins}"

        assert len(self.manager_user_ids) <= self.max_managers, \
            f"Managers {len(self.manager_user_ids)} exceeds limit {self.max_managers}"

    @invariant()
    def role_specific_bundles_are_subsets(self):
        """Admin and manager sets are subsets of all users."""
        assert self.admin_user_ids.issubset(self.all_user_ids)
        assert self.manager_user_ids.issubset(self.all_user_ids)
        assert self.regular_user_ids.issubset(self.all_user_ids)

    @invariant()
    def role_sets_are_disjoint(self):
        """Admin, manager, and regular user sets don't overlap."""
        assert len(self.admin_user_ids & self.manager_user_ids) == 0
        assert len(self.admin_user_ids & self.regular_user_ids) == 0
        assert len(self.manager_user_ids & self.regular_user_ids) == 0

    @invariant()
    def all_users_accounted_for(self):
        """All users are in exactly one role set."""
        all_in_roles = self.admin_user_ids | self.manager_user_ids | self.regular_user_ids
        assert self.all_user_ids == all_in_roles


TestUserLimits = UserLimitsStateMachine.TestCase
```

---

## Common Patterns Summary

### Skip if at Limit
```python
if len(self.items) >= self.max_items:
    return multiple()  # Skip
```

### Skip if Duplicate
```python
if item_id in self.existing_items:
    return multiple()  # Skip
```

### Skip if Invalid
```python
try:
    result = self.repo.create(...)
    return self.bundle, result.id
except ValueError:
    return multiple()  # Skip on error
```

### Conditional Bundle Selection
```python
if condition_a:
    return multiple((self.bundle_a, value))
elif condition_b:
    return multiple((self.bundle_b, value))
else:
    return multiple()  # Skip - no appropriate bundle
```

### Multiple Bundles Based on Conditions
```python
bundles = [(self.all_items, item.id)]  # Always add

if item.is_premium:
    bundles.append((self.premium_items, item.id))

if item.is_featured:
    bundles.append((self.featured_items, item.id))

return multiple(*bundles) if len(bundles) > 1 else bundles[0]
```

---

## Using `multiple()` with `target=` vs Tuple Syntax

**Important**: `multiple()` works with **both** syntaxes!

### With `target=` Parameter ✅

```python
@rule(target=users)
def create_user(self, should_skip: bool):
    if should_skip:
        return multiple()  # ✅ Skip - adds nothing

    user = create(...)
    return user.id  # ✅ Add to 'users' (specified by target=)
```

**Note**: When using `target=`, return the **value directly** (not a tuple).

---

### With Tuple Syntax (No `target=`) ✅

```python
@rule()  # NO target= parameter
def create_user(self, should_skip: bool):
    if should_skip:
        return multiple()  # ✅ Skip - adds nothing

    user = create(...)
    return self.users, user.id  # ✅ Add to 'users' (specified by tuple)
```

**Note**: Without `target=`, return `(bundle, value)` tuple.

---

### Key Takeaway

`return multiple()` **always** means "skip adding", regardless of whether you use `target=` or tuple syntax.

---

## `assume()` vs `multiple()`

### Use `assume()` to Filter Inputs

```python
from hypothesis import assume

@rule(username=st.text())
def create_user(self, username: str):
    # Tell Hypothesis "don't use this value"
    assume(username not in self.existing_usernames)

    # Rule doesn't run if assume() fails
    user = self.repo.users.create(...)
    return self.users, user.id
```

**When to use**:
- Filtering generated inputs
- Skipping invalid test cases
- Hypothesis will generate different value

---

### Use `multiple()` to Skip Addition

```python
@rule(username=st.text())
def create_user(self, username: str):
    # Check after running logic
    if username in self.existing_usernames:
        return multiple()  # Rule runs but adds nothing

    user = self.repo.users.create(...)
    return self.users, user.id
```

**When to use**:
- After performing operations
- When you want rule to execute but not add to bundle
- Conditional bundle selection

---

## Quick Reference

| Goal | Solution |
|------|----------|
| **Skip adding to bundle** | `return multiple()` |
| **Add to one bundle** | `return self.bundle, value` |
| **Add to multiple bundles** | `return multiple((b1, v1), (b2, v2))` |
| **Add same value to multiple bundles** | `return multiple((b1, v), (b2, v))` |
| **Conditional addition** | `if cond: return bundle, val` <br> `else: return multiple()` |
| **Skip invalid inputs** | `assume(is_valid(input))` |
| **Skip after operation** | `return multiple()` |

---

## Key Takeaways

1. **`return None` adds `None` to bundle** - don't do this!
2. **`return multiple()` adds nothing** - use this to skip
3. **`assume()` filters inputs** - Hypothesis generates different value
4. **`multiple()` skips addition** - rule executes but doesn't add to bundle
5. **Use tuples for explicit bundle targets** - `(bundle, value)`
6. **Unpack lists with `*`** - `multiple(*list_of_tuples)`

---

## Testing the Pattern

```python
# Test that limits are respected
pytest tests/stateful_example.py::TestUserLimits -v

# You should see output like:
# Creating admin user: user1_admin
#   → Added to users + admins bundles
# Creating write user: user2_write_access
#   → Added to users bundle only
# Skipping: at admin limit (5)
# Creating manager user: user3_manager
#   → Added to users + managers bundles
# Skipping: at user limit (50)
```

This demonstrates that `multiple()` allows fine-grained control over when and how values are added to bundles!
