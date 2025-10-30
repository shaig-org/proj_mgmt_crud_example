# Property-Based Testing: Complete Documentation Summary

## Document Overview

This directory contains comprehensive documentation for implementing property-based testing (PBT) with Hypothesis in the project management CRUD application.

---

## 📚 Documentation Map

### 1. **Quick Start** (15 minutes)

**Read First**: [`pbt_quick_reference.md`](pbt_quick_reference.md)

**What it covers**:
- 5 core property patterns (roundtrip, invariants, idempotency, metamorphic, oracle)
- Top 10 high-value property tests to implement first
- Custom Hypothesis strategies (usernames, emails, workflows)
- Common pitfalls and solutions
- Quick start checklist

**Best for**: Getting started quickly, learning core concepts.

---

### 2. **Comprehensive Strategy** (1 hour)

**Read Second**: [`pbt_strategy.md`](pbt_strategy.md)

**What it covers**:
- Detailed explanation of all 5 property patterns with examples
- 60+ specific test ideas for repository and API layers
- Stateful testing introduction
- Custom strategies for all domain models
- 10-week implementation roadmap
- Test organization and file structure

**Best for**: Planning your PBT implementation, understanding all options.

---

### 3. **Stateful Testing Deep Dive** (2 hours)

**Read Third**: [`pbt_stateful_testing_guide.md`](pbt_stateful_testing_guide.md)

**What it covers**:
- 7 invariant patterns explained in detail:
  1. Shadow State Consistency
  2. Count Invariants
  3. Relationship Invariants
  4. Business Rule Invariants
  5. Aggregate Consistency
  6. Temporal Consistency
  7. Permission Invariants
- Complete state machine anatomy
- Advanced techniques (Bundles, multiple state machines)
- Debugging tips

**Best for**: Implementing stateful tests, understanding invariants deeply.

---

### 4. **Invariants Cheatsheet** (Quick Reference)

**Bookmark**: [`pbt_invariants_cheatsheet.md`](pbt_invariants_cheatsheet.md)

**What it covers**:
- Quick reference for all 7 invariant patterns
- Code templates for each pattern
- Complete state machine template
- Anti-patterns to avoid
- Debugging tips
- Quick start checklist

**Best for**: Reference while coding, copy-paste templates.

---

### 5. **Real Bug Examples** (30 minutes)

**Read**: [`pbt_bug_examples.md`](pbt_bug_examples.md)

**What it covers**:
- 12 concrete bug examples from 6 categories:
  - CRUD operation bugs
  - Relationship bugs
  - Business rule violations
  - Aggregate/count bugs
  - Timestamp bugs
  - Permission/multi-tenancy bugs
- Exact invariants that catch each bug
- Why example-based tests miss these bugs
- Bug detection matrix

**Best for**: Understanding what PBT catches that you'd miss otherwise.

---

## 🧪 Code Examples

### 1. **Stateless Property Tests**

**File**: [`tests/property_based_example.py`](../tests/property_based_example.py)

**What it contains**:
- Roundtrip properties (User, Organization, Workflow)
- Uniqueness constraints
- Password hashing security
- Idempotency tests
- Custom Hypothesis strategies

**Run**: `pytest tests/property_based_example.py -v`

---

### 2. **Stateful Property Tests**

**File**: [`tests/stateful_example.py`](../tests/stateful_example.py)

**What it contains**:
- User CRUD state machine (shadow state, counts)
- Project lifecycle state machine (archive/unarchive)
- Epic-Ticket state machine (relationships with Bundles)
- Organization boundaries state machine (permissions)
- All 7 invariant patterns demonstrated

**Run**: `pytest tests/stateful_example.py -v`

---

## 📖 Reading Path by Role

### If You're New to Property-Based Testing

**Path**: Learn concepts → See examples → Implement

1. Read: `pbt_quick_reference.md` (15 min) - Learn core concepts
2. Run: `pytest tests/property_based_example.py -v` (5 min) - See it work
3. Read: `pbt_bug_examples.md` (30 min) - Understand why it matters
4. Implement: Start with User roundtrip test (30 min)
5. Read: `pbt_stateful_testing_guide.md` (2 hours) - Deep dive when ready

---

### If You're Implementing PBT Now

**Path**: Quick start → Templates → Implementation

1. Read: `pbt_quick_reference.md` (15 min) - Overview
2. Bookmark: `pbt_invariants_cheatsheet.md` - Reference
3. Copy: State machine template from cheatsheet
4. Implement: User CRUD state machine using template
5. Reference: `pbt_stateful_testing_guide.md` for specific invariants

---

### If You're Debugging a Failing PBT

**Path**: Examples → Debugging → Reference

1. Look at: `pbt_bug_examples.md` - Similar bugs?
2. Check: `pbt_invariants_cheatsheet.md` - Debugging section
3. Reference: `pbt_stateful_testing_guide.md` - Specific invariant pattern

---

## 🎯 Implementation Priorities

### Phase 1: Foundation (Week 1)
- [ ] Install Hypothesis: `uv add --dev hypothesis`
- [ ] Create `tests/property_based/` structure
- [ ] Implement username roundtrip test
- [ ] Implement organization name roundtrip test

### Phase 2: Stateful Testing (Week 2-3)
- [ ] Implement User CRUD state machine
- [ ] Add shadow state invariants
- [ ] Add count invariants
- [ ] Test with 100 examples

### Phase 3: Relationships (Week 4-5)
- [ ] Implement Project state machine (archive/unarchive)
- [ ] Implement Ticket-Project relationship invariants
- [ ] Implement Epic-Ticket state machine with Bundles

### Phase 4: Business Rules (Week 6-7)
- [ ] Workflow status validation invariants
- [ ] Ticket status in workflow invariants
- [ ] Permission boundary invariants

### Phase 5: Polish (Week 8)
- [ ] Run all tests with 1000 examples
- [ ] Fix any discovered bugs
- [ ] Add to CI pipeline
- [ ] Document findings

---

## 🔧 Quick Commands

### Run All Property-Based Tests
```bash
pytest tests/property_based/ -v
```

### Run Stateful Tests Only
```bash
pytest tests/property_based/stateful/ -v
```

### Run with More Examples (Stress Test)
```bash
pytest tests/property_based/ --hypothesis-profile=ci -v
```

### Show Statistics
```bash
pytest tests/property_based/ --hypothesis-show-statistics
```

### Reproduce Specific Failure
```bash
pytest tests/property_based/ --hypothesis-seed=12345
```

### Debug Mode (Show Generated Values)
```bash
pytest tests/property_based/ -v --hypothesis-verbosity=verbose
```

---

## 📊 Coverage Matrix

### Repository Layer

| Entity | Roundtrip | Count | Relationships | Business Rules | Temporal | Permissions |
|--------|-----------|-------|---------------|----------------|----------|-------------|
| User | ✅ Example | ✅ Example | → Org | Unique username | ✅ | Org boundary |
| Organization | ✅ Example | - | - | Unique name | - | - |
| Project | ✅ Strategy | ✅ Example | → Org, Workflow | Archive flag | - | Org boundary |
| Workflow | ✅ Example | - | - | ✅ Statuses | - | - |
| Ticket | ✅ Strategy | - | → Project, User | ✅ Status | - | - |
| Epic | ✅ Strategy | ✅ Example | → Tickets | - | - | Org boundary |
| Comment | ✅ Strategy | - | → Ticket, User | - | - | - |

**Legend**:
- ✅ Example: Working code in examples
- ✅ Strategy: Detailed in strategy doc
- Number: Priority level

---

## 🎓 Key Concepts Summary

### What is Property-Based Testing?

**Traditional Testing**:
```python
def test_create_user():
    user = create_user("alice")
    assert user.username == "alice"
```
Tests **one example** with **specific input**.

**Property-Based Testing**:
```python
@given(username=st.text(min_size=3, max_size=50))
def test_create_user_roundtrip(username):
    user = create_user(username)
    retrieved = get_user(user.id)
    assert retrieved.username == username
```
Tests **property** that holds for **all valid inputs** (Hypothesis generates 100+ examples).

---

### What is Stateful Testing?

**Traditional Testing**: One operation at a time
```python
def test_create_then_delete():
    user = create_user("alice")
    delete_user(user.id)
    assert get_user(user.id) is None
```

**Stateful Testing**: Random operation sequences
```python
# Hypothesis generates sequences like:
# create("alice") → create("bob") → delete("alice") → create("carol") → ...
# And checks invariants after EVERY operation
```

Finds bugs in **interaction sequences** that manual tests miss.

---

### What are Invariants?

**Invariants** are facts that should **always be true**, regardless of operations performed.

**Examples**:
- "All active users can be retrieved by ID" (Shadow State)
- "Total created - deleted = current count" (Count Invariants)
- "All tickets reference existing projects" (Relationships)
- "Ticket status is in workflow" (Business Rules)

**Why powerful**: Checked **automatically** after **every operation** in **hundreds of sequences**.

---

## 💡 Key Insights

### 1. Stateful Testing Finds Deep Bugs

Example-based tests check **specific paths**:
- Create → Get ✓
- Create → Update → Get ✓
- Create → Delete → Get ✓

Stateful tests check **all paths**:
- Hypothesis generates random sequences
- Checks invariants after **every** operation
- Finds bugs in combinations you'd never think to test

**Example**: "Create 3 users, delete 2nd, update 1st, create 4th, delete 3rd" — would you manually test this? Hypothesis does automatically.

---

### 2. Invariants Are More Powerful Than Assertions

**Traditional assertion**:
```python
assert user.username == "alice"  # Checks specific value
```

**Invariant**:
```python
@invariant()
def all_users_retrievable(self):
    for user_id in self.active_users:
        assert self.repo.get(user_id) is not None
```
Checks **property for all entities** after **every operation**.

---

### 3. Shadow State Catches Most Bugs

Maintaining a Python dict/set of "what should exist" catches:
- Soft delete bugs (deleted items still retrievable)
- Update wrong entity bugs (ID mixups)
- Count mismatches
- Missing cascade deletes

**Pattern**:
```python
self.active_entities = {}   # What SHOULD exist
self.deleted_entities = set()  # What SHOULD NOT exist

@invariant()
def verify_shadow_state_matches_reality():
    # Check real system matches shadow state
```

---

## 🚀 Quick Start (30 Minutes)

### Step 1: Install (2 minutes)
```bash
uv add --dev hypothesis
```

### Step 2: Run Examples (5 minutes)
```bash
# See stateless properties in action
pytest tests/property_based_example.py::TestUserRepositoryProperties -v

# See stateful testing in action
pytest tests/stateful_example.py::TestUserCRUD -v
```

### Step 3: Understand (10 minutes)
Read the output from Step 2. Notice:
- Hypothesis generates many examples automatically
- Tests explore edge cases (empty strings, max length, special chars)
- Stateful tests show operation sequences

### Step 4: Create Your First Test (15 minutes)

Create `tests/property_based/test_my_first_pbt.py`:
```python
from hypothesis import given
from hypothesis.strategies import text

@given(name=text(min_size=1, max_size=255))
def test_organization_name_roundtrip(test_repo, name):
    """Any valid org name should survive create-get cycle."""
    # Create
    org_data = OrganizationData(name=name)
    created = test_repo.organizations.create(
        OrganizationCreateCommand(organization_data=org_data)
    )

    # Retrieve
    retrieved = test_repo.organizations.get_by_id(created.id)

    # Verify
    assert retrieved is not None
    assert retrieved.name == name
```

Run:
```bash
pytest tests/property_based/test_my_first_pbt.py -v
```

Congratulations! You've written your first property-based test.

---

## 📈 Expected Results

### What You'll Find

**Week 1**: 0-2 bugs (most foundational code is solid)
**Week 2-3**: 3-7 bugs (edge cases, race conditions)
**Week 4-5**: 5-10 bugs (relationship bugs, cascade issues)
**Week 6+**: 2-5 bugs (business rule violations, subtle bugs)

**Total**: Expect to find **10-25 real bugs** that your example-based tests missed.

### Bug Categories Found

1. **CRUD bugs** (soft delete, wrong entity updated): 30%
2. **Relationship bugs** (orphaned entities, cascade failures): 25%
3. **Business rule violations** (invalid status, validation skipped): 20%
4. **Aggregate bugs** (counts wrong, duplicates): 15%
5. **Timestamp bugs** (timezone issues, immutability): 5%
6. **Permission bugs** (cross-org leaks): 5%

---

## 🎉 Benefits Summary

✅ **Finds bugs automatically** - 10-25 real bugs in mature codebases
✅ **Tests edge cases** - Thousands of generated inputs
✅ **Minimal code** - One property test = 100+ example tests
✅ **Regression protection** - Hypothesis saves failing examples
✅ **Living documentation** - Properties document system invariants
✅ **Confidence in refactoring** - Properties still pass after changes
✅ **Catches interaction bugs** - Stateful testing finds deep bugs

---

## 📚 Further Learning

### Official Resources
- **Hypothesis Docs**: https://hypothesis.readthedocs.io/
- **Stateful Testing Guide**: https://hypothesis.readthedocs.io/en/latest/stateful.html
- **Examples**: https://github.com/HypothesisWorks/hypothesis/tree/master/hypothesis-python/examples

### Recommended Reading
- "Property-Based Testing with PropEr, Erlang, and Elixir" - Concepts apply to Python
- David MacIver's blog: https://www.drmaciver.com/

### Community
- Hypothesis issue tracker: https://github.com/HypothesisWorks/hypothesis/issues
- #hypothesis on Python Discord

---

## 🤝 Contributing

Found a bug with PBT? Document it:
1. Add example to `pbt_bug_examples.md`
2. Show which invariant caught it
3. Include failing test output

Created useful strategies? Share:
1. Add to `pbt_strategy.md`
2. Include example usage
3. Document edge cases

---

## 📝 License

Documentation and examples follow the project's license.

Hypothesis library is MPL-2.0 licensed.

---

**Last Updated**: 2025-10-29

**Maintained By**: Project Team

**Questions?** See `pbt_quick_reference.md` or create an issue.
