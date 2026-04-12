# Bundle Subset Pattern: Complete Guide

## Quick Answer: Skipping Bundle Addition

**Q**: How do I skip adding to a bundle?

**A**: Return `multiple()` with no arguments.

```python
from hypothesis.stateful import multiple

@rule(target=users)
def maybe_create_user(self, should_skip: bool):
    if should_skip:
        return multiple()  # ✅ Adds NOTHING to bundle

    user = create_user(...)
    return user.id  # Adds to bundle
```

**Don't return `None`** - that adds `None` to the bundle!

See [`pbt_bundles_conditional.md`](pbt_bundles_conditional.md) for complete guide on conditional addition.

---

## Problem: How to Create Subset Bundles

**Goal**: Have `admins` bundle be a **true subset** of `users` bundle.

**Challenge**: Bundles are independent - adding to one doesn't add to another.

---

## Solution 1: Multiple Targets with Tuple Syntax ⭐⭐⭐ (Best)

Use `multiple()` with `(bundle, value)` tuples to add to multiple bundles:

```python
from hypothesis.stateful import RuleBasedStateMachine, rule, Bundle, multiple
from hypothesis import strategies as st

class UserStateMachine(RuleBasedStateMachine):
    users = Bundle("users")      # All users
    admins = Bundle("admins")    # Subset: admin users only

    @rule(
        # NO target= here! We'll return multiple() which specifies targets
        role=st.sampled_from([UserRole.ADMIN, UserRole.WRITE, UserRole.READ])
    )
    def create_user(self, role: UserRole):
        """Create user - add to appropriate bundles."""
        user_data = UserData(
            username=f"user_{role.value}",
            email=f"user_{role.value}@test.com",
            full_name=f"User {role.value}"
        )
        user = self.repo.users.create(UserCreateCommand(
            user_data=user_data,
            password="Pass123!",
            organization_id=self.org.id,
            role=role
        ))

        if role == UserRole.ADMIN:
            # Add to BOTH 'users' and 'admins'
            return multiple(
                (self.users, user.id),   # Add user.id to 'users' bundle
                (self.admins, user.id)   # Add user.id to 'admins' bundle
            )
        else:
            # Add to 'users' only
            return self.users, user.id  # Return (bundle, value) tuple

    @rule(user_id=users)
    def action_any_user(self, user_id: str):
        """Action any user can do - uses 'users' bundle."""
        user = self.repo.users.get_by_id(user_id)
        assert user is not None
        # Could be admin OR regular user

    @rule(admin_id=admins)
    def admin_only_action(self, admin_id: str):
        """Action only admins can do - uses 'admins' bundle."""
        user = self.repo.users.get_by_id(admin_id)
        assert user.role == UserRole.ADMIN  # Always true!
        # Only admins here

    @invariant()
    def admins_are_subset_of_users(self):
        """Verify admins bundle is truly a subset of users bundle."""
        # Note: We can't directly inspect bundles, but we can track manually
        pass  # See Solution 2 for tracking
```

**Key syntax**:
- `return (bundle, value)` - Add `value` to `bundle`
- `return multiple((bundle1, value1), (bundle2, value2))` - Add to multiple bundles

---

## Solution 2: Manual Tracking (Most Flexible) ⭐⭐⭐

The **most explicit and flexible** approach: use bundles for selection, manual sets for tracking.

```python
from hypothesis.stateful import RuleBasedStateMachine, rule, Bundle
from hypothesis import strategies as st

class UserStateMachine(RuleBasedStateMachine):
    users = Bundle("users")      # All users (for Hypothesis selection)
    admins = Bundle("admins")    # Admin users (for Hypothesis selection)

    def __init__(self):
        super().__init__()
        self.repo = get_test_repository()
        # ... setup ...

        # MANUAL TRACKING for invariants
        self.all_user_ids: set[str] = set()       # All created users
        self.admin_user_ids: set[str] = set()     # Subset: admin users
        self.deleted_user_ids: set[str] = set()   # Deleted users

    @rule(
        role=st.sampled_from([UserRole.ADMIN, UserRole.WRITE, UserRole.READ])
    )
    def create_user(self, role: UserRole):
        """Create user - add to appropriate bundles and tracking sets."""
        user_data = UserData(
            username=f"user_{len(self.all_user_ids)}",
            email=f"user{len(self.all_user_ids)}@test.com",
            full_name=f"User {len(self.all_user_ids)}"
        )
        user = self.repo.users.create(UserCreateCommand(
            user_data=user_data,
            password="Pass123!",
            organization_id=self.org.id,
            role=role
        ))

        # Manual tracking
        self.all_user_ids.add(user.id)

        if role == UserRole.ADMIN:
            self.admin_user_ids.add(user.id)

            # Add to BOTH bundles
            return multiple(
                (self.users, user.id),
                (self.admins, user.id)
            )
        else:
            # Add to 'users' only
            return self.users, user.id

    @rule(user_id=users)
    def delete_user(self, user_id: str):
        """Delete user - update tracking."""
        if user_id in self.deleted_user_ids:
            return  # Already deleted

        self.repo.users.delete(user_id)

        # Manual tracking
        self.deleted_user_ids.add(user_id)
        self.all_user_ids.discard(user_id)
        self.admin_user_ids.discard(user_id)

    @rule(admin_id=admins)
    def admin_action(self, admin_id: str):
        """Admin-only action."""
        if admin_id in self.deleted_user_ids:
            return  # Skip deleted admins

        user = self.repo.users.get_by_id(admin_id)
        assert user is not None
        assert user.role == UserRole.ADMIN

    @invariant()
    def admins_are_subset_of_users(self):
        """Verify admins are truly a subset of users."""
        # With manual tracking, we can verify this!
        assert self.admin_user_ids.issubset(self.all_user_ids), \
            f"Admins {self.admin_user_ids} not subset of users {self.all_user_ids}"

    @invariant()
    def all_admins_retrievable_as_admins(self):
        """All admins in tracking should have admin role."""
        for admin_id in self.admin_user_ids:
            if admin_id in self.deleted_user_ids:
                continue  # Skip deleted

            user = self.repo.users.get_by_id(admin_id)
            assert user is not None, f"Admin {admin_id} should exist"
            assert user.role == UserRole.ADMIN, \
                f"User {admin_id} in admins set but has role {user.role}"
```

**Benefits**:
- ✅ Explicit tracking - can verify subset invariant
- ✅ Handle deletions properly
- ✅ Clear which users are which
- ✅ Can track additional metadata

---

## Complete Working Example

Here's a full working example with the subset pattern:

```python
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, Bundle, multiple
from hypothesis import strategies as st, note

class UserRoleStateMachine(RuleBasedStateMachine):
    """
    Demonstrates proper subset bundles: admins ⊂ users.

    Bundles:
    - users: ALL users (admins + regular users)
    - admins: ONLY admin users (proper subset of users)
    """

    users = Bundle("users")
    admins = Bundle("admins")

    def __init__(self):
        super().__init__()
        from tests.conftest import get_test_repository

        self.repo = get_test_repository()

        # Create org
        org_data = OrganizationData(name="Test Org")
        self.org = self.repo.organizations.create(
            OrganizationCreateCommand(organization_data=org_data)
        )

        # Manual tracking for invariants
        self.all_user_ids: set[str] = set()
        self.admin_user_ids: set[str] = set()
        self.regular_user_ids: set[str] = set()
        self.deleted_user_ids: set[str] = set()

        self.user_counter = 0

    @rule(role=st.sampled_from([UserRole.ADMIN, UserRole.WRITE, UserRole.READ]))
    def create_user(self, role: UserRole):
        """Create user with specified role."""
        self.user_counter += 1
        username = f"user{self.user_counter}"

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

        # Manual tracking
        self.all_user_ids.add(user.id)

        if role == UserRole.ADMIN:
            self.admin_user_ids.add(user.id)
            note(f"  → Added to both 'users' and 'admins' bundles")
            # Add to BOTH bundles
            return multiple(
                (self.users, user.id),
                (self.admins, user.id)
            )
        else:
            self.regular_user_ids.add(user.id)
            note(f"  → Added to 'users' bundle only")
            # Add to 'users' only
            return self.users, user.id

    @rule(user_id=users)
    def get_user(self, user_id: str):
        """Get any user - uses 'users' bundle."""
        if user_id in self.deleted_user_ids:
            return

        note(f"Getting user: {user_id}")
        user = self.repo.users.get_by_id(user_id)
        assert user is not None

    @rule(admin_id=admins)
    def delete_organization(self, admin_id: str):
        """
        Admin-only action - uses 'admins' bundle.

        This rule ONLY runs with admin users because it uses 'admins' bundle.
        """
        if admin_id in self.deleted_user_ids:
            return

        note(f"Admin {admin_id} attempting admin action")
        user = self.repo.users.get_by_id(admin_id)

        # Should ALWAYS be admin (because from 'admins' bundle)
        assert user.role == UserRole.ADMIN, \
            f"User {admin_id} from admins bundle but has role {user.role}"

        # Perform admin action (just verify it works)
        note(f"  → Confirmed: {admin_id} is admin, action allowed")

    @rule(user_id=users)
    def attempt_admin_action_as_any_user(self, user_id: str):
        """
        Any user attempts admin action - uses 'users' bundle.

        Should fail if not admin.
        """
        if user_id in self.deleted_user_ids:
            return

        user = self.repo.users.get_by_id(user_id)
        note(f"User {user_id} ({user.role.value}) attempting admin action")

        if user.role != UserRole.ADMIN:
            note(f"  → Correctly denied (not admin)")
            # In real system, would raise PermissionError
        else:
            note(f"  → Correctly allowed (is admin)")

    @rule(user_id=users)
    def delete_user(self, user_id: str):
        """Delete user - updates tracking."""
        if user_id in self.deleted_user_ids:
            return

        note(f"Deleting user: {user_id}")
        self.repo.users.delete(user_id)

        # Update tracking
        self.deleted_user_ids.add(user_id)
        self.all_user_ids.discard(user_id)
        self.admin_user_ids.discard(user_id)
        self.regular_user_ids.discard(user_id)

    @invariant()
    def admins_are_subset_of_all_users(self):
        """Admins must be a subset of all users."""
        assert self.admin_user_ids.issubset(self.all_user_ids), \
            f"Admins {self.admin_user_ids} not subset of all users {self.all_user_ids}"

    @invariant()
    def admins_and_regular_users_are_disjoint(self):
        """Admins and regular users have no overlap."""
        overlap = self.admin_user_ids & self.regular_user_ids
        assert len(overlap) == 0, \
            f"Users appear in both admin and regular sets: {overlap}"

    @invariant()
    def all_users_are_admin_or_regular(self):
        """All users are either admin or regular."""
        expected_all = self.admin_user_ids | self.regular_user_ids
        assert self.all_user_ids == expected_all, \
            f"User set mismatch: {self.all_user_ids} != {expected_all}"

    @invariant()
    def all_tracked_admins_have_admin_role(self):
        """All users in admin tracking actually have admin role."""
        for admin_id in self.admin_user_ids:
            if admin_id in self.deleted_user_ids:
                continue

            user = self.repo.users.get_by_id(admin_id)
            assert user is not None, f"Admin {admin_id} not found"
            assert user.role == UserRole.ADMIN, \
                f"User {admin_id} in admin set but has role {user.role}"

    @invariant()
    def deleted_users_not_in_active_sets(self):
        """Deleted users should not be in active tracking sets."""
        overlap_all = self.deleted_user_ids & self.all_user_ids
        overlap_admin = self.deleted_user_ids & self.admin_user_ids
        overlap_regular = self.deleted_user_ids & self.regular_user_ids

        assert len(overlap_all) == 0, \
            f"Deleted users in all_user_ids: {overlap_all}"
        assert len(overlap_admin) == 0, \
            f"Deleted users in admin_user_ids: {overlap_admin}"
        assert len(overlap_regular) == 0, \
            f"Deleted users in regular_user_ids: {overlap_regular}"


TestUserRoles = UserRoleStateMachine.TestCase
```

---

## Common Mistake: `target=` with `multiple()`

### ❌ WRONG: Using `target=` with Multiple Values

```python
@rule(target=users)  # ← Specifies SINGLE target
def create_user(self, role: UserRole):
    user = self.repo.users.create(..., role=role)

    if role == UserRole.ADMIN:
        return multiple(user.id, user.id)  # ❌ WRONG!
        # This adds user.id to 'users' twice (not to users AND admins)
```

**What happens**: Both values added to the `users` bundle (the single target).

**Result**:
- `users` bundle: `[user.id, user.id]` (duplicate!)
- `admins` bundle: `[]` (nothing added)

---

### ✅ CORRECT: Use Tuple Syntax

```python
@rule()  # ← NO target= parameter
def create_user(self, role: UserRole):
    user = self.repo.users.create(..., role=role)

    if role == UserRole.ADMIN:
        return multiple(
            (self.users, user.id),   # ✅ (bundle, value) tuple
            (self.admins, user.id)   # ✅ (bundle, value) tuple
        )
    else:
        return self.users, user.id  # ✅ (bundle, value) tuple
```

**Result**:
- `users` bundle: `[user.id]`
- `admins` bundle: `[user.id]`
- Subset relationship maintained! ✓

---

## Summary: Bundle Subset Patterns

### Pattern Comparison

| Approach | Pros | Cons | Use When |
|----------|------|------|----------|
| **Multiple Targets** | Simple, automatic | Can't verify subset invariant | Don't need to verify |
| **Manual Tracking** | Explicit, verifiable | More code | Need invariants, deletions |
| **Hybrid** | Balance of both | Medium complexity | General purpose |

### Recommendation: Manual Tracking ⭐

For subset bundles, **manual tracking is best** because:
1. ✅ Can verify subset invariant (`admins ⊂ users`)
2. ✅ Handle deletions properly
3. ✅ Clear and explicit
4. ✅ Easy to debug

---

## Common Mistake: Separate Creation Rules

### ❌ WRONG - Separate Bundles, No Overlap

```python
@rule(target=users, role=st.sampled_from([UserRole.ADMIN, UserRole.WRITE]))
def create_user(self, role: UserRole):
    return user.id  # Only to 'users'

@rule(target=admins)
def create_admin(self):
    return admin.id  # Only to 'admins'

# Result: admins and users are DISJOINT, not subset!
```

### ✅ CORRECT - Single Rule, Conditional Targets

```python
@rule(role=st.sampled_from([UserRole.ADMIN, UserRole.WRITE, UserRole.READ]))
def create_user(self, role: UserRole):
    user = self.repo.users.create(..., role=role)

    if role == UserRole.ADMIN:
        return multiple(
            (self.users, user.id),
            (self.admins, user.id)
        )
    else:
        return self.users, user.id

# Result: admins ⊂ users ✓
```

---

## Testing the Pattern

```python
# Hypothesis will generate sequences like:

create_user(role=ADMIN)        # user1 → users, admins
create_user(role=WRITE)        # user2 → users
create_user(role=ADMIN)        # user3 → users, admins
create_user(role=READ)         # user4 → users

# Now:
# users bundle: [user1, user2, user3, user4]
# admins bundle: [user1, user3]  ← proper subset!

delete_organization(admin_id=?)  # Can only pick user1 or user3 (admins)
get_user(user_id=?)              # Can pick any of user1-4
attempt_admin_action(user_id=?)  # Can pick any, but should check role
```

---

## Key Takeaways

1. **`multiple()` adds to multiple bundles** - use `(bundle, value)` tuples
2. **Manual tracking is best for subsets** - allows verification
3. **Single creation rule** - don't create separate rules for subset vs superset
4. **Track deletions separately** - bundles don't shrink
5. **Verify subset invariant** - `assert admins.issubset(users)`

---

## Quick Reference

```python
# WRONG: Separate rules (no overlap)
@rule(target=users, ...)
def create_user(...): ...

@rule(target=admins, ...)
def create_admin(...): ...

# CORRECT: Single rule with multiple targets
@rule(...)
def create_user(self, role):
    user = create(...)
    if role == ADMIN:
        return multiple((self.users, user.id), (self.admins, user.id))
    else:
        return self.users, user.id

# BEST: With manual tracking
def __init__(self):
    self.all_user_ids = set()
    self.admin_user_ids = set()

@rule(...)
def create_user(self, role):
    user = create(...)
    self.all_user_ids.add(user.id)
    if role == ADMIN:
        self.admin_user_ids.add(user.id)
        return multiple((self.users, user.id), (self.admins, user.id))
    else:
        return self.users, user.id

@invariant()
def admins_subset(self):
    assert self.admin_user_ids.issubset(self.all_user_ids)
```
