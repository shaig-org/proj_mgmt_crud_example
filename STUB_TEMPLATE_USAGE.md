# Stub Entity Template Usage Guide

This scaffolding includes a complete **StubEntity** implementation that serves as a template for creating new real entities in your application.

## Why "Stub"?

Using "stub" naming makes it obvious this is template/scaffolding code:
- **Unmistakable**: Won't confuse with real features
- **Searchable**: Easy to find all template code with "stub" search
- **Clear intent**: Signals this needs to be adapted, not used as-is

## Template Files Overview

All template files use explicit "stub" naming:

### Domain Layer
- **`domain_models.py`**
  - `StubEntity` - Complete entity with ID and timestamps
  - `StubEntityData` - Base data (name, description)
  - `StubEntityCreateCommand` - Create command
  - `StubEntityUpdateCommand` - Update command

### Data Access Layer (DAL)
- **`dal/sqlite/orm_data_models.py`**
  - `StubEntityORM` - SQLAlchemy model
  - Table: `stub_entities`

- **`dal/sqlite/repository.py`**
  - `StubEntityRepository` - Repository class
  - Methods: `create_stub_entity()`, `get_stub_entity_by_id()`, `get_all_stub_entities()`, `delete_stub_entity()`

- **`dal/sqlite/converters.py`**
  - `orm_stub_entity_to_business_stub_entity()` - ORM → Domain
  - `orm_stub_entities_to_business_stub_entities()` - List converter

### API Layer
- **`routers/stub_entity_api.py`**
  - Router prefix: `/stub_entities`
  - Endpoints: POST, GET (all), GET (by ID), DELETE
  - Functions: `create_stub_entity()`, `get_stub_entity()`, `get_all_stub_entities()`, `delete_stub_entity()`

- **`dependencies.py`**
  - `get_stub_entity_repo()` - Dependency injection

### Test Layer
- **`tests/conftest.py`**
  - `test_stub_entity_repo` - Repository fixture

- **`tests/dal/test_stub_entity_repository.py`**
  - `TestStubEntityRepository` - Repository tests
  - 7 tests covering all CRUD operations

- **`tests/api/test_stub_entity_api.py`**
  - `TestStubEntityAPIEndpoints` - API endpoint tests
  - `TestStubEntityAPICRUDWorkflow` - Full workflow test
  - 9 tests total

## How to Use This Template

### Option 1: Create a New Entity (e.g., "Task")

1. **Copy or edit files** - Work in existing files or copy template files

2. **Search and replace** throughout the codebase:
   ```
   StubEntity          → Task
   StubEntityData      → TaskData
   stub_entity         → task
   stub_entities       → tasks (table name, URLs)
   stub-entities       → tasks (router tags)
   "Stub entity"       → "Task" (in docstrings)
   ```

3. **Customize the domain model** (`domain_models.py`):
   ```python
   class TaskData(BaseModel):
       """Base data structure for tasks."""
       title: str = Field(...)           # was 'name'
       description: Optional[str] = ...
       status: TaskStatus = ...          # new field
       due_date: Optional[datetime] = ... # new field
   ```

4. **Update ORM model** (`dal/sqlite/orm_data_models.py`):
   ```python
   class TaskORM(Base):
       __tablename__ = "tasks"
       id = Column(...)
       title = Column(String(255), ...)  # was 'name'
       description = Column(...)
       status = Column(...)               # new
       due_date = Column(DateTime, ...)  # new
       # ... timestamps
   ```

5. **Update repository methods** as needed for business logic

6. **Update API endpoints** with proper validation rules

7. **Update tests** to match new field names and behavior

8. **Run validations**: `cd backend && ./devtools/run_all_agent_validations.sh`

### Option 2: Keep Stub Template + Add New Entity

1. **Keep all stub files** as reference implementation
2. **Create new files** for your entity (e.g., `TaskRepository`, `task_api.py`)
3. **Reference stub files** when implementing similar patterns
4. **Stub entity remains working** - can test against it

## Search Patterns

Find all template code with these searches:

- **Classes**: `StubEntity` (13 occurrences across domain, ORM, converters, repository)
- **Functions**: `stub_entity` (method names, variables)
- **URLs**: `/stub_entities` (API endpoints)
- **Tables**: `stub_entities` (database table)
- **Files**: Files with "stub" in name

## Template Features

✅ **Complete CRUD** - Create, Read (all/by ID), Update, Delete
✅ **Full test coverage** - 18 passing tests (DAL + API)
✅ **Disk-based testing** - Uses `db_path` fixture (disk by default, `--db-mode=memory` optional)
✅ **Proper isolation** - Each test gets its own database
✅ **Type-safe** - Full type annotations throughout
✅ **Repository pattern** - Clean separation of concerns
✅ **FastAPI integration** - Dependency injection, validation, error handling

## Architecture Layers

```
┌─────────────────────────────────────┐
│  API Layer (FastAPI)                │
│  • stub_entity_api.py               │
│  • Endpoints at /stub_entities      │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│  Domain Layer                       │
│  • StubEntity, StubEntityData       │
│  • Commands (Create/Update)         │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│  Repository Layer                   │
│  • StubEntityRepository             │
│  • CRUD operations                  │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│  ORM Layer (SQLAlchemy)             │
│  • StubEntityORM                    │
│  • Table: stub_entities             │
└─────────────────────────────────────┘
```

## Best Practices

1. **Read spec first** - Get requirements from spec, not from stub template
2. **Adapt, don't just rename** - Template shows structure, your entity may need different fields/logic
3. **Update all layers** - Domain → ORM → Repository → API → Tests
4. **Run validations** - Must pass with zero errors/warnings
5. **Test behaviors** - Test observable behavior, not implementation details

## Example: Creating a "Project" Entity

```bash
# 1. In domain_models.py, add:
class ProjectData(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    # ... adapt from StubEntityData

# 2. In orm_data_models.py, add:
class ProjectORM(Base):
    __tablename__ = "projects"
    # ... adapt from StubEntityORM

# 3. In repository.py, add:
class ProjectRepository:
    # ... adapt from StubEntityRepository

# 4. Create routers/project_api.py
# ... adapt from stub_entity_api.py

# 5. Update app.py to include project router

# 6. Create tests
# ... adapt from test_stub_entity_*.py

# 7. Run validations
cd backend && ./devtools/run_all_agent_validations.sh
```

## Questions?

- **"Should I delete stub files after creating real entities?"**
  No! Keep them as working reference. They don't hurt anything.

- **"Can I use stub entity in production?"**
  Only if you actually need a generic "entity" feature. Usually you'll create specific entities like Task, Project, etc.

- **"What if my entity needs different fields?"**
  Perfect! The template shows the structure. Add/remove/modify fields as needed.

- **"Do I need to keep the same repository methods?"**
  No. Add methods your entity needs (search, filter, etc.). The template shows basic CRUD.

## Summary

The StubEntity template provides:
- ✅ Working implementation to reference
- ✅ All architectural layers properly connected
- ✅ Comprehensive tests showing how to test each layer
- ✅ Clear naming that won't confuse with real features
- ✅ Easy search-and-replace to create new entities

**Start by copying the stub pattern, then adapt to your specific needs!**
