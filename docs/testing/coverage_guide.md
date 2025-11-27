# Test Coverage Guide

## Quick Start

### Run Coverage
```bash
# Full coverage report
uv run pytest --cov=project_management_crud_example --cov-report=term-missing

# Coverage with HTML report (open htmlcov/index.html in browser)
uv run pytest --cov=project_management_crud_example --cov-report=html

# Coverage for specific component
uv run pytest tests/api/test_ticket_api.py --cov=project_management_crud_example/routers/ticket_api.py --cov-report=term-missing
```

### Current Coverage Status
- **Overall**: 95.11%
- **Target**: 95%+ maintained
- **Total Tests**: 703

## Coverage Reports by Test Suite

### 1. Overall Coverage (All Tests)
```bash
uv run pytest --cov=project_management_crud_example --cov-report=term-missing
```
**Shows**: Complete coverage across entire codebase
**Use for**: Release readiness, overall health check

### 2. API-Only Coverage
```bash
uv run pytest tests/api/ --cov=project_management_crud_example --cov-report=term-missing
```
**Shows**: How well API tests cover entire codebase (~90%)
**Use for**: Validating end-to-end test effectiveness

### 3. DAL-Only Coverage
```bash
uv run pytest tests/dal/ --cov=project_management_crud_example/dal --cov-report=term-missing
```
**Shows**: How well DAL tests cover data layer (~91%)
**Use for**: Validating unit test coverage of repositories

## Coverage Configuration

### Location
`.coveragerc` - Coverage configuration file

### What's Excluded
```ini
[run]
omit =
    */bootstrap.py          # App initialization (tested manually)
    */bootstrap_data.py     # Bootstrap/setup code
    */tests/*               # Test code itself
    */__pycache__/*         # Python cache
```

### Excluded from Reports
```ini
[report]
exclude_lines =
    pragma: no cover        # Explicit exclusions
```

## Using `pragma: no cover`

### When to Use
✅ **Good candidates**:
- General exception handlers (catch-all for unexpected errors)
- Debug-only code paths
- `__repr__` methods (developer convenience)
- Platform-specific code you can't test in CI

❌ **Bad candidates**:
- Business logic error handling
- Defensive checks that are testable
- Permission validations
- Any code that could realistically execute

### How to Use
```python
# Single line
def debug_only():  # pragma: no cover
    print("Debug info")

# Multiple lines
def debug_function():
    # pragma: no cover
    print("Debug line 1")
    print("Debug line 2")

# Whole function
@app.exception_handler(Exception)
async def catch_all(request, exc):  # pragma: no cover
    """Handles truly unexpected errors."""
    return error_response()
```

## Understanding Coverage Metrics

### Statement Coverage (What We Use)
- Measures which **lines of code** are executed
- Industry standard for Python
- Our target: 95%+

### What Coverage Does NOT Measure
- ❌ **Quality** of tests
- ❌ **All execution paths** (e.g., different combinations of if/else)
- ❌ **Business logic correctness**

### Good Coverage ≠ Good Tests
```python
# ❌ BAD: 100% coverage, 0% value
def add(a, b):
    return a + b

def test_add():
    add(1, 2)  # No assertion!

# ✅ GOOD: 100% coverage, 100% value
def test_add():
    assert add(1, 2) == 3
    assert add(-1, 1) == 0
    assert add(0, 0) == 0
```

## Coverage Gaps by Priority

### High Priority (Test These)
- Business logic error paths
- Permission/authorization checks
- Cross-organization access violations
- Data validation edge cases

### Medium Priority (Consider Testing)
- Defensive "should not happen" checks
- Error recovery paths
- Edge cases in filtering/searching

### Low Priority (Consider `pragma: no cover`)
- Debug utilities exception handlers
- Bootstrap error recovery
- ORM `__repr__` methods
- General exception catch-all handlers

## Component Coverage Goals

| Component | Target | Current | Status |
|-----------|--------|---------|--------|
| API Routers | 95%+ | 92-100% | ✅ |
| Repository | 95%+ | 95% | ✅ |
| Domain Models | 95%+ | 98.57% | ✅ |
| Utils | 90%+ | 83-100% | ✅ |

## Interpreting Coverage Reports

### Reading Terminal Output
```
Name                                    Stmts   Miss   Cover   Missing
---------------------------------------------------------------------
routers/ticket_api.py                     181      8  95.58%   188, 196, 293
```

- **Stmts**: Total statements in file
- **Miss**: Statements not executed
- **Cover**: Percentage covered
- **Missing**: Line numbers not covered

### Using HTML Reports
```bash
uv run pytest --cov=project_management_crud_example --cov-report=html
open htmlcov/index.html  # macOS
```

Benefits:
- Visual highlighting of covered/missed lines
- Click through to see exact uncovered code
- Filter by file/directory

## Common Coverage Scenarios

### Scenario 1: Adding New Feature
```bash
# Before implementation
uv run pytest --cov=project_management_crud_example --cov-report=term-missing

# Implement feature + tests

# Check coverage improved/maintained
uv run pytest --cov=project_management_crud_example --cov-report=term-missing

# Must maintain 95%+ overall coverage
```

### Scenario 2: Investigating Coverage Drop
```bash
# Run coverage with HTML report
uv run pytest --cov=project_management_crud_example --cov-report=html

# Open report
open htmlcov/index.html

# Find the file with dropped coverage
# Red lines = not covered
# Green lines = covered
# Yellow lines = partially covered (branches)
```

### Scenario 3: Testing Specific Component
```bash
# Check router coverage from API tests only
uv run pytest tests/api/test_ticket_api.py \
    --cov=project_management_crud_example/routers/ticket_api.py \
    --cov-report=term-missing

# Check if DAL tests cover repository
uv run pytest tests/dal/ \
    --cov=project_management_crud_example/dal \
    --cov-report=term-missing
```

## Best Practices

### ✅ DO
- Maintain 95%+ overall coverage
- Test business logic error paths
- Test permission boundaries
- Use `pragma: no cover` sparingly for truly untestable code
- Review coverage reports before merging PRs

### ❌ DON'T
- Chase 100% coverage at all costs
- Use `pragma: no cover` to hide undertested code
- Skip testing error paths because "they'll never happen"
- Ignore coverage drops without investigation
- Write tests just to hit coverage without assertions

## Troubleshooting

### Coverage Shows 0%
```bash
# Make sure you're running from project root
cd /path/to/project_management_crud_example_3

# Check .coveragerc is present
cat .coveragerc

# Run with explicit source
uv run pytest --cov=project_management_crud_example
```

### Missing Coverage Files
```bash
# Coverage files are in .gitignore
# To see them:
ls -la | grep coverage

# Should see:
# .coverage          (data file)
# .coveragerc        (config)
# htmlcov/           (HTML report directory)
```

### Coverage Lower Than Expected
1. Check if tests are actually running: `pytest -v`
2. Check if coverage is measuring right source: `--cov=project_management_crud_example`
3. Review HTML report to see what's missed: `--cov-report=html`
4. Verify `.coveragerc` omit list isn't too aggressive

## Quick Reference

```bash
# Most common commands
uv run pytest --cov=project_management_crud_example --cov-report=term-missing    # Terminal report
uv run pytest --cov=project_management_crud_example --cov-report=html            # HTML report
uv run pytest --cov=project_management_crud_example --cov-report=term-missing:skip-covered  # Only show incomplete files

# Useful flags
--cov-report=term-missing:skip-covered   # Hide 100% covered files
--cov-report=html                        # Generate HTML report
--cov-report=xml                         # Generate XML (for CI tools)
--cov-fail-under=95                      # Fail if coverage below 95%
```

## Related Documentation
- [Testing Guidelines](../spec/how_to_write_specs.md)
- [Test Implementation Guide](../how_to_implement_tasks.md)
- [Test Structure](../../tests/CLAUDE.md)
