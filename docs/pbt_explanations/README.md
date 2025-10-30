# Property-Based Testing (PBT) Explanations

This directory contains educational documentation and examples about property-based testing with Hypothesis.

## Contents

### Strategy & Overview
- **pbt_strategy.md** - Comprehensive strategy with 60+ test ideas for this codebase
- **pbt_quick_reference.md** - 15-minute overview of PBT concepts
- **pbt_summary.md** - Documentation map and reading guide
- **README_PBT.md** - Visual index for all documentation
- **PBT_EXPLORATION_SUMMARY.md** - Initial exploration and ideas

### Stateful Testing
- **pbt_stateful_testing_guide.md** - Deep dive on stateful testing with 7 invariant patterns
- **pbt_invariants_cheatsheet.md** - Quick reference for invariant patterns

### Hypothesis Bundles
- **pbt_bundles_guide.md** - Complete technical guide on Hypothesis Bundles
- **pbt_bundles_visual.md** - Visual guide with diagrams
- **pbt_bundles_quick_ref.md** - Quick reference card for bundle syntax
- **pbt_bundles_subset_pattern.md** - Subset bundle pattern (admins ⊂ users)
- **pbt_bundles_conditional.md** - Conditional addition and skipping

### Bug Examples
- **pbt_bug_examples.md** - 12 concrete bug examples that PBT catches

### Example Code
- **property_based_example.py** - Stateless property test examples
- **stateful_example.py** - Four state machine examples

## Actual Tests

The actual working property-based tests are in `tests/property_based/`:
- `tests/property_based/dal/test_user_properties.py` - Repository roundtrip test
- `tests/property_based/stateful/test_user_crud.py` - Repository CRUD state machine
- `tests/property_based/stateful/test_user_api.py` - API endpoint state machine

## Note

This documentation was created during the initial exploration and learning phase. The actual implementation may differ from the examples shown here.
