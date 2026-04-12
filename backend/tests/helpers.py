"""Test helper functions for reducing repetition in API tests.

This module provides simple helper functions to create common test data
via API endpoints, reducing boilerplate in test files.

Note: These helpers are designed for API tests and use API endpoints.
Repository tests should create entities directly via repository.
"""

from fastapi.testclient import TestClient

from project_management_crud_example.domain_models import UserRole


def auth_headers(token: str) -> dict[str, str]:
    """Create authorization headers from token.

    Args:
        token: Authentication token

    Returns:
        Dictionary with Authorization header
    """
    return {"Authorization": f"Bearer {token}"}


def create_test_org(client: TestClient, token: str, name: str = "Test Org", description: str | None = None) -> str:
    """Create a test organization via API and return its ID.

    Args:
        client: FastAPI TestClient
        token: Authentication token (must be Super Admin)
        name: Organization name (default: "Test Org")
        description: Optional organization description (default: None)

    Returns:
        Organization ID
    """
    headers = auth_headers(token)
    org_data = {"name": name}
    if description is not None:
        org_data["description"] = description
    response = client.post("/api/organizations", json=org_data, headers=headers)
    return response.json()["id"]


def create_test_user(
    client: TestClient,
    token: str,
    org_id: str,
    username: str = "testuser",
    email: str | None = None,
    full_name: str | None = None,
    role: UserRole = UserRole.WRITE_ACCESS,
) -> tuple[str, str]:
    """Create a test user via API and return user ID and generated password.

    Args:
        client: FastAPI TestClient
        token: Authentication token (must have Admin permission)
        org_id: Organization ID for the user
        username: Username (default: "testuser")
        email: Email (default: {username}@example.com)
        full_name: Full name (default: capitalized username)
        role: User role (default: WRITE_ACCESS)

    Returns:
        Tuple of (user_id, generated_password)
    """
    email = email or f"{username}@example.com"
    full_name = full_name or username.replace("_", " ").title()

    headers = auth_headers(token)
    response = client.post(
        "/api/users",
        params={"organization_id": org_id, "role": role.value},
        json={"username": username, "email": email, "full_name": full_name},
        headers=headers,
    )
    data = response.json()
    return data["user"]["id"], data["generated_password"]


# Role-specific user creation helpers with expressive defaults


def create_admin_user(
    client: TestClient,
    token: str,
    org_id: str,
    username: str = "admin",
    email: str = "admin@example.com",
    full_name: str = "Admin User",
) -> tuple[str, str]:
    """Create an admin user via API with expressive defaults.

    Args:
        client: FastAPI TestClient
        token: Authentication token (must have Admin permission)
        org_id: Organization ID for the user
        username: Username (default: "admin")
        email: Email (default: "admin@example.com")
        full_name: Full name (default: "Admin User")

    Returns:
        Tuple of (user_id, generated_password)
    """
    return create_test_user(client, token, org_id, username, email, full_name, UserRole.ADMIN)


def create_project_manager(
    client: TestClient,
    token: str,
    org_id: str,
    username: str = "projectmanager",
    email: str = "pm@example.com",
    full_name: str = "Project Manager",
) -> tuple[str, str]:
    """Create a project manager user via API with expressive defaults.

    Args:
        client: FastAPI TestClient
        token: Authentication token (must have Admin permission)
        org_id: Organization ID for the user
        username: Username (default: "projectmanager")
        email: Email (default: "pm@example.com")
        full_name: Full name (default: "Project Manager")

    Returns:
        Tuple of (user_id, generated_password)
    """
    return create_test_user(client, token, org_id, username, email, full_name, UserRole.PROJECT_MANAGER)


def create_write_user(
    client: TestClient,
    token: str,
    org_id: str,
    username: str = "writer",
    email: str = "writer@example.com",
    full_name: str = "Write User",
) -> tuple[str, str]:
    """Create a write access user via API with expressive defaults.

    Args:
        client: FastAPI TestClient
        token: Authentication token (must have Admin permission)
        org_id: Organization ID for the user
        username: Username (default: "writer")
        email: Email (default: "writer@example.com")
        full_name: Full name (default: "Write User")

    Returns:
        Tuple of (user_id, generated_password)
    """
    return create_test_user(client, token, org_id, username, email, full_name, UserRole.WRITE_ACCESS)


def create_read_user(
    client: TestClient,
    token: str,
    org_id: str,
    username: str = "reader",
    email: str = "reader@example.com",
    full_name: str = "Read User",
) -> tuple[str, str]:
    """Create a read-only user via API with expressive defaults.

    Args:
        client: FastAPI TestClient
        token: Authentication token (must have Admin permission)
        org_id: Organization ID for the user
        username: Username (default: "reader")
        email: Email (default: "reader@example.com")
        full_name: Full name (default: "Read User")

    Returns:
        Tuple of (user_id, generated_password)
    """
    return create_test_user(client, token, org_id, username, email, full_name, UserRole.READ_ACCESS)


def create_test_project(
    client: TestClient, token: str, name: str = "Test Project", description: str | None = None
) -> str:
    """Create a project via API and return its ID.

    Args:
        client: FastAPI TestClient
        token: Authentication token
        name: Project name (default: "Test Project")
        description: Optional project description (default: None)

    Returns:
        Project ID
    """
    headers = auth_headers(token)
    project_data = {"name": name}
    if description is not None:
        project_data["description"] = description
    response = client.post("/api/projects", json=project_data, headers=headers)
    return response.json()["id"]


def create_test_epic(client: TestClient, token: str, name: str = "Test Epic", description: str | None = None) -> str:
    """Create an epic via API and return its ID.

    Args:
        client: FastAPI TestClient
        token: Authentication token
        name: Epic name (default: "Test Epic")
        description: Optional epic description (default: None)

    Returns:
        Epic ID
    """
    headers = auth_headers(token)
    epic_data = {"name": name}
    if description is not None:
        epic_data["description"] = description
    response = client.post("/api/epics", json=epic_data, headers=headers)
    return response.json()["id"]


def create_test_ticket(
    client: TestClient,
    token: str,
    project_id: str,
    reporter_id: str,
    title: str = "Test Ticket",
    description: str = "Test ticket description",
    priority: str = "MEDIUM",
) -> str:
    """Create a ticket via API and return its ID.

    Args:
        client: FastAPI TestClient
        token: Authentication token
        project_id: Project ID for the ticket
        reporter_id: User ID of the ticket reporter
        title: Ticket title (default: "Test Ticket")
        description: Ticket description (default: "Test ticket description")
        priority: Ticket priority (default: "MEDIUM")

    Returns:
        Ticket ID
    """
    headers = auth_headers(token)
    ticket_data = {"title": title, "description": description, "priority": priority}
    response = client.post(f"/api/tickets?project_id={project_id}", json=ticket_data, headers=headers)
    return response.json()["id"]
