# Property-Based Testing Documentation

> Comprehensive guide to implementing property-based testing with Hypothesis for the project management CRUD application.

---

## 🚀 Start Here

**New to PBT?** → Read [`pbt_quick_reference.md`](pbt_quick_reference.md) (15 min)

**Ready to implement?** → Copy templates from [`pbt_invariants_cheatsheet.md`](pbt_invariants_cheatsheet.md)

**Need examples?** → Run `pytest tests/property_based_example.py -v`

---

## 📚 Documentation

### Quick Reference (15 minutes)
**[pbt_quick_reference.md](pbt_quick_reference.md)**
- 5 core property patterns
- Top 10 high-value tests
- Custom strategies
- Quick start checklist

### Complete Strategy (1 hour)
**[pbt_strategy.md](pbt_strategy.md)**
- 60+ specific test ideas
- Repository and API layer coverage
- Implementation roadmap
- Test organization

### Stateful Testing Guide (2 hours)
**[pbt_stateful_testing_guide.md](pbt_stateful_testing_guide.md)**
- 7 invariant patterns with examples
- State machine anatomy
- Advanced techniques
- Debugging tips

### Invariants Cheatsheet
**[pbt_invariants_cheatsheet.md](pbt_invariants_cheatsheet.md)**
- Quick reference for all patterns
- Copy-paste templates
- Anti-patterns to avoid
- Debugging guide

### Real Bug Examples (30 minutes)
**[pbt_bug_examples.md](pbt_bug_examples.md)**
- 12 concrete bug examples
- Exact invariants that catch each
- Why example-based tests miss them
- Bug detection matrix

### Complete Summary
**[pbt_summary.md](pbt_summary.md)**
- Documentation map
- Reading paths by role
- Implementation priorities
- Quick commands

---

## 🧪 Code Examples

### Stateless Properties
**[`tests/property_based_example.py`](../tests/property_based_example.py)**

Demonstrates:
- Roundtrip properties
- Uniqueness constraints
- Password hashing security
- Idempotency tests
- Custom strategies

Run: `pytest tests/property_based_example.py -v`

---

### Stateful Testing
**[`tests/stateful_example.py`](../tests/stateful_example.py)**

Demonstrates:
- User CRUD state machine
- Project lifecycle (archive/unarchive)
- Epic-Ticket relationships with Bundles
- Organization boundaries (permissions)
- All 7 invariant patterns

Run: `pytest tests/stateful_example.py -v`

---

## 🎯 Quick Start (30 Minutes)

### 1. Install Hypothesis
```bash
uv add --dev hypothesis
```

### 2. Run Examples
```bash
# Stateless properties
pytest tests/property_based_example.py::TestUserRepositoryProperties -v

# Stateful testing
pytest tests/stateful_example.py::TestUserCRUD -v
```

### 3. Create Your First Test
Copy template from [`pbt_invariants_cheatsheet.md`](pbt_invariants_cheatsheet.md) → Implement User roundtrip test

---

## 📖 Reading Paths

### Path 1: Learn PBT Concepts
1. [`pbt_quick_reference.md`](pbt_quick_reference.md) - Core concepts
2. Run examples: `pytest tests/property_based_example.py -v`
3. [`pbt_bug_examples.md`](pbt_bug_examples.md) - Why it matters
4. Implement your first test

### Path 2: Implement Stateful Tests
1. [`pbt_quick_reference.md`](pbt_quick_reference.md) - Overview
2. [`pbt_invariants_cheatsheet.md`](pbt_invariants_cheatsheet.md) - Templates
3. Copy state machine template
4. Implement User CRUD state machine
5. Reference [`pbt_stateful_testing_guide.md`](pbt_stateful_testing_guide.md) for details

### Path 3: Debug Failing Test
1. Check [`pbt_bug_examples.md`](pbt_bug_examples.md) - Similar bugs?
2. Review [`pbt_invariants_cheatsheet.md`](pbt_invariants_cheatsheet.md) - Debugging section
3. Reference [`pbt_stateful_testing_guide.md`](pbt_stateful_testing_guide.md) - Specific pattern

---

## 🔧 Common Commands

```bash
# Run all property-based tests
pytest tests/property_based/ -v

# Run stateful tests only
pytest tests/property_based/stateful/ -v

# Stress test (1000 examples)
pytest tests/property_based/ --hypothesis-profile=ci -v

# Show statistics
pytest tests/property_based/ --hypothesis-show-statistics

# Reproduce failure
pytest tests/property_based/ --hypothesis-seed=12345

# Debug mode
pytest tests/property_based/ -v --hypothesis-verbosity=verbose
```

---

## 🎓 Key Concepts

### Property-Based Testing
Tests **properties** that hold for **all valid inputs**, not just specific examples.

**Example**: "Any valid username survives create-get roundtrip" → Hypothesis generates 100+ usernames automatically.

### Stateful Testing
Tests **random operation sequences** to find interaction bugs.

**Example**: `create("alice") → delete("alice") → create("bob") → update("bob")` → Checks invariants after each operation.

### Invariants
Facts that **always hold**, regardless of operations.

**Examples**:
- Active users are retrievable
- Total created - deleted = current count
- Tickets reference existing projects
- Ticket status is in workflow

---

## 💡 What You'll Find

**Expected bugs**: 10-25 real bugs in mature codebases

**Bug categories**:
- CRUD bugs (soft delete, wrong entity): 30%
- Relationship bugs (orphaned entities): 25%
- Business rule violations: 20%
- Aggregate bugs (counts wrong): 15%
- Timestamp bugs: 5%
- Permission bugs: 5%

---

## ✅ Benefits

- 🔍 **Finds bugs automatically** - 10-25 real bugs
- 🎲 **Tests edge cases** - Thousands of generated inputs
- 📝 **Minimal code** - One property = 100+ examples
- 🛡️ **Regression protection** - Saves failing examples
- 📚 **Living documentation** - Properties document invariants
- 🔧 **Refactoring confidence** - Properties still pass

---

## 📊 Coverage Matrix

| Entity | Roundtrip | Counts | Relationships | Business Rules | Stateful |
|--------|-----------|--------|---------------|----------------|----------|
| **User** | ✅ Example | ✅ Example | → Org | Unique username | ✅ Example |
| **Organization** | ✅ Example | - | - | Unique name | - |
| **Project** | Strategy | ✅ Example | → Org, Workflow | Archive flag | ✅ Example |
| **Workflow** | ✅ Example | - | - | Status validation | - |
| **Ticket** | Strategy | - | → Project, Users | Status in workflow | Strategy |
| **Epic** | Strategy | ✅ Example | → Tickets | Aggregates | ✅ Example |

**Legend**: ✅ Example = Working code in examples | Strategy = Detailed in docs

---

## 🗺️ Implementation Roadmap

### Week 1: Foundation
- Install Hypothesis
- Create test structure
- Implement 2-3 roundtrip tests

### Week 2-3: Stateful Testing
- User CRUD state machine
- Shadow state + count invariants

### Week 4-5: Relationships
- Project state machine
- Ticket-Project relationships
- Epic-Ticket with Bundles

### Week 6-7: Business Rules
- Workflow validation
- Status transitions
- Permission boundaries

### Week 8: Polish
- Run with 1000 examples
- Fix discovered bugs
- Add to CI

---

## 📚 External Resources

- **Hypothesis Docs**: https://hypothesis.readthedocs.io/
- **Stateful Testing**: https://hypothesis.readthedocs.io/en/latest/stateful.html
- **Examples**: https://github.com/HypothesisWorks/hypothesis/tree/master/hypothesis-python/examples

---

## 🤝 Questions?

1. Check [`pbt_quick_reference.md`](pbt_quick_reference.md) for basics
2. See [`pbt_bug_examples.md`](pbt_bug_examples.md) for concrete examples
3. Review [`pbt_invariants_cheatsheet.md`](pbt_invariants_cheatsheet.md) for templates
4. Create an issue if still unclear

---

**Last Updated**: 2025-10-29
