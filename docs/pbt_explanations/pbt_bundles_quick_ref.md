# Hypothesis Bundles: Quick Reference Card

## Bundle Syntax Cheat Sheet

### Declare Bundles (Class Level)

```python
class MyStateMachine(RuleBasedStateMachine):
    users = Bundle("users")
    projects = Bundle("projects")
```

---

## Adding to Bundles: Two Syntaxes

### Syntax 1: Using `target=` Parameter

```python
@rule(target=users)
def create_user(self):
    user = create(...)
    return user.id  # ✅ Add to 'users'

@rule(target=users)
def skip_creating_user(self, should_skip: bool):
    if should_skip:
        return multiple()  # ✅ Skip - add nothing
    return user.id
```

**When to use**: Simple single-bundle addition

---

### Syntax 2: Using Tuple Returns (No `target=`)

```python
@rule()  # NO target= parameter
def create_user(self):
    user = create(...)
    return self.users, user.id  # ✅ (bundle, value) tuple

@rule()
def skip_creating_user(self, should_skip: bool):
    if should_skip:
        return multiple()  # ✅ Skip - add nothing
    return self.users, user.id
```

**When to use**: Multiple bundles, subset relationships, conditional selection

---

## Common Operations

### Add to One Bundle

**With `target=`**:
```python
@rule(target=users)
def create_user(self):
    return user.id
```

**With tuples**:
```python
@rule()
def create_user(self):
    return self.users, user.id
```

---

### Add to Multiple Bundles (Subset Pattern)

```python
from hypothesis.stateful import multiple

@rule()  # NO target=
def create_user(self, role: UserRole):
    user = create(..., role=role)

    if role == UserRole.ADMIN:
        return multiple(
            (self.users, user.id),   # Add to both
            (self.admins, user.id)
        )
    else:
        return self.users, user.id  # Add to users only
```

**Can't use `target=` for this** - must use tuple syntax.

---

### Skip Adding (Conditional)

```python
@rule(target=users)  # OR @rule() with tuples
def maybe_create_user(self, should_skip: bool):
    if should_skip:
        return multiple()  # ✅ Add nothing

    user = create(...)
    return user.id  # With target=
    # OR return self.users, user.id  # Without target=
```

**Works with both syntaxes!**

---

### Consume from Bundle

```python
@rule(user_id=users)  # Get value FROM bundle
def delete_user(self, user_id: str):
    delete(user_id)
```

**Automatic**: Rule only runs if bundle is non-empty.

---

### Consume from Multiple Bundles

```python
@rule(project_id=projects, reporter_id=users)
def create_ticket(self, project_id: str, reporter_id: str):
    create_ticket(project=project_id, reporter=reporter_id)
```

**Hypothesis picks**: Automatically selects interesting combinations.

---

## Quick Decision Tree

```
Do you need to add to multiple bundles?
├─ YES → Use tuple syntax (no target=)
│         return multiple((bundle1, v), (bundle2, v))
│
└─ NO → Do you need conditional addition?
   ├─ YES → Use tuple syntax (more flexible)
   │         if cond: return multiple()
   │         else: return bundle, value
   │
   └─ NO → Either syntax works
            target= is simpler
```

---

## Common Patterns

### Pattern 1: Simple Addition

```python
@rule(target=users)
def create_user(self):
    return user.id
```

---

### Pattern 2: Subset Bundles

```python
@rule()  # NO target=
def create_user(self, role):
    if role == ADMIN:
        return multiple((self.users, id), (self.admins, id))
    return self.users, id
```

---

### Pattern 3: Conditional Skip

```python
@rule(target=users)
def create_user(self):
    if at_limit():
        return multiple()  # Skip
    return user.id
```

---

### Pattern 4: With Tracking

```python
def __init__(self):
    self.all_user_ids = set()

@rule()
def create_user(self):
    user = create(...)
    self.all_user_ids.add(user.id)  # Manual tracking
    return self.users, user.id  # Bundle
```

---

## Common Mistakes

### ❌ WRONG: Mixing `target=` with Tuples

```python
@rule(target=users)  # Has target=
def create_user(self):
    return self.users, user.id  # ❌ Error! Can't use both
```

**Fix**: Pick one syntax:
```python
@rule(target=users)  # Use target=
def create_user(self):
    return user.id  # ✅ Just value

# OR

@rule()  # No target=
def create_user(self):
    return self.users, user.id  # ✅ Tuple
```

---

### ❌ WRONG: `target=` with Multiple Bundles

```python
@rule(target=users)
def create_admin(self):
    return multiple(user.id, user.id)  # ❌ Adds to 'users' twice!
```

**Fix**: Use tuple syntax:
```python
@rule()  # NO target=
def create_admin(self):
    return multiple(
        (self.users, user.id),
        (self.admins, user.id)
    )  # ✅ Adds to both bundles
```

---

### ❌ WRONG: Returning `None`

```python
@rule(target=users)
def maybe_create(self, skip: bool):
    if skip:
        return None  # ❌ Might add None to bundle!
```

**Fix**: Use `multiple()`:
```python
@rule(target=users)
def maybe_create(self, skip: bool):
    if skip:
        return multiple()  # ✅ Adds nothing
```

---

## Syntax Comparison Table

| Operation | `target=` Syntax | Tuple Syntax |
|-----------|------------------|--------------|
| **Add to one bundle** | `return value` | `return bundle, value` |
| **Add to multiple** | ❌ Not supported | `return multiple((b1, v), (b2, v))` |
| **Skip adding** | `return multiple()` | `return multiple()` |
| **Consume from bundle** | `@rule(v=bundle)` | `@rule(v=bundle)` |
| **Subset pattern** | ❌ Not supported | ✅ Use `multiple()` |

---

## Complete Example

```python
from hypothesis.stateful import RuleBasedStateMachine, rule, Bundle, multiple
from hypothesis import strategies as st

class MyStateMachine(RuleBasedStateMachine):
    # Declare bundles
    users = Bundle("users")
    admins = Bundle("admins")
    projects = Bundle("projects")

    def __init__(self):
        super().__init__()
        self.repo = get_repository()
        self.deleted_users = set()

    # Add to one bundle (target= syntax)
    @rule(target=projects)
    def create_project(self):
        project = self.repo.projects.create(...)
        return project.id

    # Add to multiple bundles (tuple syntax)
    @rule(role=st.sampled_from([UserRole.ADMIN, UserRole.WRITE]))
    def create_user(self, role: UserRole):
        user = self.repo.users.create(..., role=role)

        if role == UserRole.ADMIN:
            return multiple(
                (self.users, user.id),
                (self.admins, user.id)
            )
        return self.users, user.id

    # Skip adding conditionally (works with both syntaxes)
    @rule(target=projects)
    def maybe_create_project(self):
        if len(self.all_projects) >= 100:
            return multiple()  # Skip
        project = self.repo.projects.create(...)
        return project.id

    # Consume from bundles
    @rule(user_id=users)
    def delete_user(self, user_id: str):
        if user_id in self.deleted_users:
            return
        self.repo.users.delete(user_id)
        self.deleted_users.add(user_id)

    # Consume from multiple bundles
    @rule(project_id=projects, admin_id=admins)
    def assign_admin_to_project(self, project_id: str, admin_id: str):
        if admin_id in self.deleted_users:
            return
        self.repo.projects.set_owner(project_id, admin_id)
```

---

## Key Takeaways

1. **Two syntaxes**: `target=` (simple) vs tuple (flexible)
2. **`multiple()` means skip**: Works with both syntaxes
3. **Subsets need tuples**: Can't use `target=` for multiple bundles
4. **Don't mix syntaxes**: Either use `target=` OR tuples, not both
5. **Bundles never shrink**: Use manual tracking for deletions

---

## Quick Reference

```python
# DECLARE
users = Bundle("users")

# ADD (target= syntax)
@rule(target=users)
def add(self): return value

# ADD (tuple syntax)
@rule()
def add(self): return self.users, value

# ADD TO MULTIPLE
@rule()
def add(self): return multiple((self.users, v), (self.admins, v))

# SKIP
@rule(target=users)  # or @rule()
def skip(self): return multiple()

# CONSUME
@rule(value=users)
def use(self, value): ...
```

---

For detailed guides, see:
- [`pbt_bundles_guide.md`](pbt_bundles_guide.md) - Complete reference
- [`pbt_bundles_visual.md`](pbt_bundles_visual.md) - Visual guide
- [`pbt_bundles_subset_pattern.md`](pbt_bundles_subset_pattern.md) - Subset bundles
- [`pbt_bundles_conditional.md`](pbt_bundles_conditional.md) - Conditional addition
