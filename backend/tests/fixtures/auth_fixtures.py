"""Authentication and user token fixtures for API tests.

This module provides centralized fixtures for creating users with various roles
and obtaining their authentication tokens via API endpoints.

Note: Only the super_admin_token fixture uses repository for bootstrap.
All other fixtures use API endpoints and role-specific helpers.
"""

import pytest
from fastapi.testclient import TestClient

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import UserCreateCommand, UserData, UserRole
from tests.conftest import client, test_repo  # noqa: F401
from tests.helpers import (
    create_admin_user,
    create_project_manager,
    create_read_user,
    create_test_org,
    create_write_user,
)


@pytest.fixture
def super_admin_token(test_repo: Repository, client: TestClient) -> str:
    """Create Super Admin user and return authentication token.

    Returns:
        JWT authentication token for Super Admin user
    """
    user_data = UserData(
        username="superadmin",
        email="superadmin@example.com",
        full_name="Super Admin",
    )
    password = "SuperAdminPass123"
    command = UserCreateCommand(
        user_data=user_data,
        password=password,
        organization_id=None,
        role=UserRole.SUPER_ADMIN,
    )
    test_repo.users.create(command)

    # Login to get token
    response = client.post("/auth/login", json={"username": "superadmin", "password": password})
    return response.json()["access_token"]


@pytest.fixture
def org_admin_token(super_admin_token: str, client: TestClient) -> tuple[str, str]:
    """Create organization and Org Admin user via API, return token and org_id.

    Returns:
        Tuple of (auth_token, organization_id)
    """
    # Create organization via API
    org_id = create_test_org(client, super_admin_token, "Test Organization", "Test org for admin")

    # Create admin user via API using role-specific helper
    user_id, password = create_admin_user(client, super_admin_token, org_id, username="orgadmin")

    # Login to get token
    response = client.post("/auth/login", json={"username": "orgadmin", "password": password})
    return response.json()["access_token"], org_id


@pytest.fixture
def project_manager_token(super_admin_token: str, client: TestClient) -> tuple[str, str]:
    """Create organization and Project Manager user via API, return token and org_id.

    Returns:
        Tuple of (auth_token, organization_id)
    """
    # Create organization via API
    org_id = create_test_org(client, super_admin_token, "PM Organization", "Org for project manager")

    # Create project manager user via API using role-specific helper
    user_id, password = create_project_manager(client, super_admin_token, org_id)

    # Login to get token
    response = client.post("/auth/login", json={"username": "projectmanager", "password": password})
    return response.json()["access_token"], org_id


@pytest.fixture
def write_user_token(super_admin_token: str, client: TestClient) -> tuple[str, str]:
    """Create organization and Write Access user via API, return token and org_id.

    Returns:
        Tuple of (auth_token, organization_id)
    """
    # Create organization via API
    org_id = create_test_org(client, super_admin_token, "Writer Organization", "Org for write user")

    # Create write access user via API using role-specific helper
    user_id, password = create_write_user(client, super_admin_token, org_id)

    # Login to get token
    response = client.post("/auth/login", json={"username": "writer", "password": password})
    return response.json()["access_token"], org_id


@pytest.fixture
def read_user_token(super_admin_token: str, client: TestClient) -> tuple[str, str]:
    """Create organization and Read Access user via API, return token and org_id.

    Returns:
        Tuple of (auth_token, organization_id)
    """
    # Create organization via API
    org_id = create_test_org(client, super_admin_token, "Reader Organization", "Org for read user")

    # Create read access user via API using role-specific helper
    user_id, password = create_read_user(client, super_admin_token, org_id)

    # Login to get token
    response = client.post("/auth/login", json={"username": "reader", "password": password})
    return response.json()["access_token"], org_id
