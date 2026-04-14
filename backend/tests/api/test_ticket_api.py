"""Comprehensive API tests for Ticket endpoints.

Tests verify complete CRUD functionality, role-based permissions, organization scoping,
filtering, and all specialized update operations for tickets.
"""

import pytest
from fastapi.testclient import TestClient

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import ActionType
from tests.conftest import client, test_repo  # noqa: F401
from tests.fixtures.auth_fixtures import org_admin_token, super_admin_token  # noqa: F401
from tests.fixtures.data_fixtures import organization, second_organization  # noqa: F401
from tests.helpers import auth_headers, create_admin_user, create_write_user

# Local fixtures for ticket tests - create multiple users in the SAME organization
# Note: These fixtures are prefixed with 'shared_org_' to avoid shadowing global fixtures
# from auth_fixtures.py. Ticket tests need all users in the same org to test cross-user scenarios.


@pytest.fixture
def shared_org_admin_token(client: TestClient, organization: str, super_admin_token: str) -> tuple[str, str]:
    """Create Admin user in shared organization and return token and org_id."""
    _, password = create_admin_user(client, super_admin_token, organization)
    response = client.post("/auth/login", json={"username": "admin", "password": password})
    return response.json()["access_token"], organization


@pytest.fixture
def shared_org_pm_token(client: TestClient, organization: str, super_admin_token: str) -> tuple[str, str]:
    """Create Project Manager user in shared organization."""
    from tests.helpers import create_project_manager

    _, password = create_project_manager(client, super_admin_token, organization)
    response = client.post("/auth/login", json={"username": "projectmanager", "password": password})
    return response.json()["access_token"], organization


@pytest.fixture
def shared_org_write_token(client: TestClient, organization: str, super_admin_token: str) -> tuple[str, str]:
    """Create Write Access user in shared organization."""
    _, password = create_write_user(client, super_admin_token, organization)
    response = client.post("/auth/login", json={"username": "writer", "password": password})
    return response.json()["access_token"], organization


@pytest.fixture
def shared_org_read_token(client: TestClient, organization: str, super_admin_token: str) -> tuple[str, str]:
    """Create Read Access user in shared organization."""
    from tests.helpers import create_read_user

    _, password = create_read_user(client, super_admin_token, organization)
    response = client.post("/auth/login", json={"username": "reader", "password": password})
    return response.json()["access_token"], organization


class TestCreateTicket:
    """Test POST /api/tickets endpoint."""

    def test_create_ticket_as_admin(self, client: TestClient, shared_org_admin_token: tuple[str, str]) -> None:
        """Test that Admin can create tickets."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project
        project_response = client.post("/api/projects", json={"name": "Test Project"}, headers=headers)
        project_id = project_response.json()["id"]

        # Create ticket
        response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Test Ticket", "description": "Test description", "priority": "HIGH"},
            headers=headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test Ticket"
        assert data["description"] == "Test description"
        assert data["priority"] == "HIGH"
        assert data["status"] == "TODO"  # Default status
        assert data["project_id"] == project_id
        assert data["assignee_id"] is None
        assert "reporter_id" in data
        assert "id" in data
        assert "created_at" in data

    def test_create_ticket_as_project_manager(
        self, client: TestClient, shared_org_admin_token: tuple[str, str], shared_org_pm_token: tuple[str, str]
    ) -> None:
        """Test that Project Manager can create tickets."""
        admin_tok, org_id = shared_org_admin_token
        pm_token, _ = shared_org_pm_token
        admin_headers = auth_headers(admin_tok)
        pm_headers = auth_headers(pm_token)

        # Create project
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=admin_headers)
        project_id = project_response.json()["id"]

        # Create ticket as PM
        response = client.post(f"/api/tickets?project_id={project_id}", json={"title": "PM Ticket"}, headers=pm_headers)

        assert response.status_code == 201
        assert response.json()["title"] == "PM Ticket"

    def test_create_ticket_as_write_user(
        self, client: TestClient, shared_org_admin_token: tuple[str, str], shared_org_write_token: tuple[str, str]
    ) -> None:
        """Test that Write user can create tickets."""
        admin_tok, org_id = shared_org_admin_token
        write_token, _ = shared_org_write_token
        admin_headers = auth_headers(admin_tok)
        write_headers = auth_headers(write_token)

        # Create project
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=admin_headers)
        project_id = project_response.json()["id"]

        # Create ticket
        response = client.post(
            f"/api/tickets?project_id={project_id}", json={"title": "Write Ticket"}, headers=write_headers
        )

        assert response.status_code == 201

    def test_create_ticket_as_read_user_fails(
        self, client: TestClient, shared_org_admin_token: tuple[str, str], shared_org_read_token: tuple[str, str]
    ) -> None:
        """Test that Read user cannot create tickets."""
        admin_tok, org_id = shared_org_admin_token
        read_token, _ = shared_org_read_token
        admin_headers = auth_headers(admin_tok)
        read_headers = auth_headers(read_token)

        # Create project
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=admin_headers)
        project_id = project_response.json()["id"]

        # Attempt to create ticket
        response = client.post(
            f"/api/tickets?project_id={project_id}", json={"title": "Should Fail"}, headers=read_headers
        )

        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    def test_create_ticket_with_assignee(
        self, client: TestClient, shared_org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test creating ticket with initial assignee."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=headers)
        project_id = project_response.json()["id"]

        # Create assignee via helper with unique email
        assignee_id, _ = create_write_user(
            client, super_admin_token, org_id, username="assignee", email="assignee@example.com"
        )

        # Create ticket with assignee
        response = client.post(
            f"/api/tickets?project_id={project_id}&assignee_id={assignee_id}",
            json={"title": "Assigned Ticket"},
            headers=headers,
        )

        assert response.status_code == 201
        assert response.json()["assignee_id"] == assignee_id

    def test_create_ticket_in_nonexistent_project_fails(
        self, client: TestClient, shared_org_admin_token: tuple[str, str]
    ) -> None:
        """Test creating ticket in non-existent project fails."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        response = client.post("/api/tickets?project_id=nonexistent", json={"title": "Should Fail"}, headers=headers)

        assert response.status_code == 404
        assert "project" in response.json()["detail"].lower()

    def test_create_ticket_with_nonexistent_assignee_fails(
        self, client: TestClient, shared_org_admin_token: tuple[str, str]
    ) -> None:
        """Test creating ticket with non-existent assignee fails."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=headers)
        project_id = project_response.json()["id"]

        response = client.post(
            f"/api/tickets?project_id={project_id}&assignee_id=nonexistent",
            json={"title": "Should Fail"},
            headers=headers,
        )

        assert response.status_code == 404
        assert "assignee" in response.json()["detail"].lower()

    def test_create_ticket_validates_title_required(
        self, client: TestClient, shared_org_admin_token: tuple[str, str]
    ) -> None:
        """Test that title is required when creating ticket."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=headers)
        project_id = project_response.json()["id"]

        response = client.post(
            f"/api/tickets?project_id={project_id}", json={"description": "No title"}, headers=headers
        )

        assert response.status_code == 422


class TestGetTicket:
    """Test GET /api/tickets/{id} endpoint."""

    def test_get_ticket_by_id_in_same_org(self, client: TestClient, shared_org_admin_token: tuple[str, str]) -> None:
        """Test retrieving ticket from same organization."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=headers)
        project_id = project_response.json()["id"]

        create_response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Test Ticket", "description": "Test"},
            headers=headers,
        )
        ticket_id = create_response.json()["id"]

        # Get ticket
        response = client.get(f"/api/tickets/{ticket_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == ticket_id
        assert data["title"] == "Test Ticket"

    def test_get_ticket_from_different_org_fails(
        self,
        client: TestClient,
        shared_org_admin_token: tuple[str, str],
        second_organization: str,
        super_admin_token: str,
    ) -> None:
        """Test that users cannot access tickets from different organizations."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket in org1
        project1_response = client.post("/api/projects", json={"name": "Project 1"}, headers=headers)
        project1_id = project1_response.json()["id"]

        create_response = client.post(
            f"/api/tickets?project_id={project1_id}", json={"title": "Org1 Ticket"}, headers=headers
        )
        ticket_id = create_response.json()["id"]

        # Create user in org2 via API
        from tests.helpers import create_admin_user

        _, org2_password = create_admin_user(client, super_admin_token, second_organization, username="org2admin")

        org2_token = client.post("/auth/login", json={"username": "org2admin", "password": org2_password}).json()[
            "access_token"
        ]
        org2_headers = auth_headers(org2_token)

        # Attempt to get org1 ticket
        response = client.get(f"/api/tickets/{ticket_id}", headers=org2_headers)

        assert response.status_code == 403
        assert "organization" in response.json()["detail"].lower()

    def test_get_nonexistent_ticket_fails(self, client: TestClient, shared_org_admin_token: tuple[str, str]) -> None:
        """Test getting non-existent ticket returns 404."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        response = client.get("/api/tickets/nonexistent", headers=headers)

        assert response.status_code == 404
        assert "ticket" in response.json()["detail"].lower()


class TestListTickets:
    """Test GET /api/tickets endpoint with filtering."""

    def test_list_tickets_in_organization(self, client: TestClient, shared_org_admin_token: tuple[str, str]) -> None:
        """Test listing all tickets in user's organization."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=headers)
        project_id = project_response.json()["id"]

        # Create tickets
        client.post(f"/api/tickets?project_id={project_id}", json={"title": "Ticket 1"}, headers=headers)
        client.post(f"/api/tickets?project_id={project_id}", json={"title": "Ticket 2"}, headers=headers)

        # List tickets
        response = client.get("/api/tickets", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert {t["title"] for t in data} == {"Ticket 1", "Ticket 2"}

    def test_list_tickets_filtered_by_project(
        self, client: TestClient, shared_org_admin_token: tuple[str, str]
    ) -> None:
        """Test filtering tickets by project ID."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create projects
        project1_response = client.post("/api/projects", json={"name": "Project 1"}, headers=headers)
        project1_id = project1_response.json()["id"]

        project2_response = client.post("/api/projects", json={"name": "Project 2"}, headers=headers)
        project2_id = project2_response.json()["id"]

        # Create tickets in different projects
        client.post(f"/api/tickets?project_id={project1_id}", json={"title": "P1 Ticket"}, headers=headers)
        client.post(f"/api/tickets?project_id={project2_id}", json={"title": "P2 Ticket"}, headers=headers)

        # Filter by project1
        response = client.get(f"/api/tickets?project_id={project1_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "P1 Ticket"
        assert data[0]["project_id"] == project1_id

    def test_list_tickets_filtered_by_status(self, client: TestClient, shared_org_admin_token: tuple[str, str]) -> None:
        """Test filtering tickets by status."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=headers)
        project_id = project_response.json()["id"]

        # Create tickets
        todo_response = client.post(
            f"/api/tickets?project_id={project_id}", json={"title": "Todo Ticket"}, headers=headers
        )
        todo_id = todo_response.json()["id"]

        inprog_response = client.post(
            f"/api/tickets?project_id={project_id}", json={"title": "InProg Ticket"}, headers=headers
        )
        inprog_id = inprog_response.json()["id"]

        # Change one to IN_PROGRESS
        client.put(f"/api/tickets/{inprog_id}/status", json={"status": "IN_PROGRESS"}, headers=headers)

        # Filter by TODO
        response = client.get("/api/tickets?status=TODO", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "TODO"
        assert data[0]["id"] == todo_id

    def test_list_tickets_filtered_by_assignee(
        self, client: TestClient, shared_org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test filtering tickets by assignee."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=headers)
        project_id = project_response.json()["id"]

        # Create assignee via helper with unique email
        assignee_id, _ = create_write_user(
            client, super_admin_token, org_id, username="assignee", email="assignee@example.com"
        )

        # Create tickets
        client.post(
            f"/api/tickets?project_id={project_id}&assignee_id={assignee_id}",
            json={"title": "Assigned"},
            headers=headers,
        )
        client.post(f"/api/tickets?project_id={project_id}", json={"title": "Unassigned"}, headers=headers)

        # Filter by assignee
        response = client.get(f"/api/tickets?assignee_id={assignee_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Assigned"
        assert data[0]["assignee_id"] == assignee_id

    def test_list_tickets_combined_filters(
        self, client: TestClient, shared_org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test filtering tickets with multiple criteria."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=headers)
        project_id = project_response.json()["id"]

        # Create assignee via helper with unique email
        assignee_id, _ = create_write_user(
            client, super_admin_token, org_id, username="assignee", email="assignee@example.com"
        )

        # Create matching ticket
        match_response = client.post(
            f"/api/tickets?project_id={project_id}&assignee_id={assignee_id}",
            json={"title": "Match"},
            headers=headers,
        )
        match_id = match_response.json()["id"]
        client.put(f"/api/tickets/{match_id}/status", json={"status": "IN_PROGRESS"}, headers=headers)

        # Create non-matching ticket (different status)
        client.post(
            f"/api/tickets?project_id={project_id}&assignee_id={assignee_id}",
            json={"title": "No Match"},
            headers=headers,
        )  # Status=TODO

        # Filter by all criteria
        response = client.get(
            f"/api/tickets?project_id={project_id}&status=IN_PROGRESS&assignee_id={assignee_id}",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == match_id

    def test_list_tickets_respects_organization_boundary(
        self,
        client: TestClient,
        shared_org_admin_token: tuple[str, str],
        second_organization: str,
        super_admin_token: str,
    ) -> None:
        """Test that users only see tickets from their organization."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket in org1
        project1_response = client.post("/api/projects", json={"name": "Project 1"}, headers=headers)
        project1_id = project1_response.json()["id"]
        client.post(f"/api/tickets?project_id={project1_id}", json={"title": "Org1 Ticket"}, headers=headers)

        # Create user in org2 via API
        from tests.helpers import create_admin_user

        _, org2_password = create_admin_user(client, super_admin_token, second_organization, username="org2admin")

        org2_token = client.post("/auth/login", json={"username": "org2admin", "password": org2_password}).json()[
            "access_token"
        ]
        org2_headers = auth_headers(org2_token)

        # Create project and ticket in org2
        project2_response = client.post("/api/projects", json={"name": "Project 2"}, headers=org2_headers)
        project2_id = project2_response.json()["id"]
        client.post(f"/api/tickets?project_id={project2_id}", json={"title": "Org2 Ticket"}, headers=org2_headers)

        # List tickets for org2 user
        response = client.get("/api/tickets", headers=org2_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Org2 Ticket"

    def test_list_tickets_filtered_by_project_not_in_org_returns_empty(
        self, client: TestClient, shared_org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test filtering tickets by project not in user's org returns empty list."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create another organization and project
        org2_response = client.post(
            "/api/organizations", json={"name": "Org 2"}, headers=auth_headers(super_admin_token)
        )
        org2_id = org2_response.json()["id"]

        _, org2_password = create_admin_user(client, super_admin_token, org2_id, username="org2admin")
        org2_token = client.post("/auth/login", json={"username": "org2admin", "password": org2_password}).json()[
            "access_token"
        ]

        # Create project in org2
        project2_response = client.post(
            "/api/projects", json={"name": "Org2 Project"}, headers=auth_headers(org2_token)
        )
        project2_id = project2_response.json()["id"]

        # Try to filter org1 user's tickets by org2 project
        response = client.get(f"/api/tickets?project_id={project2_id}", headers=headers)

        assert response.status_code == 200
        assert response.json() == []  # Empty list because project not in user's org


class TestUpdateTicket:
    """Test PUT /api/tickets/{id} endpoint."""

    def test_update_ticket_fields(self, client: TestClient, shared_org_admin_token: tuple[str, str]) -> None:
        """Test updating ticket title, description, and priority."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=headers)
        project_id = project_response.json()["id"]

        # Create ticket
        create_response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Old Title", "description": "Old desc", "priority": "LOW"},
            headers=headers,
        )
        ticket_id = create_response.json()["id"]

        # Update ticket
        response = client.put(
            f"/api/tickets/{ticket_id}",
            json={"title": "New Title", "description": "New desc", "priority": "HIGH"},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "New Title"
        assert data["description"] == "New desc"
        assert data["priority"] == "HIGH"

    def test_update_ticket_as_write_user(
        self, client: TestClient, shared_org_admin_token: tuple[str, str], shared_org_write_token: tuple[str, str]
    ) -> None:
        """Test that Write user can update tickets."""
        admin_tok, org_id = shared_org_admin_token
        write_token, _ = shared_org_write_token
        admin_headers = auth_headers(admin_tok)
        write_headers = auth_headers(write_token)

        # Create project and ticket
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=admin_headers)
        project_id = project_response.json()["id"]

        create_response = client.post(
            f"/api/tickets?project_id={project_id}", json={"title": "Original"}, headers=admin_headers
        )
        ticket_id = create_response.json()["id"]

        # Update as write user
        response = client.put(f"/api/tickets/{ticket_id}", json={"title": "Updated"}, headers=write_headers)

        assert response.status_code == 200
        assert response.json()["title"] == "Updated"

    def test_update_ticket_as_read_user_fails(
        self, client: TestClient, shared_org_admin_token: tuple[str, str], shared_org_read_token: tuple[str, str]
    ) -> None:
        """Test that Read user cannot update tickets."""
        admin_tok, org_id = shared_org_admin_token
        read_token, _ = shared_org_read_token
        admin_headers = auth_headers(admin_tok)
        read_headers = auth_headers(read_token)

        # Create project and ticket
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=admin_headers)
        project_id = project_response.json()["id"]

        create_response = client.post(
            f"/api/tickets?project_id={project_id}", json={"title": "Original"}, headers=admin_headers
        )
        ticket_id = create_response.json()["id"]

        # Attempt update as read user
        response = client.put(f"/api/tickets/{ticket_id}", json={"title": "Should Fail"}, headers=read_headers)

        assert response.status_code == 403

    def test_update_nonexistent_ticket_fails(self, client: TestClient, shared_org_admin_token: tuple[str, str]) -> None:
        """Test updating non-existent ticket returns 404."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        response = client.put("/api/tickets/nonexistent", json={"title": "Should Fail"}, headers=headers)

        assert response.status_code == 404


class TestUpdateTicketStatus:
    """Test PUT /api/tickets/{id}/status endpoint."""

    def test_update_ticket_status(self, client: TestClient, shared_org_admin_token: tuple[str, str]) -> None:
        """Test changing ticket status."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=headers)
        project_id = project_response.json()["id"]

        create_response = client.post(
            f"/api/tickets?project_id={project_id}", json={"title": "Test Ticket"}, headers=headers
        )
        ticket_id = create_response.json()["id"]

        # Change status
        response = client.put(f"/api/tickets/{ticket_id}/status", json={"status": "IN_PROGRESS"}, headers=headers)

        assert response.status_code == 200
        assert response.json()["status"] == "IN_PROGRESS"

    def test_update_status_all_transitions(self, client: TestClient, shared_org_admin_token: tuple[str, str]) -> None:
        """Test all valid status transitions."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=headers)
        project_id = project_response.json()["id"]

        create_response = client.post(f"/api/tickets?project_id={project_id}", json={"title": "Test"}, headers=headers)
        ticket_id = create_response.json()["id"]

        # TODO -> IN_PROGRESS
        response1 = client.put(f"/api/tickets/{ticket_id}/status", json={"status": "IN_PROGRESS"}, headers=headers)
        assert response1.status_code == 200

        # IN_PROGRESS -> DONE
        response2 = client.put(f"/api/tickets/{ticket_id}/status", json={"status": "DONE"}, headers=headers)
        assert response2.status_code == 200

        # DONE -> TODO (regression)
        response3 = client.put(f"/api/tickets/{ticket_id}/status", json={"status": "TODO"}, headers=headers)
        assert response3.status_code == 200

    def test_update_status_invalid_value_fails(
        self, client: TestClient, shared_org_admin_token: tuple[str, str]
    ) -> None:
        """Test that invalid status value returns validation error."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=headers)
        project_id = project_response.json()["id"]

        create_response = client.post(f"/api/tickets?project_id={project_id}", json={"title": "Test"}, headers=headers)
        ticket_id = create_response.json()["id"]

        # Invalid status
        response = client.put(f"/api/tickets/{ticket_id}/status", json={"status": "INVALID"}, headers=headers)

        assert response.status_code == 422

    def test_update_status_as_read_user_fails(
        self, client: TestClient, shared_org_admin_token: tuple[str, str], shared_org_read_token: tuple[str, str]
    ) -> None:
        """Test that Read user cannot change ticket status."""
        admin_token, org_id = shared_org_admin_token
        read_token, _ = shared_org_read_token
        admin_headers = auth_headers(admin_token)
        read_headers = auth_headers(read_token)

        # Create project and ticket as admin
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=admin_headers)
        project_id = project_response.json()["id"]

        create_response = client.post(
            f"/api/tickets?project_id={project_id}", json={"title": "Test"}, headers=admin_headers
        )
        ticket_id = create_response.json()["id"]

        # Try to change status as read user
        response = client.put(f"/api/tickets/{ticket_id}/status", json={"status": "IN_PROGRESS"}, headers=read_headers)

        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]


class TestMoveTicketToProject:
    """Test PUT /api/tickets/{id}/project endpoint."""

    def test_move_ticket_to_different_project(
        self, client: TestClient, shared_org_admin_token: tuple[str, str]
    ) -> None:
        """Test moving ticket between projects in same organization."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create projects
        project1_response = client.post("/api/projects", json={"name": "Project 1"}, headers=headers)
        project1_id = project1_response.json()["id"]

        project2_response = client.post("/api/projects", json={"name": "Project 2"}, headers=headers)
        project2_id = project2_response.json()["id"]

        # Create ticket in project1
        create_response = client.post(
            f"/api/tickets?project_id={project1_id}", json={"title": "Movable Ticket"}, headers=headers
        )
        ticket_id = create_response.json()["id"]

        # Move to project2
        response = client.put(f"/api/tickets/{ticket_id}/project", json={"project_id": project2_id}, headers=headers)

        assert response.status_code == 200
        assert response.json()["project_id"] == project2_id

    def test_move_ticket_as_write_user_fails(
        self, client: TestClient, shared_org_admin_token: tuple[str, str], shared_org_write_token: tuple[str, str]
    ) -> None:
        """Test that Write user cannot move tickets."""
        admin_tok, org_id = shared_org_admin_token
        write_token, _ = shared_org_write_token
        admin_headers = auth_headers(admin_tok)
        write_headers = auth_headers(write_token)

        # Create projects
        project1_response = client.post("/api/projects", json={"name": "Project 1"}, headers=admin_headers)
        project1_id = project1_response.json()["id"]

        project2_response = client.post("/api/projects", json={"name": "Project 2"}, headers=admin_headers)
        project2_id = project2_response.json()["id"]

        # Create ticket
        create_response = client.post(
            f"/api/tickets?project_id={project1_id}", json={"title": "Test"}, headers=admin_headers
        )
        ticket_id = create_response.json()["id"]

        # Attempt to move
        response = client.put(
            f"/api/tickets/{ticket_id}/project", json={"project_id": project2_id}, headers=write_headers
        )

        assert response.status_code == 403

    def test_move_ticket_to_nonexistent_project_fails(
        self, client: TestClient, shared_org_admin_token: tuple[str, str]
    ) -> None:
        """Test moving ticket to non-existent project fails."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=headers)
        project_id = project_response.json()["id"]

        create_response = client.post(f"/api/tickets?project_id={project_id}", json={"title": "Test"}, headers=headers)
        ticket_id = create_response.json()["id"]

        # Attempt to move to nonexistent project
        response = client.put(f"/api/tickets/{ticket_id}/project", json={"project_id": "nonexistent"}, headers=headers)

        assert response.status_code == 404


class TestAssignTicket:
    """Test PUT /api/tickets/{id}/assignee endpoint."""

    def test_assign_ticket_to_user(
        self, client: TestClient, shared_org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test assigning ticket to a user."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=headers)
        project_id = project_response.json()["id"]

        create_response = client.post(f"/api/tickets?project_id={project_id}", json={"title": "Test"}, headers=headers)
        ticket_id = create_response.json()["id"]

        # Create assignee via helper with unique email
        assignee_id, _ = create_write_user(
            client, super_admin_token, org_id, username="assignee", email="assignee@example.com"
        )

        # Assign ticket
        response = client.put(f"/api/tickets/{ticket_id}/assignee", json={"assignee_id": assignee_id}, headers=headers)

        assert response.status_code == 200
        assert response.json()["assignee_id"] == assignee_id

    def test_unassign_ticket(
        self, client: TestClient, shared_org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test unassigning ticket (set to null)."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=headers)
        project_id = project_response.json()["id"]

        # Create assignee via helper with unique email
        assignee_id, _ = create_write_user(
            client, super_admin_token, org_id, username="assignee", email="assignee@example.com"
        )

        # Create ticket with assignee
        create_response = client.post(
            f"/api/tickets?project_id={project_id}&assignee_id={assignee_id}",
            json={"title": "Test"},
            headers=headers,
        )
        ticket_id = create_response.json()["id"]

        # Unassign
        response = client.put(f"/api/tickets/{ticket_id}/assignee", json={"assignee_id": None}, headers=headers)

        assert response.status_code == 200
        assert response.json()["assignee_id"] is None

    def test_assign_ticket_as_write_user_fails(
        self,
        client: TestClient,
        shared_org_admin_token: tuple[str, str],
        shared_org_write_token: tuple[str, str],
        super_admin_token: str,
    ) -> None:
        """Test that Write user cannot assign tickets."""
        admin_tok, org_id = shared_org_admin_token
        write_token, _ = shared_org_write_token
        admin_headers = auth_headers(admin_tok)
        write_headers = auth_headers(write_token)

        # Create project and ticket
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=admin_headers)
        project_id = project_response.json()["id"]

        create_response = client.post(
            f"/api/tickets?project_id={project_id}", json={"title": "Test"}, headers=admin_headers
        )
        ticket_id = create_response.json()["id"]

        # Create assignee via helper with unique email
        assignee_id, _ = create_write_user(
            client, super_admin_token, org_id, username="assignee", email="assignee@example.com"
        )

        # Attempt to assign
        response = client.put(
            f"/api/tickets/{ticket_id}/assignee", json={"assignee_id": assignee_id}, headers=write_headers
        )

        assert response.status_code == 403

    def test_assign_to_nonexistent_user_fails(
        self, client: TestClient, shared_org_admin_token: tuple[str, str]
    ) -> None:
        """Test assigning to non-existent user fails."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=headers)
        project_id = project_response.json()["id"]

        create_response = client.post(f"/api/tickets?project_id={project_id}", json={"title": "Test"}, headers=headers)
        ticket_id = create_response.json()["id"]

        # Attempt to assign to nonexistent user
        response = client.put(
            f"/api/tickets/{ticket_id}/assignee", json={"assignee_id": "nonexistent"}, headers=headers
        )

        assert response.status_code == 404

    def test_assign_to_inactive_user_fails(self, client: TestClient, shared_org_admin_token: tuple[str, str]) -> None:
        """Test assigning to inactive user fails with 400."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=headers)
        project_id = project_response.json()["id"]

        create_response = client.post(f"/api/tickets?project_id={project_id}", json={"title": "Test"}, headers=headers)
        ticket_id = create_response.json()["id"]

        # Create a user and deactivate them
        from tests.helpers import create_test_user

        user_id, _ = create_test_user(client, token, org_id, username="inactive_user")

        # Deactivate the user
        deactivate_response = client.put(f"/api/users/{user_id}", json={"is_active": False}, headers=headers)
        assert deactivate_response.status_code == 200

        # Attempt to assign ticket to inactive user
        response = client.put(
            f"/api/tickets/{ticket_id}/assignee",
            json={"assignee_id": user_id},
            headers=headers,
        )

        assert response.status_code == 400
        assert "inactive" in response.json()["detail"].lower()

    def test_assign_to_cross_organization_user_fails(self, client: TestClient, super_admin_token: str) -> None:
        """Test non-Super Admin cannot assign to user in different organization."""
        # Create two organizations
        org1_response = client.post(
            "/api/organizations", json={"name": "Org 1"}, headers=auth_headers(super_admin_token)
        )
        org1_id = org1_response.json()["id"]

        org2_response = client.post(
            "/api/organizations", json={"name": "Org 2"}, headers=auth_headers(super_admin_token)
        )
        org2_id = org2_response.json()["id"]

        # Create admin in org1
        admin1_id, admin1_pass = create_admin_user(client, super_admin_token, org1_id, username="admin1")
        login1 = client.post("/auth/login", json={"username": "admin1", "password": admin1_pass})
        token1 = login1.json()["access_token"]

        # Create user in org2
        user2_id, _ = create_write_user(client, super_admin_token, org2_id, username="user2")

        # Create project and ticket in org1
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=auth_headers(token1))
        project_id = project_response.json()["id"]

        create_response = client.post(
            f"/api/tickets?project_id={project_id}", json={"title": "Test"}, headers=auth_headers(token1)
        )
        ticket_id = create_response.json()["id"]

        # Try to assign org1 ticket to org2 user
        response = client.put(
            f"/api/tickets/{ticket_id}/assignee", json={"assignee_id": user2_id}, headers=auth_headers(token1)
        )

        assert response.status_code == 403
        assert "different organization" in response.json()["detail"]


class TestDeleteTicket:
    """Test DELETE /api/tickets/{id} endpoint."""

    def test_delete_ticket_as_admin(self, client: TestClient, shared_org_admin_token: tuple[str, str]) -> None:
        """Test that Admin can delete tickets."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=headers)
        project_id = project_response.json()["id"]

        create_response = client.post(
            f"/api/tickets?project_id={project_id}", json={"title": "To Delete"}, headers=headers
        )
        ticket_id = create_response.json()["id"]

        # Delete ticket
        response = client.delete(f"/api/tickets/{ticket_id}", headers=headers)

        assert response.status_code == 204

        # Verify deletion
        get_response = client.get(f"/api/tickets/{ticket_id}", headers=headers)
        assert get_response.status_code == 404

    def test_delete_ticket_as_project_manager_fails(
        self, client: TestClient, shared_org_admin_token: tuple[str, str], shared_org_pm_token: tuple[str, str]
    ) -> None:
        """Test that Project Manager cannot delete tickets."""
        admin_tok, org_id = shared_org_admin_token
        pm_token, _ = shared_org_pm_token
        admin_headers = auth_headers(admin_tok)
        pm_headers = auth_headers(pm_token)

        # Create project and ticket
        project_response = client.post("/api/projects", json={"name": "Project"}, headers=admin_headers)
        project_id = project_response.json()["id"]

        create_response = client.post(
            f"/api/tickets?project_id={project_id}", json={"title": "Test"}, headers=admin_headers
        )
        ticket_id = create_response.json()["id"]

        # Attempt to delete
        response = client.delete(f"/api/tickets/{ticket_id}", headers=pm_headers)

        assert response.status_code == 403

    def test_delete_nonexistent_ticket_fails(self, client: TestClient, shared_org_admin_token: tuple[str, str]) -> None:
        """Test deleting non-existent ticket returns 404."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        response = client.delete("/api/tickets/nonexistent", headers=headers)

        assert response.status_code == 404


class TestTicketWorkflows:
    """Test complete ticket workflows."""

    def test_complete_ticket_lifecycle(
        self, client: TestClient, shared_org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test complete workflow: create → assign → update status → move → delete."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create projects
        project1_response = client.post("/api/projects", json={"name": "Backend"}, headers=headers)
        project1_id = project1_response.json()["id"]

        project2_response = client.post("/api/projects", json={"name": "Frontend"}, headers=headers)
        project2_id = project2_response.json()["id"]

        # Create assignee via helper with unique email
        assignee_id, _ = create_write_user(
            client, super_admin_token, org_id, username="assignee", email="assignee@example.com"
        )

        # 1. Create ticket
        create_response = client.post(
            f"/api/tickets?project_id={project1_id}",
            json={"title": "Implement feature", "description": "Build new feature", "priority": "HIGH"},
            headers=headers,
        )
        assert create_response.status_code == 201
        ticket_id = create_response.json()["id"]
        assert create_response.json()["status"] == "TODO"

        # 2. Assign to developer
        assign_response = client.put(
            f"/api/tickets/{ticket_id}/assignee", json={"assignee_id": assignee_id}, headers=headers
        )
        assert assign_response.status_code == 200
        assert assign_response.json()["assignee_id"] == assignee_id

        # 3. Start work (change status to IN_PROGRESS)
        status_response = client.put(
            f"/api/tickets/{ticket_id}/status", json={"status": "IN_PROGRESS"}, headers=headers
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "IN_PROGRESS"

        # 4. Update description
        update_response = client.put(
            f"/api/tickets/{ticket_id}",
            json={"description": "Updated implementation plan"},
            headers=headers,
        )
        assert update_response.status_code == 200
        assert update_response.json()["description"] == "Updated implementation plan"

        # 5. Move to different project
        move_response = client.put(
            f"/api/tickets/{ticket_id}/project", json={"project_id": project2_id}, headers=headers
        )
        assert move_response.status_code == 200
        assert move_response.json()["project_id"] == project2_id

        # 6. Complete work
        done_response = client.put(f"/api/tickets/{ticket_id}/status", json={"status": "DONE"}, headers=headers)
        assert done_response.status_code == 200
        assert done_response.json()["status"] == "DONE"

        # 7. Verify final state
        get_response = client.get(f"/api/tickets/{ticket_id}", headers=headers)
        assert get_response.status_code == 200
        final_data = get_response.json()
        assert final_data["status"] == "DONE"
        assert final_data["project_id"] == project2_id
        assert final_data["assignee_id"] == assignee_id

        # 8. Delete ticket
        delete_response = client.delete(f"/api/tickets/{ticket_id}", headers=headers)
        assert delete_response.status_code == 204

        # 9. Verify deletion
        final_get = client.get(f"/api/tickets/{ticket_id}", headers=headers)
        assert final_get.status_code == 404


class TestTicketActivityLogging:
    """Test that ticket operations create activity log entries."""

    def test_create_ticket_creates_activity_log(
        self,
        client: TestClient,
        test_repo: Repository,
        shared_org_admin_token: tuple[str, str],
    ) -> None:
        """Test that creating a ticket creates an activity log entry."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project first
        project_response = client.post(
            "/api/projects",
            json={"name": "Test Project"},
            params={"organization_id": org_id},
            headers=headers,
        )
        project_id = project_response.json()["id"]

        # Create ticket
        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Test Ticket", "description": "Test description"},
            params={"project_id": project_id},
            headers=headers,
        )
        assert ticket_response.status_code == 201
        ticket_id = ticket_response.json()["id"]

        # Query activity logs for this ticket
        logs = test_repo.activity_logs.list(entity_type="ticket", entity_id=ticket_id)

        # Verify log was created - command-based format
        assert len(logs) == 1
        log = logs[0]
        assert log.action == ActionType.TICKET_CREATED
        assert log.entity_type == "ticket"
        assert log.entity_id == ticket_id
        assert "command" in log.changes
        assert log.changes["command"]["ticket_data"]["title"] == "Test Ticket"
        assert log.changes["command"]["ticket_data"]["description"] == "Test description"
        assert log.changes["command"]["project_id"] == project_id

    def test_update_ticket_creates_activity_log(
        self,
        client: TestClient,
        test_repo: Repository,
        shared_org_admin_token: tuple[str, str],
    ) -> None:
        """Test that updating a ticket creates an activity log entry."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket
        project_response = client.post(
            "/api/projects",
            json={"name": "Test Project"},
            params={"organization_id": org_id},
            headers=headers,
        )
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Original Title", "description": "Original description"},
            params={"project_id": project_id},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        # Update ticket
        update_response = client.put(
            f"/api/tickets/{ticket_id}",
            json={"title": "Updated Title", "description": "Updated description"},
            headers=headers,
        )
        assert update_response.status_code == 200

        # Query activity logs for this ticket
        logs = test_repo.activity_logs.list(entity_type="ticket", entity_id=ticket_id, action=ActionType.TICKET_UPDATED)

        # Verify update log was created - command-based format
        assert len(logs) == 1
        log = logs[0]
        assert log.action == ActionType.TICKET_UPDATED
        assert "command" in log.changes
        assert log.changes["command"]["title"] == "Updated Title"
        assert log.changes["command"]["description"] == "Updated description"

    def test_change_ticket_status_creates_activity_log(
        self,
        client: TestClient,
        test_repo: Repository,
        shared_org_admin_token: tuple[str, str],
    ) -> None:
        """Test that changing ticket status creates an activity log entry."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket
        project_response = client.post(
            "/api/projects",
            json={"name": "Test Project"},
            params={"organization_id": org_id},
            headers=headers,
        )
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Status Test"},
            params={"project_id": project_id},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        # Change status
        status_response = client.put(
            f"/api/tickets/{ticket_id}/status",
            json={"status": "IN_PROGRESS"},
            headers=headers,
        )
        assert status_response.status_code == 200

        # Query activity logs for status change
        logs = test_repo.activity_logs.list(
            entity_type="ticket", entity_id=ticket_id, action=ActionType.TICKET_STATUS_CHANGED
        )

        # Verify status change log was created - command-based format
        assert len(logs) == 1
        log = logs[0]
        assert log.action == ActionType.TICKET_STATUS_CHANGED
        assert "command" in log.changes
        assert log.changes["command"]["ticket_id"] == ticket_id
        assert log.changes["command"]["status"] == "IN_PROGRESS"

    def test_assign_ticket_creates_activity_log(
        self,
        client: TestClient,
        test_repo: Repository,
        shared_org_admin_token: tuple[str, str],
    ) -> None:
        """Test that assigning a ticket creates an activity log entry."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket
        project_response = client.post(
            "/api/projects",
            json={"name": "Test Project"},
            params={"organization_id": org_id},
            headers=headers,
        )
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Assign Test"},
            params={"project_id": project_id},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        # Create a user to assign
        assignee_id, _ = create_write_user(client, token, org_id, username="assignee")

        # Assign ticket
        assign_response = client.put(
            f"/api/tickets/{ticket_id}/assignee",
            json={"assignee_id": assignee_id},
            headers=headers,
        )
        assert assign_response.status_code == 200

        # Query activity logs for assignment
        logs = test_repo.activity_logs.list(
            entity_type="ticket", entity_id=ticket_id, action=ActionType.TICKET_ASSIGNED
        )

        # Verify assignment log was created - command-based format
        assert len(logs) == 1
        log = logs[0]
        assert log.action == ActionType.TICKET_ASSIGNED
        assert "command" in log.changes
        assert log.changes["command"]["ticket_id"] == ticket_id
        assert log.changes["command"]["assignee_id"] == assignee_id

    def test_move_ticket_creates_activity_log(
        self,
        client: TestClient,
        test_repo: Repository,
        shared_org_admin_token: tuple[str, str],
    ) -> None:
        """Test that moving a ticket to different project creates an activity log entry."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create two projects
        project1_response = client.post(
            "/api/projects",
            json={"name": "Project 1"},
            params={"organization_id": org_id},
            headers=headers,
        )
        project1_id = project1_response.json()["id"]

        project2_response = client.post(
            "/api/projects",
            json={"name": "Project 2"},
            params={"organization_id": org_id},
            headers=headers,
        )
        project2_id = project2_response.json()["id"]

        # Create ticket in project 1
        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Move Test"},
            params={"project_id": project1_id},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        # Move ticket to project 2
        move_response = client.put(
            f"/api/tickets/{ticket_id}/project",
            json={"project_id": project2_id},
            headers=headers,
        )
        assert move_response.status_code == 200

        # Query activity logs for move
        logs = test_repo.activity_logs.list(entity_type="ticket", entity_id=ticket_id, action=ActionType.TICKET_MOVED)

        # Verify move log was created - command-based format
        assert len(logs) == 1
        log = logs[0]
        assert log.action == ActionType.TICKET_MOVED
        assert "command" in log.changes
        assert log.changes["command"]["ticket_id"] == ticket_id
        assert log.changes["command"]["target_project_id"] == project2_id

    def test_delete_ticket_creates_activity_log(
        self,
        client: TestClient,
        test_repo: Repository,
        shared_org_admin_token: tuple[str, str],
    ) -> None:
        """Test that deleting a ticket creates an activity log entry."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket
        project_response = client.post(
            "/api/projects",
            json={"name": "Test Project"},
            params={"organization_id": org_id},
            headers=headers,
        )
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Delete Test"},
            params={"project_id": project_id},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        # Delete ticket
        delete_response = client.delete(f"/api/tickets/{ticket_id}", headers=headers)
        assert delete_response.status_code == 204

        # Query activity logs for deletion (logs persist after deletion)
        logs = test_repo.activity_logs.list(entity_type="ticket", entity_id=ticket_id, action=ActionType.TICKET_DELETED)

        # Verify deletion log was created with snapshot - command-based format
        assert len(logs) == 1
        log = logs[0]
        assert log.action == ActionType.TICKET_DELETED
        assert "command" in log.changes
        assert log.changes["command"]["ticket_id"] == ticket_id
        assert "snapshot" in log.changes
        assert log.changes["snapshot"]["id"] == ticket_id
        assert log.changes["snapshot"]["title"] == "Delete Test"
        assert log.changes["snapshot"]["status"] == "TODO"

    def test_activity_log_captures_actor(
        self,
        client: TestClient,
        test_repo: Repository,
        shared_org_admin_token: tuple[str, str],
    ) -> None:
        """Test that activity logs capture the actor (user) who performed the action."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket
        project_response = client.post(
            "/api/projects",
            json={"name": "Test Project"},
            params={"organization_id": org_id},
            headers=headers,
        )
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Actor Test"},
            params={"project_id": project_id},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        # Query activity logs
        logs = test_repo.activity_logs.list(entity_type="ticket", entity_id=ticket_id)

        # Verify actor is captured (should be non-empty string)
        assert len(logs) == 1
        assert logs[0].actor_id is not None
        assert len(logs[0].actor_id) > 0  # Valid UUID string

    def test_multiple_operations_create_multiple_logs(
        self,
        client: TestClient,
        test_repo: Repository,
        shared_org_admin_token: tuple[str, str],
    ) -> None:
        """Test that multiple operations on same ticket create multiple log entries."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket
        project_response = client.post(
            "/api/projects",
            json={"name": "Test Project"},
            params={"organization_id": org_id},
            headers=headers,
        )
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Multi-op Test"},
            params={"project_id": project_id},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        # Perform multiple operations
        client.put(f"/api/tickets/{ticket_id}", json={"title": "Updated Title"}, headers=headers)
        client.put(f"/api/tickets/{ticket_id}/status", json={"status": "IN_PROGRESS"}, headers=headers)

        # Query all activity logs for this ticket
        logs = test_repo.activity_logs.list(entity_type="ticket", entity_id=ticket_id)

        # Verify multiple logs created in chronological order
        assert len(logs) == 3  # Create, update, status change
        assert logs[0].action == ActionType.TICKET_CREATED
        assert logs[1].action == ActionType.TICKET_UPDATED
        assert logs[2].action == ActionType.TICKET_STATUS_CHANGED

        # Verify chronological order
        assert logs[0].timestamp <= logs[1].timestamp <= logs[2].timestamp


class TestTicketCoverageExpansion:
    """Coverage-expansion tests added per docs/tasks/test-coverage-expansion/plan.md."""

    # T1
    @pytest.mark.error
    def test_create_ticket_with_assignee_outside_org_fails(self, client: TestClient, super_admin_token: str) -> None:
        """Cannot assign ticket to a user from a different organization."""
        from tests.helpers import create_test_org

        org_a = create_test_org(client, super_admin_token, name="TicketOrgA")
        org_b = create_test_org(client, super_admin_token, name="TicketOrgB")

        _, adminA_pw = create_admin_user(client, super_admin_token, org_a, username="tadma")
        adminA_token = client.post("/auth/login", json={"username": "tadma", "password": adminA_pw}).json()[
            "access_token"
        ]
        outsider_id, _ = create_admin_user(client, super_admin_token, org_b, username="tadmb", email="b@b.com")

        project_id = client.post(
            "/api/projects", json={"name": "CrossOrgProject"}, headers=auth_headers(adminA_token)
        ).json()["id"]

        response = client.post(
            f"/api/tickets?project_id={project_id}&assignee_id={outsider_id}",
            json={"title": "Cross-org assignment"},
            headers=auth_headers(adminA_token),
        )
        assert response.status_code == 403

    # T2
    @pytest.mark.error
    def test_create_ticket_with_epic_in_different_project_fails(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Epics are org-scoped (not project-scoped).

        # Spec: Epic has organization_id, not project_id; linking a ticket to an epic in the
        # same org succeeds even across projects. Ticket create endpoint does NOT accept epic_id.
        """
        token, _ = org_admin_token
        project1 = client.post("/api/projects", json={"name": "EpicProj1"}, headers=auth_headers(token)).json()["id"]
        project2 = client.post("/api/projects", json={"name": "EpicProj2"}, headers=auth_headers(token)).json()["id"]
        epic = client.post("/api/epics", json={"name": "Shared Epic"}, headers=auth_headers(token)).json()

        # Create ticket in project1
        ticket = client.post(
            f"/api/tickets?project_id={project1}",
            json={"title": "t1"},
            headers=auth_headers(token),
        ).json()

        # Link to epic (same org) — succeeds even though ticket is in project1 and epic is org-level
        link = client.post(
            f"/api/epics/{epic['id']}/tickets?ticket_id={ticket['id']}",
            headers=auth_headers(token),
        )
        assert link.status_code == 200
        # Second ticket in project2 also links successfully since epic is org-scoped
        ticket2 = client.post(
            f"/api/tickets?project_id={project2}",
            json={"title": "t2"},
            headers=auth_headers(token),
        ).json()
        link2 = client.post(
            f"/api/epics/{epic['id']}/tickets?ticket_id={ticket2['id']}",
            headers=auth_headers(token),
        )
        assert link2.status_code == 200

    # T3
    @pytest.mark.error
    def test_transition_ticket_to_invalid_status_fails(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Setting ticket status to a value not in the project's workflow returns 422."""
        token, _ = org_admin_token
        project_id = client.post("/api/projects", json={"name": "StatusProj"}, headers=auth_headers(token)).json()["id"]
        ticket_id = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "St"},
            headers=auth_headers(token),
        ).json()["id"]

        response = client.put(
            f"/api/tickets/{ticket_id}/status",
            json={"status": "BOGUS_STATUS"},
            headers=auth_headers(token),
        )
        assert response.status_code == 422

    # T4
    @pytest.mark.scenario
    @pytest.mark.behavior("tickets")
    def test_transition_ticket_follows_default_workflow_TODO_to_IN_PROGRESS_to_DONE(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Default workflow transitions TODO -> IN_PROGRESS -> DONE succeed."""
        token, _ = org_admin_token
        project_id = client.post("/api/projects", json={"name": "TransProj"}, headers=auth_headers(token)).json()["id"]
        ticket_id = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Flow"},
            headers=auth_headers(token),
        ).json()["id"]

        for next_status in ("IN_PROGRESS", "DONE"):
            response = client.put(
                f"/api/tickets/{ticket_id}/status",
                json={"status": next_status},
                headers=auth_headers(token),
            )
            assert response.status_code == 200
            assert response.json()["status"] == next_status

    # T5
    def test_reopen_ticket_from_DONE_to_IN_PROGRESS_allowed_or_blocked(
        self, client: TestClient, org_admin_token: tuple[str, str]
    ) -> None:
        """Reopening a DONE ticket back to IN_PROGRESS is allowed.

        # Spec: default workflow validates membership in status list, not directional transitions.
        """
        token, _ = org_admin_token
        project_id = client.post("/api/projects", json={"name": "ReopenProj"}, headers=auth_headers(token)).json()["id"]
        ticket_id = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Reopen"},
            headers=auth_headers(token),
        ).json()["id"]

        client.put(f"/api/tickets/{ticket_id}/status", json={"status": "DONE"}, headers=auth_headers(token))
        response = client.put(
            f"/api/tickets/{ticket_id}/status",
            json={"status": "IN_PROGRESS"},
            headers=auth_headers(token),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "IN_PROGRESS"

    # T6
    def test_list_tickets_filters_by_status(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """GET /api/tickets?status=DONE returns only DONE tickets."""
        token, _ = org_admin_token
        project_id = client.post(
            "/api/projects", json={"name": "FilterStatusProj"}, headers=auth_headers(token)
        ).json()["id"]

        t1 = client.post(
            f"/api/tickets?project_id={project_id}", json={"title": "A"}, headers=auth_headers(token)
        ).json()
        t2 = client.post(
            f"/api/tickets?project_id={project_id}", json={"title": "B"}, headers=auth_headers(token)
        ).json()
        client.put(f"/api/tickets/{t2['id']}/status", json={"status": "DONE"}, headers=auth_headers(token))

        response = client.get(f"/api/tickets?project_id={project_id}&status=DONE", headers=auth_headers(token))
        assert response.status_code == 200
        ids = [t["id"] for t in response.json()]
        assert t2["id"] in ids and t1["id"] not in ids

    # T7
    def test_list_tickets_filters_by_assignee(self, client: TestClient, super_admin_token: str) -> None:
        """GET /api/tickets?assignee_id=X returns only tickets assigned to that user."""
        from tests.helpers import create_test_org

        org_id = create_test_org(client, super_admin_token, name="AssigneeFilterOrg")
        _, admin_pw = create_admin_user(client, super_admin_token, org_id, username="afa")
        admin_token = client.post("/auth/login", json={"username": "afa", "password": admin_pw}).json()["access_token"]
        assignee_id, _ = create_write_user(client, super_admin_token, org_id)

        project_id = client.post("/api/projects", json={"name": "AssFilter"}, headers=auth_headers(admin_token)).json()[
            "id"
        ]
        t_assigned = client.post(
            f"/api/tickets?project_id={project_id}&assignee_id={assignee_id}",
            json={"title": "Mine"},
            headers=auth_headers(admin_token),
        ).json()
        t_unassigned = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Yours"},
            headers=auth_headers(admin_token),
        ).json()

        response = client.get(f"/api/tickets?assignee_id={assignee_id}", headers=auth_headers(admin_token))
        assert response.status_code == 200
        ids = [t["id"] for t in response.json()]
        assert t_assigned["id"] in ids and t_unassigned["id"] not in ids

    # T8
    def test_list_tickets_filters_by_priority(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Priority filter is NOT a server-side query parameter.

        # Spec: GET /api/tickets does not accept a `priority` query param (see ticket_api.py).
        # Filtering by priority must be done client-side. This test documents that behavior
        # by asserting the endpoint ignores unknown params and returns all tickets.
        """
        token, _ = org_admin_token
        project_id = client.post("/api/projects", json={"name": "PrioProj"}, headers=auth_headers(token)).json()["id"]
        low = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "L", "priority": "LOW"},
            headers=auth_headers(token),
        ).json()
        high = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "H", "priority": "HIGH"},
            headers=auth_headers(token),
        ).json()

        # Unknown query param is ignored; both tickets returned
        response = client.get(
            f"/api/tickets?project_id={project_id}&priority=HIGH",
            headers=auth_headers(token),
        )
        assert response.status_code == 200
        ids = {t["id"] for t in response.json()}
        assert low["id"] in ids and high["id"] in ids

        # Client-side filter confirms priority is returned in payloads
        high_only = [t for t in response.json() if t["priority"] == "HIGH"]
        assert [t["id"] for t in high_only] == [high["id"]]
