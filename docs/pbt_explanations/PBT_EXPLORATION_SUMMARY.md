# Property-Based Testing Exploration Summary

## Project Structure Overview

This is a **FastAPI-based project management CRUD application** with the following architecture:

### Layers:
1. **API Layer** (`project_management_crud_example/routers/`) - FastAPI endpoints
2. **Repository/DAL Layer** (`project_management_crud_example/dal/sqlite/`) - Database access
3. **Domain Layer** (`project_management_crud_example/domain_models.py`) - Business logic & validation
4. **ORM Layer** (`project_management_crud_example/dal/sqlite/orm_data_models.py`) - SQLAlchemy models

---

## 1. Entity Types and Key Fields

### Core Entities:

#### **Organization**
- **Fields**: `id`, `name` (unique, max 255), `description` (optional, max 1000), `is_active`, `created_at`, `updated_at`
- **Validation**: `name` required, 1-255 chars, globally unique
- **CRUD**: Create, Read, Update, Delete

#### **User**
- **Fields**: `id`, `username` (alphanumeric/dash/underscore, 3-50), `email` (EmailStr), `full_name` (1-255), `password_hash` (hashed), `organization_id` (optional, None for Super Admin), `role` (enum), `is_active`, `created_at`, `updated_at`
- **Roles**: SUPER_ADMIN, ADMIN, PROJECT_MANAGER, WRITE_ACCESS, READ_ACCESS
- **Validation**: Email must be valid, username pattern `^[a-zA-Z0-9_-]+$`
- **Special**: Password hashing, authentication with `get_by_username_with_password()` returning `UserAuthData`

#### **Project**
- **Fields**: `id`, `name` (1-255), `description` (optional, max 1000), `organization_id` (required), `workflow_id` (required), `is_active`, `is_archived`, `archived_at` (nullable), `created_at`, `updated_at`
- **Relationships**: Belongs to Organization, uses Workflow for ticket statuses
- **Operations**: Create, Read, Update, Archive, Unarchive, Delete

#### **Workflow**
- **Fields**: `id`, `name` (1-255), `description` (optional, max 1000), `statuses` (non-empty list, JSON stored), `organization_id`, `is_default`, `created_at`, `updated_at`
- **Status Validation**: Pattern `^[A-Z0-9_-]+$`, no duplicates, non-empty list
- **Special**: Default workflow created per organization, custom workflows for projects

#### **Ticket**
- **Fields**: `id`, `title` (1-500), `description` (optional, max 2000), `priority` (LOW, MEDIUM, HIGH, CRITICAL - optional), `status` (required, validated against project workflow), `assignee_id` (optional), `reporter_id` (required), `project_id`, `created_at`, `updated_at`
- **Relationships**: Belongs to Project, Reporter (User), optional Assignee (User)
- **Operations**: Create, Read, Update, Delete, Change Status, Move to Project, Assign/Unassign

#### **Epic**
- **Fields**: `id`, `name` (1-255), `description` (optional, max 1000), `organization_id`, `created_at`, `updated_at`
- **Relationships**: Belongs to Organization, can contain many Tickets (many-to-many via EpicTicketORM)
- **Operations**: Create, Read, Update, Delete, Add Ticket, Remove Ticket

#### **Comment**
- **Fields**: `id`, `content` (1-5000), `ticket_id`, `author_id`, `created_at`, `updated_at`
- **Relationships**: Belongs to Ticket, Author (User)
- **Operations**: Create, Read, Update, Delete

#### **ActivityLog**
- **Fields**: `id`, `entity_type`, `entity_id`, `action` (ActionType enum), `actor_id`, `organization_id`, `timestamp`, `changes` (dict), `metadata` (dict, optional)
- **Special**: Audit trail for all entity changes, action types for 7 entity types

#### **StubEntity** (Template/Scaffolding)
- **Fields**: `id`, `name` (1-255), `description` (optional, max 1000), `created_at`, `updated_at`
- **Purpose**: Template for creating new entity types

---

## 2. All Repository Operations

### Repository Structure
Location: `/project_management_crud_example/dal/sqlite/repository.py`

**Pattern**: Single `Repository` class with nested classes for organization:
- `repo.users.*`
- `repo.organizations.*`
- `repo.projects.*`
- `repo.epics.*`
- `repo.workflows.*`
- `repo.tickets.*`
- `repo.comments.*`
- `repo.activity_logs.*`
- `repo.stub_entities.*`

### Users Repository Methods
```python
create(user_create_command: UserCreateCommand) -> User
get_by_id(user_id: str) -> Optional[User]
get_by_username(username: str) -> Optional[User]  # Case-insensitive
get_by_username_with_password(username: str) -> Optional[UserAuthData]  # Returns special auth model
get_all() -> List[User]
get_by_filters(organization_id, role, is_active) -> List[User]
update(user_id: str, update_command: UserUpdateCommand) -> Optional[User]
update_password(user_id: str, new_password: str) -> bool
delete(user_id: str) -> bool
create_super_admin_if_needed(...) -> tuple[bool, Optional[User]]  # Bootstrap helper, idempotent
```

### Organizations Repository Methods
```python
create(organization_create_command: OrganizationCreateCommand) -> Organization
get_by_id(organization_id: str) -> Optional[Organization]
update(organization_id: str, update_command: OrganizationUpdateCommand) -> Optional[Organization]
delete(organization_id: str) -> bool
```

### Projects Repository Methods
```python
create(project_create_command: ProjectCreateCommand) -> Project
get_by_id(project_id: str) -> Optional[Project]
get_by_organization_id(organization_id: str) -> List[Project]
get_by_filters(organization_id, is_active, is_archived) -> List[Project]
update(project_id: str, update_command: ProjectUpdateCommand) -> Optional[Project]
delete(project_id: str) -> bool
archive(project_id: str) -> Optional[Project]
unarchive(project_id: str) -> Optional[Project]
```

### Workflows Repository Methods
```python
create(workflow_create_command: WorkflowCreateCommand) -> Workflow
get_by_id(workflow_id: str) -> Optional[Workflow]
get_by_organization_id(organization_id: str) -> List[Workflow]
create_default_workflow(organization_id: str) -> Workflow
update(workflow_id: str, update_command: WorkflowUpdateCommand) -> Optional[Workflow]
delete(workflow_id: str) -> bool
```

### Tickets Repository Methods
```python
create(ticket_create_command: TicketCreateCommand, reporter_id: str) -> Ticket
get_by_id(ticket_id: str) -> Optional[Ticket]
get_by_project_id(project_id: str) -> List[Ticket]
get_by_filters(project_id, status, assignee_id, priority) -> List[Ticket]
update(ticket_id: str, update_command: TicketUpdateCommand) -> Optional[Ticket]
update_status(ticket_id: str, status: str) -> Optional[Ticket]
update_project(ticket_id: str, project_id: str) -> Optional[Ticket]
update_assignee(ticket_id: str, assignee_id: Optional[str]) -> Optional[Ticket]
delete(ticket_id: str) -> bool
```

### Epics Repository Methods
```python
create(epic_create_command: EpicCreateCommand) -> Epic
get_by_id(epic_id: str) -> Optional[Epic]
get_by_organization_id(organization_id: str) -> List[Epic]
update(epic_id: str, update_command: EpicUpdateCommand) -> Optional[Epic]
delete(epic_id: str) -> bool
add_ticket_to_epic(epic_id: str, ticket_id: str) -> bool
remove_ticket_from_epic(epic_id: str, ticket_id: str) -> bool
```

### Comments Repository Methods
```python
create(comment_create_command: CommentCreateCommand, author_id: str) -> Comment
get_by_id(comment_id: str) -> Optional[Comment]
get_by_ticket_id(ticket_id: str) -> List[Comment]
update(comment_id: str, update_command: CommentUpdateCommand) -> Optional[Comment]
delete(comment_id: str) -> bool
```

### ActivityLogs Repository Methods
```python
create(command: ActivityLogCreateCommand) -> ActivityLog
get_by_id(log_id: str) -> Optional[ActivityLog]
list(entity_type, entity_id, organization_id, start_date, end_date, limit) -> List[ActivityLog]
```

### StubEntities Repository Methods
```python
create(stub_entity_create_command: StubEntityCreateCommand) -> StubEntity
get_by_id(stub_entity_id: str) -> Optional[StubEntity]
update(stub_entity_id: str, stub_entity_data: StubEntityUpdateCommand) -> Optional[StubEntity]
delete(stub_entity_id: str) -> bool
```

---

## 3. All API Endpoints

### API Structure
Location: `/project_management_crud_example/routers/`

**Pattern**: Each entity has its own router file with prefixes like `/api/users`, `/api/organizations`, etc.

#### User API (`/api/users`)
```
POST   /api/users                           - Create user
GET    /api/users                           - List all users
GET    /api/users/{user_id}                 - Get user by ID
PUT    /api/users/{user_id}                 - Update user
DELETE /api/users/{user_id}                 - Delete user
POST   /auth/login                          - Login user
POST   /auth/change-password                - Change password
```

#### Organization API (`/api/organizations`)
```
POST   /api/organizations                   - Create organization
GET    /api/organizations                   - List all organizations
GET    /api/organizations/{organization_id} - Get organization
PUT    /api/organizations/{organization_id} - Update organization
```

#### Project API (`/api/projects`)
```
POST   /api/projects                        - Create project
GET    /api/projects                        - List all projects
GET    /api/projects/{project_id}           - Get project by ID
PUT    /api/projects/{project_id}           - Update project
DELETE /api/projects/{project_id}           - Delete project
PATCH  /api/projects/{project_id}/archive   - Archive project
PATCH  /api/projects/{project_id}/unarchive - Unarchive project
```

#### Workflow API (`/api/workflows`)
```
POST   /api/workflows                       - Create workflow
GET    /api/workflows                       - List all workflows
GET    /api/workflows/{workflow_id}         - Get workflow by ID
PUT    /api/workflows/{workflow_id}         - Update workflow
DELETE /api/workflows/{workflow_id}         - Delete workflow
```

#### Ticket API (`/api/tickets`)
```
POST   /api/tickets                         - Create ticket
GET    /api/tickets                         - List all tickets
GET    /api/tickets/{ticket_id}             - Get ticket by ID
PUT    /api/tickets/{ticket_id}             - Update ticket
PUT    /api/tickets/{ticket_id}/status      - Change ticket status
PUT    /api/tickets/{ticket_id}/assignee    - Assign/unassign ticket
PUT    /api/tickets/{ticket_id}/project     - Move ticket to project
DELETE /api/tickets/{ticket_id}             - Delete ticket
```

#### Epic API (`/api/epics`)
```
POST   /api/epics                           - Create epic
GET    /api/epics                           - List all epics
GET    /api/epics/{epic_id}                 - Get epic by ID
PUT    /api/epics/{epic_id}                 - Update epic
DELETE /api/epics/{epic_id}                 - Delete epic
GET    /api/epics/{epic_id}/tickets         - Get tickets in epic
POST   /api/epics/{epic_id}/tickets         - Add ticket to epic
DELETE /api/epics/{epic_id}/tickets/{ticket_id} - Remove ticket from epic
```

#### Comment API (`/api/tickets/{ticket_id}/comments`)
```
POST   /api/tickets/{ticket_id}/comments    - Create comment
GET    /api/tickets/{ticket_id}/comments    - List ticket comments
GET    /api/comments/{comment_id}           - Get comment by ID
PUT    /api/comments/{comment_id}           - Update comment
DELETE /api/comments/{comment_id}           - Delete comment
```

#### ActivityLog API (`/api/activity-logs`)
```
GET    /api/activity-logs                   - List activity logs (with filters)
GET    /api/activity-logs/{log_id}          - Get activity log by ID
```

#### StubEntity API (`/api/stub_entities`) - Example/Template
```
POST   /api/stub_entities                   - Create stub entity
GET    /api/stub_entities                   - List all stub entities
GET    /api/stub_entities/{stub_entity_id}  - Get stub entity by ID
PUT    /api/stub_entities/{stub_entity_id}  - Update stub entity
DELETE /api/stub_entities/{stub_entity_id}  - Delete stub entity
```

---

## 4. Validation Rules & Constraints

### String Field Validation
- **Names/Titles**: 1-255 chars (most entities)
- **Descriptions**: 0-1000 chars (most entities), 0-2000 for tickets
- **Username**: 3-50 chars, pattern `^[a-zA-Z0-9_-]+$`
- **Comment Content**: 1-5000 chars
- **Email**: Must be valid EmailStr (Pydantic validator)

### List Validation
- **Workflow Statuses**: Non-empty list, each status matches `^[A-Z0-9_-]+$`, no duplicates

### Enum Constraints
- **UserRole**: SUPER_ADMIN, ADMIN, PROJECT_MANAGER, WRITE_ACCESS, READ_ACCESS
- **TicketPriority**: LOW, MEDIUM, HIGH, CRITICAL (optional)
- **ActionType**: 30+ action types for audit logging

### Unique Constraints
- **Organization name**: Globally unique
- **Username**: Globally unique (case-insensitive lookup)
- **Workflow statuses**: No duplicates within a workflow

### Required Field Rules
- **User**: username, email, full_name, password (on create), role, organization_id (except Super Admin)
- **Ticket**: title, status (must match project workflow), project_id, reporter_id
- **Project**: name, organization_id, workflow_id
- **Workflow**: name, statuses (non-empty)
- **Organization**: name

### Foreign Key Relationships
- **Ticket** → Project (via project_id)
- **Ticket** → User (reporter_id, assignee_id)
- **Project** → Organization (via organization_id)
- **Project** → Workflow (via workflow_id)
- **Workflow** → Organization (via organization_id)
- **Epic** → Organization (via organization_id)
- **EpicTicket** (M2M) → Epic & Ticket
- **Comment** → Ticket (via ticket_id)
- **Comment** → User (author_id)
- **ActivityLog** → Organization (via organization_id)

### Status/State Rules
- **Ticket status**: Must be valid status from project's workflow
- **Project archived status**: Can be archived/unarchived
- **User active status**: Can be active/inactive
- **Organization active status**: Can be active/inactive

---

## 5. Current Test Structure

### Test Layout
- **API Tests**: `/tests/api/test_*_api.py` - HTTP endpoint tests
- **Repository Tests**: `/tests/dal/test_*_repository.py` - Data access tests
- **Utility Tests**: `/tests/utils/` - Helper function tests
- **Fixtures**: `/tests/fixtures/auth_fixtures.py` - Authentication test fixtures
- **Helpers**: `/tests/helpers.py` - Helper functions for test setup

### Test Fixtures (conftest.py)
```python
db_path: str                          # ':memory:' or temp file path
test_db: Database                     # Initialized database
test_session: Session                 # SQLAlchemy session
test_repo: Repository                 # Repository instance
client: TestClient                    # FastAPI TestClient
organization: str                     # Test organization ID
super_admin_token: str                # Super admin JWT token
org_admin_token: tuple[str, str]      # (token, org_id) for org admin
project_manager_token: ...            # (token, org_id) for project manager
write_user_token: ...                 # (token, org_id) for write user
read_user_token: ...                  # (token, org_id) for read user
```

### Test Helper Functions
- `create_test_org()` - Create org via API
- `create_test_project()` - Create project via API
- `create_test_user()` - Generic user creation
- `create_admin_user()` - Create admin with defaults
- `create_project_manager()` - Create PM with defaults
- `create_write_user()` - Create write user with defaults
- `create_read_user()` - Create read user with defaults
- `auth_headers()` - Create auth header from token

### Repository Test Helpers (dal/helpers.py)
- `create_test_org_via_repo()` - Create org via repository
- `create_test_project_via_repo()` - Create project via repository
- `create_test_user_via_repo()` - Create user via repository

### Existing Test Coverage Examples
- `/tests/api/test_user_api.py` - User CRUD & permission tests
- `/tests/api/test_project_api.py` - Project CRUD tests
- `/tests/api/test_ticket_api.py` - Ticket CRUD tests
- `/tests/dal/test_user_repository.py` - Repository-level user tests
- `/tests/dal/test_project_repository.py` - Repository-level project tests

### Test Pattern Examples
**API Tests**: Use `client: TestClient` fixture, test HTTP status codes, response data
**Repository Tests**: Use `test_repo: Repository` fixture, test domain models, not ORM

---

## 6. Dependencies & Testing Framework

### Main Dependencies
- **FastAPI** (0.119.1+) - Web framework
- **Pydantic** (2.11.5+) - Data validation
- **SQLAlchemy** (2.0.44+) - ORM
- **JWT** (2.10.1+) - Authentication
- **bcrypt** (5.0.0+) - Password hashing
- **email-validator** (2.3.0+) - Email validation

### Test Dependencies
- **pytest** (8.3.5+) - Test framework
- **pytest-testmon** (2.1.3+) - Test change detection
- **pytest-watch** (4.2.0+) - Test auto-run
- **httpx** (0.28.1+) - For TestClient
- **deepdiff** (8.6.1+) - Diff utilities

### **No hypothesis/property-based testing currently exists** in dependencies or codebase

---

## 7. Key Properties for Property-Based Testing

### 1. **Idempotency Properties**
- Creating same entity twice: Should fail or return same result
- `create_super_admin_if_needed()`: Must be idempotent
- Calling get/update: Multiple calls return consistent data

### 2. **CRUD Roundtrip Properties**
- **Create → Get**: Created entity matches retrieved entity
- **Create → Update → Get**: Updated data persists and is correct
- **Create → Delete → Get**: Deleted entity returns not found

### 3. **Data Persistence Properties**
- Data survives database roundtrips
- Timestamps are consistent
- IDs are unique

### 4. **Validation Properties**
- Invalid data rejected with appropriate errors
- Valid data accepted
- Boundary values handled (min/max length)
- Constraints enforced (unique fields, foreign keys)

### 5. **Relationship Properties**
- Tickets belong to exactly one project
- Comments belong to exactly one ticket
- Users can be in exactly one organization (except Super Admin)
- Workflow statuses follow format rules

### 6. **Status Transition Properties**
- Ticket status must be valid per project workflow
- Project can transition between archived/unarchived
- User can be activated/deactivated

### 7. **Permission/Authorization Properties**
- Different roles have different accessible endpoints
- Super Admin can access all
- Org Admin limited to own org
- Users can't see other org's data

### 8. **Search/Filter Properties**
- Filter results are subset of all items
- Multiple filters AND together correctly
- Searching for non-existent values returns empty

### 9. **Cascade/Dependency Properties**
- Deleting org should delete related projects
- Deleting project should delete related tickets
- Foreign key constraints enforced

### 10. **Password & Security Properties**
- Password hash differs from plaintext
- Same password + same user = same hash
- Different passwords = different hashes
- Password updates work correctly

---

## Summary for PBT Design

**Candidates for Property-Based Testing:**
1. ✅ **CRUD operations** - Create/Read/Update/Delete roundtrips
2. ✅ **Data validation** - Min/max lengths, formats, uniqueness
3. ✅ **Relationships** - FK constraints, cascading
4. ✅ **Filtering** - Filter combinations, subset properties
5. ✅ **Password security** - Hash consistency, one-way property
6. ✅ **Timestamp consistency** - Always UTC, ordered correctly
7. ✅ **Idempotency** - Repeated operations stable
8. ✅ **List operations** - Workflow statuses, multi-select
9. ✅ **String constraints** - Username pattern, email format
10. ✅ **Status transitions** - Valid state changes

**NOT Ideal for PBT:**
- Permission/authorization (requires specific roles)
- Multi-user/concurrency scenarios (limited hypothesis generators)
- Complex business workflows (require orchestration)
