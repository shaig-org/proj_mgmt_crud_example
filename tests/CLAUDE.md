# Testing Implementation Guidelines

This file provides guidance to Claude Code (claude.ai/code) when working on tests in this repository.

## **How to test each task**
After implementing a task, you MUST implement tests for it.
- Plan tests for the behavior in detail, follow all testing guidelines below.
- Implement the tests for this task.
- Consider if any tests for previous task need to be updated due to changes in the code, for example if existing behaviors need to support new features.
- Follow the Testing & Validations Strategy for running validations and fixing issues.

## **Testing guidelines**
A test should almost always test a single fact about the behavior of the code. test_after_put_get_returns_the_object is a good example.

Cover ALL behaviors of a feature as much as possible.

Test scope: Test behavior == cohesive whole == complete story
for example, in order to test put(), you also need to test get().
The "truth" of how some component or full software is its external observable behavior. Tests should verify using that behavior is much as possible.
It's ok to test a small part of something larger - as long as that part is a "complete stroy" in itself.
Test behaviors instead of implementations (again, an implementation detail that is in itself a cohesive whole is fine to test).
If you created a test that uses implementation details such is private members - ask yourself if you can write the test
to verify the same behavior only using external API. If yes - re-write the test.

Tests must be isolated so they never interfere with each other.

Tests must use clear language: decisive, specific and explicit.

Avoid using mocks. Simulators for quick tests are fine (for example, it's ok to test using in-memory sqlite some of the time instead of disk based for performance).

Test a variety of inputs, including variations on input data, including edge cases.

Test file names should be significant, specific and descriptive of content.
GOOD: test_basic_put_and_get.py
BAD: test_task_03_basic_put_and_get.py
BAD: test_cache.py

## Test Coverage Requirements

**Every feature implementation MUST include ALL applicable test layers:**

### **1. API Tests - ALWAYS REQUIRED ⭐⭐⭐**

**Why Critical**: Test externally observable behavior through HTTP endpoints

**Location**: `tests/api/test_*_api.py`

**Required Coverage**:
- ✅ **Happy path scenarios**: Valid requests, correct responses, proper HTTP status codes
- ✅ **Error handling**: 422 validation, 404 not found, 400 business logic violations
- ✅ **Complete workflows**: Multi-step user scenarios, data persistence verification

### **2. Repository Tests - ALWAYS REQUIRED ⭐⭐**

**Why Required**: Repository layer is a cohesive architectural layer that must work independently

**Location**: `tests/dal/test_*_repository.py`

**Required Coverage**:
- ✅ **CRUD operations**: create, read, update, delete methods
- ✅ **Data persistence**: Verify data survives round-trips
- ✅ **Error handling**: Not found, edge cases
- ✅ **Independent testing**: Test without HTTP layer
- ✅ **ALL repository methods**: Every method in the repository MUST have tests (see "100% Coverage Rule" below)

**Important**: Repository tests verify the data access layer works correctly on its own.

#### **100% Repository Method Coverage Rule - CRITICAL**

**Every repository method MUST have dedicated repository tests, regardless of API test coverage.**

**Why This Matters**:
- Repository layer is a cohesive architectural boundary that must work independently
- Methods returning different domain models (e.g., `UserAuthData` vs `User`) need specific testing
- Security-critical operations (password management, authentication) require isolated verification
- Bootstrap/utility methods need testing even if not directly called via API

**Common Gaps to Avoid**:

❌ **DON'T skip these types of repository methods:**
1. **Authentication methods** that return special models (e.g., `get_by_username_with_password()` returning `UserAuthData`)
2. **Password management** methods (e.g., `update_password()`)
3. **Bootstrap/setup methods** (e.g., `create_super_admin_if_needed()`)
4. **Filtering methods** with complex logic (e.g., `get_by_filters()`)
5. **Specialized update methods** (e.g., `update_status()`, `update_assignee()`)

✅ **DO test every method** with repository-level tests showing:
- Method works correctly in isolation
- Returns correct domain model type
- Handles edge cases (not found, validation failures)
- Security properties (password hashing, idempotency)

**Example Coverage Requirements**:

```python
# If repository has these methods, ALL need tests:
class Users:
    def create(...)                          # ✅ Must test
    def get_by_id(...)                       # ✅ Must test
    def get_by_username(...)                 # ✅ Must test
    def get_by_username_with_password(...)   # ✅ Must test (returns UserAuthData!)
    def update(...)                          # ✅ Must test
    def update_password(...)                 # ✅ Must test (security-critical!)
    def delete(...)                          # ✅ Must test
    def get_by_filters(...)                  # ✅ Must test (all filter combinations)
    def create_super_admin_if_needed(...)    # ✅ Must test (idempotency!)
```

**Authentication Method Testing - Special Attention Required**:

Methods that return authentication data (e.g., `get_by_username_with_password()`) need careful testing:

```python
def test_get_by_username_with_password(self, test_repo: Repository) -> None:
    """Test retrieving user with password hash for authentication."""
    user = test_repo.users.create(...)

    # Retrieve with password
    auth_data = test_repo.users.get_by_username_with_password("username")

    # Verify correct domain model (UserAuthData, not User)
    assert auth_data is not None
    assert auth_data.password_hash is not None  # Key difference from User model
    assert auth_data.username == "username"
    assert auth_data.role == UserRole.ADMIN
```

**Password Management Testing - Security Critical**:

```python
def test_update_password(self, test_repo: Repository) -> None:
    """Test updating user password."""
    user = test_repo.users.create(...)

    # Get original hash
    original_auth = test_repo.users.get_by_username_with_password("username")
    original_hash = original_auth.password_hash

    # Update password
    success = test_repo.users.update_password(user.id, "NewPassword123")
    assert success is True

    # Verify hash changed
    updated_auth = test_repo.users.get_by_username_with_password("username")
    assert updated_auth.password_hash != original_hash
```

**Bootstrap Method Testing - Idempotency Critical**:

```python
def test_create_super_admin_if_needed_idempotent(self, test_repo: Repository) -> None:
    """Test bootstrap function doesn't create duplicates."""
    # First call creates
    created1, user1 = test_repo.users.create_super_admin_if_needed(...)
    assert created1 is True

    # Second call doesn't create
    created2, user2 = test_repo.users.create_super_admin_if_needed(...)
    assert created2 is False
    assert user2 is None

    # Verify only one exists
    all_users = test_repo.users.get_all()
    super_admins = [u for u in all_users if u.role == UserRole.SUPER_ADMIN]
    assert len(super_admins) == 1
```

#### **Repository Testing Pattern - CRITICAL**

**❌ DO NOT test ORM models directly**
- Direct ORM tests are brittle and low-value
- They only verify that ORM declarations exist
- They expose implementation details

**✅ ALWAYS test through Repository methods**
- Use repository methods to create, retrieve, update, delete
- Use domain models and commands (not ORM models)
- Verify behavior through repository interface
- This provides strong correctness guarantees without brittleness

**Repository Architecture**:
- **Single `Repository` class** for all data access operations
- Use nested classes for organization: `repo.users.create()`, `repo.organizations.get_by_id()`
- Queries can span multiple entities naturally (e.g., get user with organization)
- The `StubEntityRepository` is scaffolding/example code only

**Pattern to Follow**:
```python
class TestUserOperations:
    """Test user operations through Repository interface."""

    def test_create_user(self, test_repo: Repository) -> None:
        """Test creating a user through repository."""
        # Create using repository command
        user_data = UserData(username="testuser", email="test@example.com", full_name="Test")
        command = UserCreateCommand(user_data=user_data, organization_id="org-123", role=UserRole.ADMIN)

        # Create through repository
        user = test_repo.users.create(command)

        # Verify domain model properties
        assert user.username == "testuser"
        assert user.id is not None

    def test_get_user_by_id(self, test_repo: Repository) -> None:
        """Test retrieving user through repository."""
        # Create through repository
        user_data = UserData(username="testuser", email="test@example.com", full_name="Test")
        command = UserCreateCommand(user_data=user_data, organization_id="org-123", role=UserRole.ADMIN)
        created_user = test_repo.users.create(command)

        # Retrieve through repository
        retrieved_user = test_repo.users.get_by_id(created_user.id)

        # Verify through domain model
        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
```

**Key Principles**:
1. ✅ Use repository methods exclusively (no `session.query()`, no ORM access)
2. ✅ Use domain models and commands (UserData, UserCreateCommand, User)
3. ✅ Verify domain model properties (username, id, email)
4. ❌ Never access ORM models (UserORM) in tests
5. ❌ Never use test_session directly for entity creation/verification
6. ✅ Test complete workflows (create → retrieve → verify)
7. ✅ Single Repository handles all entities - queries can span multiple tables naturally

**CRITICAL ARCHITECTURAL RULE**:
- ❌ Repository methods MUST NEVER return ORM models (UserORM, etc.) to callers
- ✅ Repository methods MUST ALWAYS return domain models only
- ✅ If additional data is needed (e.g., password_hash for auth), create a specific domain model
- **Why**: Exposing ORM models breaks layering and can cause serious issues (lazy loading, session lifecycle, tight coupling)

#### **Repository Test Helper Functions - CRITICAL**

**ALWAYS use helper functions** from `tests/dal/helpers.py` for test setup code in repository tests.

**✅ CORRECT: Use Repository Helpers**

```python
from tests.dal.helpers import create_test_org_via_repo, create_test_project_via_repo, create_test_user_via_repo

def test_get_ticket_by_id(self, test_repo: Repository) -> None:
    """Test retrieving ticket by ID."""
    # Setup using helpers - clean and concise
    org = create_test_org_via_repo(test_repo)
    project = create_test_project_via_repo(test_repo, org.id, "Test Project")
    reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)

    # Test the actual behavior
    ticket = test_repo.tickets.create(...)
    retrieved = test_repo.tickets.get_by_id(ticket.id)
    assert retrieved is not None
```

**❌ WRONG: Verbose Setup Code**

```python
def test_get_ticket_by_id(self, test_repo: Repository) -> None:
    """Test retrieving ticket by ID."""
    # DON'T DO THIS - repetitive and verbose
    org_data = OrganizationData(name="Test Org")
    org = test_repo.organizations.create(OrganizationCreateCommand(organization_data=org_data))

    project_data = ProjectData(name="Test Project")
    project = test_repo.projects.create(
        ProjectCreateCommand(project_data=project_data, organization_id=org.id)
    )

    user_data = UserData(username="reporter", email="reporter@test.com", full_name="Reporter")
    reporter = test_repo.users.create(
        UserCreateCommand(
            user_data=user_data,
            password="password",
            organization_id=org.id,
            role=UserRole.ADMIN,
        )
    )
```

**Available Repository Helpers**

Located in `tests/dal/helpers.py`:

- `create_test_org_via_repo(test_repo, name="Test Org")` - Create organization
- `create_test_project_via_repo(test_repo, org_id, name="Test Project", description=None)` - Create project
- `create_test_user_via_repo(test_repo, org_id, username="testuser", email=None, full_name=None, role=UserRole.ADMIN, password="password")` - Create user

**Why Use Repository Helpers?**

1. **Reduces duplication**: Setup code in 1 line instead of 5-10
2. **Improves readability**: Focus on what's being tested, not setup
3. **Consistent defaults**: All tests use same test data patterns
4. **Easier maintenance**: Changes to setup logic in one place

**When to Use Helpers vs Direct Creation**

- ✅ **Use helpers** for test setup/scaffolding (creating org, project, users needed for test)
- ❌ **DON'T use helpers** when testing the CREATE operation itself
- ✅ **Use helpers** for related entities (e.g., testing tickets needs project/user setup)

**Example: Testing CREATE Operation**

```python
def test_create_project_with_all_fields(self, test_repo: Repository) -> None:
    """Test creating a project through repository."""
    # Use helper for org (we're not testing org creation)
    org = create_test_org_via_repo(test_repo)

    # DON'T use helper for project - we're testing project creation!
    project_data = ProjectData(name="Backend API", description="REST API")
    command = ProjectCreateCommand(project_data=project_data, organization_id=org.id)
    project = test_repo.projects.create(command)

    # Verify the creation worked
    assert project.name == "Backend API"
    assert project.description == "REST API"
```

### **3. Utility/Logic Tests - IF APPLICABLE**

**Location**: `tests/utils/` or appropriate location

**Coverage**: Helper functions, converters, business logic utilities

**Converter Tests**:
- ORM-to-domain converters should be tested in `tests/dal/test_converters.py`
- Test that converters properly transform ORM models to domain models
- Test edge cases like null values, special fields exclusions (e.g., password_hash)

### **4. Domain Validation Tests - IF APPLICABLE**

**Location**: `tests/domain/` or appropriate location

**Coverage**: Pydantic model validation, command objects, business rules

## Testing Implementation Rules

### **MANDATORY Implementation Order**
1. **First**: Write API endpoint tests that define expected behavior
2. **Second**: Implement the feature to make tests pass
3. **Third**: Add supporting DAL/unit tests as needed

### **Test Quality Requirements**

#### **Always Import PyTest Fixtures Explicitly**

**MANDATORY**: All tests must explicitly import fixtures from conftest, even though pytest auto-discovers them.

```python
# ✅ CORRECT: Explicit imports at top of test file
from fastapi.testclient import TestClient

from tests.conftest import client  # noqa: F401

class TestMyAPI:
    def test_something(self, client: TestClient) -> None:
        # ... test code
```

```python
# ❌ WRONG: Relying on auto-discovery
# Missing: from tests.conftest import client

class TestMyAPI:
    def test_something(self, client: TestClient) -> None:
        # ... test code
```

**Why**: Makes dependencies explicit, improves code clarity, prevents confusion.

#### **Test Naming Convention**
- **Pattern**: `test_[action]_[entity]_[scenario]` or `test_[scenario_description]`
- **Good**: `test_create_stub_entity`, `test_delete_stub_entity_not_found`
- **Bad**: `test_entity` (not specific enough)

#### **Test Language & Structure**
- **Decisive, explicit, specific** (not generic)
- **Test one fact** about behavior per test
- **Independent and isolated** tests
- Use **Arrange-Act-Assert** pattern

```python
def test_create_stub_entity_with_valid_data_succeeds(self, client: TestClient) -> None:
    """Test creating stub entity with valid data returns 201."""
    # Arrange
    stub_entity_data = {"name": "Test Entity", "description": "Test"}

    # Act
    response = client.post("/stub_entities", json=stub_entity_data)

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Entity"
```

#### **Error Testing Requirements**
- **Every endpoint must test error conditions**
- **Validate proper HTTP status codes**
- **Verify error message content and format**

```python
def test_get_stub_entity_by_non_existent_id_is_not_found(self, client: TestClient) -> None:
    """Test getting a non-existent stub entity returns 404."""
    response = client.get("/stub_entities/non-existent-id")

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Stub entity not found"
```

### **API Test Helper Functions - CRITICAL**

**ALWAYS use role-specific helper functions** instead of generic create_test_user with explicit role parameters.

#### **✅ CORRECT: Use Role-Specific Helpers**

```python
from tests.helpers import create_admin_user, create_project_manager, create_write_user, create_read_user

# Create admin user - expressive defaults make intent clear
user_id, password = create_admin_user(client, super_admin_token, org_id)

# Create project manager - defaults to username="projectmanager", email="pm@example.com"
pm_id, pm_password = create_project_manager(client, super_admin_token, org_id)

# Override username only when needed for test-specific reasons
user_id, password = create_write_user(client, super_admin_token, org_id, username="writer2")
```

#### **❌ WRONG: Generic Helper with Explicit Role**

```python
# DON'T DO THIS - verbose and requires manual parameter passing
user_id, password = create_test_user(
    client,
    super_admin_token,
    org_id,
    username="admin",
    email="admin@example.com",
    full_name="Admin User",
    role=UserRole.ADMIN,  # Role should be implicit in helper name
)
```

#### **Why Use Role-Specific Helpers?**

1. **Self-documenting**: `create_admin_user()` immediately communicates intent
2. **Expressive defaults**: Email "admin@example.com" clearly indicates admin user
3. **Less boilerplate**: Only override parameters when test requires specific values
4. **Consistency**: All tests use same defaults, making test data predictable

#### **Available Role-Specific Helpers**

Located in `tests/helpers.py`:

- `create_admin_user()` - username="admin", email="admin@example.com"
- `create_project_manager()` - username="projectmanager", email="pm@example.com"
- `create_write_user()` - username="writer", email="writer@example.com"
- `create_read_user()` - username="reader", email="reader@example.com"

All helpers use expressive defaults that make the role immediately obvious.

### **Fixture Naming and Organization**

#### **Avoid Fixture Name Shadowing**

When creating local fixtures, **NEVER shadow global fixtures** from `tests/fixtures/`.

**❌ WRONG: Shadowing Global Fixtures**

```python
# In test_ticket_api.py - local fixture shadows global one
@pytest.fixture
def org_admin_token(client: TestClient, organization: str, super_admin_token: str):
    # This shadows tests/fixtures/auth_fixtures.py::org_admin_token
    ...
```

**✅ CORRECT: Use Descriptive Prefix**

```python
# In test_ticket_api.py - clear, non-shadowing name
@pytest.fixture
def shared_org_admin_token(client: TestClient, organization: str, super_admin_token: str):
    """Create Admin user in shared organization and return token and org_id."""
    from tests.helpers import create_admin_user

    _, password = create_admin_user(client, super_admin_token, organization)
    response = client.post("/auth/login", json={"username": "admin", "password": password})
    return response.json()["access_token"], organization
```

#### **Global vs Local Fixtures**

**Global Fixtures** (`tests/fixtures/auth_fixtures.py`):
- Each creates its **own separate organization**
- Use when tests need **organization isolation**
- Examples: `org_admin_token`, `project_manager_token`, `write_user_token`

**Local Fixtures** (test file-specific):
- All users share **same organization**
- Use when tests need **cross-user scenarios** in same org
- **Prefix with context** (e.g., `shared_org_admin_token`)
- Common in ticket/project tests where multiple users collaborate

**Pattern for Shared-Org Fixtures:**

```python
# Note: Prefix with 'shared_org_' to indicate all users share same organization
@pytest.fixture
def shared_org_admin_token(client: TestClient, organization: str, super_admin_token: str):
    """Create Admin user in shared organization."""
    _, password = create_admin_user(client, super_admin_token, organization)
    response = client.post("/auth/login", json={"username": "admin", "password": password})
    return response.json()["access_token"], organization

@pytest.fixture
def shared_org_pm_token(client: TestClient, organization: str, super_admin_token: str):
    """Create Project Manager in shared organization."""
    _, password = create_project_manager(client, super_admin_token, organization)
    response = client.post("/auth/login", json={"username": "projectmanager", "password": password})
    return response.json()["access_token"], organization
```

#### **When to Create Local Fixtures**

Create local fixtures when:
- ✅ Multiple users need to be in the **same organization** for test scenarios
- ✅ Testing **cross-user interactions** (assigning tickets, viewing others' work)
- ✅ Testing **organization-scoped permissions** (can/cannot see other users' data)

Use global fixtures when:
- ✅ Each test needs **organization isolation**
- ✅ No cross-user scenarios in same org
- ✅ Standard permission/CRUD testing

## Core Testing Principles

### **Testing Guidelines**

A test should almost always test a single fact about the behavior of the code.

**Good example**: `test_after_create_get_returns_the_entity`

**Test scope**: Test behavior = cohesive whole = complete story. For example, to test create(), you also need to test get() to verify creation worked.

**Test behaviors, not implementations**: The "truth" of a component is its external observable behavior. Tests should verify that behavior as much as possible. If you created a test that uses implementation details like private members, ask yourself if you can write the test to verify the same behavior only using external API. If yes, re-write the test.

**Tests must be isolated** so they never interfere with each other.

**Tests must use clear language**: decisive, specific and explicit.

**Avoid using mocks**: Simulators for quick tests are fine (e.g., using in-memory SQLite instead of disk-based for performance).

**Test a variety of inputs**: Include variations on input data and edge cases.

**Test file names** should be significant, specific and descriptive of content:
- GOOD: `test_stub_entity_api.py`
- BAD: `test_task_03_stub_entity.py`
- BAD: `test_api.py`

## Property-Based Testing (PBT)

### **When to Use Property-Based Tests**

Property-based tests complement traditional example-based tests by testing **invariants that should hold for all inputs**, not just specific examples.

**Location**: `tests/property_based/`

**Use property-based tests for:**
- ✅ Testing properties that should hold across all valid inputs
- ✅ Finding edge cases and bugs that example-based tests miss
- ✅ Stateful testing of complex workflows with many possible action sequences
- ✅ Verifying invariants like count consistency, data integrity, uniqueness constraints

**Property-based test types:**
1. **Stateless PBT** (`tests/property_based/dal/`): Test individual operations with generated inputs
2. **Stateful PBT** (`tests/property_based/stateful/`): Test sequences of operations maintain invariants

### **CRITICAL: When PBT Discovers a Bug**

**When a property-based test discovers a bug, you MUST create a hardcoded regression test.**

#### **For Stateless Property-Based Tests**

Use Hypothesis's `@example()` decorator to add the failing case as a hardcoded example:

```python
from hypothesis import given, example
from hypothesis import strategies as st

@given(username=usernames(), email=emails())
@example(username="admin", email="duplicate@example.com")  # Bug found by PBT
def test_user_create_with_duplicate_email_fails(test_repo: Repository, username: str, email: str) -> None:
    """Test that duplicate emails are rejected.

    Note: Bug originally discovered by property-based testing in test_user_create_roundtrip.
    Added hardcoded example to ensure this specific case is always tested.
    """
    # ... test implementation
```

**Why use @example():**
- Ensures the specific failing case is always tested (fast, deterministic)
- Documents the bug that was found
- Maintains the property-based test for finding future bugs
- No need for separate test function

#### **For Stateful Property-Based Tests**

Create a separate hardcoded API/repository test that replicates the bug:

```python
def test_duplicate_email_within_organization_fails(self, client: TestClient, super_admin_token: str) -> None:
    """Test that duplicate emails are rejected within same organization.

    Regression test for bug discovered by property-based stateful testing.

    Bug Discovery:
    - Original test: tests/property_based/stateful/test_user_api.py::test_user_api_state_machine
    - Rule: attempt_duplicate_email_update
    - Issue: Email uniqueness constraint was missing from database schema
    - Fix: Added composite unique constraint on (organization_id, email)

    This test ensures the bug doesn't regress.
    """
    org_id = create_test_org(client, super_admin_token)

    # Create first user
    create_admin_user(client, super_admin_token, org_id, username="user1", email="test@example.com")

    # Create second user
    user2_id, _ = create_admin_user(client, super_admin_token, org_id, username="user2", email="user2@example.com")

    # Attempt to update second user's email to duplicate first user's email
    response = client.put(
        f"/api/users/{user2_id}",
        json={"email": "test@example.com"},
        headers=auth_headers(super_admin_token)
    )

    # Should fail with 400
    assert response.status_code == 400
    assert "email" in response.json()["detail"].lower()
```

**Why create a separate test:**
- Stateful tests are complex and slow - hard to pin down specific scenarios
- Separate test is fast, deterministic, and clearly documents the bug
- Test name and docstring explain what bug was found and how
- Makes it easy to verify the fix and prevent regressions

#### **Documentation Requirements**

Every regression test MUST include in its docstring:
1. **Where the bug was found**: Reference the PBT test file and rule/function
2. **What the bug was**: Brief description of the incorrect behavior
3. **How it was fixed**: Brief description of the fix (e.g., "Added unique constraint")
4. **Purpose**: "This test ensures the bug doesn't regress"

### **Property-Based Testing Workflow**

1. **Run PBT regularly** during development (included in validation script)
2. **When PBT finds a bug**:
   - ✅ Investigate the root cause
   - ✅ Fix the bug in the code
   - ✅ Add regression test (using @example() or separate test)
   - ✅ Document the bug discovery in the regression test
   - ✅ Verify both PBT and regression test pass
3. **Keep the original PBT test** - it may find other bugs in the future

### **Example: Real Bug Found by PBT**

**Bug**: Duplicate emails allowed within same organization

**PBT Test**: `tests/property_based/stateful/test_user_api.py::test_user_api_state_machine`
- Rule `attempt_duplicate_email_update` consistently failed
- Expected: API returns 400 for duplicate email
- Actual: API returns 200 (update succeeds)

**Root Cause**: Missing database constraint on `(organization_id, email)`

**Regression Test Created**: `tests/api/test_user_api.py::test_duplicate_email_within_organization_fails`
- Hardcoded test with specific emails
- Fast, deterministic, clearly documents the bug
- Ensures the fix prevents regression

## PyTest Fixtures

### **Available Test Fixtures**

All fixtures defined in `tests/conftest.py`:

**`db_path: str`**
- Configurable database path: disk (default) or `:memory:`
- Run with: `pytest` (disk) or `pytest --db-mode=memory` (memory)
- Each test gets isolated database

**`test_db: Database`**
- Initialized Database instance with tables
- Automatically creates/drops tables and disposes engine

**`test_session: Session`**
- SQLAlchemy session connected to test database
- Automatically commits and closes

**`test_stub_entity_repo: StubEntityRepository`**
- Repository instance ready for CRUD operations

**`client: TestClient`**
- FastAPI TestClient with test database dependency overrides
- **Use for all API tests**

### **Fixture Usage Examples**

**Repository Tests:**
```python
from tests.conftest import test_stub_entity_repo  # noqa: F401

class TestStubEntityRepository:
    def test_create_stub_entity(self, test_stub_entity_repo: StubEntityRepository) -> None:
        """Test creating a stub entity in the database."""
        # ... test code
```

**API Tests:**
```python
from fastapi.testclient import TestClient
from tests.conftest import client  # noqa: F401

class TestStubEntityAPI:
    def test_create_stub_entity(self, client: TestClient) -> None:
        """Test creating stub entity via API."""
        # ... test code
```

## Test File Organization

### **File Naming Conventions**
- **API Tests**: `test_[entity]_api.py`
- **Repository Tests**: `test_[entity]_repository.py`
- **Domain Tests**: `test_[model]_validation.py` (if needed)

### **Test Class Organization**
```python
class TestStubEntityAPIEndpoints:
    """Test all stub entity API endpoints for CRUD operations."""

    def test_create_stub_entity(self, client: TestClient) -> None:
        """Test successful stub entity creation."""

    def test_create_stub_entity_without_description(self, client: TestClient) -> None:
        """Test creation without optional field."""

    def test_get_stub_entity_by_id(self, client: TestClient) -> None:
        """Test successful stub entity retrieval."""

    def test_get_stub_entity_by_id_not_found(self, client: TestClient) -> None:
        """Test 404 for non-existent entity."""

class TestStubEntityAPICRUDWorkflow:
    """Test complete CRUD workflow for stub entities."""

    def test_complete_stub_entity_crud_workflow(self, client: TestClient) -> None:
        """Test complete workflow: create, read, update, delete."""
```

## Common Testing Patterns

### **Integration Over Isolation**
- **Prefer real HTTP requests** over mocking
- **Test actual database operations**
- **Validate complete request-response cycles**

### **Test Data Management**
- **Use unique values** to avoid test conflicts
- **Clean up happens automatically** via fixtures
- **Each test gets isolated database**

### **Complete Workflow Testing**
```python
def test_complete_stub_entity_crud_workflow(self, client: TestClient) -> None:
    """Test a complete CRUD workflow for a stub entity."""
    # 1. Create
    create_response = client.post("/stub_entities", json={
        "name": "Workflow Entity",
        "description": "Full CRUD test"
    })
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]

    # 2. Read
    get_response = client.get(f"/stub_entities/{entity_id}")
    assert get_response.status_code == 200

    # 3. List
    list_response = client.get("/stub_entities")
    assert len(list_response.json()) == 1

    # 4. Delete
    delete_response = client.delete(f"/stub_entities/{entity_id}")
    assert delete_response.status_code == 204

    # 5. Verify deletion
    final_get = client.get(f"/stub_entities/{entity_id}")
    assert final_get.status_code == 404
```

## Test Validation Rules

### **Before Completing Any Feature**
- [ ] All API endpoints have comprehensive tests
- [ ] Happy path scenarios covered
- [ ] Error conditions tested with proper status codes
- [ ] Complete workflows tested end-to-end
- [ ] All tests pass in isolation
- [ ] All tests pass when run together
- [ ] All fixtures explicitly imported

### **Test Quality Checklist**
- [ ] Test names are descriptive and specific
- [ ] Tests follow Arrange-Act-Assert pattern
- [ ] Error messages are validated
- [ ] HTTP status codes are correct
- [ ] Response data structure is validated
- [ ] Tests are independent and isolated
- [ ] PyTest fixtures explicitly imported with `# noqa: F401`

**Remember: If the API works correctly in tests, users can accomplish their goals. No amount of perfect unit tests matters if the API doesn't work.**
