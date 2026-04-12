# Property-Based Testing Strategy with Hypothesis

## Overview

This document outlines a comprehensive property-based testing (PBT) strategy for the project management CRUD application using Hypothesis. Property-based testing complements our existing example-based tests by automatically generating hundreds of test cases to verify properties that should hold true across all inputs.

## Why Property-Based Testing?

**Complements existing tests**: Our current test suite uses example-based testing (specific inputs → expected outputs). PBT automatically generates diverse inputs to find edge cases we haven't considered.

**Two approaches**:
1. **Stateless PBT**: Test individual operations with generated inputs (e.g., "any valid username should be retrievable after creation")
2. **Stateful PBT**: Test sequences of operations to find complex interaction bugs (e.g., "after any sequence of CRUD operations, the database remains consistent")

## Testing Layers

We'll focus on two primary layers:

### 1. Repository Layer (DAL) - Primary Focus ⭐⭐⭐

**Why prioritize**: Repository layer is a cohesive architectural boundary that must maintain invariants regardless of API layer.

**Key properties to test**:
- Data persistence (roundtrip properties)
- Uniqueness constraints
- Referential integrity
- Data validation rules
- Idempotency

### 2. API Layer - Secondary Focus ⭐⭐

**Why test**: Ensures HTTP layer correctly enforces all repository-level properties plus authorization.

**Key properties to test**:
- CRUD roundtrips through HTTP
- Error responses for invalid data
- Authorization enforcement
- Data serialization correctness

---

## Core Property Patterns

### Pattern 1: Roundtrip Properties (CRITICAL)

**Concept**: `create(x) → get(id) → result` should equal `x`

**Why powerful**: Verifies data persistence, serialization, and retrieval all work correctly together.

**Example**:
```python
@given(st.text(min_size=3, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-")))
def test_user_username_roundtrip(self, test_repo: Repository, username: str):
    """Any valid username should survive create-retrieve roundtrip."""
    # Arrange
    user_data = UserData(username=username, email=f"{username}@test.com", full_name="Test")
    org = create_test_org_via_repo(test_repo)

    # Act
    created = test_repo.users.create(UserCreateCommand(
        user_data=user_data,
        password="Pass123!",
        organization_id=org.id,
        role=UserRole.ADMIN
    ))
    retrieved = test_repo.users.get_by_id(created.id)

    # Assert
    assert retrieved is not None
    assert retrieved.username == username
```

### Pattern 2: Invariant Properties

**Concept**: Certain facts should ALWAYS be true, regardless of operations performed.

**Examples**:
- User IDs are always non-empty strings
- Usernames are always unique across all users
- Deleted entities should never be retrievable
- Timestamps are always in UTC
- Organization names are unique

### Pattern 3: Idempotency Properties

**Concept**: Performing the same operation multiple times has the same effect as doing it once.

**Example**:
```python
@given(st.text(min_size=1, max_size=255))
def test_create_super_admin_idempotent(self, test_repo: Repository, username: str):
    """Creating super admin multiple times should not duplicate."""
    # First creation
    created1, user1 = test_repo.users.create_super_admin_if_needed(username, "Pass123!")
    assert created1 is True

    # Second creation - should be no-op
    created2, user2 = test_repo.users.create_super_admin_if_needed(username, "Pass123!")
    assert created2 is False
    assert user2 is None

    # Verify only one exists
    all_users = test_repo.users.get_all()
    super_admins = [u for u in all_users if u.role == UserRole.SUPER_ADMIN and u.username == username]
    assert len(super_admins) == 1
```

### Pattern 4: Metamorphic Properties

**Concept**: Performing operation A then B should produce the same result as performing equivalent operation C.

**Example**:
```python
@given(st.text(min_size=1, max_size=255), st.text(min_size=1, max_size=255))
def test_update_is_equivalent_to_delete_and_recreate_with_same_id(
    self, test_repo: Repository, name1: str, name2: str
):
    """Updating name should be equivalent to the final state after create with different name."""
    org = create_test_org_via_repo(test_repo, name=name1)

    # Path 1: Update
    test_repo.organizations.update(org.id, OrganizationUpdateCommand(name=name2))
    result1 = test_repo.organizations.get_by_id(org.id)

    # Path 2: Create with final name directly
    org2 = create_test_org_via_repo(test_repo, name=name2)
    result2 = test_repo.organizations.get_by_id(org2.id)

    # Both should have the final name
    assert result1.name == name2
    assert result2.name == name2
```

### Pattern 5: Oracle Properties

**Concept**: Use a simpler model as "oracle" to verify complex implementation.

**Example**:
```python
@given(st.lists(st.text(min_size=1, max_size=255), min_size=0, max_size=20))
def test_filter_results_match_python_filter(self, test_repo: Repository, names: list[str]):
    """Repository filtering should match Python's built-in filter logic."""
    org = create_test_org_via_repo(test_repo)

    # Create users with generated names
    created_users = []
    for name in names:
        user_data = UserData(username=name, email=f"{name}@test.com", full_name=name)
        user = test_repo.users.create(UserCreateCommand(
            user_data=user_data,
            password="Pass123!",
            organization_id=org.id,
            role=UserRole.ADMIN
        ))
        created_users.append(user)

    # Filter using repository
    pattern = "test"
    repo_results = test_repo.users.get_by_filters(username_contains=pattern)

    # Filter using Python (oracle)
    python_results = [u for u in created_users if pattern in u.username]

    # Results should match
    assert len(repo_results) == len(python_results)
    assert set(u.id for u in repo_results) == set(u.id for u in python_results)
```

---

## Repository Layer: Specific Test Ideas

### User Repository

#### Stateless Properties

**1. Username Uniqueness (CRITICAL)**
```python
@given(st.lists(st.text(min_size=3, max_size=50, alphabet=USERNAME_CHARS), min_size=2, max_size=2, unique=True))
def test_creating_duplicate_usernames_fails(self, test_repo: Repository, usernames: list[str]):
    """Creating users with duplicate usernames should fail."""
    org = create_test_org_via_repo(test_repo)

    # First user succeeds
    user_data1 = UserData(username=usernames[0], email=f"{usernames[0]}@test.com", full_name="User 1")
    test_repo.users.create(UserCreateCommand(user_data=user_data1, password="Pass123!", organization_id=org.id, role=UserRole.ADMIN))

    # Second user with same username fails
    user_data2 = UserData(username=usernames[0], email=f"{usernames[0]}2@test.com", full_name="User 2")
    with pytest.raises(IntegrityError):
        test_repo.users.create(UserCreateCommand(user_data=user_data2, password="Pass123!", organization_id=org.id, role=UserRole.ADMIN))
```

**2. Username Case-Insensitivity**
```python
@given(st.text(min_size=3, max_size=50, alphabet=USERNAME_CHARS))
def test_usernames_are_case_insensitive(self, test_repo: Repository, username: str):
    """Usernames should be case-insensitive (can't create 'user' and 'USER')."""
    assume(username.lower() != username.upper())  # Skip if case doesn't matter

    org = create_test_org_via_repo(test_repo)

    # Create with lowercase
    user_data1 = UserData(username=username.lower(), email="user1@test.com", full_name="User 1")
    test_repo.users.create(UserCreateCommand(user_data=user_data1, password="Pass123!", organization_id=org.id, role=UserRole.ADMIN))

    # Attempt to create with uppercase - should fail
    user_data2 = UserData(username=username.upper(), email="user2@test.com", full_name="User 2")
    with pytest.raises(IntegrityError):
        test_repo.users.create(UserCreateCommand(user_data=user_data2, password="Pass123!", organization_id=org.id, role=UserRole.ADMIN))
```

**3. Password Hashing Security**
```python
@given(st.text(min_size=8, max_size=100))
def test_password_never_equals_hash(self, test_repo: Repository, password: str):
    """Password hash should never equal the plaintext password."""
    org = create_test_org_via_repo(test_repo)

    user_data = UserData(username="testuser", email="test@test.com", full_name="Test")
    user = test_repo.users.create(UserCreateCommand(
        user_data=user_data,
        password=password,
        organization_id=org.id,
        role=UserRole.ADMIN
    ))

    # Get user with password hash
    auth_data = test_repo.users.get_by_username_with_password("testuser")

    assert auth_data.password_hash != password
    assert len(auth_data.password_hash) > len(password)  # Hash is longer
```

**4. Password Hashing Consistency**
```python
@given(st.text(min_size=8, max_size=100))
def test_same_password_produces_different_hashes(self, test_repo: Repository, password: str):
    """Same password should produce different hashes (due to salt)."""
    org = create_test_org_via_repo(test_repo)

    user_data1 = UserData(username="user1", email="user1@test.com", full_name="User 1")
    user1 = test_repo.users.create(UserCreateCommand(user_data=user_data1, password=password, organization_id=org.id, role=UserRole.ADMIN))

    user_data2 = UserData(username="user2", email="user2@test.com", full_name="User 2")
    user2 = test_repo.users.create(UserCreateCommand(user_data=user_data2, password=password, organization_id=org.id, role=UserRole.ADMIN))

    auth1 = test_repo.users.get_by_username_with_password("user1")
    auth2 = test_repo.users.get_by_username_with_password("user2")

    # Same password, different hashes (due to salt)
    assert auth1.password_hash != auth2.password_hash
```

**5. User Update Preserves Unchanged Fields**
```python
@given(st.text(min_size=1, max_size=255))
def test_partial_update_preserves_other_fields(self, test_repo: Repository, new_email: str):
    """Updating one field should not modify other fields."""
    assume("@" in new_email)  # Ensure valid email format

    org = create_test_org_via_repo(test_repo)

    # Create user
    user_data = UserData(username="testuser", email="original@test.com", full_name="Original Name")
    user = test_repo.users.create(UserCreateCommand(user_data=user_data, password="Pass123!", organization_id=org.id, role=UserRole.ADMIN))

    # Update only email
    test_repo.users.update(user.id, UserUpdateCommand(email=new_email))

    # Retrieve and verify
    updated = test_repo.users.get_by_id(user.id)
    assert updated.email == new_email
    assert updated.username == "testuser"  # Unchanged
    assert updated.full_name == "Original Name"  # Unchanged
    assert updated.role == UserRole.ADMIN  # Unchanged
```

**6. Get All Returns All Created Users**
```python
@given(st.lists(st.text(min_size=3, max_size=50, alphabet=USERNAME_CHARS), min_size=1, max_size=10, unique=True))
def test_get_all_returns_all_created_users(self, test_repo: Repository, usernames: list[str]):
    """get_all() should return all created users."""
    org = create_test_org_via_repo(test_repo)

    created_ids = set()
    for username in usernames:
        user_data = UserData(username=username, email=f"{username}@test.com", full_name=username)
        user = test_repo.users.create(UserCreateCommand(user_data=user_data, password="Pass123!", organization_id=org.id, role=UserRole.ADMIN))
        created_ids.add(user.id)

    all_users = test_repo.users.get_all()
    retrieved_ids = set(u.id for u in all_users)

    assert created_ids.issubset(retrieved_ids)
```

**7. Deleted User Cannot Be Retrieved**
```python
@given(st.text(min_size=3, max_size=50, alphabet=USERNAME_CHARS))
def test_deleted_user_returns_none(self, test_repo: Repository, username: str):
    """Deleted user should return None on get_by_id."""
    org = create_test_org_via_repo(test_repo)

    user_data = UserData(username=username, email=f"{username}@test.com", full_name="Test")
    user = test_repo.users.create(UserCreateCommand(user_data=user_data, password="Pass123!", organization_id=org.id, role=UserRole.ADMIN))

    # Delete
    test_repo.users.delete(user.id)

    # Attempt to retrieve
    retrieved = test_repo.users.get_by_id(user.id)
    assert retrieved is None
```

#### Stateful Testing: User CRUD State Machine

**Property**: After any sequence of CRUD operations, the repository should remain in a consistent state.

```python
class UserStateMachine(RuleBasedStateMachine):
    """Stateful testing for user CRUD operations."""

    def __init__(self):
        super().__init__()
        self.repo = get_test_repository()
        self.org = create_test_org_via_repo(self.repo)
        self.created_users: dict[str, str] = {}  # username -> id
        self.deleted_users: set[str] = set()

    @rule(username=st.text(min_size=3, max_size=50, alphabet=USERNAME_CHARS))
    def create_user(self, username: str):
        """Create a user."""
        assume(username not in self.created_users)
        assume(username not in self.deleted_users)

        user_data = UserData(username=username, email=f"{username}@test.com", full_name=username)
        user = self.repo.users.create(UserCreateCommand(
            user_data=user_data,
            password="Pass123!",
            organization_id=self.org.id,
            role=UserRole.ADMIN
        ))

        self.created_users[username] = user.id

    @rule(username=st.sampled_from(list))
    @precondition(lambda self: len(self.created_users) > 0)
    def get_user(self, username: str):
        """Retrieve a user."""
        username = list(self.created_users.keys())[0]
        user_id = self.created_users[username]

        user = self.repo.users.get_by_id(user_id)

        if username not in self.deleted_users:
            assert user is not None
            assert user.username == username
        else:
            assert user is None

    @rule(username=st.sampled_from(list))
    @precondition(lambda self: len(self.created_users) > 0)
    def delete_user(self, username: str):
        """Delete a user."""
        username = list(self.created_users.keys())[0]
        user_id = self.created_users[username]

        self.repo.users.delete(user_id)
        self.deleted_users.add(username)
        del self.created_users[username]

    @invariant()
    def check_consistency(self):
        """Verify repository is always consistent."""
        # All created users should be retrievable
        for username, user_id in self.created_users.items():
            user = self.repo.users.get_by_id(user_id)
            assert user is not None
            assert user.username == username

        # All deleted users should not be retrievable
        for username in self.deleted_users:
            user = self.repo.users.get_by_username(username)
            assert user is None

TestUserCRUD = UserStateMachine.TestCase
```

---

### Organization Repository

**1. Organization Name Uniqueness**
```python
@given(st.lists(st.text(min_size=1, max_size=255), min_size=2, max_size=2, unique=True))
def test_duplicate_organization_names_fail(self, test_repo: Repository, names: list[str]):
    """Creating organizations with duplicate names should fail."""
    org_data1 = OrganizationData(name=names[0])
    test_repo.organizations.create(OrganizationCreateCommand(organization_data=org_data1))

    org_data2 = OrganizationData(name=names[0])
    with pytest.raises(IntegrityError):
        test_repo.organizations.create(OrganizationCreateCommand(organization_data=org_data2))
```

**2. Organization Name Case-Sensitivity**
```python
@given(st.text(min_size=1, max_size=255))
def test_organization_names_are_case_sensitive(self, test_repo: Repository, name: str):
    """Organization names should be case-sensitive (can create 'Org' and 'org')."""
    assume(name.lower() != name.upper())

    org_data1 = OrganizationData(name=name.lower())
    org1 = test_repo.organizations.create(OrganizationCreateCommand(organization_data=org_data1))

    org_data2 = OrganizationData(name=name.upper())
    org2 = test_repo.organizations.create(OrganizationCreateCommand(organization_data=org_data2))

    assert org1.id != org2.id
    assert org1.name != org2.name
```

**3. Description Field is Optional**
```python
@given(st.text(min_size=1, max_size=255))
def test_organization_without_description_succeeds(self, test_repo: Repository, name: str):
    """Creating organization without description should work."""
    org_data = OrganizationData(name=name, description=None)
    org = test_repo.organizations.create(OrganizationCreateCommand(organization_data=org_data))

    assert org.name == name
    assert org.description is None
```

---

### Project Repository

**1. Project-Workflow Relationship**
```python
@given(st.text(min_size=1, max_size=255))
def test_project_requires_valid_workflow(self, test_repo: Repository, project_name: str):
    """Projects must have a valid workflow_id."""
    org, workflow = create_test_org_with_workflow_via_repo(test_repo)

    project_data = ProjectData(name=project_name)
    project = test_repo.projects.create(ProjectCreateCommand(
        project_data=project_data,
        organization_id=org.id,
        workflow_id=workflow.id
    ))

    assert project.workflow_id == workflow.id

    # Verify project has workflow
    retrieved = test_repo.projects.get_by_id(project.id)
    assert retrieved.workflow_id == workflow.id
```

**2. Archived Projects Not in Active List**
```python
@given(st.lists(st.text(min_size=1, max_size=255), min_size=2, max_size=10, unique=True))
def test_archived_projects_excluded_from_list(self, test_repo: Repository, names: list[str]):
    """Archived projects should not appear in get_all() by default."""
    org, workflow = create_test_org_with_workflow_via_repo(test_repo)

    # Create projects
    project_ids = []
    for name in names:
        project_data = ProjectData(name=name)
        project = test_repo.projects.create(ProjectCreateCommand(
            project_data=project_data,
            organization_id=org.id,
            workflow_id=workflow.id
        ))
        project_ids.append(project.id)

    # Archive first project
    test_repo.projects.archive(project_ids[0])

    # Get active projects
    active_projects = test_repo.projects.get_all()
    active_ids = set(p.id for p in active_projects)

    assert project_ids[0] not in active_ids  # Archived excluded
    for pid in project_ids[1:]:
        assert pid in active_ids  # Others included
```

---

### Workflow Repository

**1. Status List Validation**
```python
@given(st.lists(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Nd"), whitelist_characters="_-")), min_size=1, max_size=20, unique=True))
def test_workflow_statuses_are_unique(self, test_repo: Repository, statuses: list[str]):
    """Workflow statuses must be unique within a workflow."""
    workflow_data = WorkflowData(name="Test Workflow", statuses=statuses)
    workflow = test_repo.workflows.create(WorkflowCreateCommand(workflow_data=workflow_data))

    assert len(workflow.statuses) == len(set(workflow.statuses))
    assert len(workflow.statuses) == len(statuses)
```

**2. Status Pattern Validation**
```python
@given(st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=10))
def test_workflow_statuses_match_pattern(self, test_repo: Repository, statuses: list[str]):
    """Workflow statuses must match pattern ^[A-Z0-9_-]+$."""
    # Filter to valid statuses only
    valid_statuses = [s for s in statuses if re.match(r"^[A-Z0-9_-]+$", s)]
    assume(len(valid_statuses) > 0)

    workflow_data = WorkflowData(name="Test Workflow", statuses=valid_statuses)
    workflow = test_repo.workflows.create(WorkflowCreateCommand(workflow_data=workflow_data))

    for status in workflow.statuses:
        assert re.match(r"^[A-Z0-9_-]+$", status) is not None
```

**3. Default Workflow Creation**
```python
def test_create_default_workflow_idempotent(self, test_repo: Repository):
    """Creating default workflow multiple times should not duplicate."""
    # First call creates
    workflow1 = test_repo.workflows.create_default_workflow()

    # Second call returns existing
    workflow2 = test_repo.workflows.create_default_workflow()

    assert workflow1.id == workflow2.id

    # Verify only one default workflow exists
    all_workflows = test_repo.workflows.get_all()
    defaults = [w for w in all_workflows if w.is_default]
    assert len(defaults) == 1
```

---

### Ticket Repository

**1. Ticket Status Must Match Workflow**
```python
@given(st.text(min_size=1, max_size=255))
def test_ticket_status_must_be_in_workflow(self, test_repo: Repository, title: str):
    """Ticket status must be valid for project's workflow."""
    org, workflow = create_test_org_with_workflow_via_repo(test_repo)
    project = create_test_project_via_repo(test_repo, org.id, "Test Project", workflow_id=workflow.id)
    reporter = create_test_user_via_repo(test_repo, org.id)

    # Create ticket with first status from workflow
    valid_status = workflow.statuses[0]
    ticket_data = TicketData(title=title, status=valid_status, priority=TicketPriority.MEDIUM)
    ticket = test_repo.tickets.create(TicketCreateCommand(
        ticket_data=ticket_data,
        project_id=project.id,
        reporter_id=reporter.id
    ))

    assert ticket.status == valid_status

    # Attempting to set invalid status should fail
    with pytest.raises(ValueError):
        test_repo.tickets.update_status(ticket.id, "INVALID_STATUS")
```

**2. Ticket Filtering Properties**
```python
@given(st.lists(st.text(min_size=1, max_size=255), min_size=5, max_size=20, unique=True))
def test_filter_by_project_returns_subset(self, test_repo: Repository, titles: list[str]):
    """Filtering tickets by project returns only tickets in that project."""
    org, workflow = create_test_org_with_workflow_via_repo(test_repo)
    project1 = create_test_project_via_repo(test_repo, org.id, "Project 1", workflow_id=workflow.id)
    project2 = create_test_project_via_repo(test_repo, org.id, "Project 2", workflow_id=workflow.id)
    reporter = create_test_user_via_repo(test_repo, org.id)

    # Create tickets in both projects
    project1_ids = set()
    for i, title in enumerate(titles[:len(titles)//2]):
        ticket_data = TicketData(title=title, status=workflow.statuses[0], priority=TicketPriority.MEDIUM)
        ticket = test_repo.tickets.create(TicketCreateCommand(
            ticket_data=ticket_data,
            project_id=project1.id,
            reporter_id=reporter.id
        ))
        project1_ids.add(ticket.id)

    for title in titles[len(titles)//2:]:
        ticket_data = TicketData(title=title, status=workflow.statuses[0], priority=TicketPriority.MEDIUM)
        test_repo.tickets.create(TicketCreateCommand(
            ticket_data=ticket_data,
            project_id=project2.id,
            reporter_id=reporter.id
        ))

    # Filter by project1
    filtered = test_repo.tickets.get_all(project_id=project1.id)
    filtered_ids = set(t.id for t in filtered)

    # Should only contain project1 tickets
    assert filtered_ids == project1_ids
```

---

### Epic Repository

**1. Epic-Ticket Relationship**
```python
@given(st.lists(st.text(min_size=1, max_size=255), min_size=2, max_size=5, unique=True))
def test_add_remove_tickets_from_epic(self, test_repo: Repository, ticket_titles: list[str]):
    """Adding and removing tickets from epic should update relationship."""
    org, workflow = create_test_org_with_workflow_via_repo(test_repo)
    project = create_test_project_via_repo(test_repo, org.id, "Test Project", workflow_id=workflow.id)
    reporter = create_test_user_via_repo(test_repo, org.id)

    # Create epic
    epic_data = EpicData(name="Test Epic")
    epic = test_repo.epics.create(EpicCreateCommand(epic_data=epic_data, organization_id=org.id))

    # Create tickets
    ticket_ids = []
    for title in ticket_titles:
        ticket_data = TicketData(title=title, status=workflow.statuses[0], priority=TicketPriority.MEDIUM)
        ticket = test_repo.tickets.create(TicketCreateCommand(
            ticket_data=ticket_data,
            project_id=project.id,
            reporter_id=reporter.id
        ))
        ticket_ids.append(ticket.id)

    # Add all tickets to epic
    for ticket_id in ticket_ids:
        test_repo.epics.add_ticket(epic.id, ticket_id)

    # Verify all tickets in epic
    epic_with_tickets = test_repo.epics.get_by_id(epic.id)
    assert len(epic_with_tickets.ticket_ids) == len(ticket_ids)

    # Remove one ticket
    test_repo.epics.remove_ticket(epic.id, ticket_ids[0])

    # Verify ticket removed
    updated_epic = test_repo.epics.get_by_id(epic.id)
    assert len(updated_epic.ticket_ids) == len(ticket_ids) - 1
    assert ticket_ids[0] not in updated_epic.ticket_ids
```

---

## API Layer: Specific Test Ideas

### User API

**1. Create-Read-Update-Delete Roundtrip**
```python
@given(
    username=st.text(min_size=3, max_size=50, alphabet=USERNAME_CHARS),
    email=st.emails(),
    full_name=st.text(min_size=1, max_size=255)
)
def test_user_crud_roundtrip_via_api(
    self, client: TestClient, super_admin_token: str, username: str, email: str, full_name: str
):
    """User data should survive complete CRUD cycle through API."""
    org_id = create_test_org(client, super_admin_token)

    # Create
    response = client.post(
        "/api/users",
        params={"organization_id": org_id, "role": "admin"},
        json={"username": username, "email": email, "full_name": full_name},
        headers=auth_headers(super_admin_token)
    )
    assert response.status_code == 201
    user_id = response.json()["user"]["id"]

    # Read
    get_response = client.get(f"/api/users/{user_id}", headers=auth_headers(super_admin_token))
    assert get_response.status_code == 200
    user_data = get_response.json()
    assert user_data["username"] == username
    assert user_data["email"] == email
    assert user_data["full_name"] == full_name

    # Update
    new_email = f"updated_{email}"
    update_response = client.put(
        f"/api/users/{user_id}",
        json={"email": new_email},
        headers=auth_headers(super_admin_token)
    )
    assert update_response.status_code == 200
    assert update_response.json()["email"] == new_email

    # Delete
    delete_response = client.delete(f"/api/users/{user_id}", headers=auth_headers(super_admin_token))
    assert delete_response.status_code == 204

    # Verify deleted
    final_get = client.get(f"/api/users/{user_id}", headers=auth_headers(super_admin_token))
    assert final_get.status_code == 404
```

**2. Invalid Data Returns 400/422**
```python
@given(st.text(max_size=2))  # Too short for username
def test_create_user_with_invalid_username_fails(
    self, client: TestClient, super_admin_token: str, invalid_username: str
):
    """Creating user with invalid username should return validation error."""
    org_id = create_test_org(client, super_admin_token)

    response = client.post(
        "/api/users",
        params={"organization_id": org_id, "role": "admin"},
        json={"username": invalid_username, "email": "test@test.com", "full_name": "Test"},
        headers=auth_headers(super_admin_token)
    )

    assert response.status_code in [400, 422]
```

---

### Organization API

**1. List Filtering is Subset**
```python
@given(st.lists(st.text(min_size=1, max_size=255), min_size=5, max_size=20, unique=True))
def test_filtered_organizations_are_subset_of_all(
    self, client: TestClient, super_admin_token: str, names: list[str]
):
    """Filtering organizations should return subset of all organizations."""
    # Create organizations
    for name in names:
        client.post(
            "/api/organizations",
            json={"name": name},
            headers=auth_headers(super_admin_token)
        )

    # Get all organizations
    all_response = client.get("/api/organizations", headers=auth_headers(super_admin_token))
    all_orgs = all_response.json()
    all_ids = set(o["id"] for o in all_orgs)

    # Get filtered organizations (active only)
    filtered_response = client.get(
        "/api/organizations",
        params={"is_active": "true"},
        headers=auth_headers(super_admin_token)
    )
    filtered_orgs = filtered_response.json()
    filtered_ids = set(o["id"] for o in filtered_orgs)

    # Filtered should be subset of all
    assert filtered_ids.issubset(all_ids)
```

---

## Hypothesis Strategies

### Custom Strategies for Domain Models

**Username Strategy**
```python
USERNAME_CHARS = st.characters(
    whitelist_categories=("Lu", "Ll", "Nd"),
    whitelist_characters="_-"
)

@st.composite
def usernames(draw):
    """Generate valid usernames (3-50 chars, alphanumeric + underscore + dash)."""
    return draw(st.text(min_size=3, max_size=50, alphabet=USERNAME_CHARS))
```

**Email Strategy**
```python
@st.composite
def emails(draw):
    """Generate valid email addresses."""
    local = draw(st.text(min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("Ll", "Nd"))))
    domain = draw(st.text(min_size=1, max_size=63, alphabet=st.characters(whitelist_categories=("Ll", "Nd"))))
    tld = draw(st.sampled_from(["com", "org", "net", "edu"]))
    return f"{local}@{domain}.{tld}"
```

**Organization Name Strategy**
```python
@st.composite
def organization_names(draw):
    """Generate valid organization names (1-255 chars)."""
    return draw(st.text(min_size=1, max_size=255))
```

**Workflow Statuses Strategy**
```python
@st.composite
def workflow_statuses(draw):
    """Generate valid workflow status lists."""
    # Valid pattern: ^[A-Z0-9_-]+$
    status_chars = st.characters(whitelist_categories=("Lu", "Nd"), whitelist_characters="_-")
    statuses = draw(st.lists(
        st.text(min_size=1, max_size=50, alphabet=status_chars),
        min_size=1,
        max_size=20,
        unique=True
    ))
    return statuses
```

**Priority Strategy**
```python
@st.composite
def ticket_priorities(draw):
    """Generate valid ticket priorities."""
    return draw(st.sampled_from([TicketPriority.LOW, TicketPriority.MEDIUM, TicketPriority.HIGH, TicketPriority.CRITICAL]))
```

---

## Stateful Testing Examples

### Project State Machine

```python
class ProjectStateMachine(RuleBasedStateMachine):
    """Stateful testing for project lifecycle."""

    def __init__(self):
        super().__init__()
        self.repo = get_test_repository()
        self.org, self.workflow = create_test_org_with_workflow_via_repo(self.repo)
        self.projects: dict[str, str] = {}  # name -> id
        self.archived_projects: set[str] = set()

    @rule(name=st.text(min_size=1, max_size=255))
    def create_project(self, name: str):
        """Create a project."""
        assume(name not in self.projects)

        project_data = ProjectData(name=name)
        project = self.repo.projects.create(ProjectCreateCommand(
            project_data=project_data,
            organization_id=self.org.id,
            workflow_id=self.workflow.id
        ))

        self.projects[name] = project.id

    @rule(target=st.sampled_from(list))
    @precondition(lambda self: len(self.projects) > 0)
    def archive_project(self):
        """Archive a project."""
        name = list(self.projects.keys())[0]
        project_id = self.projects[name]

        self.repo.projects.archive(project_id)
        self.archived_projects.add(name)

    @rule(target=st.sampled_from(list))
    @precondition(lambda self: len(self.archived_projects) > 0)
    def unarchive_project(self):
        """Unarchive a project."""
        name = list(self.archived_projects)[0]
        project_id = self.projects[name]

        self.repo.projects.unarchive(project_id)
        self.archived_projects.remove(name)

    @invariant()
    def check_archived_status(self):
        """Verify archive status is consistent."""
        for name, project_id in self.projects.items():
            project = self.repo.projects.get_by_id(project_id)

            if name in self.archived_projects:
                assert project.is_archived is True
            else:
                assert project.is_archived is False

TestProjectStateMachine = ProjectStateMachine.TestCase
```

---

## Test Organization

### File Structure

```
tests/
├── property_based/
│   ├── __init__.py
│   ├── strategies.py              # Custom Hypothesis strategies
│   ├── dal/
│   │   ├── __init__.py
│   │   ├── test_user_properties.py
│   │   ├── test_organization_properties.py
│   │   ├── test_project_properties.py
│   │   ├── test_workflow_properties.py
│   │   ├── test_ticket_properties.py
│   │   ├── test_epic_properties.py
│   │   └── test_comment_properties.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── test_user_api_properties.py
│   │   ├── test_organization_api_properties.py
│   │   └── test_project_api_properties.py
│   └── stateful/
│       ├── __init__.py
│       ├── test_user_state_machine.py
│       ├── test_project_state_machine.py
│       └── test_ticket_state_machine.py
```

### Test Naming Convention

- **Stateless**: `test_<property_name>` (e.g., `test_username_roundtrip`)
- **Stateful**: `test_<entity>_state_machine` (e.g., `test_user_state_machine`)

---

## Running Property-Based Tests

### Configuration

**pytest.ini**:
```ini
[pytest]
# Hypothesis settings
hypothesis_profile = dev

[hypothesis:dev]
max_examples = 100
deadline = None

[hypothesis:ci]
max_examples = 1000
deadline = 5000
```

### Commands

```bash
# Run all property-based tests
pytest tests/property_based/

# Run with more examples (stress testing)
pytest tests/property_based/ --hypothesis-profile=ci

# Run specific property test
pytest tests/property_based/dal/test_user_properties.py::test_username_roundtrip

# Run with verbose output
pytest tests/property_based/ -v --hypothesis-show-statistics
```

---

## Benefits and Trade-offs

### Benefits ✅

1. **Finds edge cases automatically**: Discovers bugs you wouldn't think to test
2. **Minimal test code**: One property test replaces dozens of example tests
3. **Better coverage**: Tests hundreds of inputs vs handful of examples
4. **Regression tests**: Hypothesis saves failing examples for regression testing
5. **Documentation**: Properties document invariants clearly

### Trade-offs ⚠️

1. **Slower execution**: Generates many test cases (mitigate with CI profile)
2. **Non-deterministic failures**: May find rare bugs (Hypothesis saves seeds)
3. **Learning curve**: Requires understanding property-based testing concepts
4. **Debugging complexity**: Generated inputs may be unintuitive (use `.example()` for debugging)

---

## Next Steps

### Phase 1: Foundation (Week 1-2)
- [ ] Install Hypothesis: `uv add --dev hypothesis`
- [ ] Create `tests/property_based/` structure
- [ ] Implement custom strategies in `strategies.py`
- [ ] Write 5 basic roundtrip tests (User, Organization, Project, Workflow, Ticket)

### Phase 2: Repository Layer (Week 3-4)
- [ ] Implement all User repository property tests
- [ ] Implement all Organization repository property tests
- [ ] Implement all Project repository property tests
- [ ] Implement all Workflow repository property tests
- [ ] Implement all Ticket repository property tests

### Phase 3: Stateful Testing (Week 5-6)
- [ ] Implement User CRUD state machine
- [ ] Implement Project state machine
- [ ] Implement Ticket state machine

### Phase 4: API Layer (Week 7-8)
- [ ] Implement User API property tests
- [ ] Implement Organization API property tests
- [ ] Implement Project API property tests

### Phase 5: Integration & Optimization (Week 9-10)
- [ ] Run all property tests, fix any failures
- [ ] Optimize slow tests
- [ ] Add to CI pipeline
- [ ] Document findings and bugs discovered

---

## Resources

- **Hypothesis Documentation**: https://hypothesis.readthedocs.io/
- **Property-Based Testing Book**: "Property-Based Testing with PropEr, Erlang, and Elixir" (concepts apply to Python)
- **Hypothesis Examples**: https://github.com/HypothesisWorks/hypothesis/tree/master/hypothesis-python/examples
- **Stateful Testing Guide**: https://hypothesis.readthedocs.io/en/latest/stateful.html
