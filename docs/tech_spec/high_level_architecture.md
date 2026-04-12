# High-Level Architecture

## Overview

This project implements a FastAPI-based backend service with a clean layered architecture, SQLite database, and comprehensive testing infrastructure.

## Architecture Layers

```
+-------------------------------------------------------+
|                API Layer (FastAPI)                    |
|  - RESTful endpoints                                  |
|  - Request/response validation (Pydantic)             |
|  - Dependency injection                               |
|  - Error handling & HTTP status codes                 |
|  Files: routers/*.py, app.py                          |
+-------------------------+-----------------------------+
                          |
                          | Uses domain models for I/O
                          v
+-------------------------------------------------------+
|                 Domain Layer                          |
|  - Business entities (Pydantic models)                |
|  - Data validation rules                              |
|  - Command objects (Create/Update)                    |
|  Files: domain_models.py                              |
+-------------------------+-----------------------------+
                          |
                          | Repositories operate on domain models
                          v
+-------------------------------------------------------+
|             Repository Layer (DAL)                    |
|  - Repository pattern for data access                 |
|  - CRUD operations abstraction                        |
|  - Database session management                        |
|  Files: dal/sqlite/repository.py                      |
+-------------------------+-----------------------------+
                          |
                          | Converters transform between layers
                          v
+-------------------------------------------------------+
|            Converter Layer (DAL)                      |
|  - ORM <-> Domain model transformations               |
|  - Explicit type-safe conversions                     |
|  - No implicit model_validate() usage                 |
|  Files: dal/sqlite/converters.py                      |
+-------------------------+-----------------------------+
                          |
                          | Uses ORM models
                          v
+-------------------------------------------------------+
|              ORM Layer (SQLAlchemy)                   |
|  - Database table definitions                         |
|  - Column mappings & constraints                      |
|  - Relationships (if any)                             |
|  Files: dal/sqlite/orm_data_models.py                 |
+-------------------------+-----------------------------+
                          |
                          | Managed by Database class
                          v
+-------------------------------------------------------+
|            Database Layer (SQLite)                    |
|  - Connection management                              |
|  - Session creation                                   |
|  - Table creation/dropping                            |
|  - Engine disposal                                    |
|  Files: dal/sqlite/database.py                        |
+-------------------------------------------------------+
```

## Technology Stack

### Core Framework
- **FastAPI**: Web framework for building APIs
- **Pydantic**: Data validation and serialization
- **SQLAlchemy**: ORM for database operations
- **Uvicorn**: ASGI server

### Database
- **SQLite**: Embedded database
- **Support for both disk-based and in-memory databases**
- Configurable via `db_path` (file path or `:memory:`)

### Testing
- **pytest**: Testing framework
- **httpx**: HTTP client for FastAPI TestClient
- **Disk-based testing by default** (configurable with `--db-mode=memory`)

## Key Design Patterns

### Repository Pattern
Abstracts data access logic from business logic:
- Each entity type has a dedicated repository (e.g., `StubEntityRepository`)
- Repositories provide CRUD operations
- Repositories work with domain models, not ORM models
- **Repository layer is a cohesive whole** - should be thoroughly tested independently
- Repository tests verify data persistence without requiring HTTP layer

### Dependency Injection
FastAPI's built-in DI system used throughout:
```python
# dependencies.py
def get_db_session() -> Iterator[Session]:
    db = get_database()
    with db.get_session() as session:
        yield session

def get_stub_entity_repo(
    session: Session = Depends(get_db_session)
) -> StubEntityRepository:
    return StubEntityRepository(session)

# routers/stub_entity_api.py
@router.post("")
async def create_stub_entity(
    stub_entity_data: StubEntityData,
    repo: StubEntityRepository = Depends(get_stub_entity_repo),
) -> StubEntity:
    # ... implementation
```

### Command Pattern
Separate command objects for create/update operations:
- `StubEntityCreateCommand` - Encapsulates creation data
- `StubEntityUpdateCommand` - Encapsulates update data (partial updates)

### Explicit Conversions
Avoid implicit model validation, use explicit converter functions:
```python
# converters.py
def orm_stub_entity_to_business_stub_entity(
    orm_stub_entity: StubEntityORM
) -> StubEntity:
    """Explicit conversion from ORM to domain model."""
    return StubEntity(
        id=str(orm_stub_entity.id),
        name=orm_stub_entity.name,
        # ... explicit field mapping
    )
```

## Data Flow

### Typical Request Flow (Create Entity)

```
1. HTTP POST /stub_entities
   |
2. FastAPI validates request body -> StubEntityData
   |
3. Router endpoint receives StubEntityData
   |
4. Wraps in StubEntityCreateCommand
   |
5. Passes to StubEntityRepository.create_stub_entity()
   |
6. Repository creates StubEntityORM instance
   |
7. SQLAlchemy persists to database
   |
8. Repository converts ORM -> StubEntity (domain model)
   |
9. FastAPI serializes StubEntity -> JSON response
   |
10. HTTP 201 Created with JSON body
```

### Typical Request Flow (Get Entity)

```
1. HTTP GET /stub_entities/{id}
   |
2. Router endpoint receives id parameter
   |
3. Calls StubEntityRepository.get_stub_entity_by_id(id)
   |
4. Repository queries database for StubEntityORM
   |
5. Repository converts ORM -> StubEntity (or None if not found)
   |
6. Router handles None -> raises HTTPException(404)
   |
7. Router returns StubEntity -> FastAPI serializes to JSON
   |
8. HTTP 200 OK with JSON body
```

## Directory Structure

```
backend/
├── project_management_crud_example/
│   ├── app.py                    # FastAPI application setup
│   ├── domain_models.py          # Domain entities & commands
│   ├── dependencies.py           # FastAPI dependencies
│   ├── dal/                      # Data Access Layer
│   │   └── sqlite/
│   │       ├── database.py       # Database connection management
│   │       ├── orm_data_models.py # SQLAlchemy ORM models
│   │       ├── repository.py     # Repository implementations
│   │       └── converters.py     # ORM <-> Domain converters
│   └── routers/                  # API route handlers
│       ├── stub_entity_api.py   # Entity CRUD endpoints
│       └── health.py            # Health check
├── tests/
│   ├── conftest.py          # Test fixtures
│   ├── api/                 # API integration tests
│   │   └── test_stub_entity_api.py
│   └── dal/                 # Repository/DAL tests
│       └── test_stub_entity_repository.py
└── devtools/                # Development validation scripts
```

## Configuration

### Database Configuration
- **Development**: `stub_entities.db` (SQLite file)
- **Testing**: Temporary files (via `db_path` fixture)
  - Default: Disk-based (`--db-mode=disk`)
  - Optional: In-memory (`--db-mode=memory`)

### Environment-Specific Behavior
- Database path configured in `dependencies.py::get_database()`
- Tests override database via fixture dependency injection

## Testing Strategy

### Test Infrastructure
- **PyTest fixtures** provide test isolation (each test gets its own database)
- **Configurable database mode**: disk-based (default) or in-memory (`--db-mode=memory`)
- **Automatic cleanup**: fixtures handle database lifecycle

### Test Fixture Hierarchy
```
db_path -> test_db -> test_session -> test_stub_entity_repo (Repository tests)
                   \
                    -> client (API tests)
```

### Test Coverage Layers

**Every feature implementation must include ALL these test layers:**

1. **API Tests** (`tests/api/`) - Priority 1
   - Test HTTP endpoints and complete workflows
   - Verify externally observable behavior
   - Test through actual HTTP requests

2. **Repository Tests** (`tests/dal/`) - Required
   - Test repository layer independently (without HTTP)
   - Verify CRUD operations and data persistence
   - **Repository is cohesive architectural layer - test thoroughly**

3. **Utility/Logic Tests** - If applicable
   - Test helper functions, converters, utilities
   - Test business logic in domain models

4. **Domain Validation Tests** - If applicable
   - Test Pydantic validation rules
   - Test command objects

See `tests/CLAUDE.md` and `docs/how_to_implement_tasks.md` for detailed testing guidelines.

## Stub Entity Template

The **StubEntity** implementation serves as a template for creating real entities:
- Demonstrates complete CRUD implementation
- Shows all architectural layers working together
- Provides working examples for:
  - Domain models
  - ORM models
  - Repository pattern
  - API endpoints
  - Comprehensive tests

See `STUB_TEMPLATE_USAGE.md` for details on using the template.

## Key Architectural Decisions

### 1. Repository Pattern
**Why**: Separates data access from business logic, makes testing easier

### 2. Explicit Conversions
**Why**: Clear type safety, avoids hidden coupling between layers

### 3. Disk-Based Testing Default
**Why**: Tests reflect real-world database behavior (file I/O, persistence)

### 4. FastAPI Dependency Injection
**Why**: Clean testability, easy to override dependencies in tests

### 5. Pydantic for Domain Models
**Why**: Automatic validation, serialization, type safety

### 6. Command Objects
**Why**: Explicit intent for create/update, supports partial updates

## Extension Points

To add a new entity (e.g., "Task"):
1. Create domain models in `domain_models.py`
2. Create ORM model in `dal/sqlite/orm_data_models.py`
3. Create repository in `dal/sqlite/repository.py`
4. Create converters in `dal/sqlite/converters.py`
5. Create router in `routers/task_api.py`
6. Add dependency in `dependencies.py`
7. Include router in `app.py`
8. Create tests in `tests/api/` and `tests/dal/`

Use the StubEntity template as a reference for each layer.
