# Project Management CRUD Example

A FastAPI-based backend service demonstrating a complete CRUD application with authentication, multi-tenancy, and project management capabilities. Built with Python, SQLite, and modern development practices.

## Features

- **JWT Authentication**: Secure token-based authentication system
- **Multi-tenancy**: Organization-based data isolation
- **Role-Based Access Control**: Five-tier permission system (Super Admin, Admin, Project Manager, Write Access, Read Access)
- **Auto-Bootstrap**: Automatic Super Admin creation for easy setup
- **RESTful API**: Clean, well-documented endpoints
- **Comprehensive Testing**: Full test coverage with API, repository, and domain tests

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd project_management_crud_example
```

2. Install dependencies:
```bash
uv sync
```

3. Set up environment variables:
```bash
# Create .env file
cat > .env <<EOF
JWT_SECRET_KEY=your-secret-key-here-change-in-production
EOF
```

### Running the Application

**Basic Development Server**:
```bash
uv run uvicorn project_management_crud_example.app:app --reload
```

**With Rich Demo Data** (for manual testing and exploration):
```bash
BOOTSTRAP_DEMO_DATA=true uv run uvicorn project_management_crud_example.app:app --reload
```

The API will be available at `http://localhost:8000`

**Interactive API Documentation**:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

> 💡 **Tip**: See [DEMO_SETUP.md](./DEMO_SETUP.md) for comprehensive instructions on running with demo data for manual testing and Playwright MCP exploration.

## Bootstrap & Initial Setup

### Automatic Bootstrap

The application **automatically creates a Super Admin user** on first startup if none exists. This makes it easy to get started immediately.

**Default Super Admin Credentials**:
- **Username**: `admin`
- **Email**: `admin@example.com`
- **Password**: `SuperAdmin123!`
- **Role**: Super Admin (no organization restriction)

⚠️ **Security Note**: The constant password is for **EXAMPLE/DEVELOPMENT purposes only**. In production:
- Never use constant passwords
- Never auto-bootstrap on startup
- Use proper secrets management and secure initialization

### Manual Bootstrap

You can also manually bootstrap the system using the CLI script:

```bash
uv run python -m project_management_crud_example.bootstrap
```

This will:
- Create database tables if they don't exist
- Create Super Admin if none exists
- Display the Super Admin credentials

### Rich Demo Data Bootstrap

For **manual testing, Playwright MCP exploration, or demonstrations**, you can bootstrap the application with rich demo data including multiple organizations, users, projects, epics, and tickets.

**Option 1: Auto-bootstrap on app startup (Recommended)**:
```bash
BOOTSTRAP_DEMO_DATA=true uv run uvicorn project_management_crud_example.app:app --reload --port 8000
```

**Option 2: Run bootstrap script manually**:
```bash
# Clear existing database (optional)
rm -f project_management_crud_example.db

# Run bootstrap script
uv run python -m project_management_crud_example.bootstrap_rich_data

# Then start the server normally
uv run uvicorn project_management_crud_example.app:app --reload --port 8000
```

**Demo Data Includes**:
- 3 Organizations (Acme Corporation, TechStart Inc, Global Systems)
- 12 Users (4 per organization: PM, 2 developers, QA) - all with password `demo`
- 6 Projects (2 per organization)
- Multiple Epics per project
- Tickets with realistic data, assignments, and comments

**Demo User Credentials** (all passwords are `demo`):
- `acme-pm`, `acme-dev1`, `acme-dev2`, `acme-qa`
- `tech-pm`, `tech-dev1`, `tech-dev2`, `tech-qa`
- `global-pm`, `global-dev1`, `global-dev2`, `global-qa`

See [DEMO_SETUP.md](./DEMO_SETUP.md) for detailed setup instructions and login credentials.

### Customizing Bootstrap Configuration

You can customize the Super Admin credentials via environment variables:

```bash
# Add to your .env file
BOOTSTRAP_ADMIN_USERNAME=customadmin
BOOTSTRAP_ADMIN_EMAIL=admin@mycompany.com
BOOTSTRAP_ADMIN_FULL_NAME=System Administrator
```

### Bootstrap Behavior

- **Idempotent**: Running bootstrap multiple times is safe - it will skip creation if a Super Admin already exists
- **Any Super Admin**: If *any* user with Super Admin role exists, bootstrap will skip creation
- **Development Focus**: Bootstrap is designed for development and testing convenience
- **Password is Constant**: The password `SuperAdmin123!` is hardcoded in `bootstrap_data.py` for example app simplicity

## Authentication & API Usage

### Login

Get an access token:

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "SuperAdmin123!"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "username": "admin",
  "role": "super_admin",
  "organization_id": null
}
```

### Using the Token

Include the token in the `Authorization` header for protected endpoints:

```bash
curl http://localhost:8000/api/stub_entities \
  -H "Authorization: Bearer eyJhbGc..."
```

## Development

### Running Tests

Run all tests:
```bash
uv run pytest
```

Run with coverage:
```bash
uv run pytest --cov=project_management_crud_example --cov-report=html
```

Run specific test file:
```bash
uv run pytest tests/api/test_auth_api.py
```

### Validation

Run all validations (lint, format, type check, tests):
```bash
./devtools/run_all_agent_validations.sh
```

### Database

The application uses SQLite by default with the database file `project_management_crud_example.db` in the project root.

To reset the database:
```bash
rm project_management_crud_example.db
# Restart the app - it will recreate tables and bootstrap Super Admin
```

## User Roles

The application implements five permission levels:

1. **Super Admin**: System-wide access, no organization restriction, can manage organizations
2. **Admin**: Full access within their organization
3. **Project Manager**: Manage projects within their organization
4. **Write Access**: Create and modify entities within their organization
5. **Read Access**: View entities within their organization

## Architecture

- **Framework**: FastAPI
- **Database**: SQLite (via SQLAlchemy ORM)
- **Authentication**: JWT tokens
- **Validation**: Pydantic models
- **Testing**: PyTest with comprehensive coverage

**Key Architectural Patterns**:
- Repository pattern for data access
- Domain-driven design with strict layer separation
- No ORM model leakage outside DAL
- Command pattern for data mutations

## Project Structure

```
project_management_crud_example/
├── project_management_crud_example/
│   ├── app.py                  # FastAPI application
│   ├── domain_models.py        # Domain models and commands
│   ├── bootstrap_data.py       # Bootstrap utilities
│   ├── bootstrap.py            # Bootstrap CLI script
│   ├── config.py              # Configuration and settings
│   ├── dependencies.py        # Dependency injection
│   ├── exceptions.py          # Custom exceptions
│   ├── dal/                   # Data Access Layer
│   │   └── sqlite/
│   │       ├── database.py
│   │       ├── orm_data_models.py
│   │       ├── repository.py
│   │       └── converters.py
│   ├── routers/              # API endpoints
│   │   ├── auth_api.py
│   │   ├── health.py
│   │   └── stub_entity_api.py
│   └── utils/                # Utilities
│       ├── jwt_handler.py
│       └── password.py
├── tests/                    # Comprehensive test suite
├── docs/                     # Specifications and documentation
└── devtools/                # Development tools
```

## API Endpoints

### Health Check
- `GET /health` - Health check endpoint

### Authentication
- `POST /api/auth/login` - User login
- `GET /api/auth/validate` - Validate token

### Stub Entities (Example CRUD)
- `POST /api/stub_entities` - Create stub entity
- `GET /api/stub_entities` - List all stub entities
- `GET /api/stub_entities/{id}` - Get stub entity by ID
- `DELETE /api/stub_entities/{id}` - Delete stub entity

See the interactive API documentation at `/docs` for complete details.

## License

This is an example application for educational purposes.
