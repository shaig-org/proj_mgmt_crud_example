"""Tests for workflow API endpoints."""

from fastapi.testclient import TestClient

from tests.conftest import client, test_repo  # noqa: F401
from tests.fixtures.auth_fixtures import (  # noqa: F401
    org_admin_token,
    project_manager_token,
    read_user_token,
    super_admin_token,
    write_user_token,
)
from tests.helpers import auth_headers


class TestCreateWorkflow:
    """Tests for POST /api/workflows endpoint."""

    def test_create_workflow_as_admin(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test creating workflow as Admin."""
        token, org_id = org_admin_token
        workflow_data = {
            "name": "Kanban Workflow",
            "description": "Standard Kanban workflow",
            "statuses": ["BACKLOG", "TODO", "IN_PROGRESS", "REVIEW", "DONE"],
        }

        response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Kanban Workflow"
        assert data["description"] == "Standard Kanban workflow"
        assert data["statuses"] == ["BACKLOG", "TODO", "IN_PROGRESS", "REVIEW", "DONE"]
        assert data["organization_id"] == org_id
        assert data["is_default"] is False
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_workflow_as_project_manager(
        self, client: TestClient, project_manager_token: tuple[str, str]
    ) -> None:
        """Test creating workflow as Project Manager."""
        token, org_id = project_manager_token
        workflow_data = {
            "name": "Simple Workflow",
            "statuses": ["TODO", "DONE"],
        }

        response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Simple Workflow"
        assert data["statuses"] == ["TODO", "DONE"]
        assert data["organization_id"] == org_id

    def test_create_workflow_as_super_admin_fails(self, client: TestClient, super_admin_token: str) -> None:
        """Test that Super Admin cannot create workflows (has no organization)."""
        # Super Admin has no organization_id, so cannot create workflows
        workflow_data = {
            "name": "Bug Tracking",
            "statuses": ["NEW", "TRIAGED", "ASSIGNED", "RESOLVED", "CLOSED"],
        }

        response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(super_admin_token))

        # Should fail because Super Admin has no organization
        assert response.status_code == 400
        assert "no organization" in response.json()["detail"].lower()

    def test_create_workflow_as_write_user_fails(self, client: TestClient, write_user_token: tuple[str, str]) -> None:
        """Test that Write user cannot create workflows."""
        token, _ = write_user_token
        workflow_data = {"name": "Unauthorized Workflow", "statuses": ["TODO", "DONE"]}

        response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))

        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    def test_create_workflow_as_read_user_fails(self, client: TestClient, read_user_token: tuple[str, str]) -> None:
        """Test that Read user cannot create workflows."""
        token, _ = read_user_token
        workflow_data = {"name": "Unauthorized Workflow", "statuses": ["TODO", "DONE"]}

        response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))

        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    def test_create_workflow_without_description(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test creating workflow without optional description."""
        token, _ = org_admin_token
        workflow_data = {"name": "Name Only Workflow", "statuses": ["TODO", "DONE"]}

        response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))

        assert response.status_code == 201
        data = response.json()
        assert data["description"] is None

    def test_create_workflow_with_single_status(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test creating workflow with minimum number of statuses (1)."""
        token, _ = org_admin_token
        workflow_data = {"name": "Minimal Workflow", "statuses": ["ACTIVE"]}

        response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))

        assert response.status_code == 201
        data = response.json()
        assert data["statuses"] == ["ACTIVE"]

    def test_create_workflow_with_many_statuses(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test creating workflow with many statuses."""
        token, _ = org_admin_token
        statuses = [
            "NEW",
            "TRIAGED",
            "ASSIGNED",
            "IN_PROGRESS",
            "CODE_REVIEW",
            "QA",
            "STAGING",
            "PRODUCTION",
            "RESOLVED",
            "CLOSED",
        ]
        workflow_data = {"name": "Complex Workflow", "statuses": statuses}

        response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))

        assert response.status_code == 201
        data = response.json()
        assert data["statuses"] == statuses

    def test_create_workflow_with_underscores_and_hyphens(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Test creating workflow with status names containing underscores and hyphens."""
        token, _ = org_admin_token
        workflow_data = {
            "name": "Special Characters",
            "statuses": ["IN-PROGRESS", "CODE_REVIEW", "QA_TESTING"],
        }

        response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))

        assert response.status_code == 201
        data = response.json()
        assert "IN-PROGRESS" in data["statuses"]
        assert "CODE_REVIEW" in data["statuses"]
        assert "QA_TESTING" in data["statuses"]

    # Validation tests
    def test_create_workflow_validation_empty_name(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test creating workflow with empty name fails validation."""
        token, _ = org_admin_token
        workflow_data = {"name": "", "statuses": ["TODO", "DONE"]}

        response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))

        assert response.status_code == 422

    def test_create_workflow_validation_empty_statuses(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Test creating workflow with empty statuses array fails validation."""
        token, _ = org_admin_token
        workflow_data = {"name": "Invalid Workflow", "statuses": []}

        response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))

        assert response.status_code == 422

    def test_create_workflow_validation_duplicate_statuses(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Test creating workflow with duplicate status names fails validation."""
        token, _ = org_admin_token
        workflow_data = {
            "name": "Duplicate Status Workflow",
            "statuses": ["TODO", "IN_PROGRESS", "TODO"],  # Duplicate "TODO"
        }

        response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))

        assert response.status_code == 422

    def test_create_workflow_validation_lowercase_status(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Test creating workflow with lowercase status name fails validation."""
        token, _ = org_admin_token
        workflow_data = {
            "name": "Invalid Case Workflow",
            "statuses": ["todo", "DONE"],  # lowercase "todo" should fail
        }

        response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))

        assert response.status_code == 422

    def test_create_workflow_validation_status_with_spaces(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Test creating workflow with status names containing spaces fails validation."""
        token, _ = org_admin_token
        workflow_data = {
            "name": "Space Status Workflow",
            "statuses": ["IN PROGRESS", "DONE"],  # Space should fail
        }

        response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))

        assert response.status_code == 422


class TestGetWorkflow:
    """Tests for GET /api/workflows/{id} endpoint."""

    def test_get_workflow_by_id(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test retrieving workflow by ID."""
        token, org_id = org_admin_token

        # Create workflow
        workflow_data = {"name": "Test Workflow", "statuses": ["TODO", "IN_PROGRESS", "DONE"]}
        create_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))
        workflow_id = create_response.json()["id"]

        # Get workflow
        response = client.get(f"/api/workflows/{workflow_id}", headers=auth_headers(token))

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == workflow_id
        assert data["name"] == "Test Workflow"
        assert data["statuses"] == ["TODO", "IN_PROGRESS", "DONE"]

    def test_get_workflow_not_found(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test getting non-existent workflow returns 404."""
        token, _ = org_admin_token

        response = client.get("/api/workflows/non-existent-id", headers=auth_headers(token))

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_workflow_cross_org_access_denied(
        self, client: TestClient, org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test that non-Super-Admin cannot access workflow from different organization."""
        # Create workflow in org1
        token1, _ = org_admin_token
        workflow_data = {"name": "Org1 Workflow", "statuses": ["TODO", "DONE"]}
        create_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token1))
        workflow_id = create_response.json()["id"]

        # Create another organization with different admin
        org2_response = client.post(
            "/api/organizations",
            json={"name": "Org2"},
            headers=auth_headers(super_admin_token),
        )
        org2_id = org2_response.json()["id"]

        # Create admin in org2
        from tests.helpers import create_admin_user

        admin2_id, admin2_password = create_admin_user(client, super_admin_token, org2_id, username="admin2")

        # Login as org2 admin
        login_response = client.post(
            "/auth/login",
            json={"username": "admin2", "password": admin2_password},
        )
        token2 = login_response.json()["access_token"]

        # Try to access org1's workflow
        response = client.get(f"/api/workflows/{workflow_id}", headers=auth_headers(token2))

        assert response.status_code == 404  # 404 to prevent information leakage

    def test_get_workflow_super_admin_cross_org(
        self, client: TestClient, org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test that Super Admin can access workflows from any organization."""
        # Create workflow in org
        token, _ = org_admin_token
        workflow_data = {"name": "Test Workflow", "statuses": ["TODO", "DONE"]}
        create_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))
        workflow_id = create_response.json()["id"]

        # Super Admin can access
        response = client.get(f"/api/workflows/{workflow_id}", headers=auth_headers(super_admin_token))

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == workflow_id


class TestListWorkflows:
    """Tests for GET /api/workflows endpoint."""

    def test_list_workflows_in_organization(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test listing workflows shows only workflows in user's organization."""
        token, org_id = org_admin_token

        # Create workflows
        workflow1_data = {"name": "Workflow 1", "statuses": ["TODO", "DONE"]}
        client.post("/api/workflows", json=workflow1_data, headers=auth_headers(token))

        workflow2_data = {"name": "Workflow 2", "statuses": ["NEW", "ACTIVE", "CLOSED"]}
        client.post("/api/workflows", json=workflow2_data, headers=auth_headers(token))

        # List workflows
        response = client.get("/api/workflows", headers=auth_headers(token))

        assert response.status_code == 200
        data = response.json()
        # Should have 3: 2 created + 1 default workflow (auto-created with org)
        assert len(data) == 3
        workflow_names = {w["name"] for w in data}
        assert "Workflow 1" in workflow_names
        assert "Workflow 2" in workflow_names
        assert "Default Workflow" in workflow_names

    def test_list_workflows_empty_organization(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test listing workflows when organization has no custom workflows."""
        token, _ = org_admin_token

        # List workflows (should have default workflow auto-created with org)
        response = client.get("/api/workflows", headers=auth_headers(token))

        assert response.status_code == 200
        data = response.json()
        # Organization has default workflow automatically created
        assert len(data) == 1
        assert data[0]["name"] == "Default Workflow"
        assert data[0]["is_default"] is True

    def test_list_workflows_filters_by_organization(
        self, client: TestClient, org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test that non-Super-Admin only sees workflows from their organization."""
        # Create workflow in org1
        token1, _ = org_admin_token
        workflow1_data = {"name": "Org1 Workflow", "statuses": ["TODO", "DONE"]}
        client.post("/api/workflows", json=workflow1_data, headers=auth_headers(token1))

        # Create org2 and workflow
        org2_response = client.post(
            "/api/organizations",
            json={"name": "Org2"},
            headers=auth_headers(super_admin_token),
        )
        org2_id = org2_response.json()["id"]

        from tests.helpers import create_admin_user

        admin2_id, admin2_password = create_admin_user(client, super_admin_token, org2_id, username="admin2")
        login_response = client.post(
            "/auth/login",
            json={"username": "admin2", "password": admin2_password},
        )
        token2 = login_response.json()["access_token"]

        workflow2_data = {"name": "Org2 Workflow", "statuses": ["NEW", "CLOSED"]}
        client.post("/api/workflows", json=workflow2_data, headers=auth_headers(token2))

        # Org1 admin should only see org1 workflows (custom + default)
        response1 = client.get("/api/workflows", headers=auth_headers(token1))
        assert response1.status_code == 200
        data1 = response1.json()
        assert len(data1) == 2  # Custom workflow + default workflow
        workflow1_names = {w["name"] for w in data1}
        assert "Org1 Workflow" in workflow1_names
        assert "Default Workflow" in workflow1_names

        # Org2 admin should only see org2 workflows (custom + default)
        response2 = client.get("/api/workflows", headers=auth_headers(token2))
        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2) == 2  # Custom workflow + default workflow
        workflow2_names = {w["name"] for w in data2}
        assert "Org2 Workflow" in workflow2_names
        assert "Default Workflow" in workflow2_names

    def test_list_workflows_super_admin_sees_all(
        self, client: TestClient, org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test that Super Admin sees workflows from all organizations."""
        # Create workflow in org
        token, _ = org_admin_token
        workflow_data = {"name": "Org Workflow", "statuses": ["TODO", "DONE"]}
        client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))

        # Super Admin lists all workflows
        response = client.get("/api/workflows", headers=auth_headers(super_admin_token))

        assert response.status_code == 200
        data = response.json()
        # Should include at least the workflow we created
        workflow_names = {w["name"] for w in data}
        assert "Org Workflow" in workflow_names


class TestUpdateWorkflow:
    """Tests for PUT /api/workflows/{id} endpoint."""

    def test_update_workflow_name(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test updating workflow name."""
        token, _ = org_admin_token

        # Create workflow
        workflow_data = {"name": "Original Name", "statuses": ["TODO", "DONE"]}
        create_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))
        workflow_id = create_response.json()["id"]

        # Update name
        update_data = {"name": "Updated Name"}
        response = client.put(f"/api/workflows/{workflow_id}", json=update_data, headers=auth_headers(token))

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["statuses"] == ["TODO", "DONE"]  # Statuses unchanged

    def test_update_workflow_description(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test updating workflow description."""
        token, _ = org_admin_token

        # Create workflow
        workflow_data = {
            "name": "Test Workflow",
            "description": "Original description",
            "statuses": ["TODO", "DONE"],
        }
        create_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))
        workflow_id = create_response.json()["id"]

        # Update description
        update_data = {"description": "Updated description"}
        response = client.put(f"/api/workflows/{workflow_id}", json=update_data, headers=auth_headers(token))

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"
        assert data["name"] == "Test Workflow"  # Name unchanged

    def test_update_workflow_statuses(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test updating workflow statuses."""
        token, _ = org_admin_token

        # Create workflow
        workflow_data = {"name": "Test Workflow", "statuses": ["TODO", "DONE"]}
        create_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))
        workflow_id = create_response.json()["id"]

        # Update statuses
        update_data = {"statuses": ["BACKLOG", "TODO", "IN_PROGRESS", "DONE"]}
        response = client.put(f"/api/workflows/{workflow_id}", json=update_data, headers=auth_headers(token))

        assert response.status_code == 200
        data = response.json()
        assert data["statuses"] == ["BACKLOG", "TODO", "IN_PROGRESS", "DONE"]

    def test_update_workflow_multiple_fields(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test updating multiple workflow fields simultaneously."""
        token, _ = org_admin_token

        # Create workflow
        workflow_data = {"name": "Original", "description": "Old desc", "statuses": ["TODO", "DONE"]}
        create_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))
        workflow_id = create_response.json()["id"]

        # Update multiple fields
        update_data = {
            "name": "Updated",
            "description": "New desc",
            "statuses": ["NEW", "ACTIVE", "CLOSED"],
        }
        response = client.put(f"/api/workflows/{workflow_id}", json=update_data, headers=auth_headers(token))

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated"
        assert data["description"] == "New desc"
        assert data["statuses"] == ["NEW", "ACTIVE", "CLOSED"]

    def test_update_workflow_as_project_manager(
        self, client: TestClient, project_manager_token: tuple[str, str]
    ) -> None:
        """Test that Project Manager can update workflows."""
        token, _ = project_manager_token

        # Create workflow
        workflow_data = {"name": "Test Workflow", "statuses": ["TODO", "DONE"]}
        create_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))
        workflow_id = create_response.json()["id"]

        # Update workflow
        update_data = {"name": "Updated by PM"}
        response = client.put(f"/api/workflows/{workflow_id}", json=update_data, headers=auth_headers(token))

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated by PM"

    def test_update_workflow_as_write_user_fails(
        self, client: TestClient, org_admin_token: tuple[str, str], write_user_token: tuple[str, str]
    ) -> None:
        """Test that Write user cannot update workflows."""
        admin_token, _ = org_admin_token

        # Create workflow as admin
        workflow_data = {"name": "Test Workflow", "statuses": ["TODO", "DONE"]}
        create_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(admin_token))
        workflow_id = create_response.json()["id"]

        # Try to update as write user
        write_token, _ = write_user_token
        update_data = {"name": "Unauthorized Update"}
        response = client.put(f"/api/workflows/{workflow_id}", json=update_data, headers=auth_headers(write_token))

        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    def test_update_workflow_not_found(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test updating non-existent workflow returns 404."""
        token, _ = org_admin_token
        update_data = {"name": "New Name"}

        response = client.put("/api/workflows/non-existent-id", json=update_data, headers=auth_headers(token))

        assert response.status_code == 404

    def test_update_workflow_cross_org_denied(
        self, client: TestClient, org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test that non-Super-Admin cannot update workflow from different organization."""
        # Create workflow in org1
        token1, _ = org_admin_token
        workflow_data = {"name": "Org1 Workflow", "statuses": ["TODO", "DONE"]}
        create_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token1))
        workflow_id = create_response.json()["id"]

        # Create org2 admin
        org2_response = client.post(
            "/api/organizations", json={"name": "Org2"}, headers=auth_headers(super_admin_token)
        )
        org2_id = org2_response.json()["id"]

        from tests.helpers import create_admin_user

        admin2_id, admin2_password = create_admin_user(client, super_admin_token, org2_id, username="admin2")
        login_response = client.post("/auth/login", json={"username": "admin2", "password": admin2_password})
        token2 = login_response.json()["access_token"]

        # Try to update org1's workflow
        update_data = {"name": "Unauthorized Update"}
        response = client.put(f"/api/workflows/{workflow_id}", json=update_data, headers=auth_headers(token2))

        assert response.status_code == 403

    def test_update_workflow_validation_empty_statuses(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Test updating workflow with empty statuses fails validation."""
        token, _ = org_admin_token

        # Create workflow
        workflow_data = {"name": "Test Workflow", "statuses": ["TODO", "DONE"]}
        create_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))
        workflow_id = create_response.json()["id"]

        # Try to update with empty statuses
        update_data = {"statuses": []}
        response = client.put(f"/api/workflows/{workflow_id}", json=update_data, headers=auth_headers(token))

        assert response.status_code == 422


class TestDeleteWorkflow:
    """Tests for DELETE /api/workflows/{id} endpoint."""

    def test_delete_workflow_as_admin(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test deleting workflow as Admin."""
        token, _ = org_admin_token

        # Create workflow
        workflow_data = {"name": "To Delete", "statuses": ["TODO", "DONE"]}
        create_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))
        workflow_id = create_response.json()["id"]

        # Delete workflow
        response = client.delete(f"/api/workflows/{workflow_id}", headers=auth_headers(token))

        assert response.status_code == 204

        # Verify deleted
        get_response = client.get(f"/api/workflows/{workflow_id}", headers=auth_headers(token))
        assert get_response.status_code == 404

    def test_delete_workflow_as_super_admin(
        self, client: TestClient, org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test that Super Admin can delete workflows."""
        # Create workflow
        token, _ = org_admin_token
        workflow_data = {"name": "To Delete", "statuses": ["TODO", "DONE"]}
        create_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))
        workflow_id = create_response.json()["id"]

        # Delete as Super Admin
        response = client.delete(f"/api/workflows/{workflow_id}", headers=auth_headers(super_admin_token))

        assert response.status_code == 204

    def test_delete_workflow_as_project_manager_fails(
        self, client: TestClient, project_manager_token: tuple[str, str]
    ) -> None:
        """Test that Project Manager cannot delete workflows."""
        token, _ = project_manager_token

        # Create workflow
        workflow_data = {"name": "Test Workflow", "statuses": ["TODO", "DONE"]}
        create_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))
        workflow_id = create_response.json()["id"]

        # Try to delete
        response = client.delete(f"/api/workflows/{workflow_id}", headers=auth_headers(token))

        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    def test_delete_workflow_as_write_user_fails(
        self, client: TestClient, org_admin_token: tuple[str, str], write_user_token: tuple[str, str]
    ) -> None:
        """Test that Write user cannot delete workflows."""
        # Create workflow as admin
        admin_token, _ = org_admin_token
        workflow_data = {"name": "Test Workflow", "statuses": ["TODO", "DONE"]}
        create_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(admin_token))
        workflow_id = create_response.json()["id"]

        # Try to delete as write user
        write_token, _ = write_user_token
        response = client.delete(f"/api/workflows/{workflow_id}", headers=auth_headers(write_token))

        assert response.status_code == 403

    def test_delete_workflow_not_found(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test deleting non-existent workflow returns 404."""
        token, _ = org_admin_token

        response = client.delete("/api/workflows/non-existent-id", headers=auth_headers(token))

        assert response.status_code == 404

    def test_delete_workflow_cross_org_denied(
        self, client: TestClient, org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test that non-Super-Admin cannot delete workflow from different organization."""
        # Create workflow in org1
        token1, _ = org_admin_token
        workflow_data = {"name": "Org1 Workflow", "statuses": ["TODO", "DONE"]}
        create_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token1))
        workflow_id = create_response.json()["id"]

        # Create org2 admin
        org2_response = client.post(
            "/api/organizations", json={"name": "Org2"}, headers=auth_headers(super_admin_token)
        )
        org2_id = org2_response.json()["id"]

        from tests.helpers import create_admin_user

        admin2_id, admin2_password = create_admin_user(client, super_admin_token, org2_id, username="admin2")
        login_response = client.post("/auth/login", json={"username": "admin2", "password": admin2_password})
        token2 = login_response.json()["access_token"]

        # Try to delete org1's workflow
        response = client.delete(f"/api/workflows/{workflow_id}", headers=auth_headers(token2))

        assert response.status_code == 403

    def test_delete_workflow_removes_from_list(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test that deleted workflow doesn't appear in organization's workflow list."""
        token, _ = org_admin_token

        # Create two workflows
        workflow1_data = {"name": "Workflow 1", "statuses": ["TODO", "DONE"]}
        create1_response = client.post("/api/workflows", json=workflow1_data, headers=auth_headers(token))
        workflow1_id = create1_response.json()["id"]

        workflow2_data = {"name": "Workflow 2", "statuses": ["NEW", "CLOSED"]}
        client.post("/api/workflows", json=workflow2_data, headers=auth_headers(token))

        # Delete first workflow
        client.delete(f"/api/workflows/{workflow1_id}", headers=auth_headers(token))

        # List workflows
        list_response = client.get("/api/workflows", headers=auth_headers(token))
        workflows = list_response.json()

        # Should have 2: Workflow 2 + Default Workflow
        assert len(workflows) == 2
        workflow_names = {w["name"] for w in workflows}
        assert "Workflow 2" in workflow_names
        assert "Default Workflow" in workflow_names
        # Workflow 1 should be gone
        assert "Workflow 1" not in workflow_names


class TestWorkflowCRUDWorkflow:
    """Test complete CRUD workflow for workflows."""

    def test_complete_workflow_crud_lifecycle(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test complete workflow: create, read, update, delete."""
        token, org_id = org_admin_token

        # 1. Create workflow
        workflow_data = {
            "name": "Test Workflow",
            "description": "Test description",
            "statuses": ["TODO", "IN_PROGRESS", "DONE"],
        }
        create_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))
        assert create_response.status_code == 201
        workflow_id = create_response.json()["id"]

        # 2. Read workflow
        get_response = client.get(f"/api/workflows/{workflow_id}", headers=auth_headers(token))
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "Test Workflow"

        # 3. List workflows
        list_response = client.get("/api/workflows", headers=auth_headers(token))
        assert list_response.status_code == 200
        assert len(list_response.json()) >= 1

        # 4. Update workflow
        update_data = {"name": "Updated Workflow", "description": "Updated description"}
        update_response = client.put(f"/api/workflows/{workflow_id}", json=update_data, headers=auth_headers(token))
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Updated Workflow"

        # 5. Delete workflow
        delete_response = client.delete(f"/api/workflows/{workflow_id}", headers=auth_headers(token))
        assert delete_response.status_code == 204

        # 6. Verify deletion
        final_get = client.get(f"/api/workflows/{workflow_id}", headers=auth_headers(token))
        assert final_get.status_code == 404


class TestWorkflowConstraints:
    """Test workflow constraints (REQ-WORKFLOW-005, REQ-WORKFLOW-006)."""

    def test_cannot_delete_default_workflow(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test that default workflow cannot be deleted (REQ-WORKFLOW-006)."""
        token, org_id = org_admin_token

        # Get default workflow for this organization
        list_response = client.get("/api/workflows", headers=auth_headers(token))
        workflows = list_response.json()

        default_workflow = next((w for w in workflows if w["is_default"] is True), None)
        assert default_workflow is not None, "Organization should have a default workflow"

        # Try to delete default workflow - should fail
        response = client.delete(f"/api/workflows/{default_workflow['id']}", headers=auth_headers(token))

        assert response.status_code == 400
        error = response.json()
        assert "Cannot delete default workflow" in error["detail"]

    def test_cannot_delete_workflow_in_use_by_projects(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Test that workflow cannot be deleted if projects use it (REQ-WORKFLOW-005)."""
        token, org_id = org_admin_token

        # Create custom workflow
        workflow_data = {"name": "Custom Workflow", "statuses": ["BACKLOG", "DOING", "DONE"]}
        workflow_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))
        assert workflow_response.status_code == 201
        workflow_id = workflow_response.json()["id"]

        # Create project using this workflow
        project_data = {"name": "Test Project", "workflow_id": workflow_id}
        project_response = client.post("/api/projects", json=project_data, headers=auth_headers(token))
        assert project_response.status_code == 201

        # Try to delete workflow - should fail because project uses it
        response = client.delete(f"/api/workflows/{workflow_id}", headers=auth_headers(token))

        assert response.status_code == 400
        error = response.json()
        assert "Cannot delete workflow" in error["detail"]
        assert "project" in error["detail"].lower()

    def test_can_delete_unused_workflow(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test that workflow can be deleted if no projects use it (REQ-WORKFLOW-005)."""
        token, org_id = org_admin_token

        # Create custom workflow
        workflow_data = {"name": "Unused Workflow", "statuses": ["TODO", "DONE"]}
        workflow_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))
        assert workflow_response.status_code == 201
        workflow_id = workflow_response.json()["id"]

        # Delete workflow - should succeed because no projects use it
        response = client.delete(f"/api/workflows/{workflow_id}", headers=auth_headers(token))

        assert response.status_code == 204

        # Verify deletion
        get_response = client.get(f"/api/workflows/{workflow_id}", headers=auth_headers(token))
        assert get_response.status_code == 404

    def test_cannot_change_is_default_flag(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test that is_default flag cannot be changed via update (REQ-WORKFLOW-006)."""
        token, org_id = org_admin_token

        # Get default workflow
        list_response = client.get("/api/workflows", headers=auth_headers(token))
        workflows = list_response.json()
        default_workflow = next((w for w in workflows if w["is_default"] is True), None)
        assert default_workflow is not None

        # Try to update is_default to false - should be ignored
        update_data = {"is_default": False}
        response = client.put(f"/api/workflows/{default_workflow['id']}", json=update_data, headers=auth_headers(token))

        assert response.status_code == 200
        updated = response.json()
        assert updated["is_default"] is True, "is_default flag should not change"

    def test_cannot_create_second_default_workflow(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test that cannot create second default workflow (REQ-WORKFLOW-006)."""
        token, org_id = org_admin_token

        # Try to create workflow with is_default=true
        workflow_data = {"name": "Another Default", "statuses": ["TODO", "DONE"], "is_default": True}
        response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))

        # Should either reject or ignore is_default flag (creating as non-default)
        if response.status_code == 201:
            # If creation succeeds, is_default should be ignored
            created = response.json()
            assert created["is_default"] is False, "Should not allow creating second default workflow"
        else:
            # Or it should reject with 400
            assert response.status_code == 400


class TestWorkflowBreakingChanges:
    """Test workflow updates that would break existing tickets (REQ-WORKFLOW-009)."""

    def test_cannot_remove_status_used_by_tickets(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test that cannot remove status if tickets use it (REQ-WORKFLOW-009)."""
        token, org_id = org_admin_token

        # Create custom workflow
        workflow_data = {"name": "Dev Workflow", "statuses": ["TODO", "IN_PROGRESS", "REVIEW", "DONE"]}
        workflow_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))
        workflow_id = workflow_response.json()["id"]

        # Create project with this workflow
        project_data = {"name": "Test Project", "workflow_id": workflow_id}
        project_response = client.post("/api/projects", json=project_data, headers=auth_headers(token))
        project_id = project_response.json()["id"]

        # Create ticket with status "REVIEW"
        ticket_data = {"title": "Test Ticket", "status": "REVIEW"}
        ticket_response = client.post(
            "/api/tickets", json=ticket_data, params={"project_id": project_id}, headers=auth_headers(token)
        )
        assert ticket_response.status_code == 201

        # Try to update workflow removing "REVIEW" status - should fail
        update_data = {"statuses": ["TODO", "IN_PROGRESS", "DONE"]}  # Removed REVIEW
        response = client.put(f"/api/workflows/{workflow_id}", json=update_data, headers=auth_headers(token))

        assert response.status_code == 400
        error = response.json()
        assert "Cannot update workflow" in error["detail"] or "would make tickets invalid" in error["detail"].lower()
        assert "REVIEW" in error["detail"]

    def test_can_add_status_to_workflow(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test that adding statuses always succeeds (REQ-WORKFLOW-009)."""
        token, org_id = org_admin_token

        # Create custom workflow
        workflow_data = {"name": "Simple Workflow", "statuses": ["TODO", "DONE"]}
        workflow_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))
        workflow_id = workflow_response.json()["id"]

        # Create project with this workflow
        project_data = {"name": "Test Project", "workflow_id": workflow_id}
        project_response = client.post("/api/projects", json=project_data, headers=auth_headers(token))
        project_id = project_response.json()["id"]

        # Create ticket
        ticket_data = {"title": "Test Ticket"}
        ticket_response = client.post(
            "/api/tickets", json=ticket_data, params={"project_id": project_id}, headers=auth_headers(token)
        )
        assert ticket_response.status_code == 201

        # Add new status - should succeed
        update_data = {"statuses": ["TODO", "IN_PROGRESS", "DONE"]}  # Added IN_PROGRESS
        response = client.put(f"/api/workflows/{workflow_id}", json=update_data, headers=auth_headers(token))

        assert response.status_code == 200
        updated = response.json()
        assert "IN_PROGRESS" in updated["statuses"]

    def test_can_remove_unused_status_from_workflow(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test that removing unused status succeeds (REQ-WORKFLOW-009)."""
        token, org_id = org_admin_token

        # Create custom workflow
        workflow_data = {"name": "Full Workflow", "statuses": ["TODO", "IN_PROGRESS", "BLOCKED", "DONE"]}
        workflow_response = client.post("/api/workflows", json=workflow_data, headers=auth_headers(token))
        workflow_id = workflow_response.json()["id"]

        # Create project with this workflow
        project_data = {"name": "Test Project", "workflow_id": workflow_id}
        project_response = client.post("/api/projects", json=project_data, headers=auth_headers(token))
        project_id = project_response.json()["id"]

        # Create ticket with status "TODO" (not BLOCKED)
        ticket_data = {"title": "Test Ticket", "status": "TODO"}
        ticket_response = client.post(
            "/api/tickets", json=ticket_data, params={"project_id": project_id}, headers=auth_headers(token)
        )
        assert ticket_response.status_code == 201

        # Remove unused "BLOCKED" status - should succeed
        update_data = {"statuses": ["TODO", "IN_PROGRESS", "DONE"]}  # Removed BLOCKED (unused)
        response = client.put(f"/api/workflows/{workflow_id}", json=update_data, headers=auth_headers(token))

        assert response.status_code == 200
        updated = response.json()
        assert "BLOCKED" not in updated["statuses"]
        assert len(updated["statuses"]) == 3
