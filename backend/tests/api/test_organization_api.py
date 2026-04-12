"""Tests for organization API endpoints."""

from fastapi.testclient import TestClient

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import ActionType
from tests.conftest import client, test_repo  # noqa: F401
from tests.fixtures.auth_fixtures import org_admin_token, super_admin_token  # noqa: F401
from tests.helpers import auth_headers, create_test_org


class TestCreateOrganization:
    """Tests for POST /api/organizations endpoint."""

    def test_create_organization_as_super_admin(self, client: TestClient, super_admin_token: str) -> None:
        """Test creating organization as Super Admin."""
        org_data = {"name": "New Organization", "description": "A new org"}

        response = client.post(
            "/api/organizations",
            json=org_data,
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Organization"
        assert data["description"] == "A new org"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_organization_without_description(self, client: TestClient, super_admin_token: str) -> None:
        """Test creating organization with only name."""
        org_data = {"name": "Minimal Org"}

        response = client.post(
            "/api/organizations",
            json=org_data,
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Org"
        assert data["description"] is None

    def test_create_organization_as_regular_user_fails(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Test that non-Super Admin cannot create organization."""
        token, _ = org_admin_token
        org_data = {"name": "Unauthorized Org"}

        response = client.post(
            "/api/organizations",
            json=org_data,
            headers=auth_headers(token),
        )

        assert response.status_code == 403
        assert "Super Admin access required" in response.json()["detail"]

    def test_create_organization_without_auth_fails(self, client: TestClient) -> None:
        """Test that creating organization without auth fails."""
        org_data = {"name": "No Auth Org"}

        response = client.post("/api/organizations", json=org_data)

        assert response.status_code == 401

    def test_create_organization_with_duplicate_name_fails(self, client: TestClient, super_admin_token: str) -> None:
        """Test that creating organization with duplicate name fails."""
        org_data = {"name": "Duplicate Org"}

        # Create first organization
        response1 = client.post(
            "/api/organizations",
            json=org_data,
            headers=auth_headers(super_admin_token),
        )
        assert response1.status_code == 201

        # Attempt to create second with same name
        response2 = client.post(
            "/api/organizations",
            json=org_data,
            headers=auth_headers(super_admin_token),
        )
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"]

    def test_create_organization_with_special_characters(self, client: TestClient, super_admin_token: str) -> None:
        """Test creating organization with special characters in name."""
        org_data = {"name": "Acme Corp. & Partners!"}

        response = client.post(
            "/api/organizations",
            json=org_data,
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 201
        assert response.json()["name"] == "Acme Corp. & Partners!"

    def test_create_organization_with_unicode(self, client: TestClient, super_admin_token: str) -> None:
        """Test creating organization with unicode characters."""
        org_data = {"name": "日本株式会社"}

        response = client.post(
            "/api/organizations",
            json=org_data,
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 201
        assert response.json()["name"] == "日本株式会社"

    def test_create_organization_with_invalid_data_fails(self, client: TestClient, super_admin_token: str) -> None:
        """Test creating organization with invalid data fails validation."""
        org_data = {"name": ""}  # Empty name

        response = client.post(
            "/api/organizations",
            json=org_data,
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 422


class TestGetOrganization:
    """Tests for GET /api/organizations/{id} endpoint."""

    def test_get_organization_as_super_admin(self, client: TestClient, super_admin_token: str) -> None:
        """Test Super Admin can get any organization."""
        # Create organization
        org_id = create_test_org(client, super_admin_token)

        response = client.get(
            f"/api/organizations/{org_id}",
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == org_id
        assert data["name"] == "Test Org"

    def test_get_own_organization_as_regular_user(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test regular user can get their own organization."""
        token, org_id = org_admin_token

        response = client.get(
            f"/api/organizations/{org_id}",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == org_id

    def test_get_other_organization_as_regular_user_fails(
        self, client: TestClient, org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test regular user cannot get different organization."""
        token, _ = org_admin_token

        # Create another organization
        other_org_id = create_test_org(client, super_admin_token, "Other Org")

        response = client.get(
            f"/api/organizations/{other_org_id}",
            headers=auth_headers(token),
        )

        assert response.status_code == 403
        assert "Cannot access other organizations" in response.json()["detail"]

    def test_get_non_existent_organization_returns_404(self, client: TestClient, super_admin_token: str) -> None:
        """Test getting non-existent organization returns 404."""
        response = client.get(
            "/api/organizations/non-existent-id",
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_get_organization_without_auth_fails(self, client: TestClient) -> None:
        """Test getting organization without auth fails."""
        response = client.get("/api/organizations/some-id")

        assert response.status_code == 401


class TestListOrganizations:
    """Tests for GET /api/organizations endpoint."""

    def test_list_organizations_as_super_admin(self, client: TestClient, super_admin_token: str) -> None:
        """Test Super Admin sees all organizations."""
        # Create multiple organizations
        create_test_org(client, super_admin_token, "Org 1")
        create_test_org(client, super_admin_token, "Org 2")

        response = client.get(
            "/api/organizations",
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        org_names = {org["name"] for org in data}
        assert org_names == {"Org 1", "Org 2"}

    def test_list_organizations_as_regular_user_sees_only_own(
        self, client: TestClient, org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test regular user sees only their organization."""
        token, org_id = org_admin_token

        # Create another organization that user shouldn't see
        create_test_org(client, super_admin_token, "Other Org")

        response = client.get(
            "/api/organizations",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == org_id

    def test_list_organizations_without_auth_fails(self, client: TestClient) -> None:
        """Test listing organizations without auth fails."""
        response = client.get("/api/organizations")

        assert response.status_code == 401


class TestUpdateOrganization:
    """Tests for PUT /api/organizations/{id} endpoint."""

    def test_update_organization_as_super_admin(self, client: TestClient, super_admin_token: str) -> None:
        """Test Super Admin can update organization."""
        # Create organization
        org_id = create_test_org(client, super_admin_token, "Original Name", "Original description")

        update_data = {"name": "Updated Name", "description": "Updated description"}

        response = client.put(
            f"/api/organizations/{org_id}",
            json=update_data,
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == org_id
        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated description"

    def test_update_organization_partial_fields(self, client: TestClient, super_admin_token: str) -> None:
        """Test updating only some fields."""
        # Create organization
        org_id = create_test_org(client, super_admin_token, "Original Name", "Original description")

        update_data = {"description": "New description only"}

        response = client.put(
            f"/api/organizations/{org_id}",
            json=update_data,
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Original Name"  # Unchanged
        assert data["description"] == "New description only"  # Updated

    def test_deactivate_organization(self, client: TestClient, super_admin_token: str) -> None:
        """Test deactivating an organization."""
        # Create organization
        org_id = create_test_org(client, super_admin_token, "Active Org")

        update_data = {"is_active": False}

        response = client.put(
            f"/api/organizations/{org_id}",
            json=update_data,
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

    def test_update_organization_as_regular_user_fails(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Test regular user cannot update organization."""
        token, org_id = org_admin_token
        update_data = {"name": "New Name"}

        response = client.put(
            f"/api/organizations/{org_id}",
            json=update_data,
            headers=auth_headers(token),
        )

        assert response.status_code == 403
        assert "Super Admin access required" in response.json()["detail"]

    def test_update_non_existent_organization_returns_404(self, client: TestClient, super_admin_token: str) -> None:
        """Test updating non-existent organization returns 404."""
        update_data = {"name": "New Name"}

        response = client.put(
            "/api/organizations/non-existent-id",
            json=update_data,
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_update_to_duplicate_name_fails(self, client: TestClient, super_admin_token: str) -> None:
        """Test updating to duplicate name fails."""
        # Create two organizations
        create_test_org(client, super_admin_token, "Organization 1")
        org2_id = create_test_org(client, super_admin_token, "Organization 2")

        # Attempt to update org2 to have same name as org1
        update_data = {"name": "Organization 1"}

        response = client.put(
            f"/api/organizations/{org2_id}",
            json=update_data,
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]


class TestOrganizationWorkflows:
    """Test complete workflows and integration scenarios."""

    def test_complete_organization_crud_workflow_as_super_admin(
        self, client: TestClient, super_admin_token: str
    ) -> None:
        """Test complete CRUD workflow as Super Admin."""
        # 1. Create
        create_response = client.post(
            "/api/organizations",
            json={"name": "Workflow Org", "description": "Testing workflow"},
            headers=auth_headers(super_admin_token),
        )
        assert create_response.status_code == 201
        org_id = create_response.json()["id"]

        # 2. Read
        get_response = client.get(
            f"/api/organizations/{org_id}",
            headers=auth_headers(super_admin_token),
        )
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "Workflow Org"

        # 3. List
        list_response = client.get(
            "/api/organizations",
            headers=auth_headers(super_admin_token),
        )
        assert list_response.status_code == 200
        org_ids = [org["id"] for org in list_response.json()]
        assert org_id in org_ids

        # 4. Update
        update_response = client.put(
            f"/api/organizations/{org_id}",
            json={"description": "Updated workflow description"},
            headers=auth_headers(super_admin_token),
        )
        assert update_response.status_code == 200
        assert update_response.json()["description"] == "Updated workflow description"

        # 5. Verify update persisted
        final_get = client.get(
            f"/api/organizations/{org_id}",
            headers=auth_headers(super_admin_token),
        )
        assert final_get.status_code == 200
        assert final_get.json()["description"] == "Updated workflow description"

    def test_regular_user_can_only_see_own_organization(
        self, client: TestClient, super_admin_token: str, org_admin_token: tuple[str, str]
    ) -> None:
        """Test data isolation between organizations for regular users."""
        token, user_org_id = org_admin_token

        # Super Admin creates another organization
        other_org_response = client.post(
            "/api/organizations",
            json={"name": "Other Organization"},
            headers=auth_headers(super_admin_token),
        )
        assert other_org_response.status_code == 201
        other_org_id = other_org_response.json()["id"]

        # Regular user lists organizations - should only see their own
        list_response = client.get(
            "/api/organizations",
            headers=auth_headers(token),
        )
        assert list_response.status_code == 200
        orgs = list_response.json()
        assert len(orgs) == 1
        assert orgs[0]["id"] == user_org_id

        # Regular user tries to access other organization - should fail
        get_other_response = client.get(
            f"/api/organizations/{other_org_id}",
            headers=auth_headers(token),
        )
        assert get_other_response.status_code == 403

    def test_organization_creation_creates_default_workflow(self, client: TestClient, super_admin_token: str) -> None:
        """Test that creating an organization automatically creates a default workflow."""
        # Create organization
        org_response = client.post(
            "/api/organizations",
            json={"name": "Test Org with Workflow"},
            headers=auth_headers(super_admin_token),
        )
        assert org_response.status_code == 201
        org_id = org_response.json()["id"]

        # List workflows - should include the default workflow for this org
        workflows_response = client.get(
            "/api/workflows",
            headers=auth_headers(super_admin_token),
        )
        assert workflows_response.status_code == 200
        workflows = workflows_response.json()

        # Find the default workflow for this organization
        org_workflows = [w for w in workflows if w["organization_id"] == org_id]
        assert len(org_workflows) == 1, "Organization should have exactly one default workflow"

        default_workflow = org_workflows[0]
        assert default_workflow["is_default"] is True
        assert default_workflow["name"] == "Default Workflow"
        assert default_workflow["description"] == "Standard workflow with TODO, IN_PROGRESS, and DONE statuses"
        assert default_workflow["statuses"] == ["TODO", "IN_PROGRESS", "DONE"]


class TestOrganizationActivityLogging:
    """Tests for organization activity logging."""

    def test_create_organization_logs_activity(
        self, client: TestClient, test_repo: Repository, super_admin_token: str
    ) -> None:
        """Test that creating an organization creates an activity log entry."""
        # Create organization
        org_data = {"name": "Test Organization", "description": "Test org for activity logging"}
        response = client.post("/api/organizations", json=org_data, headers=auth_headers(super_admin_token))
        assert response.status_code == 201
        org_id = response.json()["id"]

        # Get super admin user ID from token
        login_response = client.get("/api/users", headers=auth_headers(super_admin_token))
        super_admin_id = login_response.json()[0]["id"]  # Super admin should be first/only user

        # Verify activity log was created
        logs = test_repo.activity_logs.list(entity_type="organization", entity_id=org_id)

        assert len(logs) == 1
        log = logs[0]
        assert log.entity_type == "organization"
        assert log.entity_id == org_id
        assert log.action == ActionType.ORGANIZATION_CREATED
        assert log.actor_id == super_admin_id
        assert log.organization_id == org_id
        assert "command" in log.changes
        assert log.changes["command"]["organization_data"]["name"] == "Test Organization"

    def test_update_organization_logs_activity(
        self, client: TestClient, test_repo: Repository, super_admin_token: str
    ) -> None:
        """Test that updating an organization creates an activity log entry."""
        # Create organization
        org_id = create_test_org(client, super_admin_token, "Test Org")

        # Get super admin user ID
        login_response = client.get("/api/users", headers=auth_headers(super_admin_token))
        super_admin_id = login_response.json()[0]["id"]

        # Update organization
        update_data = {"name": "Updated Organization", "description": "Updated description"}
        response = client.put(f"/api/organizations/{org_id}", json=update_data, headers=auth_headers(super_admin_token))
        assert response.status_code == 200

        # Verify activity log was created for update
        logs = test_repo.activity_logs.list(entity_type="organization", entity_id=org_id)

        # Should have 2 logs: create + update
        assert len(logs) == 2
        update_log = logs[1]  # Most recent log
        assert update_log.action == ActionType.ORGANIZATION_UPDATED
        assert update_log.actor_id == super_admin_id
        assert update_log.organization_id == org_id
        assert "command" in update_log.changes
        assert update_log.changes["command"]["name"] == "Updated Organization"
