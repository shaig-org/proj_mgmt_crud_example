"""Tests for epic API endpoints."""

from fastapi.testclient import TestClient

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import ActionType
from tests.conftest import client, test_repo  # noqa: F401
from tests.fixtures.auth_fixtures import (  # noqa: F401
    org_admin_token,
    project_manager_token,
    read_user_token,
    super_admin_token,
    write_user_token,
)
from tests.helpers import (
    auth_headers,
    create_admin_user,
    create_project_manager,
    create_test_epic,
    create_test_org,
    create_test_project,
    create_test_ticket,
)


class TestCreateEpic:
    """Tests for POST /api/epics endpoint."""

    def test_create_epic_as_admin(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test creating epic as Admin."""
        token, org_id = org_admin_token
        epic_data = {"name": "Launch V1", "description": "MVP launch epic"}

        response = client.post("/api/epics", json=epic_data, headers=auth_headers(token))

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Launch V1"
        assert data["description"] == "MVP launch epic"
        assert data["organization_id"] == org_id
        assert "id" in data

    def test_create_epic_as_project_manager(self, client: TestClient, project_manager_token: tuple[str, str]) -> None:
        """Test creating epic as Project Manager."""
        token, org_id = project_manager_token
        epic_data = {"name": "Q1 Goals"}

        response = client.post("/api/epics", json=epic_data, headers=auth_headers(token))

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Q1 Goals"

    def test_create_epic_as_write_user_fails(self, client: TestClient, write_user_token: tuple[str, str]) -> None:
        """Test that Write user cannot create epics."""
        token, _ = write_user_token
        epic_data = {"name": "Unauthorized Epic"}

        response = client.post("/api/epics", json=epic_data, headers=auth_headers(token))

        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    def test_create_epic_without_description(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test creating epic without optional description."""
        token, _ = org_admin_token
        epic_data = {"name": "Name Only Epic"}

        response = client.post("/api/epics", json=epic_data, headers=auth_headers(token))

        assert response.status_code == 201
        data = response.json()
        assert data["description"] is None

    def test_create_epic_validation_empty_name(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test creating epic with empty name fails validation."""
        token, _ = org_admin_token
        epic_data = {"name": ""}

        response = client.post("/api/epics", json=epic_data, headers=auth_headers(token))

        assert response.status_code == 422

    def test_create_epic_user_without_organization_fails(
        self, client: TestClient, super_admin_token: str, test_repo: Repository
    ) -> None:
        """Test creating epic when user has no organization fails."""
        # Create a user without organization directly via repository (bypassing API validation)
        from project_management_crud_example.domain_models import UserCreateCommand, UserData, UserRole

        user_data = UserData(username="orphan_user", email="orphan@test.com", full_name="Orphan User")
        command = UserCreateCommand(user_data=user_data, password="password", organization_id=None, role=UserRole.ADMIN)
        test_repo.users.create(command)

        # Login as this user
        login_response = client.post("/auth/login", json={"username": "orphan_user", "password": "password"})
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        # Try to create epic
        epic_data = {"name": "Test Epic"}
        response = client.post("/api/epics", json=epic_data, headers=auth_headers(token))

        assert response.status_code == 400
        assert "User has no organization" in response.json()["detail"]


class TestGetEpic:
    """Tests for GET /api/epics/{id} endpoint."""

    def test_get_epic_by_id(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test retrieving epic by ID."""
        token, org_id = org_admin_token
        epic_id = create_test_epic(client, token, "Test Epic")

        response = client.get(f"/api/epics/{epic_id}", headers=auth_headers(token))

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == epic_id
        assert data["name"] == "Test Epic"

    def test_get_epic_not_found(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test getting non-existent epic returns 404."""
        token, _ = org_admin_token

        response = client.get("/api/epics/nonexistent-id", headers=auth_headers(token))

        assert response.status_code == 404

    def test_get_epic_from_different_org_fails(
        self, client: TestClient, org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test cannot get epic from different organization."""
        token, _ = org_admin_token

        # Create epic in different org
        other_org_id = create_test_org(client, super_admin_token, "Other Org")
        _, other_admin_password = create_admin_user(client, super_admin_token, other_org_id, username="other_admin")
        login_resp = client.post("/auth/login", json={"username": "other_admin", "password": other_admin_password})
        other_token = login_resp.json()["access_token"]
        epic_id = create_test_epic(client, other_token, "Other Epic")

        # Try to get from first org
        response = client.get(f"/api/epics/{epic_id}", headers=auth_headers(token))

        assert response.status_code == 403
        assert "different organization" in response.json()["detail"]


class TestListEpics:
    """Tests for GET /api/epics endpoint."""

    def test_list_epics_in_organization(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test listing epics returns only organization's epics."""
        token, org_id = org_admin_token

        create_test_epic(client, token, "Epic 1")
        create_test_epic(client, token, "Epic 2")

        response = client.get("/api/epics", headers=auth_headers(token))

        assert response.status_code == 200
        epics = response.json()
        assert len(epics) == 2
        assert all(e["organization_id"] == org_id for e in epics)

    def test_list_epics_empty(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test listing epics when none exist returns empty array."""
        token, _ = org_admin_token

        response = client.get("/api/epics", headers=auth_headers(token))

        assert response.status_code == 200
        assert response.json() == []

    def test_list_epics_super_admin_sees_all(
        self, client: TestClient, super_admin_token: str, org_admin_token: tuple[str, str]
    ) -> None:
        """Test Super Admin sees epics from all organizations."""
        # Create epic in org
        org_token, _ = org_admin_token
        create_test_epic(client, org_token, "Org Epic")

        # Super Admin lists all
        response = client.get("/api/epics", headers=auth_headers(super_admin_token))

        assert response.status_code == 200
        epics = response.json()
        assert len(epics) >= 1  # At least the one we created


class TestUpdateEpic:
    """Tests for PUT /api/epics/{id} endpoint."""

    def test_update_epic_name(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test updating epic name."""
        token, _ = org_admin_token
        epic_id = create_test_epic(client, token, "Old Name")

        response = client.put(f"/api/epics/{epic_id}", json={"name": "New Name"}, headers=auth_headers(token))

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"

    def test_update_epic_description(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test updating epic description."""
        token, _ = org_admin_token
        epic_id = create_test_epic(client, token, "Epic")

        response = client.put(
            f"/api/epics/{epic_id}", json={"description": "New description"}, headers=auth_headers(token)
        )

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "New description"

    def test_update_epic_as_project_manager(self, client: TestClient, project_manager_token: tuple[str, str]) -> None:
        """Test Project Manager can update epic."""
        token, _ = project_manager_token
        epic_id = create_test_epic(client, token, "PM Epic")

        response = client.put(f"/api/epics/{epic_id}", json={"name": "Updated"}, headers=auth_headers(token))

        assert response.status_code == 200

    def test_update_epic_as_write_user_fails(
        self, client: TestClient, write_user_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test Write user cannot update epic."""
        write_token, org_id = write_user_token

        # Create PM to create epic
        _, pm_password = create_project_manager(client, super_admin_token, org_id, username="pm_for_update")
        login_resp = client.post("/auth/login", json={"username": "pm_for_update", "password": pm_password})
        pm_token = login_resp.json()["access_token"]
        epic_id = create_test_epic(client, pm_token, "Epic")

        # Try to update as write user
        response = client.put(f"/api/epics/{epic_id}", json={"name": "Hacked"}, headers=auth_headers(write_token))

        assert response.status_code == 403

    def test_update_epic_not_found(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test updating non-existent epic returns 404."""
        token, _ = org_admin_token

        response = client.put("/api/epics/nonexistent", json={"name": "New"}, headers=auth_headers(token))

        assert response.status_code == 404

    def test_update_epic_from_different_org_fails(self, client: TestClient, super_admin_token: str) -> None:
        """Test non-Super Admin cannot update epic from different organization."""
        # Create two organizations
        org1_id = create_test_org(client, super_admin_token, "Org 1")
        org2_id = create_test_org(client, super_admin_token, "Org 2")

        # Create admin users for each org
        admin1_id, admin1_pass = create_admin_user(client, super_admin_token, org1_id, username="admin1")
        admin2_id, admin2_pass = create_admin_user(client, super_admin_token, org2_id, username="admin2")

        # Login as both admins
        login1 = client.post("/auth/login", json={"username": "admin1", "password": admin1_pass})
        token1 = login1.json()["access_token"]

        login2 = client.post("/auth/login", json={"username": "admin2", "password": admin2_pass})
        token2 = login2.json()["access_token"]

        # Create epic in org1
        epic_id = create_test_epic(client, token1, "Org1 Epic")

        # Try to update org1 epic from org2 admin
        response = client.put(f"/api/epics/{epic_id}", json={"name": "Hacked"}, headers=auth_headers(token2))

        assert response.status_code == 403
        assert "different organization" in response.json()["detail"]


class TestDeleteEpic:
    """Tests for DELETE /api/epics/{id} endpoint."""

    def test_delete_epic_as_admin(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test deleting epic as Admin."""
        token, _ = org_admin_token
        epic_id = create_test_epic(client, token, "To Delete")

        response = client.delete(f"/api/epics/{epic_id}", headers=auth_headers(token))

        assert response.status_code == 204

        # Verify deletion
        get_response = client.get(f"/api/epics/{epic_id}", headers=auth_headers(token))
        assert get_response.status_code == 404

    def test_delete_epic_as_project_manager_fails(
        self, client: TestClient, project_manager_token: tuple[str, str]
    ) -> None:
        """Test Project Manager cannot delete epic."""
        token, _ = project_manager_token
        epic_id = create_test_epic(client, token, "PM Epic")

        response = client.delete(f"/api/epics/{epic_id}", headers=auth_headers(token))

        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    def test_delete_epic_not_found(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test deleting non-existent epic returns 404."""
        token, _ = org_admin_token

        response = client.delete("/api/epics/nonexistent", headers=auth_headers(token))

        assert response.status_code == 404


class TestEpicWorkflows:
    """Test complete epic workflows."""

    def test_complete_epic_crud_workflow(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test complete CRUD workflow for an epic."""
        token, org_id = org_admin_token

        # 1. Create epic
        create_response = client.post(
            "/api/epics", json={"name": "Workflow Epic", "description": "Test"}, headers=auth_headers(token)
        )
        assert create_response.status_code == 201
        epic_id = create_response.json()["id"]

        # 2. Get epic
        get_response = client.get(f"/api/epics/{epic_id}", headers=auth_headers(token))
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "Workflow Epic"

        # 3. List epics
        list_response = client.get("/api/epics", headers=auth_headers(token))
        assert any(e["id"] == epic_id for e in list_response.json())

        # 4. Update epic
        update_response = client.put(
            f"/api/epics/{epic_id}", json={"name": "Updated Epic"}, headers=auth_headers(token)
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Updated Epic"

        # 5. Delete epic
        delete_response = client.delete(f"/api/epics/{epic_id}", headers=auth_headers(token))
        assert delete_response.status_code == 204

        # 6. Verify deletion
        final_get = client.get(f"/api/epics/{epic_id}", headers=auth_headers(token))
        assert final_get.status_code == 404


class TestAddTicketToEpic:
    """Tests for POST /api/epics/{epic_id}/tickets endpoint."""

    def test_add_ticket_to_epic_as_admin(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test adding a ticket to an epic as Admin."""
        token, org_id = org_admin_token

        # Create project, epic, and ticket
        project_id = create_test_project(client, token, "Test Project")
        epic_id = create_test_epic(client, token, "Test Epic")

        # Create ticket
        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Test Ticket", "description": "Test"},
            params={"project_id": project_id},
            headers=auth_headers(token),
        )
        assert ticket_response.status_code == 201
        ticket_id = ticket_response.json()["id"]

        # Add ticket to epic
        response = client.post(
            f"/api/epics/{epic_id}/tickets", params={"ticket_id": ticket_id}, headers=auth_headers(token)
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Ticket added to epic successfully"

    def test_add_ticket_to_epic_as_project_manager(
        self, client: TestClient, project_manager_token: tuple[str, str]
    ) -> None:
        """Test adding ticket to epic as Project Manager."""
        token, org_id = project_manager_token

        project_id = create_test_project(client, token, "PM Project")
        epic_id = create_test_epic(client, token, "PM Epic")

        ticket_response = client.post(
            "/api/tickets",
            json={"title": "PM Ticket", "description": "Test"},
            params={"project_id": project_id},
            headers=auth_headers(token),
        )
        ticket_id = ticket_response.json()["id"]

        response = client.post(
            f"/api/epics/{epic_id}/tickets", params={"ticket_id": ticket_id}, headers=auth_headers(token)
        )

        assert response.status_code == 200

    def test_add_ticket_to_epic_as_write_user_fails(
        self, client: TestClient, write_user_token: tuple[str, str], org_admin_token: tuple[str, str]
    ) -> None:
        """Test Write Access user cannot add tickets to epic."""
        admin_token, org_id = org_admin_token
        write_token, _ = write_user_token

        project_id = create_test_project(client, admin_token, "Project")
        epic_id = create_test_epic(client, admin_token, "Epic")

        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Ticket", "description": "Test"},
            params={"project_id": project_id},
            headers=auth_headers(admin_token),
        )
        ticket_id = ticket_response.json()["id"]

        response = client.post(
            f"/api/epics/{epic_id}/tickets", params={"ticket_id": ticket_id}, headers=auth_headers(write_token)
        )

        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    def test_add_ticket_to_epic_idempotent(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test adding same ticket twice is idempotent."""
        token, org_id = org_admin_token

        project_id = create_test_project(client, token, "Project")
        epic_id = create_test_epic(client, token, "Epic")

        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Ticket", "description": "Test"},
            params={"project_id": project_id},
            headers=auth_headers(token),
        )
        ticket_id = ticket_response.json()["id"]

        # Add ticket twice
        response1 = client.post(
            f"/api/epics/{epic_id}/tickets", params={"ticket_id": ticket_id}, headers=auth_headers(token)
        )
        response2 = client.post(
            f"/api/epics/{epic_id}/tickets", params={"ticket_id": ticket_id}, headers=auth_headers(token)
        )

        assert response1.status_code == 200
        assert response2.status_code == 200

    def test_add_ticket_to_nonexistent_epic(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test adding ticket to non-existent epic returns 404."""
        token, org_id = org_admin_token

        project_id = create_test_project(client, token, "Project")
        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Ticket", "description": "Test"},
            params={"project_id": project_id},
            headers=auth_headers(token),
        )
        ticket_id = ticket_response.json()["id"]

        response = client.post(
            "/api/epics/nonexistent/tickets", params={"ticket_id": ticket_id}, headers=auth_headers(token)
        )

        assert response.status_code == 404

    def test_add_nonexistent_ticket_to_epic(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test adding non-existent ticket to epic returns 404."""
        token, org_id = org_admin_token

        epic_id = create_test_epic(client, token, "Epic")

        response = client.post(
            f"/api/epics/{epic_id}/tickets", params={"ticket_id": "nonexistent"}, headers=auth_headers(token)
        )

        assert response.status_code == 404

    def test_add_cross_organization_ticket_to_epic(
        self, client: TestClient, super_admin_token: str, org_admin_token: tuple[str, str]
    ) -> None:
        """Test cannot add ticket from different organization to epic."""
        # Create two organizations
        org1_id = create_test_org(client, super_admin_token, "Org 1")
        org2_id = create_test_org(client, super_admin_token, "Org 2")

        # Create admin users for each org
        admin1_id, admin1_pass = create_admin_user(client, super_admin_token, org1_id, username="admin1")
        admin2_id, admin2_pass = create_admin_user(client, super_admin_token, org2_id, username="admin2")

        # Login as both admins
        login1 = client.post("/auth/login", json={"username": "admin1", "password": admin1_pass})
        token1 = login1.json()["access_token"]

        login2 = client.post("/auth/login", json={"username": "admin2", "password": admin2_pass})
        token2 = login2.json()["access_token"]

        # Create epic in org1
        epic_id = create_test_epic(client, token1, "Org1 Epic")

        # Create project and ticket in org2
        project_id = create_test_project(client, token2, "Org2 Project")
        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Org2 Ticket", "description": "Test"},
            params={"project_id": project_id},
            headers=auth_headers(token2),
        )
        ticket_id = ticket_response.json()["id"]

        # Try to add org2 ticket to org1 epic
        response = client.post(
            f"/api/epics/{epic_id}/tickets", params={"ticket_id": ticket_id}, headers=auth_headers(token1)
        )

        assert response.status_code == 403
        assert "different organization" in response.json()["detail"]

    def test_add_ticket_to_epic_project_not_found(
        self, client: TestClient, org_admin_token: tuple[str, str], test_repo: Repository
    ) -> None:
        """Test adding ticket to epic when ticket's project is missing (data integrity issue)."""
        token, org_id = org_admin_token

        # Create epic, project, and ticket
        epic_id = create_test_epic(client, token, "Epic")
        project_id = create_test_project(client, token, "Project")
        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Ticket", "description": "Test"},
            params={"project_id": project_id},
            headers=auth_headers(token),
        )
        ticket_id = ticket_response.json()["id"]

        # Delete project directly via repository (simulating data integrity issue)
        test_repo.projects.delete(project_id)

        # Try to add ticket to epic - should fail because project is gone
        response = client.post(
            f"/api/epics/{epic_id}/tickets", params={"ticket_id": ticket_id}, headers=auth_headers(token)
        )

        assert response.status_code == 500
        assert "project not found" in response.json()["detail"].lower()

    def test_add_ticket_to_epic_from_different_org_user_fails(self, client: TestClient, super_admin_token: str) -> None:
        """Test user from different organization cannot add ticket to epic."""
        # Create two organizations
        org1_id = create_test_org(client, super_admin_token, "Org 1")
        org2_id = create_test_org(client, super_admin_token, "Org 2")

        # Create admin users for each org
        admin1_id, admin1_pass = create_admin_user(client, super_admin_token, org1_id, username="admin1")
        admin2_id, admin2_pass = create_admin_user(client, super_admin_token, org2_id, username="admin2")

        # Login as both admins
        login1 = client.post("/auth/login", json={"username": "admin1", "password": admin1_pass})
        token1 = login1.json()["access_token"]

        login2 = client.post("/auth/login", json={"username": "admin2", "password": admin2_pass})
        token2 = login2.json()["access_token"]

        # Create epic and project and ticket in org1
        epic_id = create_test_epic(client, token1, "Org1 Epic")
        project_id = create_test_project(client, token1, "Org1 Project")
        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Org1 Ticket", "description": "Test"},
            params={"project_id": project_id},
            headers=auth_headers(token1),
        )
        ticket_id = ticket_response.json()["id"]

        # Try to add org1 ticket to org1 epic from org2 user (user from different org)
        response = client.post(
            f"/api/epics/{epic_id}/tickets", params={"ticket_id": ticket_id}, headers=auth_headers(token2)
        )

        assert response.status_code == 403
        assert "different organization" in response.json()["detail"]


class TestRemoveTicketFromEpic:
    """Tests for DELETE /api/epics/{epic_id}/tickets/{ticket_id} endpoint."""

    def test_remove_ticket_from_epic_as_admin(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test removing ticket from epic as Admin."""
        token, org_id = org_admin_token

        project_id = create_test_project(client, token, "Project")
        epic_id = create_test_epic(client, token, "Epic")

        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Ticket", "description": "Test"},
            params={"project_id": project_id},
            headers=auth_headers(token),
        )
        ticket_id = ticket_response.json()["id"]

        # Add ticket to epic
        client.post(f"/api/epics/{epic_id}/tickets", params={"ticket_id": ticket_id}, headers=auth_headers(token))

        # Remove ticket from epic
        response = client.delete(f"/api/epics/{epic_id}/tickets/{ticket_id}", headers=auth_headers(token))

        assert response.status_code == 204

    def test_remove_ticket_from_epic_as_project_manager(
        self, client: TestClient, project_manager_token: tuple[str, str]
    ) -> None:
        """Test removing ticket from epic as Project Manager."""
        token, org_id = project_manager_token

        project_id = create_test_project(client, token, "Project")
        epic_id = create_test_epic(client, token, "Epic")

        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Ticket", "description": "Test"},
            params={"project_id": project_id},
            headers=auth_headers(token),
        )
        ticket_id = ticket_response.json()["id"]

        client.post(f"/api/epics/{epic_id}/tickets", params={"ticket_id": ticket_id}, headers=auth_headers(token))

        response = client.delete(f"/api/epics/{epic_id}/tickets/{ticket_id}", headers=auth_headers(token))

        assert response.status_code == 204

    def test_remove_ticket_from_epic_as_write_user_fails(
        self, client: TestClient, write_user_token: tuple[str, str], org_admin_token: tuple[str, str]
    ) -> None:
        """Test Write Access user cannot remove tickets from epic."""
        admin_token, org_id = org_admin_token
        write_token, _ = write_user_token

        project_id = create_test_project(client, admin_token, "Project")
        epic_id = create_test_epic(client, admin_token, "Epic")

        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Ticket", "description": "Test"},
            params={"project_id": project_id},
            headers=auth_headers(admin_token),
        )
        ticket_id = ticket_response.json()["id"]

        client.post(f"/api/epics/{epic_id}/tickets", params={"ticket_id": ticket_id}, headers=auth_headers(admin_token))

        response = client.delete(f"/api/epics/{epic_id}/tickets/{ticket_id}", headers=auth_headers(write_token))

        assert response.status_code == 403

    def test_remove_ticket_idempotent(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test removing ticket not in epic succeeds (idempotent)."""
        token, org_id = org_admin_token

        project_id = create_test_project(client, token, "Project")
        epic_id = create_test_epic(client, token, "Epic")

        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Ticket", "description": "Test"},
            params={"project_id": project_id},
            headers=auth_headers(token),
        )
        ticket_id = ticket_response.json()["id"]

        # Remove without adding (idempotent)
        response = client.delete(f"/api/epics/{epic_id}/tickets/{ticket_id}", headers=auth_headers(token))

        assert response.status_code == 204

    def test_remove_ticket_doesnt_delete_ticket(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test removing ticket from epic doesn't delete the ticket."""
        token, org_id = org_admin_token

        project_id = create_test_project(client, token, "Project")
        epic_id = create_test_epic(client, token, "Epic")

        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Ticket", "description": "Test"},
            params={"project_id": project_id},
            headers=auth_headers(token),
        )
        ticket_id = ticket_response.json()["id"]

        client.post(f"/api/epics/{epic_id}/tickets", params={"ticket_id": ticket_id}, headers=auth_headers(token))
        client.delete(f"/api/epics/{epic_id}/tickets/{ticket_id}", headers=auth_headers(token))

        # Verify ticket still exists
        ticket_get = client.get(f"/api/tickets/{ticket_id}", headers=auth_headers(token))
        assert ticket_get.status_code == 200

    def test_remove_ticket_from_epic_project_not_found(
        self, client: TestClient, org_admin_token: tuple[str, str], test_repo: Repository
    ) -> None:
        """Test removing ticket from epic when ticket's project is missing (data integrity issue)."""
        token, org_id = org_admin_token

        # Create epic, project, and ticket
        epic_id = create_test_epic(client, token, "Epic")
        project_id = create_test_project(client, token, "Project")
        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Ticket", "description": "Test"},
            params={"project_id": project_id},
            headers=auth_headers(token),
        )
        ticket_id = ticket_response.json()["id"]

        # Add ticket to epic
        client.post(f"/api/epics/{epic_id}/tickets", params={"ticket_id": ticket_id}, headers=auth_headers(token))

        # Delete project directly via repository (simulating data integrity issue)
        test_repo.projects.delete(project_id)

        # Try to remove ticket from epic - should fail because project is gone
        response = client.delete(f"/api/epics/{epic_id}/tickets/{ticket_id}", headers=auth_headers(token))

        assert response.status_code == 500
        assert "project not found" in response.json()["detail"].lower()

    def test_remove_ticket_from_epic_from_different_org_user_fails(
        self, client: TestClient, super_admin_token: str
    ) -> None:
        """Test user from different organization cannot remove ticket from epic."""
        # Create two organizations
        org1_id = create_test_org(client, super_admin_token, "Org 1")
        org2_id = create_test_org(client, super_admin_token, "Org 2")

        # Create admin users for each org
        admin1_id, admin1_pass = create_admin_user(client, super_admin_token, org1_id, username="admin1")
        admin2_id, admin2_pass = create_admin_user(client, super_admin_token, org2_id, username="admin2")

        # Login as both admins
        login1 = client.post("/auth/login", json={"username": "admin1", "password": admin1_pass})
        token1 = login1.json()["access_token"]

        login2 = client.post("/auth/login", json={"username": "admin2", "password": admin2_pass})
        token2 = login2.json()["access_token"]

        # Create epic, project, and ticket in org1
        epic_id = create_test_epic(client, token1, "Org1 Epic")
        project_id = create_test_project(client, token1, "Org1 Project")
        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Org1 Ticket", "description": "Test"},
            params={"project_id": project_id},
            headers=auth_headers(token1),
        )
        ticket_id = ticket_response.json()["id"]

        # Add ticket to epic in org1
        client.post(f"/api/epics/{epic_id}/tickets", params={"ticket_id": ticket_id}, headers=auth_headers(token1))

        # Try to remove org1 ticket from org1 epic as org2 user
        response = client.delete(f"/api/epics/{epic_id}/tickets/{ticket_id}", headers=auth_headers(token2))

        assert response.status_code == 403
        assert "different organization" in response.json()["detail"]

    def test_remove_cross_organization_ticket_from_epic(self, client: TestClient, super_admin_token: str) -> None:
        """Test cannot remove ticket from different organization from epic."""
        # Create two organizations
        org1_id = create_test_org(client, super_admin_token, "Org 1")
        org2_id = create_test_org(client, super_admin_token, "Org 2")

        # Create admin users for each org
        admin1_id, admin1_pass = create_admin_user(client, super_admin_token, org1_id, username="admin1")
        admin2_id, admin2_pass = create_admin_user(client, super_admin_token, org2_id, username="admin2")

        # Login as both admins
        login1 = client.post("/auth/login", json={"username": "admin1", "password": admin1_pass})
        token1 = login1.json()["access_token"]

        login2 = client.post("/auth/login", json={"username": "admin2", "password": admin2_pass})
        token2 = login2.json()["access_token"]

        # Create epic in org1
        epic_id = create_test_epic(client, token1, "Org1 Epic")

        # Create project and ticket in org2
        project_id = create_test_project(client, token2, "Org2 Project")
        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Org2 Ticket", "description": "Test"},
            params={"project_id": project_id},
            headers=auth_headers(token2),
        )
        ticket_id = ticket_response.json()["id"]

        # Try to remove org2 ticket from org1 epic (even though not added, should still check org)
        response = client.delete(f"/api/epics/{epic_id}/tickets/{ticket_id}", headers=auth_headers(token1))

        assert response.status_code == 403
        assert "different organization" in response.json()["detail"]


class TestGetEpicTickets:
    """Tests for GET /api/epics/{epic_id}/tickets endpoint."""

    def test_get_epic_tickets(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test getting all tickets in an epic."""
        token, org_id = org_admin_token

        project_id = create_test_project(client, token, "Project")
        epic_id = create_test_epic(client, token, "Epic")

        # Create and add multiple tickets
        ticket_ids = []
        for i in range(3):
            ticket_response = client.post(
                "/api/tickets",
                json={"title": f"Ticket {i}", "description": "Test"},
                params={"project_id": project_id},
                headers=auth_headers(token),
            )
            ticket_id = ticket_response.json()["id"]
            ticket_ids.append(ticket_id)
            client.post(f"/api/epics/{epic_id}/tickets", params={"ticket_id": ticket_id}, headers=auth_headers(token))

        # Get tickets in epic
        response = client.get(f"/api/epics/{epic_id}/tickets", headers=auth_headers(token))

        assert response.status_code == 200
        tickets = response.json()
        assert len(tickets) == 3
        assert {t["id"] for t in tickets} == set(ticket_ids)

    def test_get_epic_tickets_empty(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test getting tickets from empty epic returns empty list."""
        token, org_id = org_admin_token

        epic_id = create_test_epic(client, token, "Empty Epic")

        response = client.get(f"/api/epics/{epic_id}/tickets", headers=auth_headers(token))

        assert response.status_code == 200
        assert response.json() == []

    def test_get_epic_tickets_nonexistent_epic(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test getting tickets from non-existent epic returns 404."""
        token, org_id = org_admin_token

        response = client.get("/api/epics/nonexistent/tickets", headers=auth_headers(token))

        assert response.status_code == 404

    def test_get_epic_tickets_from_multiple_projects(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Test epic can contain tickets from multiple projects."""
        token, org_id = org_admin_token

        project1_id = create_test_project(client, token, "Backend")
        project2_id = create_test_project(client, token, "Frontend")
        epic_id = create_test_epic(client, token, "Feature Epic")

        # Create ticket in project1
        ticket1_response = client.post(
            "/api/tickets",
            json={"title": "Backend Ticket", "description": "Test"},
            params={"project_id": project1_id},
            headers=auth_headers(token),
        )
        ticket1_id = ticket1_response.json()["id"]

        # Create ticket in project2
        ticket2_response = client.post(
            "/api/tickets",
            json={"title": "Frontend Ticket", "description": "Test"},
            params={"project_id": project2_id},
            headers=auth_headers(token),
        )
        ticket2_id = ticket2_response.json()["id"]

        # Add both to epic
        client.post(f"/api/epics/{epic_id}/tickets", params={"ticket_id": ticket1_id}, headers=auth_headers(token))
        client.post(f"/api/epics/{epic_id}/tickets", params={"ticket_id": ticket2_id}, headers=auth_headers(token))

        # Get tickets
        response = client.get(f"/api/epics/{epic_id}/tickets", headers=auth_headers(token))

        assert response.status_code == 200
        tickets = response.json()
        assert len(tickets) == 2
        assert {t["project_id"] for t in tickets} == {project1_id, project2_id}

    def test_get_epic_tickets_cross_organization_fails(self, client: TestClient, super_admin_token: str) -> None:
        """Test cannot get epic tickets from different organization."""
        # Create two organizations
        org1_id = create_test_org(client, super_admin_token, "Org 1")
        org2_id = create_test_org(client, super_admin_token, "Org 2")

        admin1_id, admin1_pass = create_admin_user(client, super_admin_token, org1_id, username="admin1")
        admin2_id, admin2_pass = create_admin_user(client, super_admin_token, org2_id, username="admin2")

        login1 = client.post("/auth/login", json={"username": "admin1", "password": admin1_pass})
        token1 = login1.json()["access_token"]

        login2 = client.post("/auth/login", json={"username": "admin2", "password": admin2_pass})
        token2 = login2.json()["access_token"]

        # Create epic in org1
        epic_id = create_test_epic(client, token1, "Org1 Epic")

        # Try to get epic tickets from org2
        response = client.get(f"/api/epics/{epic_id}/tickets", headers=auth_headers(token2))

        assert response.status_code == 403


class TestEpicTicketWorkflows:
    """Test complete epic-ticket workflows."""

    def test_delete_epic_removes_associations_but_not_tickets(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Test deleting epic removes associations but tickets remain."""
        token, org_id = org_admin_token

        project_id = create_test_project(client, token, "Project")
        epic_id = create_test_epic(client, token, "Epic")

        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Ticket", "description": "Test"},
            params={"project_id": project_id},
            headers=auth_headers(token),
        )
        ticket_id = ticket_response.json()["id"]

        # Add ticket to epic
        client.post(f"/api/epics/{epic_id}/tickets", params={"ticket_id": ticket_id}, headers=auth_headers(token))

        # Delete epic
        client.delete(f"/api/epics/{epic_id}", headers=auth_headers(token))

        # Verify epic is deleted
        epic_get = client.get(f"/api/epics/{epic_id}", headers=auth_headers(token))
        assert epic_get.status_code == 404

        # Verify ticket still exists
        ticket_get = client.get(f"/api/tickets/{ticket_id}", headers=auth_headers(token))
        assert ticket_get.status_code == 200


class TestEpicActivityLogging:
    """Tests for epic activity logging."""

    def test_create_epic_logs_activity(self, client: TestClient, test_repo: Repository, super_admin_token: str) -> None:
        """Test that creating an epic creates an activity log entry."""
        org_id = create_test_org(client, super_admin_token)
        admin_id, password = create_admin_user(client, super_admin_token, org_id, username="admin")

        # Login as admin
        login_response = client.post("/auth/login", json={"username": "admin", "password": password})
        admin_token = login_response.json()["access_token"]

        # Create epic
        epic_data = {"name": "Test Epic", "description": "Test epic for activity logging"}
        response = client.post("/api/epics", json=epic_data, headers=auth_headers(admin_token))
        assert response.status_code == 201
        epic_id = response.json()["id"]

        # Verify activity log was created
        logs = test_repo.activity_logs.list(entity_type="epic", entity_id=epic_id)

        assert len(logs) == 1
        log = logs[0]
        assert log.entity_type == "epic"
        assert log.entity_id == epic_id
        assert log.action == ActionType.EPIC_CREATED
        assert log.actor_id == admin_id
        assert log.organization_id == org_id
        assert "command" in log.changes
        assert log.changes["command"]["epic_data"]["name"] == "Test Epic"

    def test_update_epic_logs_activity(self, client: TestClient, test_repo: Repository, super_admin_token: str) -> None:
        """Test that updating an epic creates an activity log entry."""
        org_id = create_test_org(client, super_admin_token)
        admin_id, password = create_admin_user(client, super_admin_token, org_id, username="admin")

        # Login as admin
        login_response = client.post("/auth/login", json={"username": "admin", "password": password})
        admin_token = login_response.json()["access_token"]

        # Create epic
        epic_id = create_test_epic(client, admin_token, "Test Epic")

        # Clear existing logs
        test_repo.activity_logs.list(entity_type="epic", entity_id=epic_id)

        # Update epic
        update_data = {"name": "Updated Epic", "description": "Updated description"}
        response = client.put(f"/api/epics/{epic_id}", json=update_data, headers=auth_headers(admin_token))
        assert response.status_code == 200

        # Verify activity log was created for update
        logs = test_repo.activity_logs.list(entity_type="epic", entity_id=epic_id)

        # Should have 2 logs: create + update
        assert len(logs) == 2
        update_log = logs[1]  # Most recent log
        assert update_log.action == ActionType.EPIC_UPDATED
        assert update_log.actor_id == admin_id
        assert update_log.organization_id == org_id
        assert "command" in update_log.changes
        assert update_log.changes["command"]["name"] == "Updated Epic"

    def test_delete_epic_logs_activity(self, client: TestClient, test_repo: Repository, super_admin_token: str) -> None:
        """Test that deleting an epic creates an activity log entry with snapshot."""
        org_id = create_test_org(client, super_admin_token)
        admin_id, password = create_admin_user(client, super_admin_token, org_id, username="admin")

        # Login as admin
        login_response = client.post("/auth/login", json={"username": "admin", "password": password})
        admin_token = login_response.json()["access_token"]

        # Create epic
        epic_id = create_test_epic(client, admin_token, "Test Epic")

        # Delete epic
        response = client.delete(f"/api/epics/{epic_id}", headers=auth_headers(admin_token))
        assert response.status_code == 204

        # Verify activity log was created for delete
        logs = test_repo.activity_logs.list(entity_type="epic", entity_id=epic_id)

        # Should have 2 logs: create + delete
        assert len(logs) == 2
        delete_log = logs[1]  # Most recent log
        assert delete_log.action == ActionType.EPIC_DELETED
        assert delete_log.actor_id == admin_id
        assert delete_log.organization_id == org_id
        assert "command" in delete_log.changes
        assert "snapshot" in delete_log.changes
        # Verify snapshot contains epic data
        assert delete_log.changes["snapshot"]["id"] == epic_id
        assert delete_log.changes["snapshot"]["name"] == "Test Epic"

    def test_add_ticket_to_epic_logs_activity(
        self, client: TestClient, test_repo: Repository, super_admin_token: str
    ) -> None:
        """Test that adding a ticket to an epic creates an activity log entry."""
        org_id = create_test_org(client, super_admin_token)
        admin_id, password = create_admin_user(client, super_admin_token, org_id, username="admin")

        # Login as admin
        login_response = client.post("/auth/login", json={"username": "admin", "password": password})
        admin_token = login_response.json()["access_token"]

        # Create project, epic, and ticket
        project_id = create_test_project(client, admin_token, "Test Project")
        epic_id = create_test_epic(client, admin_token, "Test Epic")
        ticket_id = create_test_ticket(
            client, admin_token, project_id, admin_id, title="Test Ticket", description="Test"
        )

        # Add ticket to epic
        response = client.post(
            f"/api/epics/{epic_id}/tickets", params={"ticket_id": ticket_id}, headers=auth_headers(admin_token)
        )
        assert response.status_code == 200

        # Verify activity log was created for ticket addition
        logs = test_repo.activity_logs.list(entity_type="epic", entity_id=epic_id)

        # Should have 2 logs: create + ticket_added
        assert len(logs) == 2
        add_log = logs[1]  # Most recent log
        assert add_log.action == ActionType.EPIC_TICKET_ADDED
        assert add_log.actor_id == admin_id
        assert add_log.organization_id == org_id
        assert "command" in add_log.changes
        assert add_log.changes["command"]["epic_id"] == epic_id
        assert add_log.changes["command"]["ticket_id"] == ticket_id

    def test_remove_ticket_from_epic_logs_activity(
        self, client: TestClient, test_repo: Repository, super_admin_token: str
    ) -> None:
        """Test that removing a ticket from an epic creates an activity log entry."""
        org_id = create_test_org(client, super_admin_token)
        admin_id, password = create_admin_user(client, super_admin_token, org_id, username="admin")

        # Login as admin
        login_response = client.post("/auth/login", json={"username": "admin", "password": password})
        admin_token = login_response.json()["access_token"]

        # Create project, epic, and ticket
        project_id = create_test_project(client, admin_token, "Test Project")
        epic_id = create_test_epic(client, admin_token, "Test Epic")
        ticket_id = create_test_ticket(
            client, admin_token, project_id, admin_id, title="Test Ticket", description="Test"
        )

        # Add ticket to epic
        client.post(f"/api/epics/{epic_id}/tickets", params={"ticket_id": ticket_id}, headers=auth_headers(admin_token))

        # Remove ticket from epic
        response = client.delete(f"/api/epics/{epic_id}/tickets/{ticket_id}", headers=auth_headers(admin_token))
        assert response.status_code == 204

        # Verify activity log was created for ticket removal
        logs = test_repo.activity_logs.list(entity_type="epic", entity_id=epic_id)

        # Should have 3 logs: create + ticket_added + ticket_removed
        assert len(logs) == 3
        remove_log = logs[2]  # Most recent log
        assert remove_log.action == ActionType.EPIC_TICKET_REMOVED
        assert remove_log.actor_id == admin_id
        assert remove_log.organization_id == org_id
        assert "command" in remove_log.changes
        assert remove_log.changes["command"]["epic_id"] == epic_id
        assert remove_log.changes["command"]["ticket_id"] == ticket_id
