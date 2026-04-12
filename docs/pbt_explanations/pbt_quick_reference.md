# Property-Based Testing Quick Reference

## Overview

This is a quick reference for implementing property-based tests (PBT) in the project. For detailed examples and full strategy, see `docs/pbt_strategy.md`.

---

## The 5 Core Property Patterns

### 1. Roundtrip Properties ⭐⭐⭐ (MOST IMPORTANT)

**Pattern**: `create(x) → retrieve(id) → result == x`

**Example**:
```python
@given(st.text(min_size=3, max_size=50))
def test_username_roundtrip(self, test_repo, username):
    created = test_repo.users.create(...)
    retrieved = test_repo.users.get_by_id(created.id)
    assert retrieved.username == username
```

**Why powerful**: Tests persistence, serialization, and retrieval in one property.

---

### 2. Invariant Properties

**Pattern**: Certain facts ALWAYS true, regardless of operations.

**Examples**:
- User IDs are always non-empty
- Deleted entities return None on get
- Timestamps are always UTC
- Usernames are always unique

```python
@given(st.text(min_size=3, max_size=50))
def test_deleted_user_returns_none(self, test_repo, username):
    user = test_repo.users.create(...)
    test_repo.users.delete(user.id)
    assert test_repo.users.get_by_id(user.id) is None
```

---

### 3. Idempotency Properties

**Pattern**: Doing operation N times == doing it once.

**Example**:
```python
def test_create_super_admin_idempotent(self, test_repo):
    created1, user1 = test_repo.users.create_super_admin_if_needed(...)
    created2, user2 = test_repo.users.create_super_admin_if_needed(...)
    assert created1 is True
    assert created2 is False  # Second call is no-op
```

---

### 4. Metamorphic Properties

**Pattern**: Operation A + B should equal operation C.

**Example**:
```python
@given(st.text(), st.text())
def test_update_equivalent_to_create_with_final_value(self, test_repo, name1, name2):
    # Path 1: Create with name1, then update to name2
    org1 = test_repo.organizations.create(name=name1)
    test_repo.organizations.update(org1.id, name=name2)
    result1 = test_repo.organizations.get_by_id(org1.id)

    # Path 2: Create directly with name2
    org2 = test_repo.organizations.create(name=name2)
    result2 = test_repo.organizations.get_by_id(org2.id)

    # Both should have name2
    assert result1.name == name2
    assert result2.name == name2
```

---

### 5. Oracle Properties

**Pattern**: Use simpler implementation as "truth" to verify complex one.

**Example**:
```python
@given(st.lists(st.text()))
def test_filter_matches_python_filter(self, test_repo, names):
    # Create users
    for name in names:
        test_repo.users.create(username=name, ...)

    # Filter using repository
    repo_results = test_repo.users.get_by_filters(username_contains="test")

    # Filter using Python (oracle)
    python_results = [u for u in created_users if "test" in u.username]

    # Should match
    assert len(repo_results) == len(python_results)
```

---

## Top 10 High-Value Property Tests

### Priority 1: Repository Layer (Start Here)

1. **User username roundtrip** - Any valid username survives create-get cycle
2. **User username uniqueness** - Duplicate usernames always fail
3. **User password hashing** - Hash never equals plaintext
4. **Organization name roundtrip** - Any valid name survives create-get cycle
5. **Workflow status validation** - Statuses always match pattern `^[A-Z0-9_-]+$`

### Priority 2: Critical Business Logic

6. **Ticket status in workflow** - Ticket status always valid for project workflow
7. **Deleted entities return None** - Any deleted entity returns None on get
8. **Partial update preserves fields** - Updating one field doesn't change others
9. **Filtering is subset** - Filtered results always subset of all results
10. **Archive/unarchive consistency** - Archived flag always reflects actual state

---

## Custom Hypothesis Strategies

### Username
```python
USERNAME_CHARS = st.characters(
    whitelist_categories=("Lu", "Ll", "Nd"),
    whitelist_characters="_-"
)

usernames = st.text(min_size=3, max_size=50, alphabet=USERNAME_CHARS)
```

### Email
```python
@st.composite
def emails(draw):
    local = draw(st.text(min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("Ll", "Nd"))))
    domain = draw(st.text(min_size=1, max_size=63, alphabet=st.characters(whitelist_categories=("Ll", "Nd"))))
    tld = draw(st.sampled_from(["com", "org", "net"]))
    return f"{local}@{domain}.{tld}"
```

### Workflow Statuses
```python
workflow_statuses = st.lists(
    st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(whitelist_categories=("Lu", "Nd"), whitelist_characters="_-")
    ),
    min_size=1,
    max_size=20,
    unique=True
)
```

---

## Stateful Testing Template

```python
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, precondition

class UserStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.repo = get_test_repository()
        self.created_users = {}  # username -> id
        self.deleted_users = set()

    @rule(username=usernames)
    def create_user(self, username):
        assume(username not in self.created_users)
        user = self.repo.users.create(...)
        self.created_users[username] = user.id

    @rule()
    @precondition(lambda self: len(self.created_users) > 0)
    def delete_user(self):
        username = list(self.created_users.keys())[0]
        user_id = self.created_users[username]
        self.repo.users.delete(user_id)
        self.deleted_users.add(username)
        del self.created_users[username]

    @invariant()
    def check_consistency(self):
        # All created users should exist
        for username, user_id in self.created_users.items():
            user = self.repo.users.get_by_id(user_id)
            assert user is not None

        # All deleted users should not exist
        for username in self.deleted_users:
            user = self.repo.users.get_by_username(username)
            assert user is None

TestUserCRUD = UserStateMachine.TestCase
```

---

## Common Pitfalls & Solutions

### Pitfall 1: Unconstrained Input Generation

**Problem**: Hypothesis generates invalid data that clutters test output.

**Solution**: Use `assume()` to filter or constrain strategies properly.

```python
# ❌ BAD: Allows invalid emails
@given(st.text())
def test_email(email):
    user = create_user(email=email)  # May fail on invalid emails

# ✅ GOOD: Only generates valid emails
@given(st.emails())
def test_email(email):
    user = create_user(email=email)
```

### Pitfall 2: Flaky Tests from Database State

**Problem**: Tests interfere with each other due to shared database.

**Solution**: Use isolated database per test (already configured in `conftest.py`).

```python
# ✅ Each test gets fresh database via fixture
def test_something(self, test_repo: Repository):
    # test_repo uses isolated database
    pass
```

### Pitfall 3: Slow Tests

**Problem**: Generating 100 examples takes too long.

**Solution**: Use different profiles for dev vs CI.

```python
# pytest.ini
[hypothesis:dev]
max_examples = 20  # Fast during development

[hypothesis:ci]
max_examples = 1000  # Thorough in CI
```

**Run with**: `pytest --hypothesis-profile=ci`

### Pitfall 4: Unclear Failure Messages

**Problem**: "Falsifying example" is hard to understand.

**Solution**: Use `.example()` to debug specific case.

```python
@given(st.text())
def test_something(username):
    ...

# Debug with specific input
test_something.hypothesis.fuzz_one_input(b"specific_username")
```

---

## Quick Start Checklist

### Setup (5 minutes)
- [ ] Install Hypothesis: `uv add --dev hypothesis`
- [ ] Create `tests/property_based/` directory
- [ ] Create `tests/property_based/strategies.py` for custom strategies
- [ ] Create `tests/property_based/dal/test_user_properties.py`

### First Test (15 minutes)
- [ ] Write username roundtrip test
- [ ] Run: `pytest tests/property_based/dal/test_user_properties.py -v`
- [ ] Verify it generates multiple examples
- [ ] Check `--hypothesis-show-statistics` output

### Expand (ongoing)
- [ ] Add 5 more repository property tests (1 hour)
- [ ] Add stateful test for User CRUD (2 hours)
- [ ] Add API property tests (1 hour)

---

## Running Tests

```bash
# Run all property tests
pytest tests/property_based/

# Run with statistics
pytest tests/property_based/ --hypothesis-show-statistics

# Run with more examples (stress test)
pytest tests/property_based/ --hypothesis-profile=ci

# Run specific test
pytest tests/property_based/dal/test_user_properties.py::test_username_roundtrip

# Debug mode (show generated examples)
pytest tests/property_based/ -v --hypothesis-verbosity=verbose
```

---

## Integration with Existing Tests

**Property tests complement, not replace, example-based tests.**

| Test Type | Use For | Example |
|-----------|---------|---------|
| **Example-based** | Specific scenarios, documentation | `test_create_user_as_org_admin` |
| **Property-based** | Edge cases, invariants, exhaustive testing | `test_any_valid_username_roundtrip` |
| **Stateful** | Complex interaction bugs, state consistency | `test_user_crud_state_machine` |

**Strategy**:
1. Keep existing example tests (they're valuable documentation)
2. Add property tests for each entity's core operations
3. Add 1-2 stateful tests for most complex workflows

---

## Benefits Summary

✅ **Finds edge cases automatically** - Discovers bugs you wouldn't manually test
✅ **Minimal test code** - One property test → hundreds of test cases
✅ **Better coverage** - Tests all valid inputs, not just examples
✅ **Regression protection** - Hypothesis saves failing examples
✅ **Living documentation** - Properties document system invariants

---

## Next Steps

1. **Read full strategy**: See `docs/pbt_strategy.md` for detailed examples
2. **Start small**: Implement 1-2 roundtrip tests for User repository
3. **Expand gradually**: Add property tests alongside new features
4. **Add to CI**: Configure `hypothesis-profile=ci` for thorough testing

---

## Resources

- **Hypothesis Docs**: https://hypothesis.readthedocs.io/
- **Stateful Testing**: https://hypothesis.readthedocs.io/en/latest/stateful.html
- **Examples**: https://github.com/HypothesisWorks/hypothesis/tree/master/hypothesis-python/examples
