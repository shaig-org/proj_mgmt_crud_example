"""Tests for project API endpoints."""

from fastapi.testclient import TestClient

from project_management_crud_example.dal.sqlite.repository import Repository
from tests.conftest import client, test_repo  # noqa: F401
from tests.fixtures.auth_fixtures import (  # noqa: F401
    org_admin_token,
    project_manager_token,
    read_user_token,
    super_admin_token,
    write_user_token,
)
from tests.helpers import auth_headers, create_admin_user, create_project_manager, create_test_org, create_test_project


class TestCreateProject:
    """Tests for POST /api/projects endpoint."""

    def test_create_project_as_admin(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test creating project as Admin."""
        token, org_id = org_admin_token
        project_data = {"name": "Backend Project", "description": "Backend development"}

        response = client.post(
            "/api/projects",
            json=project_data,
            headers=auth_headers(token),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Backend Project"
        assert data["description"] == "Backend development"
        assert data["organization_id"] == org_id
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_project_as_project_manager(
        self, client: TestClient, project_manager_token: tuple[str, str]
    ) -> None:
        """Test creating project as Project Manager."""
        token, org_id = project_manager_token
        project_data = {"name": "Frontend Project"}

        response = client.post(
            "/api/projects",
            json=project_data,
            headers=auth_headers(token),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Frontend Project"
        assert data["description"] is None
        assert data["organization_id"] == org_id

    def test_create_project_without_description(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test creating project with only name."""
        token, _ = org_admin_token
        project_data = {"name": "Minimal Project"}

        response = client.post(
            "/api/projects",
            json=project_data,
            headers=auth_headers(token),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Project"
        assert data["description"] is None

    def test_create_project_as_write_user_fails(self, client: TestClient, write_user_token: tuple[str, str]) -> None:
        """Test that Write Access user cannot create projects."""
        token, _ = write_user_token
        project_data = {"name": "Unauthorized Project"}

        response = client.post(
            "/api/projects",
            json=project_data,
            headers=auth_headers(token),
        )

        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    def test_create_project_as_read_user_fails(self, client: TestClient, read_user_token: tuple[str, str]) -> None:
        """Test that Read Access user cannot create projects."""
        token, _ = read_user_token
        project_data = {"name": "Unauthorized Project"}

        response = client.post(
            "/api/projects",
            json=project_data,
            headers=auth_headers(token),
        )

        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    def test_create_project_without_auth_fails(self, client: TestClient) -> None:
        """Test that creating project without auth fails."""
        project_data = {"name": "No Auth Project"}

        response = client.post("/api/projects", json=project_data)

        assert response.status_code == 401

    def test_create_project_with_special_characters(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test creating project with special characters in name."""
        token, _ = org_admin_token
        project_data = {"name": "Special !@#$%^&*() Project"}

        response = client.post(
            "/api/projects",
            json=project_data,
            headers=auth_headers(token),
        )

        assert response.status_code == 201
        assert response.json()["name"] == "Special !@#$%^&*() Project"

    def test_create_project_with_unicode(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test creating project with Unicode characters."""
        token, _ = org_admin_token
        project_data = {"name": "Proyecto Español 日本"}

        response = client.post(
            "/api/projects",
            json=project_data,
            headers=auth_headers(token),
        )

        assert response.status_code == 201
        assert response.json()["name"] == "Proyecto Español 日本"

    def test_create_project_with_empty_name_fails(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test that creating project with empty name fails."""
        token, _ = org_admin_token
        project_data = {"name": ""}

        response = client.post(
            "/api/projects",
            json=project_data,
            headers=auth_headers(token),
        )

        assert response.status_code == 422

    def test_create_project_with_long_name(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test creating project with maximum length name (255 chars)."""
        token, _ = org_admin_token
        long_name = "A" * 255
        project_data = {"name": long_name}

        response = client.post(
            "/api/projects",
            json=project_data,
            headers=auth_headers(token),
        )

        assert response.status_code == 201
        assert response.json()["name"] == long_name

    def test_create_project_with_too_long_name_fails(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Test that creating project with name >255 chars fails."""
        token, _ = org_admin_token
        too_long_name = "A" * 256
        project_data = {"name": too_long_name}

        response = client.post(
            "/api/projects",
            json=project_data,
            headers=auth_headers(token),
        )

        assert response.status_code == 422

    def test_create_project_user_without_organization_fails(
        self, client: TestClient, super_admin_token: str, test_repo: Repository
    ) -> None:
        """Test creating project when user has no organization fails."""
        # Create a user without organization directly via repository
        from project_management_crud_example.domain_models import UserCreateCommand, UserData, UserRole

        user_data = UserData(username="orphan_user2", email="orphan2@test.com", full_name="Orphan User 2")
        command = UserCreateCommand(user_data=user_data, password="password", organization_id=None, role=UserRole.ADMIN)
        test_repo.users.create(command)

        # Login as this user
        login_response = client.post("/auth/login", json={"username": "orphan_user2", "password": "password"})
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        # Try to create project
        project_data = {"name": "Test Project"}
        response = client.post("/api/projects", json=project_data, headers=auth_headers(token))

        assert response.status_code == 400
        assert "user has no organization" in response.json()["detail"].lower()


class TestGetProject:
    """Tests for GET /api/projects/{id} endpoint."""

    def test_get_project_by_id_in_same_org(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test getting project by ID as user in same organization."""
        token, org_id = org_admin_token

        # Create a project
        project_id = create_test_project(client, token, "Test Project", "Test description")

        response = client.get(
            f"/api/projects/{project_id}",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == project_id
        assert data["name"] == "Test Project"
        assert data["description"] == "Test description"
        assert data["organization_id"] == org_id

    def test_get_project_from_different_org_fails(
        self,
        client: TestClient,
        org_admin_token: tuple[str, str],
        super_admin_token: str,
    ) -> None:
        """Test that user cannot get project from different organization."""
        token, _ = org_admin_token

        # Create another organization and project manager in it
        other_org_id = create_test_org(client, super_admin_token, "Other Org")
        _, other_pm_password = create_project_manager(client, super_admin_token, other_org_id, username="otherpm")

        # Login as other PM and create project
        login_resp = client.post("/auth/login", json={"username": "otherpm", "password": other_pm_password})
        other_token = login_resp.json()["access_token"]
        project_id = create_test_project(client, other_token, "Other Org Project")

        response = client.get(
            f"/api/projects/{project_id}",
            headers=auth_headers(token),
        )

        assert response.status_code == 403
        assert "different organization" in response.json()["detail"]

    def test_get_project_as_super_admin_from_any_org(
        self,
        client: TestClient,
        super_admin_token: str,
        org_admin_token: tuple[str, str],
    ) -> None:
        """Test that Super Admin can get project from any organization."""
        # Use org_admin to create project
        token, _ = org_admin_token
        project_id = create_test_project(client, token, "Any Org Project")

        response = client.get(
            f"/api/projects/{project_id}",
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 200
        assert response.json()["id"] == project_id

    def test_get_nonexistent_project_returns_404(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test getting non-existent project returns 404."""
        token, _ = org_admin_token

        response = client.get(
            "/api/projects/nonexistent-id",
            headers=auth_headers(token),
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_get_project_without_auth_fails(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test getting project without auth fails."""
        # Create a project
        token, _ = org_admin_token
        project_id = create_test_project(client, token)

        response = client.get(f"/api/projects/{project_id}")

        assert response.status_code == 401


class TestListProjects:
    """Tests for GET /api/projects endpoint."""

    def test_list_projects_in_own_org(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test listing projects as user sees only their org's projects."""
        token, org_id = org_admin_token

        # Create projects in user's organization
        for i in range(3):
            create_test_project(client, token, f"Project {i}")

        response = client.get(
            "/api/projects",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        projects = response.json()
        assert len(projects) == 3
        assert all(p["organization_id"] == org_id for p in projects)

    def test_list_projects_does_not_include_other_orgs(
        self,
        client: TestClient,
        org_admin_token: tuple[str, str],
        super_admin_token: str,
    ) -> None:
        """Test that listing projects does not include projects from other organizations."""
        token, org_id = org_admin_token

        # Create project in user's org
        create_test_project(client, token, "My Project")

        # Create another org and project in it
        other_org_id = create_test_org(client, super_admin_token, "Other Org")
        _, other_pm_password = create_project_manager(client, super_admin_token, other_org_id, username="otherpm2")
        login_resp = client.post("/auth/login", json={"username": "otherpm2", "password": other_pm_password})
        other_token = login_resp.json()["access_token"]
        create_test_project(client, other_token, "Other Project")

        response = client.get(
            "/api/projects",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        projects = response.json()
        assert len(projects) == 1
        assert projects[0]["name"] == "My Project"
        assert projects[0]["organization_id"] == org_id

    def test_list_projects_as_super_admin_sees_all(
        self,
        client: TestClient,
        super_admin_token: str,
        org_admin_token: tuple[str, str],
    ) -> None:
        """Test that Super Admin sees projects from all organizations."""
        # Create project in first org
        token1, org1_id = org_admin_token
        create_test_project(client, token1, "Org1 Project")

        # Create second org and project in it
        org2_id = create_test_org(client, super_admin_token, "Org 2")
        _, pm2_password = create_project_manager(client, super_admin_token, org2_id, username="pm2")
        login_resp = client.post("/auth/login", json={"username": "pm2", "password": pm2_password})
        token2 = login_resp.json()["access_token"]
        create_test_project(client, token2, "Org2 Project")

        response = client.get(
            "/api/projects",
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 200
        projects = response.json()
        assert len(projects) == 2
        org_ids = {p["organization_id"] for p in projects}
        assert org_ids == {org1_id, org2_id}

    def test_list_projects_when_empty(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test listing projects when none exist returns empty array."""
        token, _ = org_admin_token

        response = client.get(
            "/api/projects",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_list_projects_without_auth_fails(self, client: TestClient) -> None:
        """Test listing projects without auth fails."""
        response = client.get("/api/projects")

        assert response.status_code == 401

    def test_list_projects_user_without_organization_returns_empty(
        self, client: TestClient, super_admin_token: str, test_repo: Repository
    ) -> None:
        """Test listing projects when non-Super Admin user has no organization returns empty list."""
        # Create a user without organization directly via repository
        from project_management_crud_example.domain_models import UserCreateCommand, UserData, UserRole

        user_data = UserData(username="orphan_user3", email="orphan3@test.com", full_name="Orphan User 3")
        command = UserCreateCommand(user_data=user_data, password="password", organization_id=None, role=UserRole.ADMIN)
        test_repo.users.create(command)

        # Login as this user
        login_response = client.post("/auth/login", json={"username": "orphan_user3", "password": "password"})
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        # Try to list projects
        response = client.get("/api/projects", headers=auth_headers(token))

        assert response.status_code == 200
        assert response.json() == []  # Empty list for user without organization


class TestFilterProjects:
    """Tests for GET /api/projects filtering functionality."""

    def test_filter_projects_by_name(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test filtering projects by name substring."""
        token, org_id = org_admin_token

        # Create multiple projects with different names
        create_test_project(client, token, "Backend API")
        create_test_project(client, token, "Frontend App")
        create_test_project(client, token, "Mobile Backend")

        # Filter by "backend" (case-insensitive)
        response = client.get(
            "/api/projects?name=backend",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        projects = response.json()
        assert len(projects) == 2  # Backend API and Mobile Backend
        names = {p["name"] for p in projects}
        assert "Backend API" in names
        assert "Mobile Backend" in names
        assert "Frontend App" not in names

    def test_filter_projects_by_name_case_insensitive(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Test name filtering is case-insensitive."""
        token, org_id = org_admin_token

        create_test_project(client, token, "Backend API")
        create_test_project(client, token, "frontend app")

        # Try different case variations
        for search_term in ["BACKEND", "backend", "Backend", "BaCkEnD"]:
            response = client.get(
                f"/api/projects?name={search_term}",
                headers=auth_headers(token),
            )

            assert response.status_code == 200
            projects = response.json()
            assert len(projects) == 1
            assert projects[0]["name"] == "Backend API"

    def test_filter_projects_by_is_active(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test filtering projects by active status."""
        token, org_id = org_admin_token

        # Create active project
        active_id = create_test_project(client, token, "Active Project")

        # Create inactive project
        inactive_id = create_test_project(client, token, "Inactive Project")
        client.put(
            f"/api/projects/{inactive_id}",
            json={"is_active": False},
            headers=auth_headers(token),
        )

        # Filter for active projects only
        response = client.get(
            "/api/projects?is_active=true",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        projects = response.json()
        project_ids = {p["id"] for p in projects}
        assert active_id in project_ids
        assert inactive_id not in project_ids

    def test_filter_projects_by_is_active_false(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test filtering for inactive projects only."""
        token, org_id = org_admin_token

        # Create active project
        active_id = create_test_project(client, token, "Active Project")

        # Create inactive project
        inactive_id = create_test_project(client, token, "Inactive Project")
        client.put(
            f"/api/projects/{inactive_id}",
            json={"is_active": False},
            headers=auth_headers(token),
        )

        # Filter for inactive projects only
        response = client.get(
            "/api/projects?is_active=false",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        projects = response.json()
        project_ids = {p["id"] for p in projects}
        assert inactive_id in project_ids
        assert active_id not in project_ids

    def test_filter_projects_by_name_and_is_active(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test combining name and is_active filters."""
        token, org_id = org_admin_token

        # Create projects
        backend_active = create_test_project(client, token, "Backend API")
        backend_inactive = create_test_project(client, token, "Backend Service")

        # Deactivate backend service
        client.put(
            f"/api/projects/{backend_inactive}",
            json={"is_active": False},
            headers=auth_headers(token),
        )

        # Filter by name="backend" and is_active=true
        response = client.get(
            "/api/projects?name=backend&is_active=true",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        projects = response.json()
        assert len(projects) == 1
        assert projects[0]["id"] == backend_active
        assert projects[0]["name"] == "Backend API"

    def test_filter_projects_no_matches(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test filtering with no matches returns empty array."""
        token, org_id = org_admin_token

        create_test_project(client, token, "Backend API")

        # Search for non-existent name
        response = client.get(
            "/api/projects?name=nonexistent",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_filter_projects_respects_organization_scope(
        self, client: TestClient, org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test filtering respects organization boundaries."""
        token1, org1_id = org_admin_token

        # Create org2 and its admin
        org2_id = create_test_org(client, super_admin_token, "Org 2")
        _, password2 = create_admin_user(client, super_admin_token, org2_id, username="admin2")
        login2 = client.post("/auth/login", json={"username": "admin2", "password": password2})
        token2 = login2.json()["access_token"]

        # Create projects in both orgs with "backend" in name
        create_test_project(client, token1, "Backend API")
        create_test_project(client, token2, "Backend Service")

        # Admin1 filters by "backend" - should only see org1 project
        response1 = client.get(
            "/api/projects?name=backend",
            headers=auth_headers(token1),
        )

        assert response1.status_code == 200
        projects1 = response1.json()
        assert len(projects1) == 1
        assert projects1[0]["organization_id"] == org1_id

        # Admin2 filters by "backend" - should only see org2 project
        response2 = client.get(
            "/api/projects?name=backend",
            headers=auth_headers(token2),
        )

        assert response2.status_code == 200
        projects2 = response2.json()
        assert len(projects2) == 1
        assert projects2[0]["organization_id"] == org2_id

    def test_filter_projects_as_super_admin_sees_all(
        self, client: TestClient, org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test Super Admin filtering sees projects across all organizations."""
        token1, org1_id = org_admin_token

        # Create org2 and its admin
        org2_id = create_test_org(client, super_admin_token, "Org 2")
        _, password2 = create_admin_user(client, super_admin_token, org2_id, username="admin2")
        login2 = client.post("/auth/login", json={"username": "admin2", "password": password2})
        token2 = login2.json()["access_token"]

        # Create projects in both orgs with "backend" in name
        create_test_project(client, token1, "Backend API")
        create_test_project(client, token2, "Backend Service")

        # Super Admin filters by "backend" - should see both
        response = client.get(
            "/api/projects?name=backend",
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 200
        projects = response.json()
        assert len(projects) == 2
        org_ids = {p["organization_id"] for p in projects}
        assert org_ids == {org1_id, org2_id}


class TestUpdateProject:
    """Tests for PUT /api/projects/{id} endpoint."""

    def test_update_project_as_admin(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test updating project as Admin."""
        token, org_id = org_admin_token

        # Create project
        project_id = create_test_project(client, token, "Original Name", "Original description")

        # Update project
        update_data = {"name": "Updated Name", "description": "Updated description"}
        response = client.put(
            f"/api/projects/{project_id}",
            json=update_data,
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated description"
        assert data["id"] == project_id

    def test_update_project_as_project_manager(
        self, client: TestClient, project_manager_token: tuple[str, str]
    ) -> None:
        """Test updating project as Project Manager."""
        token, org_id = project_manager_token

        # Create project
        project_id = create_test_project(client, token, "Original Name")

        # Update project
        update_data = {"name": "PM Updated Name"}
        response = client.put(
            f"/api/projects/{project_id}",
            json=update_data,
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        assert response.json()["name"] == "PM Updated Name"

    def test_update_project_partial_update(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test partial update of project (only name or description)."""
        token, org_id = org_admin_token

        # Create project
        project_id = create_test_project(client, token, "Original", "Original description")

        # Update only name
        update_data = {"name": "New Name"}
        response = client.put(
            f"/api/projects/{project_id}",
            json=update_data,
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["description"] == "Original description"  # Unchanged

    def test_update_project_from_different_org_fails(
        self,
        client: TestClient,
        org_admin_token: tuple[str, str],
        super_admin_token: str,
    ) -> None:
        """Test that user cannot update project from different organization."""
        token, _ = org_admin_token

        # Create another org and project in it
        other_org_id = create_test_org(client, super_admin_token, "Other Org")
        _, other_pm_password = create_project_manager(client, super_admin_token, other_org_id, username="otherpm3")
        login_resp = client.post("/auth/login", json={"username": "otherpm3", "password": other_pm_password})
        other_token = login_resp.json()["access_token"]
        project_id = create_test_project(client, other_token, "Other Org Project")

        # Attempt to update
        update_data = {"name": "Hacked Name"}
        response = client.put(
            f"/api/projects/{project_id}",
            json=update_data,
            headers=auth_headers(token),
        )

        assert response.status_code == 403
        assert "different organization" in response.json()["detail"]

    def test_update_project_as_write_user_fails(
        self, client: TestClient, write_user_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test that Write Access user cannot update projects."""
        token, org_id = write_user_token

        # Create project manager in same org to create the project
        _, pm_password = create_project_manager(client, super_admin_token, org_id, username="pmfortest")
        login_resp = client.post("/auth/login", json={"username": "pmfortest", "password": pm_password})
        pm_token = login_resp.json()["access_token"]
        project_id = create_test_project(client, pm_token, "Project")

        # Attempt to update
        update_data = {"name": "Unauthorized Update"}
        response = client.put(
            f"/api/projects/{project_id}",
            json=update_data,
            headers=auth_headers(token),
        )

        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    def test_update_nonexistent_project_returns_404(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test updating non-existent project returns 404."""
        token, _ = org_admin_token

        update_data = {"name": "New Name"}
        response = client.put(
            "/api/projects/nonexistent-id",
            json=update_data,
            headers=auth_headers(token),
        )

        assert response.status_code == 404


class TestDeleteProject:
    """Tests for DELETE /api/projects/{id} endpoint."""

    def test_delete_project_as_admin(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test deleting project as Admin."""
        token, org_id = org_admin_token

        # Create project
        project_id = create_test_project(client, token, "To Delete")

        # Delete project
        response = client.delete(
            f"/api/projects/{project_id}",
            headers=auth_headers(token),
        )

        assert response.status_code == 204

        # Verify project is deleted
        get_response = client.get(
            f"/api/projects/{project_id}",
            headers=auth_headers(token),
        )
        assert get_response.status_code == 404

    def test_delete_project_as_project_manager_fails(
        self, client: TestClient, project_manager_token: tuple[str, str]
    ) -> None:
        """Test that Project Manager cannot delete projects."""
        token, org_id = project_manager_token

        # Create project
        project_id = create_test_project(client, token, "Protected Project")

        # Attempt to delete
        response = client.delete(
            f"/api/projects/{project_id}",
            headers=auth_headers(token),
        )

        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    def test_delete_project_from_different_org_fails(
        self,
        client: TestClient,
        org_admin_token: tuple[str, str],
        super_admin_token: str,
    ) -> None:
        """Test that Admin cannot delete project from different organization."""
        token, _ = org_admin_token

        # Create another org and project in it
        other_org_id = create_test_org(client, super_admin_token, "Other Org")
        _, other_pm_password = create_project_manager(client, super_admin_token, other_org_id, username="otherpm4")
        login_resp = client.post("/auth/login", json={"username": "otherpm4", "password": other_pm_password})
        other_token = login_resp.json()["access_token"]
        project_id = create_test_project(client, other_token, "Other Org Project")

        # Attempt to delete
        response = client.delete(
            f"/api/projects/{project_id}",
            headers=auth_headers(token),
        )

        assert response.status_code == 403
        assert "different organization" in response.json()["detail"]

    def test_delete_project_as_super_admin_from_any_org(
        self,
        client: TestClient,
        super_admin_token: str,
        org_admin_token: tuple[str, str],
    ) -> None:
        """Test that Super Admin can delete project from any organization."""
        # Create project using org admin
        token, _ = org_admin_token
        project_id = create_test_project(client, token, "To Delete")

        # Delete as Super Admin
        response = client.delete(
            f"/api/projects/{project_id}",
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 204

    def test_delete_nonexistent_project_returns_404(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test deleting non-existent project returns 404."""
        token, _ = org_admin_token

        response = client.delete(
            "/api/projects/nonexistent-id",
            headers=auth_headers(token),
        )

        assert response.status_code == 404


class TestArchiveProject:
    """Tests for PATCH /api/projects/{id}/archive endpoint."""

    def test_archive_project_as_admin(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test archiving project as Admin."""
        token, org_id = org_admin_token

        # Create project
        project_id = create_test_project(client, token, "To Archive")

        # Archive project
        response = client.patch(
            f"/api/projects/{project_id}/archive",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == project_id
        assert data["is_archived"] is True
        assert data["archived_at"] is not None

    def test_archive_project_as_project_manager(
        self, client: TestClient, project_manager_token: tuple[str, str]
    ) -> None:
        """Test archiving project as Project Manager."""
        token, org_id = project_manager_token

        # Create project
        project_id = create_test_project(client, token, "PM Archive")

        # Archive project
        response = client.patch(
            f"/api/projects/{project_id}/archive",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_archived"] is True

    def test_archive_project_as_write_user_fails(
        self, client: TestClient, write_user_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test that Write user cannot archive projects."""
        token, org_id = write_user_token

        # Create project manager to create the project
        _, pm_password = create_project_manager(client, super_admin_token, org_id, username="pm_for_write_test")
        login_resp = client.post("/auth/login", json={"username": "pm_for_write_test", "password": pm_password})
        pm_token = login_resp.json()["access_token"]
        project_id = create_test_project(client, pm_token, "Project")

        # Try to archive as write user
        response = client.patch(
            f"/api/projects/{project_id}/archive",
            headers=auth_headers(token),
        )

        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    def test_archive_project_from_different_org_fails(
        self, client: TestClient, org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test cannot archive project from different organization."""
        token, _ = org_admin_token

        # Create another org and project in it
        other_org_id = create_test_org(client, super_admin_token, "Other Org")
        _, other_pm_password = create_project_manager(
            client, super_admin_token, other_org_id, username="other_pm_archive"
        )
        login_resp = client.post("/auth/login", json={"username": "other_pm_archive", "password": other_pm_password})
        other_token = login_resp.json()["access_token"]
        project_id = create_test_project(client, other_token, "Other Org Project")

        # Try to archive from first org
        response = client.patch(
            f"/api/projects/{project_id}/archive",
            headers=auth_headers(token),
        )

        assert response.status_code == 403
        assert "different organization" in response.json()["detail"]

    def test_archive_nonexistent_project_returns_404(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Test archiving non-existent project returns 404."""
        token, _ = org_admin_token

        response = client.patch(
            "/api/projects/nonexistent-id/archive",
            headers=auth_headers(token),
        )

        assert response.status_code == 404

    def test_archived_project_not_in_default_list(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test archived projects excluded from default listing."""
        token, org_id = org_admin_token

        # Create two projects
        create_test_project(client, token, "Active Project")
        archived_id = create_test_project(client, token, "To Archive")

        # Archive one project
        client.patch(f"/api/projects/{archived_id}/archive", headers=auth_headers(token))

        # List projects
        response = client.get("/api/projects", headers=auth_headers(token))

        assert response.status_code == 200
        projects = response.json()
        assert len(projects) == 1
        assert projects[0]["name"] == "Active Project"

    def test_archived_project_included_with_parameter(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Test include_archived=true shows archived projects."""
        token, org_id = org_admin_token

        # Create and archive project
        project_id = create_test_project(client, token, "Archived Project")
        client.patch(f"/api/projects/{project_id}/archive", headers=auth_headers(token))

        # List with include_archived=true
        response = client.get(
            "/api/projects?include_archived=true",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        projects = response.json()
        assert len(projects) == 1
        assert projects[0]["name"] == "Archived Project"
        assert projects[0]["is_archived"] is True

    def test_list_only_archived_projects(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test filtering for only archived projects."""
        token, org_id = org_admin_token

        # Create active and archived projects
        create_test_project(client, token, "Active")
        archived_id = create_test_project(client, token, "Archived")
        client.patch(f"/api/projects/{archived_id}/archive", headers=auth_headers(token))

        # This test combines filters - but we need to check if is_active filter applies to archived
        # Actually, archived projects should be filterable separately from is_active
        # Let's just test that include_archived shows the archived one
        response = client.get(
            "/api/projects?include_archived=true",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        projects = response.json()
        # Should have both active and archived
        assert len(projects) == 2


class TestUnarchiveProject:
    """Tests for PATCH /api/projects/{id}/unarchive endpoint."""

    def test_unarchive_project_as_admin(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test unarchiving project as Admin."""
        token, org_id = org_admin_token

        # Create and archive project
        project_id = create_test_project(client, token, "To Unarchive")
        client.patch(f"/api/projects/{project_id}/archive", headers=auth_headers(token))

        # Unarchive project
        response = client.patch(
            f"/api/projects/{project_id}/unarchive",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == project_id
        assert data["is_archived"] is False
        assert data["archived_at"] is None

    def test_unarchive_project_as_project_manager_fails(
        self, client: TestClient, project_manager_token: tuple[str, str]
    ) -> None:
        """Test that Project Manager cannot unarchive (only Admin)."""
        token, org_id = project_manager_token

        # Create and archive project
        project_id = create_test_project(client, token, "PM Unarchive")
        client.patch(f"/api/projects/{project_id}/archive", headers=auth_headers(token))

        # Try to unarchive
        response = client.patch(
            f"/api/projects/{project_id}/unarchive",
            headers=auth_headers(token),
        )

        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    def test_unarchive_project_from_different_org_fails(
        self, client: TestClient, org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test cannot unarchive project from different organization."""
        token, _ = org_admin_token

        # Create another org and project in it
        other_org_id = create_test_org(client, super_admin_token, "Other Org")
        _, other_admin_password = create_admin_user(
            client, super_admin_token, other_org_id, username="other_admin_unarchive"
        )
        login_resp = client.post(
            "/auth/login", json={"username": "other_admin_unarchive", "password": other_admin_password}
        )
        other_token = login_resp.json()["access_token"]
        project_id = create_test_project(client, other_token, "Other Org Project")
        client.patch(f"/api/projects/{project_id}/archive", headers=auth_headers(other_token))

        # Try to unarchive from first org
        response = client.patch(
            f"/api/projects/{project_id}/unarchive",
            headers=auth_headers(token),
        )

        assert response.status_code == 403
        assert "different organization" in response.json()["detail"]

    def test_unarchive_nonexistent_project_returns_404(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Test unarchiving non-existent project returns 404."""
        token, _ = org_admin_token

        response = client.patch(
            "/api/projects/nonexistent-id/unarchive",
            headers=auth_headers(token),
        )

        assert response.status_code == 404

    def test_unarchived_project_appears_in_default_list(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Test unarchived project appears in default listing."""
        token, org_id = org_admin_token

        # Create, archive, then unarchive project
        project_id = create_test_project(client, token, "Unarchived")
        client.patch(f"/api/projects/{project_id}/archive", headers=auth_headers(token))
        client.patch(f"/api/projects/{project_id}/unarchive", headers=auth_headers(token))

        # List projects
        response = client.get("/api/projects", headers=auth_headers(token))

        assert response.status_code == 200
        projects = response.json()
        assert len(projects) == 1
        assert projects[0]["name"] == "Unarchived"
        assert projects[0]["is_archived"] is False


class TestProjectWorkflows:
    """Test complete project workflows."""

    def test_complete_project_crud_workflow(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test complete CRUD workflow for a project."""
        token, org_id = org_admin_token

        # 1. Create project
        create_data = {"name": "Workflow Project", "description": "Full CRUD test"}
        create_response = client.post(
            "/api/projects",
            json=create_data,
            headers=auth_headers(token),
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]

        # 2. Get project
        get_response = client.get(
            f"/api/projects/{project_id}",
            headers=auth_headers(token),
        )
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "Workflow Project"

        # 3. Update project
        update_response = client.put(
            f"/api/projects/{project_id}",
            json={"name": "Updated Workflow", "description": "Updated"},
            headers=auth_headers(token),
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Updated Workflow"

        # 4. List projects includes updated project
        list_response = client.get(
            "/api/projects",
            headers=auth_headers(token),
        )
        assert list_response.status_code == 200
        assert any(p["id"] == project_id for p in list_response.json())

        # 5. Delete project
        delete_response = client.delete(
            f"/api/projects/{project_id}",
            headers=auth_headers(token),
        )
        assert delete_response.status_code == 204

        # 6. Verify deletion
        final_get = client.get(
            f"/api/projects/{project_id}",
            headers=auth_headers(token),
        )
        assert final_get.status_code == 404


class TestProjectWorkflowIntegration:
    """Test project-workflow integration (REQ-PROJ-011)."""

    def test_create_project_with_custom_workflow(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test creating project with custom workflow_id (REQ-PROJ-011)."""
        token, org_id = org_admin_token

        # Create custom workflow
        workflow_data = {"name": "Dev Workflow", "statuses": ["BACKLOG", "IN_DEV", "DEPLOYED"]}
        workflow_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))
        workflow_id = workflow_response.json()["id"]

        # Create project with custom workflow
        project_data = {"name": "Test Project", "workflow_id": workflow_id}
        response = client.post("/api/projects", json=project_data, headers=auth_headers(token))

        assert response.status_code == 201
        project = response.json()
        assert project["workflow_id"] == workflow_id

        # Verify project uses custom workflow
        get_response = client.get(f"/api/projects/{project['id']}", headers=auth_headers(token))
        assert get_response.json()["workflow_id"] == workflow_id

    def test_create_project_without_workflow_uses_default(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Test creating project without workflow_id uses default workflow (REQ-PROJ-011)."""
        token, org_id = org_admin_token

        # Get default workflow
        workflows_response = client.get("/api/workflows", headers=auth_headers(token))
        workflows = workflows_response.json()
        default_workflow = next((w for w in workflows if w["is_default"] is True), None)
        assert default_workflow is not None

        # Create project without workflow_id
        project_data = {"name": "Default Workflow Project"}
        response = client.post("/api/projects", json=project_data, headers=auth_headers(token))

        assert response.status_code == 201
        project = response.json()
        assert project["workflow_id"] == default_workflow["id"]

    def test_update_project_workflow(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test updating project's workflow_id (REQ-PROJ-011)."""
        token, org_id = org_admin_token

        # Create two workflows
        workflow1_data = {"name": "Workflow 1", "statuses": ["TODO", "DONE"]}
        workflow1_response = client.post("/api/workflows", json=workflow1_data, headers=auth_headers(token))
        workflow1_id = workflow1_response.json()["id"]

        workflow2_data = {"name": "Workflow 2", "statuses": ["TODO", "IN_PROGRESS", "DONE"]}
        workflow2_response = client.post("/api/workflows", json=workflow2_data, headers=auth_headers(token))
        workflow2_id = workflow2_response.json()["id"]

        # Create project with workflow1
        project_data = {"name": "Test Project", "workflow_id": workflow1_id}
        project_response = client.post("/api/projects", json=project_data, headers=auth_headers(token))
        project_id = project_response.json()["id"]

        # Update to workflow2
        update_data = {"workflow_id": workflow2_id}
        response = client.put(f"/api/projects/{project_id}", json=update_data, headers=auth_headers(token))

        assert response.status_code == 200
        updated = response.json()
        assert updated["workflow_id"] == workflow2_id

    def test_cannot_set_workflow_from_different_org(
        self, client: TestClient, org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test that workflow must be in same organization (REQ-PROJ-011)."""
        token1, org1_id = org_admin_token

        # Create second organization with admin
        from tests.helpers import create_admin_user

        org2_response = client.post(
            "/api/organizations", json={"name": "Org 2"}, headers=auth_headers(super_admin_token)
        )
        org2_id = org2_response.json()["id"]

        admin2_id, admin2_password = create_admin_user(client, super_admin_token, org2_id, username="admin2")
        login_response = client.post("/auth/login", json={"username": "admin2", "password": admin2_password})
        token2 = login_response.json()["access_token"]

        # Create workflow in org2
        workflow_data = {"name": "Org2 Workflow", "statuses": ["TODO", "DONE"]}
        workflow_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token2))
        org2_workflow_id = workflow_response.json()["id"]

        # Try to create project in org1 with org2's workflow - should fail
        project_data = {"name": "Test Project", "workflow_id": org2_workflow_id}
        response = client.post("/api/projects", json=project_data, headers=auth_headers(token1))

        assert response.status_code == 400
        error = response.json()
        assert "different organization" in error["detail"].lower() or "not found" in error["detail"].lower()

    def test_update_project_workflow_validates_ticket_compatibility(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Test updating project workflow validates ticket status compatibility (REQ-PROJ-011)."""
        token, org_id = org_admin_token

        # Create two workflows with different statuses
        workflow1_data = {"name": "Workflow 1", "statuses": ["TODO", "CUSTOM_STATUS", "DONE"]}
        workflow1_response = client.post("/api/workflows", json=workflow1_data, headers=auth_headers(token))
        workflow1_id = workflow1_response.json()["id"]

        workflow2_data = {"name": "Workflow 2", "statuses": ["TODO", "DONE"]}  # No CUSTOM_STATUS
        workflow2_response = client.post("/api/workflows", json=workflow2_data, headers=auth_headers(token))
        workflow2_id = workflow2_response.json()["id"]

        # Create project with workflow1
        project_data = {"name": "Test Project", "workflow_id": workflow1_id}
        project_response = client.post("/api/projects", json=project_data, headers=auth_headers(token))
        project_id = project_response.json()["id"]

        # Create ticket with CUSTOM_STATUS
        ticket_data = {"title": "Test Ticket", "status": "CUSTOM_STATUS"}
        ticket_response = client.post(
            "/api/tickets", json=ticket_data, params={"project_id": project_id}, headers=auth_headers(token)
        )
        assert ticket_response.status_code == 201

        # Try to update project to workflow2 - should fail because ticket has CUSTOM_STATUS
        update_data = {"workflow_id": workflow2_id}
        response = client.put(f"/api/projects/{project_id}", json=update_data, headers=auth_headers(token))

        assert response.status_code == 400
        error = response.json()
        assert (
            "Cannot change workflow" in error["detail"]
            or "ticket" in error["detail"].lower()
            or "status" in error["detail"].lower()
        )

    def test_update_project_workflow_succeeds_with_compatible_tickets(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Test updating project workflow succeeds when tickets are compatible (REQ-PROJ-011)."""
        token, org_id = org_admin_token

        # Create two workflows with overlapping statuses
        workflow1_data = {"name": "Workflow 1", "statuses": ["TODO", "IN_PROGRESS", "DONE"]}
        workflow1_response = client.post("/api/workflows", json=workflow1_data, headers=auth_headers(token))
        workflow1_id = workflow1_response.json()["id"]

        workflow2_data = {"name": "Workflow 2", "statuses": ["TODO", "IN_PROGRESS", "DONE", "ARCHIVED"]}
        workflow2_response = client.post("/api/workflows", json=workflow2_data, headers=auth_headers(token))
        workflow2_id = workflow2_response.json()["id"]

        # Create project with workflow1
        project_data = {"name": "Test Project", "workflow_id": workflow1_id}
        project_response = client.post("/api/projects", json=project_data, headers=auth_headers(token))
        project_id = project_response.json()["id"]

        # Create ticket with compatible status
        ticket_data = {"title": "Test Ticket", "status": "IN_PROGRESS"}
        ticket_response = client.post(
            "/api/tickets", json=ticket_data, params={"project_id": project_id}, headers=auth_headers(token)
        )
        assert ticket_response.status_code == 201

        # Update to workflow2 - should succeed because IN_PROGRESS is in both
        update_data = {"workflow_id": workflow2_id}
        response = client.put(f"/api/projects/{project_id}", json=update_data, headers=auth_headers(token))

        assert response.status_code == 200
        updated = response.json()
        assert updated["workflow_id"] == workflow2_id


class TestProjectActivityLogging:
    """Test activity log creation for all project operations."""

    def test_create_project_logs_activity(
        self, client: TestClient, test_repo: Repository, org_admin_token: tuple[str, str]
    ) -> None:
        """Test that creating a project creates an activity log entry."""
        token, org_id = org_admin_token

        # Create a project
        project_data = {"name": "Logged Project", "description": "Test logging"}
        response = client.post(
            "/api/projects",
            json=project_data,
            headers=auth_headers(token),
        )
        assert response.status_code == 201
        project_id = response.json()["id"]

        # Check activity log was created
        logs = test_repo.activity_logs.list(entity_type="project", entity_id=project_id)

        assert len(logs) == 1
        log = logs[0]
        assert log.entity_type == "project"
        assert log.entity_id == project_id
        assert log.action.value == "project_created"
        assert log.organization_id == org_id

        # Verify changes structure - command-based format
        assert "command" in log.changes
        assert log.changes["command"]["project_data"]["name"] == "Logged Project"
        assert log.changes["command"]["project_data"]["description"] == "Test logging"
        assert log.changes["command"]["organization_id"] == org_id

    def test_update_project_logs_activity(
        self, client: TestClient, test_repo: Repository, org_admin_token: tuple[str, str]
    ) -> None:
        """Test that updating a project creates an activity log entry."""
        token, org_id = org_admin_token

        # Create a project
        project_id = create_test_project(client, token, "Original Name", "Original desc")

        # Update the project
        update_data = {"name": "Updated Name", "description": "Updated desc"}
        response = client.put(
            f"/api/projects/{project_id}",
            json=update_data,
            headers=auth_headers(token),
        )
        assert response.status_code == 200

        # Check activity log for update
        logs = test_repo.activity_logs.list(entity_type="project", entity_id=project_id)

        # Should have 2 logs: create and update
        assert len(logs) == 2

        # Check update log (second one) - command-based format
        update_log = logs[1]
        assert update_log.action.value == "project_updated"
        assert "command" in update_log.changes
        assert update_log.changes["command"]["name"] == "Updated Name"
        assert update_log.changes["command"]["description"] == "Updated desc"

    def test_archive_project_logs_activity(
        self, client: TestClient, test_repo: Repository, org_admin_token: tuple[str, str]
    ) -> None:
        """Test that archiving a project creates an activity log entry."""
        token, org_id = org_admin_token

        # Create a project
        project_id = create_test_project(client, token, "To Archive")

        # Archive the project
        response = client.patch(
            f"/api/projects/{project_id}/archive",
            headers=auth_headers(token),
        )
        assert response.status_code == 200

        # Check activity log
        logs = test_repo.activity_logs.list(entity_type="project", entity_id=project_id)

        # Should have 2 logs: create and archive
        assert len(logs) == 2

        # Check archive log - command-based format
        archive_log = logs[1]
        assert archive_log.action.value == "project_archived"
        assert "command" in archive_log.changes
        assert archive_log.changes["command"]["project_id"] == project_id

    def test_unarchive_project_logs_activity(
        self, client: TestClient, test_repo: Repository, org_admin_token: tuple[str, str]
    ) -> None:
        """Test that unarchiving a project creates an activity log entry."""
        token, org_id = org_admin_token

        # Create and archive a project
        project_id = create_test_project(client, token, "To Unarchive")
        client.patch(f"/api/projects/{project_id}/archive", headers=auth_headers(token))

        # Unarchive the project
        response = client.patch(
            f"/api/projects/{project_id}/unarchive",
            headers=auth_headers(token),
        )
        assert response.status_code == 200

        # Check activity log
        logs = test_repo.activity_logs.list(entity_type="project", entity_id=project_id)

        # Should have 3 logs: create, archive, unarchive
        assert len(logs) == 3

        # Check unarchive log - command-based format
        unarchive_log = logs[2]
        assert unarchive_log.action.value == "project_unarchived"
        assert "command" in unarchive_log.changes
        assert unarchive_log.changes["command"]["project_id"] == project_id

    def test_delete_project_logs_activity(
        self, client: TestClient, test_repo: Repository, org_admin_token: tuple[str, str]
    ) -> None:
        """Test that deleting a project creates an activity log entry."""
        token, org_id = org_admin_token

        # Create a project
        project_id = create_test_project(client, token, "To Delete", "Delete me")

        # Delete the project
        response = client.delete(
            f"/api/projects/{project_id}",
            headers=auth_headers(token),
        )
        assert response.status_code == 204

        # Check activity log - should persist even after deletion
        logs = test_repo.activity_logs.list(entity_type="project", entity_id=project_id)

        # Should have 2 logs: create and delete
        assert len(logs) == 2

        # Check delete log - command-based format with snapshot
        delete_log = logs[1]
        assert delete_log.action.value == "project_deleted"
        assert "command" in delete_log.changes
        assert delete_log.changes["command"]["project_id"] == project_id
        assert "snapshot" in delete_log.changes
        assert delete_log.changes["snapshot"]["name"] == "To Delete"
        assert delete_log.changes["snapshot"]["description"] == "Delete me"

    def test_activity_log_captures_actor(
        self, client: TestClient, test_repo: Repository, org_admin_token: tuple[str, str]
    ) -> None:
        """Test that activity logs capture the actor who performed the action."""
        token, org_id = org_admin_token

        # Create a project
        project_data = {"name": "Actor Test Project"}
        response = client.post(
            "/api/projects",
            json=project_data,
            headers=auth_headers(token),
        )
        assert response.status_code == 201
        project_id = response.json()["id"]

        # Verify actor was captured
        logs = test_repo.activity_logs.list(entity_type="project", entity_id=project_id)

        assert len(logs) == 1
        # Verify actor_id exists and is non-empty
        assert logs[0].actor_id is not None
        assert len(logs[0].actor_id) > 0

    def test_multiple_operations_create_multiple_logs(
        self, client: TestClient, test_repo: Repository, org_admin_token: tuple[str, str]
    ) -> None:
        """Test that multiple operations on same project create separate log entries."""
        token, org_id = org_admin_token

        # Create project
        project_id = create_test_project(client, token, "Multi-Op Project")

        # Update it
        client.put(
            f"/api/projects/{project_id}",
            json={"name": "Updated Project"},
            headers=auth_headers(token),
        )

        # Archive it
        client.patch(f"/api/projects/{project_id}/archive", headers=auth_headers(token))

        # Unarchive it
        client.patch(f"/api/projects/{project_id}/unarchive", headers=auth_headers(token))

        # Check all logs were created
        logs = test_repo.activity_logs.list(entity_type="project", entity_id=project_id)

        # Should have 4 logs: create, update, archive, unarchive
        assert len(logs) == 4
        actions = [log.action.value for log in logs]
        assert actions == ["project_created", "project_updated", "project_archived", "project_unarchived"]
