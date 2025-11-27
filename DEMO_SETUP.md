# Demo Setup Instructions

This guide explains how to run the application with rich demo data for manual testing and Playwright MCP exploration.

## Quick Start

### Option 1: Bootstrap on App Startup (Recommended)

Start the backend with the `BOOTSTRAP_DEMO_DATA` environment variable set:

```bash
# Terminal 1: Start backend with bootstrap flag
BOOTSTRAP_DEMO_DATA=true python -m uvicorn project_management_crud_example.app:app --reload --port 8000

# Terminal 2: Start frontend
cd frontend
npm run dev
```

Navigate to: http://localhost:3000

The backend will automatically create demo data on first startup.

### Option 2: Manual Bootstrap Script

If you prefer to bootstrap data manually before starting the server:

```bash
# Clear existing database (optional)
rm -f project_management_crud_example.db

# Run bootstrap script
python -m project_management_crud_example.bootstrap_rich_data

# Then start the servers normally:
# Terminal 1: Start backend
python -m uvicorn project_management_crud_example.app:app --reload --port 8000

# Terminal 2: Start frontend
cd frontend
npm run dev
```

### What Gets Created

Both methods create:
- 3 organizations (Acme Corporation, TechStart Inc, Global Systems)
- 12 users (4 per organization: PM, 2 developers, QA)
- 6 projects (2 per organization)
- Multiple epics per project (2-3 per project)
- Tickets with realistic data, assignments, and comments

## Login Credentials

**All regular users have password: `demo`**

### Super Admin
- **Username:** `admin`
- **Password:** `SuperAdmin123!`
- **Can:** Manage everything, create organizations, see all data

### Acme Corporation Users (password: `demo`)
- **acme-pm** - Project Manager (can create projects, epics, tickets)
- **acme-dev1** - Developer (can create/update tickets)
- **acme-dev2** - Developer (can create/update tickets)
- **acme-qa** - QA Engineer (can create/update tickets)

### TechStart Inc Users (password: `demo`)
- **tech-pm** - Project Manager
- **tech-dev1** - Developer
- **tech-dev2** - Developer
- **tech-qa** - QA Engineer

### Global Systems Users (password: `demo`)
- **global-pm** - Project Manager
- **global-dev1** - Developer
- **global-dev2** - Developer
- **global-qa** - QA Engineer

## For Playwright MCP

When using Playwright MCP to explore the application:

1. **Start the application** as described above
2. **Use these credentials** to login:
   - Try different user roles to see different permissions
   - All regular users: password is `demo`
   - Super admin: username `admin`, password `SuperAdmin123!`
3. **Sample scenarios to explore:**
   - Login as `acme-pm` and create a new project
   - Login as `tech-dev1` and view/update tickets
   - Login as `admin` and create a new organization
   - Navigate between projects, epics, and tickets
   - Test filters and sorting on tickets

## What's Included

The bootstrap data includes:

- ✅ **3 Organizations** with realistic names
- ✅ **12 Users** with various roles
- ✅ **6 Projects** with descriptions and statuses
- ✅ **Multiple Epics** per project (2-3 per project)
- ✅ **Multiple Tickets** per epic (3-5 per epic)
- ✅ **Realistic ticket data:**
  - Various priorities (LOW, MEDIUM, HIGH, CRITICAL)
  - Different statuses (TODO, IN_PROGRESS, DONE)
  - Assigned to different developers
  - Some have comments
- ✅ **Epic-ticket relationships** properly configured
- ✅ **Organization isolation** - users only see their org's data

## Resetting Data

To reset and regenerate demo data:

```bash
# Stop the backend server (Ctrl+C)

# Clear database
rm -f project_management_crud_example.db

# Option 1: Restart with bootstrap flag
BOOTSTRAP_DEMO_DATA=true python -m uvicorn project_management_crud_example.app:app --reload --port 8000

# Option 2: Run bootstrap script manually then start normally
python -m project_management_crud_example.bootstrap_rich_data
python -m uvicorn project_management_crud_example.app:app --reload --port 8000
```

## Troubleshooting

### Database already exists error
If you see "Organization with this name already exists", clear the database first:
```bash
rm -f stub_entities.db project_management_crud_example.db
```

### Login fails with "Invalid credentials"
- Check you're using the correct password (`demo` for regular users)
- For super admin, use `SuperAdmin123!`
- Try resetting the data

### Port already in use
- Backend port 8000: Kill existing uvicorn process
- Frontend port 3000: Kill existing vite dev server
- Or use different ports in the startup commands

## Production Warning

⚠️ **This bootstrap script is for DEMO/TESTING ONLY**

- Uses simple passwords ("demo") for all users
- Uses TestPasswordHasher for fast execution
- Creates data without proper security considerations
- **DO NOT use in production environments**
