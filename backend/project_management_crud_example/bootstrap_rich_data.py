"""Bootstrap script for creating rich test data using FastAPI TestClient.

This script creates a comprehensive dataset for manual testing and Playwright MCP exploration:
- Multiple organizations
- Multiple users with different roles
- Projects with various statuses
- Epics with tickets in different states
- Comments on tickets

Uses FastAPI TestClient for reliable API-based data creation.
"""

import random
import sys
from typing import Any

from fastapi.testclient import TestClient

from project_management_crud_example.app import app
from project_management_crud_example.bootstrap_data import SUPER_ADMIN_PASSWORD
from project_management_crud_example.dal.sqlite.database import Database


def auth_headers(token: str) -> dict[str, str]:
    """Create authorization headers with bearer token."""
    return {"Authorization": f"Bearer {token}"}


def login_as_admin(client: TestClient) -> str:
    """Login as Super Admin and return access token."""
    from project_management_crud_example.config import get_settings

    settings = get_settings()

    response = client.post(
        "/auth/login",
        json={"username": settings.BOOTSTRAP_ADMIN_USERNAME, "password": SUPER_ADMIN_PASSWORD},
    )
    if response.status_code != 200:
        raise RuntimeError(f"Failed to login as admin: {response.text}")

    return response.json()["access_token"]


def create_organization(
    client: TestClient, admin_token: str, name: str, description: str | None = None
) -> dict[str, Any]:
    """Create an organization and return the response."""
    response = client.post(
        "/api/organizations",
        json={"name": name, "description": description},
        headers=auth_headers(admin_token),
    )
    if response.status_code != 201:
        raise RuntimeError(f"Failed to create organization {name}: {response.text}")

    return response.json()


def create_user_with_password(
    db: "Database",  # type: ignore
    org_id: str,
    username: str,
    email: str,
    full_name: str,
    role: str,
    password: str = "demo",
) -> dict[str, Any]:
    """Create a user with specific password via repository."""
    from project_management_crud_example.dal.sqlite.repository import Repository
    from project_management_crud_example.domain_models import UserCreateCommand, UserData, UserRole
    from project_management_crud_example.utils.password import PasswordHasher

    # Convert string role to UserRole enum
    role_map = {
        "project_manager": UserRole.PROJECT_MANAGER,
        "write_access": UserRole.WRITE_ACCESS,
        "read_access": UserRole.READ_ACCESS,
        "admin": UserRole.ADMIN,
    }
    user_role = role_map.get(role, UserRole.READ_ACCESS)

    with db.get_session() as session:
        repo = Repository(session, password_hasher=PasswordHasher())

        user_data = UserData(username=username, email=email, full_name=full_name)

        command = UserCreateCommand(
            user_data=user_data,
            password=password,
            organization_id=org_id,
            role=user_role,
        )

        user = repo.users.create(command)

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "organization_id": user.organization_id,
        }


def login_as_user(client: TestClient, username: str, password: str) -> str:
    """Login as user and return access token."""
    response = client.post("/auth/login", json={"username": username, "password": password})
    if response.status_code != 200:
        raise RuntimeError(f"Failed to login as {username}: {response.text}")

    return response.json()["access_token"]


def create_project(
    client: TestClient,
    user_token: str,
    name: str,
    description: str | None = None,
    status: str = "ACTIVE",
) -> dict[str, Any]:
    """Create a project and return the response."""
    response = client.post(
        "/api/projects",
        json={"name": name, "description": description, "status": status},
        headers=auth_headers(user_token),
    )
    if response.status_code != 201:
        raise RuntimeError(f"Failed to create project {name}: {response.text}")

    return response.json()


def create_epic(client: TestClient, user_token: str, name: str, description: str | None = None) -> dict[str, Any]:
    """Create an epic and return the response."""
    response = client.post(
        "/api/epics",
        json={"name": name, "description": description},
        headers=auth_headers(user_token),
    )
    if response.status_code != 201:
        raise RuntimeError(f"Failed to create epic {name}: {response.text}")

    return response.json()


def create_ticket(
    client: TestClient,
    user_token: str,
    project_id: str,
    title: str,
    description: str | None = None,
    priority: str | None = None,
    assignee_id: str | None = None,
    status: str = "TODO",
) -> dict[str, Any]:
    """Create a ticket and return the response."""
    ticket_data: dict[str, Any] = {
        "title": title,
        "description": description,
        "priority": priority,
        "status": status,
    }

    # Build URL with query parameters
    url = f"/api/tickets?project_id={project_id}"
    if assignee_id:
        url += f"&assignee_id={assignee_id}"

    response = client.post(url, json=ticket_data, headers=auth_headers(user_token))

    if response.status_code != 201:
        raise RuntimeError(f"Failed to create ticket {title}: {response.text}")

    return response.json()


def update_ticket_status(client: TestClient, user_token: str, ticket_id: str, status: str) -> None:
    """Update ticket status."""
    response = client.patch(
        f"/api/tickets/{ticket_id}",
        json={"status": status},
        headers=auth_headers(user_token),
    )
    if response.status_code != 200:
        raise RuntimeError(f"Failed to update ticket status: {response.text}")


def assign_ticket_to_epic(client: TestClient, user_token: str, ticket_id: str, epic_id: str) -> None:
    """Assign a ticket to an epic."""
    response = client.post(
        f"/api/epics/{epic_id}/tickets",
        params={"ticket_id": ticket_id},
        headers=auth_headers(user_token),
    )
    if response.status_code not in [200, 201]:
        raise RuntimeError(f"Failed to assign ticket to epic: {response.text}")


def add_comment(client: TestClient, user_token: str, ticket_id: str, content: str) -> dict[str, Any]:
    """Add a comment to a ticket."""
    response = client.post(
        f"/api/tickets/{ticket_id}/comments",
        json={"content": content},
        headers=auth_headers(user_token),
    )
    if response.status_code != 201:
        raise RuntimeError(f"Failed to add comment: {response.text}")

    return response.json()


def bootstrap_rich_data() -> None:
    """Create rich test data using FastAPI TestClient."""
    from typing import Generator

    from fastapi import Depends
    from sqlalchemy.orm import Session

    from project_management_crud_example.dal.sqlite.repository import Repository
    from project_management_crud_example.dependencies import get_db_session, get_repository
    from project_management_crud_example.utils.password import PasswordHasher

    print("🚀 Bootstrapping rich demo data using FastAPI TestClient...")
    print()

    # Initialize database with production password hashing
    db = Database("project_management_crud_example.db", is_testing=False)
    db.create_tables()

    # Bootstrap Super Admin (must happen before TestClient is used)
    from project_management_crud_example.bootstrap_data import ensure_super_admin

    created, user_id = ensure_super_admin(db)

    if created:
        print("✓ Super Admin created successfully!")
    else:
        print("✓ Super Admin already exists")

    print()

    # Override app dependencies to use our database with production password hashing
    def override_get_db_session() -> Generator[Session, None, None]:
        with db.get_session() as session:
            yield session

    def override_get_repository(session: Session = Depends(override_get_db_session)) -> Repository:  # noqa: B008
        return Repository(session, password_hasher=PasswordHasher())

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_repository] = override_get_repository

    # Create TestClient with overridden dependencies
    client = TestClient(app)

    # Login as admin
    print("→ Logging in as Super Admin...")
    admin_token = login_as_admin(client)
    print("✓ Logged in as Super Admin")
    print()

    # Create organizations
    print("→ Creating organizations...")
    orgs = [
        create_organization(client, admin_token, "Acme Corporation", "Enterprise software solutions"),
        create_organization(client, admin_token, "TechStart Inc", "Innovative tech startup"),
        create_organization(client, admin_token, "Global Systems", "Worldwide IT services"),
    ]
    print(f"✓ Created {len(orgs)} organizations")
    print()

    # Create users and projects for each organization
    for i, org in enumerate(orgs, 1):
        org_name = org["name"]
        org_id = org["id"]

        print(f"→ Setting up {org_name}...")

        # Simple usernames based on organization
        org_prefix = ["acme", "tech", "global"][i - 1]

        # Create users for this org - all with password "demo"
        pm_user = create_user_with_password(
            db,
            org_id,
            f"{org_prefix}-pm",
            f"pm@{org_prefix}.com",
            f"{org_name} Project Manager",
            "project_manager",
            password="demo",
        )

        dev1_user = create_user_with_password(
            db,
            org_id,
            f"{org_prefix}-dev1",
            f"dev1@{org_prefix}.com",
            f"{org_name} Developer 1",
            "write_access",
            password="demo",
        )

        dev2_user = create_user_with_password(
            db,
            org_id,
            f"{org_prefix}-dev2",
            f"dev2@{org_prefix}.com",
            f"{org_name} Developer 2",
            "write_access",
            password="demo",
        )

        qa_user = create_user_with_password(
            db,
            org_id,
            f"{org_prefix}-qa",
            f"qa@{org_prefix}.com",
            f"{org_name} QA Engineer",
            "write_access",
            password="demo",
        )

        # Login as PM to create projects
        pm_token = login_as_user(client, pm_user["username"], "demo")

        # Create projects
        projects = []
        for j in range(2):  # 2 projects per org
            project = create_project(
                client,
                pm_token,
                f"{org_name} - Project {j + 1}",
                f"Strategic initiative {j + 1} for {org_name}",
                status="ACTIVE" if j == 0 else random.choice(["ACTIVE", "ON_HOLD"]),
            )
            projects.append(project)

        # Create epics and tickets
        for project in projects:
            project_id = project["id"]

            # Create 2-3 epics per project
            num_epics = random.randint(2, 3)
            for k in range(num_epics):
                epic = create_epic(
                    client,
                    pm_token,
                    f"Epic {k + 1}: {project['name']}",
                    f"Major feature area {k + 1} for this project",
                )

                # Create 3-5 tickets per epic
                num_tickets = random.randint(3, 5)
                for t in range(num_tickets):
                    assignee = random.choice([dev1_user["id"], dev2_user["id"], qa_user["id"], None])
                    priority = random.choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"])
                    status = random.choice(
                        ["TODO", "TODO", "IN_PROGRESS", "IN_PROGRESS", "DONE"]
                    )  # Bias towards TODO/IN_PROGRESS

                    ticket = create_ticket(
                        client,
                        pm_token,
                        project_id,
                        f"Ticket {t + 1} for {epic['name'][:30]}",
                        f"Implementation task {t + 1}",
                        priority=priority,
                        assignee_id=assignee,
                        status=status,  # Set status directly during creation
                    )

                    # Assign ticket to epic
                    assign_ticket_to_epic(client, pm_token, ticket["id"], epic["id"])

                    # Add some comments
                    if random.random() > 0.5:  # 50% chance of comments
                        num_comments = random.randint(1, 3)
                        for c in range(num_comments):
                            comment_user_token = random.choice(
                                [pm_token, login_as_user(client, dev1_user["username"], "demo")]
                            )
                            add_comment(
                                client,
                                comment_user_token,
                                ticket["id"],
                                f"Comment {c + 1}: Progress update on this ticket",
                            )

        print(f"  ✓ Created {len(projects)} projects with epics and tickets for {org_name}")

    print()
    print("=" * 80)
    print("✅ RICH DATA BOOTSTRAP COMPLETE!")
    print("=" * 80)
    print()
    print("🔐 LOGIN CREDENTIALS (all users have password: demo)")
    print("=" * 80)
    print()
    print("Super Admin (can manage everything):")
    print("  Username: admin")
    print(f"  Password: {SUPER_ADMIN_PASSWORD}")
    print()
    print("─" * 80)
    print()
    print("ACME CORPORATION Users (password: demo for all):")
    print("  acme-pm      - Project Manager (can create projects, epics, tickets)")
    print("  acme-dev1    - Developer (can create/update tickets)")
    print("  acme-dev2    - Developer (can create/update tickets)")
    print("  acme-qa      - QA Engineer (can create/update tickets)")
    print()
    print("TECHSTART INC Users (password: demo for all):")
    print("  tech-pm      - Project Manager")
    print("  tech-dev1    - Developer")
    print("  tech-dev2    - Developer")
    print("  tech-qa      - QA Engineer")
    print()
    print("GLOBAL SYSTEMS Users (password: demo for all):")
    print("  global-pm    - Project Manager")
    print("  global-dev1  - Developer")
    print("  global-dev2  - Developer")
    print("  global-qa    - QA Engineer")
    print()
    print("=" * 80)
    print()
    print("📊 DATA SUMMARY:")
    print(f"  • {len(orgs)} Organizations")
    print(f"  • {len(orgs) * 4} Users (4 per organization)")
    print(f"  • {len(orgs) * 2} Projects (2 per organization)")
    print("  • Multiple Epics per project with tickets")
    print("  • Tickets with various statuses, priorities, and assignments")
    print("  • Some tickets have comments")
    print()
    print("=" * 80)
    print()
    print("🎉 Ready for manual testing and Playwright MCP exploration!")
    print()
    print("Quick Start:")
    print(
        "  1. Start backend: cd backend && python -m uvicorn project_management_crud_example.app:app --reload --port 8000"
    )
    print("  2. Start frontend: cd frontend && npm run dev")
    print("  3. Navigate to http://localhost:3000")
    print("  4. Login with any user above (all passwords are 'demo')")
    print("  5. Explore projects, epics, and tickets")
    print()

    # Reset dependency overrides and dispose database
    app.dependency_overrides = {}
    db.dispose()


def main() -> None:
    """CLI entry point for rich data bootstrapping."""
    bootstrap_rich_data()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Bootstrap cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Bootstrap failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
