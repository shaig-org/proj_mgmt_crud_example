"""Tests for custom workflow validation (REQ-TICKET-016, REQ-TICKET-017).

Tests verify that ticket status values are validated against project's workflow,
and that moving tickets between projects validates status compatibility.
"""

from fastapi.testclient import TestClient

from tests.conftest import client  # noqa: F401
from tests.fixtures.auth_fixtures import super_admin_token  # noqa: F401
from tests.helpers import auth_headers, create_admin_user


def setup_org_with_admin(client: TestClient, super_admin_token: str, org_name: str = "Test Org") -> tuple[str, str]:
    """Helper to create organization and return (org_id, admin_token)."""
    super_admin_headers = auth_headers(super_admin_token)

    # Create organization
    org_response = client.post("/api/organizations", json={"name": org_name}, headers=super_admin_headers)
    org_id = org_response.json()["id"]

    # Create admin user in the org
    admin_id, admin_password = create_admin_user(client, super_admin_token, org_id)
    login_response = client.post("/auth/login", json={"username": "admin", "password": admin_password})
    admin_token = login_response.json()["access_token"]

    return org_id, admin_token


class TestTicketStatusWorkflowValidation:
    """Test REQ-TICKET-016: Validate status against project workflow."""

    def test_create_ticket_without_status_defaults_to_first_workflow_status(
        self, client: TestClient, super_admin_token: str
    ) -> None:
        """Test ticket creation without status defaults to first status in workflow."""
        org_id, admin_token = setup_org_with_admin(client, super_admin_token)
        headers = auth_headers(admin_token)

        # Create custom workflow
        workflow_response = client.post(
            "/api/workflows",
            json={
                "name": "Custom Workflow",
                "description": "Test workflow",
                "statuses": ["BACKLOG", "IN_DEV", "TESTING", "DEPLOYED"],
            },
            params={"organization_id": org_id},
            headers=headers,
        )
        workflow_id = workflow_response.json()["id"]

        # Create project with custom workflow
        project_response = client.post(
            "/api/projects",
            json={"name": "Test Project", "workflow_id": workflow_id},
            headers=headers,
        )
        project_id = project_response.json()["id"]

        # Create ticket WITHOUT status - should default to "BACKLOG" (first in workflow)
        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Test Ticket", "description": "Test"},
            params={"project_id": project_id},
            headers=headers,
        )

        assert ticket_response.status_code == 201
        ticket = ticket_response.json()
        assert ticket["status"] == "BACKLOG"  # First status in custom workflow

    def test_create_ticket_with_valid_custom_status_succeeds(self, client: TestClient, super_admin_token: str) -> None:
        """Test ticket creation with valid custom workflow status succeeds."""
        org_id, admin_token = setup_org_with_admin(client, super_admin_token)
        headers = auth_headers(admin_token)

        # Create custom workflow
        workflow_response = client.post(
            "/api/workflows",
            json={
                "name": "Custom Workflow",
                "statuses": ["BACKLOG", "IN_DEV", "TESTING", "DEPLOYED"],
            },
            params={"organization_id": org_id},
            headers=headers,
        )
        workflow_id = workflow_response.json()["id"]

        # Create project with custom workflow
        project_response = client.post(
            "/api/projects",
            json={"name": "Test Project", "workflow_id": workflow_id},
            headers=headers,
        )
        project_id = project_response.json()["id"]

        # Create ticket with valid custom status "IN_DEV"
        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Test Ticket", "status": "IN_DEV"},
            params={"project_id": project_id},
            headers=headers,
        )

        assert ticket_response.status_code == 201
        ticket = ticket_response.json()
        assert ticket["status"] == "IN_DEV"

    def test_create_ticket_with_invalid_status_returns_422(self, client: TestClient, super_admin_token: str) -> None:
        """Test ticket creation with invalid status returns 422 with helpful error."""
        org_id, admin_token = setup_org_with_admin(client, super_admin_token)
        headers = auth_headers(admin_token)

        # Create custom workflow
        workflow_response = client.post(
            "/api/workflows",
            json={
                "name": "Custom Workflow",
                "statuses": ["BACKLOG", "IN_DEV", "TESTING", "DEPLOYED"],
            },
            params={"organization_id": org_id},
            headers=headers,
        )
        workflow_id = workflow_response.json()["id"]

        # Create project with custom workflow
        project_response = client.post(
            "/api/projects",
            json={"name": "Test Project", "workflow_id": workflow_id},
            headers=headers,
        )
        project_id = project_response.json()["id"]

        # Create ticket with INVALID status "TODO" (not in custom workflow)
        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Test Ticket", "status": "TODO"},
            params={"project_id": project_id},
            headers=headers,
        )

        assert ticket_response.status_code == 422
        error = ticket_response.json()
        assert "Invalid status 'TODO'" in error["detail"]
        assert "Valid statuses: BACKLOG, IN_DEV, TESTING, DEPLOYED" in error["detail"]

    def test_update_status_with_valid_custom_status_succeeds(self, client: TestClient, super_admin_token: str) -> None:
        """Test updating ticket to valid custom workflow status succeeds."""
        org_id, admin_token = setup_org_with_admin(client, super_admin_token)
        headers = auth_headers(admin_token)

        # Create custom workflow
        workflow_response = client.post(
            "/api/workflows",
            json={
                "name": "Custom Workflow",
                "statuses": ["BACKLOG", "IN_DEV", "TESTING", "DEPLOYED"],
            },
            params={"organization_id": org_id},
            headers=headers,
        )
        workflow_id = workflow_response.json()["id"]

        # Create project with custom workflow
        project_response = client.post(
            "/api/projects",
            json={"name": "Test Project", "workflow_id": workflow_id},
            headers=headers,
        )
        project_id = project_response.json()["id"]

        # Create ticket (defaults to BACKLOG)
        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Test Ticket"},
            params={"project_id": project_id},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        # Update to valid custom status
        update_response = client.put(
            f"/api/tickets/{ticket_id}/status",
            json={"status": "TESTING"},
            headers=headers,
        )

        assert update_response.status_code == 200
        updated_ticket = update_response.json()
        assert updated_ticket["status"] == "TESTING"

    def test_update_status_with_invalid_status_returns_422(self, client: TestClient, super_admin_token: str) -> None:
        """Test updating ticket to invalid status returns 422 with helpful error."""
        org_id, admin_token = setup_org_with_admin(client, super_admin_token)
        headers = auth_headers(admin_token)

        # Create custom workflow
        workflow_response = client.post(
            "/api/workflows",
            json={
                "name": "Custom Workflow",
                "statuses": ["BACKLOG", "IN_DEV", "TESTING", "DEPLOYED"],
            },
            params={"organization_id": org_id},
            headers=headers,
        )
        workflow_id = workflow_response.json()["id"]

        # Create project with custom workflow
        project_response = client.post(
            "/api/projects",
            json={"name": "Test Project", "workflow_id": workflow_id},
            headers=headers,
        )
        project_id = project_response.json()["id"]

        # Create ticket
        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Test Ticket"},
            params={"project_id": project_id},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        # Update to INVALID status
        update_response = client.put(
            f"/api/tickets/{ticket_id}/status",
            json={"status": "DONE"},  # Not in custom workflow
            headers=headers,
        )

        assert update_response.status_code == 422
        error = update_response.json()
        assert "Invalid status 'DONE'" in error["detail"]
        assert "Valid statuses: BACKLOG, IN_DEV, TESTING, DEPLOYED" in error["detail"]


class TestMoveTicketBetweenWorkflows:
    """Test REQ-TICKET-017: Validate workflow when moving tickets between projects."""

    def test_move_ticket_with_compatible_status_succeeds(self, client: TestClient, super_admin_token: str) -> None:
        """Test moving ticket between projects with compatible workflows succeeds."""
        org_id, admin_token = setup_org_with_admin(client, super_admin_token)
        headers = auth_headers(admin_token)

        # Create two workflows with overlapping statuses
        workflow1_response = client.post(
            "/api/workflows",
            json={
                "name": "Workflow 1",
                "statuses": ["TODO", "IN_PROGRESS", "DONE", "ARCHIVED"],
            },
            params={"organization_id": org_id},
            headers=headers,
        )
        workflow1_id = workflow1_response.json()["id"]

        workflow2_response = client.post(
            "/api/workflows",
            json={
                "name": "Workflow 2",
                "statuses": ["TODO", "IN_PROGRESS", "DONE"],  # Compatible subset
            },
            params={"organization_id": org_id},
            headers=headers,
        )
        workflow2_id = workflow2_response.json()["id"]

        # Create two projects with different workflows
        project1_response = client.post(
            "/api/projects",
            json={"name": "Project 1", "workflow_id": workflow1_id},
            headers=headers,
        )
        project1_id = project1_response.json()["id"]

        project2_response = client.post(
            "/api/projects",
            json={"name": "Project 2", "workflow_id": workflow2_id},
            headers=headers,
        )
        project2_id = project2_response.json()["id"]

        # Create ticket in project 1 with status "IN_PROGRESS"
        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Test Ticket", "status": "IN_PROGRESS"},
            params={"project_id": project1_id},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        # Move ticket to project 2 (status "IN_PROGRESS" is compatible)
        move_response = client.put(
            f"/api/tickets/{ticket_id}/project",
            json={"project_id": project2_id},
            headers=headers,
        )

        assert move_response.status_code == 200
        moved_ticket = move_response.json()
        assert moved_ticket["project_id"] == project2_id
        assert moved_ticket["status"] == "IN_PROGRESS"  # Status unchanged

    def test_move_ticket_with_incompatible_status_returns_400(self, client: TestClient, super_admin_token: str) -> None:
        """Test moving ticket with incompatible status returns 400 with helpful error."""
        org_id, admin_token = setup_org_with_admin(client, super_admin_token)
        headers = auth_headers(admin_token)

        # Create two workflows with different statuses
        workflow1_response = client.post(
            "/api/workflows",
            json={
                "name": "Dev Workflow",
                "statuses": ["BACKLOG", "IN_DEV", "CODE_REVIEW", "DEPLOYED"],
            },
            params={"organization_id": org_id},
            headers=headers,
        )
        workflow1_id = workflow1_response.json()["id"]

        workflow2_response = client.post(
            "/api/workflows",
            json={
                "name": "Simple Workflow",
                "statuses": ["TODO", "DONE"],  # Incompatible
            },
            params={"organization_id": org_id},
            headers=headers,
        )
        workflow2_id = workflow2_response.json()["id"]

        # Create two projects with different workflows
        project1_response = client.post(
            "/api/projects",
            json={"name": "Dev Project", "workflow_id": workflow1_id},
            headers=headers,
        )
        project1_id = project1_response.json()["id"]

        project2_response = client.post(
            "/api/projects",
            json={"name": "Simple Project", "workflow_id": workflow2_id},
            headers=headers,
        )
        project2_id = project2_response.json()["id"]

        # Create ticket in project 1 with status "CODE_REVIEW"
        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Test Ticket", "status": "CODE_REVIEW"},
            params={"project_id": project1_id},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        # Try to move ticket to project 2 (status "CODE_REVIEW" not in target workflow)
        move_response = client.put(
            f"/api/tickets/{ticket_id}/project",
            json={"project_id": project2_id},
            headers=headers,
        )

        assert move_response.status_code == 400
        error = move_response.json()
        assert "Cannot move ticket" in error["detail"]
        assert "CODE_REVIEW" in error["detail"]
        assert "Valid statuses in target workflow: TODO, DONE" in error["detail"]
        assert "Please update ticket status first" in error["detail"]

    def test_move_ticket_then_update_status_workflow(self, client: TestClient, super_admin_token: str) -> None:
        """Test workflow: update incompatible status first, then move ticket."""
        org_id, admin_token = setup_org_with_admin(client, super_admin_token)
        headers = auth_headers(admin_token)

        # Create two workflows
        workflow1_response = client.post(
            "/api/workflows",
            json={
                "name": "Workflow 1",
                "statuses": ["TODO", "IN_PROGRESS", "ARCHIVED"],
            },
            params={"organization_id": org_id},
            headers=headers,
        )
        workflow1_id = workflow1_response.json()["id"]

        workflow2_response = client.post(
            "/api/workflows",
            json={
                "name": "Workflow 2",
                "statuses": ["TODO", "IN_PROGRESS"],  # No ARCHIVED
            },
            params={"organization_id": org_id},
            headers=headers,
        )
        workflow2_id = workflow2_response.json()["id"]

        # Create two projects
        project1_response = client.post(
            "/api/projects",
            json={"name": "Project 1", "workflow_id": workflow1_id},
            headers=headers,
        )
        project1_id = project1_response.json()["id"]

        project2_response = client.post(
            "/api/projects",
            json={"name": "Project 2", "workflow_id": workflow2_id},
            headers=headers,
        )
        project2_id = project2_response.json()["id"]

        # Create ticket in project 1 with status "ARCHIVED"
        ticket_response = client.post(
            "/api/tickets",
            json={"title": "Test Ticket", "status": "ARCHIVED"},
            params={"project_id": project1_id},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        # Try to move - should fail
        move_response1 = client.put(
            f"/api/tickets/{ticket_id}/project",
            json={"project_id": project2_id},
            headers=headers,
        )
        assert move_response1.status_code == 400

        # Update status to compatible value "TODO"
        status_response = client.put(
            f"/api/tickets/{ticket_id}/status",
            json={"status": "TODO"},
            headers=headers,
        )
        assert status_response.status_code == 200

        # Now move should succeed
        move_response2 = client.put(
            f"/api/tickets/{ticket_id}/project",
            json={"project_id": project2_id},
            headers=headers,
        )
        assert move_response2.status_code == 200
        moved_ticket = move_response2.json()
        assert moved_ticket["project_id"] == project2_id
        assert moved_ticket["status"] == "TODO"
