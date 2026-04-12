# How to Implement Tasks

This guide defines the process for implementing tasks from the task list.

## Task Implementation Process

When user approves implementing tasks, work autonomously through each task using this standardized process.

Tasks follow a plan-implement-validate feedback loop, descibed below.

### Standardized Progress Messages

Use these exact format messages to show progress:

```markdown
### 🎯 Starting Task: [Task Name]
**Implements**: REQ-XXX-YYY, REQ-XXX-ZZZ
**Status**: ⏳ → 🔄

---

### 📋 Planning Task: [Task Name]
Reading spec requirements...
[description of what you're doing]

---

### 📝 Writing Implementation Plan
Creating task_implementation_plan.md...

---

### 💻 Implementing: [Task Name]
[concise description of what's being implemented]

---

### ✅ Validating: [Task Name]
Running cd backend && ./devtools/run_all_agent_validations.sh...

---

### 📊 Updating Status
- Task status: 🔄 → ✅
- Requirements: 🔴 → ✅
```

## Step 1: Plan Task

**Message**: `### PLANNING TASK: [Task Name]`

**Actions**:
1. Read ALL relevant spec requirements this task implements
2. Understand the observable behaviors required
3. Check if any existing code/tests need updates
4. Design comprehensive test coverage (see below)
5. Write task implementation plan file

### Task Implementation Plan File

**File**: `docs/tasks/task_implementation_plan.md` (overwrites each task)

**Purpose**: Detailed planning document for current task implementation

**Format**:
```markdown
# Task Implementation Plan: [Task Name]

**Task Status**: 🔄 In Progress
**Date**: YYYY-MM-DD
**Implements Requirements**: REQ-XXX-YYY, REQ-XXX-ZZZ

## Behaviors to Implement

### From REQ-XXX-YYY: [Requirement Title]
**Observable Behavior**:
- [What external systems can verify]
- [API endpoints/responses involved]
- [State changes observable through API]

**Acceptance Criteria**:
- [Criterion 1 from spec]
- [Criterion 2 from spec]

### From REQ-XXX-ZZZ: [Another Requirement]
[Same format...]

## Implementation Plan

### Domain Layer Changes
- [ ] Create/modify XYZ model in domain_models.py
- [ ] Add validation rules: [specific rules]
- [ ] Fields: [list fields and types]

### Repository Layer Changes
- [ ] Create/modify XYZ repository
- [ ] Implement methods: create_xyz(), get_xyz_by_id(), etc.
- [ ] Add ORM model in orm_data_models.py
- [ ] Add converters in converters.py

### API Layer Changes
- [ ] Create/modify routers/xyz_api.py
- [ ] Endpoints: POST /xyz, GET /xyz/{id}, etc.
- [ ] Add dependency injection in dependencies.py
- [ ] Error handling: 404, 400/422, etc.

### Other Changes
- [ ] Update database.py to include new tables
- [ ] [Any other changes needed]

## Test Planning

### 1. API Tests (External Behavior)
**File**: tests/api/test_xyz_api.py

**Tests for REQ-XXX-YYY**:
- `test_after_create_xyz_get_returns_the_xyz`
  - Verifies: Created XYZ is retrievable via GET
  - Steps: POST /xyz → GET /xyz/{id} → verify data matches

- `test_after_create_xyz_appears_in_list`
  - Verifies: Created XYZ appears in GET /xyz list
  - Steps: POST /xyz → GET /xyz → verify in list

- `test_create_xyz_with_invalid_data_returns_400`
  - Verifies: Validation errors handled properly
  - Steps: POST invalid data → assert 400 → verify error message

[List ALL API tests needed for all requirements]

**Edge Cases**:
- Maximum length inputs
- Minimum length inputs
- Special characters
- Unicode characters
- Concurrent operations
- [Other edge cases from spec]

### 2. Repository Layer Tests
**File**: tests/dal/test_xyz_repository.py

**Repository tests** (test through repository, not HTTP):
- `test_create_xyz_then_get_by_id_returns_it`
  - Verifies: Repository create + retrieve workflow
  - Uses: repository.create_xyz() → repository.get_xyz_by_id()

- `test_get_xyz_by_non_existent_id_returns_none`
  - Verifies: Repository handles not-found correctly
  - Uses: repository.get_xyz_by_id("fake-id") → assert None

- `test_create_xyz_appears_in_get_all`
  - Verifies: Repository list includes created items
  - Uses: create → get_all → verify in list

[List ALL repository tests needed]

### 3. Utility/Logic Tests (if applicable)
**File**: tests/utils/test_xyz_utils.py (if needed)

[List any utility function tests]

### 4. Domain Model Validation Tests (if applicable)
**File**: tests/domain/test_xyz_models.py (if needed)

[List any Pydantic validation tests]

## Existing Tests to Update

- [ ] tests/api/test_abc.py - Update because [reason]
- [ ] tests/dal/test_abc_repository.py - Update because [reason]

## Dependencies

**Requires completion of**:
- Task N (if any)

**Blocks**:
- Task M (if any)

## Notes

[Any additional implementation notes, concerns, or decisions]
```

## Step 2: Implement Task

**Message**: `### IMPLEMENTING: [Task Name]`

**Actions**:
1. Implement all code layers (domain, repository, API) as planned
2. Implement ALL tests as planned:
   - External behavior tests (API)
   - Repository layer tests
   - Utility tests
   - Domain validation tests
3. Ensure complete coverage of all requirements
4. No partial implementations

**Implementation Order**:
1. Domain models (if needed)
2. ORM models + converters
3. Repository layer
4. Repository tests (verify repository works)
5. API layer
6. API tests (verify complete workflows)
7. Utility tests (if any)

## Step 3: Validate

**Message**: `### VALIDATING: [Task Name]`

**Actions**:
1. Run `cd backend && ./devtools/run_all_agent_validations.sh`
2. Fix any failures (see validation feedback loop below)
3. Repeat until ZERO errors/warnings

### Validation Feedback Loop

When validation fails:

1. **Identify failure** - test, lint, type error?

2. **Check spec FIRST**:
   - Re-read relevant spec section
   - Confirm correct behavior
   - Verify understanding matches spec

3. **Determine fix**:
   - Code wrong? → Fix code to match spec
   - Test wrong? → Verify against spec, then fix test
   - NEVER change tests just to make them pass

4. **Apply fix and re-run** - Repeat until passing

**🚨 ZERO TOLERANCE 🚨**
- ZERO test failures
- ZERO linting errors
- ZERO type errors
- ZERO warnings

**✅ ONLY 2 ACCEPTABLE OUTCOMES ✅**
- All validations pass
- You've tried to fix and failed (tell user)

## Step 4: Update Status

**Message**: `### 📊 Updating Status`

**Actions**:
1. Update task status in `docs/tasks/current_task_list.md`: 🔄 → ✅
2. Update requirement statuses in spec files: 🔴 → ✅
3. Update feature status counts if needed

## Step 5: Request Commit Approval

**Message**: `### ✅ Task Complete - Ready to Commit`

**Actions**:
1. Summarize what was implemented
2. List requirements completed
3. Confirm all validations passed
4. Ask user for approval to commit

**Format**:
```
### ✅ Task Complete - Ready to Commit

**Implemented**: [Task name]
**Requirements completed**: REQ-XXX-YYY ✅, REQ-XXX-ZZZ ✅
**Tests added**: [count] API tests, [count] repository tests
**Validations**: ✅ All passed (zero errors/warnings)

Ready to commit?
```

## Test Coverage Requirements

Every task implementation MUST include tests for:

### 1. External Behavior (API Tests) - ALWAYS REQUIRED
- Test through HTTP API endpoints
- Verify complete user workflows
- Test all scenarios from spec
- Cover all edge cases
- **File location**: `tests/api/test_*_api.py`

### 2. Repository Layer - ALWAYS REQUIRED
- Test repository methods directly
- Verify CRUD operations
- Test data persistence
- Test error handling (not found, etc.)
- **File location**: `tests/dal/test_*_repository.py`
- **Important**: Repository layer is cohesive whole, test thoroughly

### 3. Utilities - IF APPLICABLE
- Test any utility functions
- Test helper methods
- Test converters/transformers
- **File location**: `tests/utils/` or appropriate location

### 4. Domain Logic - IF APPLICABLE
- Test Pydantic validation rules
- Test business logic in domain models
- Test command objects
- **File location**: `tests/domain/` or appropriate location

## Important Notes

### Complete Capabilities Only
- No partial implementations
- All requirements in task must be 100% done
- All planned tests must be implemented
- All validations must pass

### Repository Layer is Critical
The repository layer (DAL) is a cohesive architectural layer that:
- Abstracts database operations
- Provides data access interface
- Must be thoroughly tested on its own
- Tests should not require HTTP layer

See architecture docs for more details.

### Test Planning is Major Work
- Test planning is not an afterthought
- Spend significant time designing tests
- Document all planned tests in implementation plan
- Tests prove the spec is implemented correctly
