---
name: write-pbt
description: How to write property-based tests in this project using Hypothesis — when to use PBT, stateless vs stateful, invariants to target, and the mandatory regression-test rule when PBT discovers a bug. Use when the feature plan calls for PBT or when you spot an invariant worth property-testing.
---

# Property-based testing

Location: `backend/tests/property_based/`

## When to use PBT

Use PBT in addition to example-based tests when:
- An invariant should hold across **all** valid inputs (not a single case).
- You want to find edge cases traditional tests miss (unicode, boundary values, weird combinations).
- You're testing a stateful workflow with many possible action sequences.
- You want to verify data-integrity properties: roundtrip (`decode(encode(x)) == x`), count consistency, uniqueness, ordering.

Do NOT use PBT for:
- Behavior that's already fully covered by specific examples and has no meaningful variation in inputs.
- Tests where the "oracle" (expected answer) is just a re-implementation of the code under test.

## Two kinds

### 1. Stateless PBT — `tests/property_based/dal/`
Single operation, generated inputs, assert an invariant.

```python
from hypothesis import given, strategies as st

@given(username=st.text(min_size=1, max_size=50), email=st.emails())
def test_user_create_roundtrip(test_repo: Repository, username: str, email: str) -> None:
    """For any valid input, created user is retrievable with matching data."""
    user = test_repo.users.create(UserCreateCommand(...))
    retrieved = test_repo.users.get_by_id(user.id)
    assert retrieved == user
```

### 2. Stateful PBT — `tests/property_based/stateful/`
State machine with rules — Hypothesis picks sequences and checks invariants after every step.

```python
class UserAPIStateMachine(RuleBasedStateMachine):
    @rule(username=usernames(), email=emails())
    def create_user(self, username, email): ...

    @rule(data=data())
    def attempt_duplicate_email_update(self, data): ...

    @invariant()
    def emails_unique_within_org(self): ...
```

## Invariants to target (examples)
- **Roundtrip**: `get(create(x)).data == x`
- **Idempotency**: `f(f(x)) == f(x)` (e.g., bootstrap, upsert)
- **Count consistency**: `len(list()) == sum(created) - sum(deleted)`
- **Uniqueness**: no two entities in same org share the constrained field
- **Ordering preservation**: list order matches insertion/sort rule
- **Permission isolation**: role X never sees role Y's private data in any sequence
- **Non-decreasing audit log**: activity log only grows, never shrinks
- **Round-trip converters**: `orm_to_domain(domain_to_orm(d)) == d`

## CRITICAL: when PBT finds a bug

You MUST also create a hardcoded regression test. PBT stays as-is (it may find future bugs).

### For stateless PBT bugs — use `@example`
```python
@given(username=usernames(), email=emails())
@example(username="admin", email="duplicate@example.com")  # bug found by PBT
def test_user_create_with_duplicate_email_fails(...): ...
```

### For stateful PBT bugs — create a separate hardcoded API/repo test

```python
def test_duplicate_email_within_organization_fails(self, client, super_admin_token) -> None:
    """Regression test for bug discovered by property-based stateful testing.

    Bug Discovery:
    - Original test: tests/property_based/stateful/test_user_api.py::test_user_api_state_machine
    - Rule: attempt_duplicate_email_update
    - Issue: missing unique constraint on (organization_id, email)
    - Fix: added composite unique constraint

    This test ensures the bug doesn't regress.
    """
    # ... hardcoded repro ...
```

**Every regression test docstring MUST include**: (1) where the bug was found, (2) what the bug was, (3) how it was fixed, (4) "This test ensures the bug doesn't regress."

## Strategies (Hypothesis)
- Keep strategies composable and named (`usernames()`, `emails()`, `org_names()`).
- Put shared strategies in `tests/property_based/strategies.py` if multiple tests use them.
- Use `st.text(alphabet=..., min_size=..., max_size=...)` to bound search space. Don't let Hypothesis burn cycles on inputs the domain rejects anyway.

## Running PBT
```bash
cd backend && uv run pytest tests/property_based/ -x
# A single state machine (slower — don't parallelize with -n):
cd backend && uv run pytest tests/property_based/stateful/test_user_api.py -x -vv
```

## Reference material
Longer explanations and examples live in `docs/pbt_explanations/` — consult them when designing complex state machines.
