"""Stateful property-based tests for Ticket API endpoints."""

from fastapi.testclient import TestClient
from hypothesis import strategies as st
from hypothesis.stateful import Bundle, RuleBasedStateMachine, rule, run_state_machine_as_test

from project_management_crud_example.domain_models import Ticket, TicketPriority
from tests.conftest import client  # noqa: F401
from tests.fixtures.auth_fixtures import super_admin_token  # noqa: F401
from tests.helpers import create_admin_user, create_test_org, create_test_project, create_test_user


class TicketAPIStateMachine(RuleBasedStateMachine):
    """Stateful property-based tests for Ticket API endpoints.

    This tests that API operations maintain consistent state:
    - Created tickets return 201 and can be retrieved with 200
    - Deleted tickets return 404 on GET
    - Updated tickets persist changes correctly
    - Status transitions follow workflow rules
    - Assignments are tracked correctly
    - List endpoint count matches created - deleted tickets
    - Organization and project isolation is enforced
    - HTTP responses are consistent with state
    """

    tickets = Bundle("tickets")
    projects = Bundle("projects")
    users = Bundle("users")

    def __init__(self, client: TestClient, super_admin_token: str, organization_id: str, admin_token: str) -> None:
        super().__init__()
        self.client = client
        self.super_admin_token = super_admin_token
        self.organization_id = organization_id
        self.admin_token = admin_token

        # Track entities
        self.created_ticket_ids: set[str] = set()
        self.deleted_ticket_ids: set[str] = set()
        self.created_project_ids: set[str] = set()
        self.created_user_ids: set[str] = set()

        # Shadow state for tickets
        self.ticket_data: dict[
            str, dict
        ] = {}  # ticket_id -> {title, description, priority, status, assignee_id, reporter_id, project_id}

        # Shadow state for projects (to track valid statuses)
        self.project_statuses: dict[str, list[str]] = {}  # project_id -> list of valid statuses

        # Shadow state for users
        self.user_data: dict[str, dict] = {}  # user_id -> {username, organization_id}

    @rule(target=projects)
    def create_project_via_api(self) -> str:
        """Create a new project via API and add to bundle."""
        import uuid

        project_name = f"Project {uuid.uuid4().hex[:8]}"

        # Use helper to create project (using admin token, not super admin)
        project_id = create_test_project(
            self.client,
            self.admin_token,
            name=project_name,
        )

        # Track project
        self.created_project_ids.add(project_id)

        # Get project to get workflow information
        project_response = self.client.get(
            f"/api/projects/{project_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )
        assert project_response.status_code == 200

        project = project_response.json()

        # Get workflow statuses for this project
        workflow_id = project.get("workflow_id")
        if workflow_id:
            workflow_response = self.client.get(
                f"/api/workflows/{workflow_id}",
                headers={"Authorization": f"Bearer {self.super_admin_token}"},
            )
            if workflow_response.status_code == 200:
                workflow = workflow_response.json()
                self.project_statuses[project_id] = workflow.get("statuses", ["TODO", "IN_PROGRESS", "DONE"])
            else:
                # Default statuses
                self.project_statuses[project_id] = ["TODO", "IN_PROGRESS", "DONE"]
        else:
            self.project_statuses[project_id] = ["TODO", "IN_PROGRESS", "DONE"]

        return project_id

    @rule(target=users)
    def create_user_via_api(self) -> str:
        """Create a new user via API and add to bundle."""
        import uuid

        username = f"user{uuid.uuid4().hex[:8]}"

        # Create user via helper
        user_id, _ = create_test_user(
            self.client,
            self.super_admin_token,
            self.organization_id,
            username=username,
        )

        # Track user
        self.created_user_ids.add(user_id)
        self.user_data[user_id] = {
            "username": username,
            "organization_id": self.organization_id,
        }

        return user_id

    @rule(target=tickets, project_id=projects, reporter_id=users)
    def create_ticket_via_api(self, project_id: str, reporter_id: str) -> str:
        """Create a new ticket via API and add to bundle."""
        import uuid

        title = f"Ticket {uuid.uuid4().hex[:8]}"
        description = f"Description for {title}"
        priority = "HIGH"

        # Create ticket via API
        response = self.client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": title, "description": description, "priority": priority},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Create should return 201
        assert response.status_code == 201, f"Create ticket should return 201, got {response.status_code}"

        ticket = Ticket.model_validate(response.json())
        ticket_id = ticket.id

        # Track in shadow state
        self.created_ticket_ids.add(ticket_id)
        self.ticket_data[ticket_id] = {
            "title": title,
            "description": description,
            "priority": priority,
            "status": ticket.status,  # Use actual status from response
            "assignee_id": None,
            "reporter_id": reporter_id,
            "project_id": project_id,
        }

        # Invariant: Ticket data matches what we sent
        assert ticket.title == title
        assert ticket.description == description
        assert ticket.priority == TicketPriority.HIGH
        assert ticket.project_id == project_id

        # Invariant: Just-created ticket should be retrievable
        get_response = self.client.get(
            f"/api/tickets/{ticket_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )
        assert get_response.status_code == 200, "Just-created ticket should return 200 on GET"

        return ticket_id

    @rule(ticket_id=tickets)
    def get_ticket_via_api(self, ticket_id: str) -> None:
        """Retrieve a ticket by ID via API."""
        response = self.client.get(
            f"/api/tickets/{ticket_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Status code matches deletion state
        if ticket_id not in self.deleted_ticket_ids:
            assert response.status_code == 200, f"Non-deleted ticket should return 200, got {response.status_code}"

            ticket = Ticket.model_validate(response.json())
            assert ticket.id == ticket_id

            # Invariant: Retrieved data matches shadow state
            if ticket_id in self.ticket_data:
                shadow = self.ticket_data[ticket_id]
                assert ticket.title == shadow["title"], f"Title mismatch for ticket {ticket_id}"
                assert ticket.description == shadow["description"], f"Description mismatch for ticket {ticket_id}"
                assert ticket.priority.value == shadow["priority"], f"Priority mismatch for ticket {ticket_id}"
                assert ticket.status == shadow["status"], f"Status mismatch for ticket {ticket_id}"
                assert ticket.project_id == shadow["project_id"], f"Project ID mismatch for ticket {ticket_id}"
        else:
            assert response.status_code == 404, f"Deleted ticket should return 404, got {response.status_code}"

    @rule(ticket_id=tickets)
    def delete_ticket_via_api(self, ticket_id: str) -> None:
        """Delete a ticket via API."""
        # Skip if already deleted
        if ticket_id in self.deleted_ticket_ids:
            return

        # Delete ticket
        response = self.client.delete(
            f"/api/tickets/{ticket_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Delete should return 204
        assert response.status_code == 204, f"Delete should return 204, got {response.status_code}"

        # Track deletion and clean up shadow state
        self.deleted_ticket_ids.add(ticket_id)
        if ticket_id in self.ticket_data:
            del self.ticket_data[ticket_id]

        # Invariant: Deleted ticket should return 404
        get_response = self.client.get(
            f"/api/tickets/{ticket_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )
        assert get_response.status_code == 404, "Deleted ticket should return 404"

    @rule(ticket_id=tickets, new_title=st.text(min_size=1, max_size=100))
    def update_ticket_title(self, ticket_id: str, new_title: str) -> None:
        """Update a ticket's title via API."""
        # Skip if deleted
        if ticket_id in self.deleted_ticket_ids:
            return

        # Update ticket
        response = self.client.put(
            f"/api/tickets/{ticket_id}",
            json={"title": new_title},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Update should return 200
        assert response.status_code == 200, f"Update should return 200, got {response.status_code}"

        ticket = Ticket.model_validate(response.json())

        # Invariant: Updated field changed
        assert ticket.title == new_title, "Title should be updated"

        # Update shadow state
        if ticket_id in self.ticket_data:
            self.ticket_data[ticket_id]["title"] = new_title

    @rule(ticket_id=tickets, new_priority=st.sampled_from(["LOW", "MEDIUM", "HIGH", "CRITICAL"]))
    def update_ticket_priority(self, ticket_id: str, new_priority: str) -> None:
        """Update a ticket's priority via API."""
        # Skip if deleted
        if ticket_id in self.deleted_ticket_ids:
            return

        # Update ticket
        response = self.client.put(
            f"/api/tickets/{ticket_id}",
            json={"priority": new_priority},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Update should return 200
        assert response.status_code == 200, f"Update should return 200, got {response.status_code}"

        ticket = Ticket.model_validate(response.json())

        # Invariant: Updated field changed
        assert ticket.priority.value == new_priority, "Priority should be updated"

        # Update shadow state
        if ticket_id in self.ticket_data:
            self.ticket_data[ticket_id]["priority"] = new_priority

    @rule(ticket_id=tickets)
    def update_ticket_status(self, ticket_id: str) -> None:
        """Update a ticket's status to a valid status from its project's workflow."""
        # Skip if deleted
        if ticket_id in self.deleted_ticket_ids:
            return

        # Get ticket's project
        if ticket_id not in self.ticket_data:
            return

        project_id = self.ticket_data[ticket_id]["project_id"]

        # Get valid statuses for this project
        if project_id not in self.project_statuses:
            return

        valid_statuses = self.project_statuses[project_id]
        if not valid_statuses:
            return

        # Pick first valid status for simplicity
        new_status = valid_statuses[0]

        # Update status via dedicated endpoint
        response = self.client.put(
            f"/api/tickets/{ticket_id}/status",
            json={"status": new_status},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Update should return 200 for valid status
        assert response.status_code == 200, f"Update status should return 200, got {response.status_code}"

        ticket = Ticket.model_validate(response.json())

        # Invariant: Status should be updated
        assert ticket.status == new_status, f"Status should be {new_status}, got {ticket.status}"

        # Update shadow state
        if ticket_id in self.ticket_data:
            self.ticket_data[ticket_id]["status"] = new_status

    @rule(ticket_id=tickets, assignee_id=users)
    def assign_ticket_to_user(self, ticket_id: str, assignee_id: str) -> None:
        """Assign a ticket to a user via API."""
        # Skip if deleted
        if ticket_id in self.deleted_ticket_ids:
            return

        # Assign ticket
        response = self.client.put(
            f"/api/tickets/{ticket_id}/assignee",
            json={"assignee_id": assignee_id},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Assignment should return 200
        assert response.status_code == 200, f"Assignment should return 200, got {response.status_code}"

        ticket = Ticket.model_validate(response.json())

        # Invariant: Assignee should be updated
        assert ticket.assignee_id == assignee_id, f"Assignee should be {assignee_id}"

        # Update shadow state
        if ticket_id in self.ticket_data:
            self.ticket_data[ticket_id]["assignee_id"] = assignee_id

    @rule(ticket_id=tickets)
    def unassign_ticket(self, ticket_id: str) -> None:
        """Unassign a ticket via API."""
        # Skip if deleted
        if ticket_id in self.deleted_ticket_ids:
            return

        # Unassign ticket
        response = self.client.put(
            f"/api/tickets/{ticket_id}/assignee",
            json={"assignee_id": None},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Unassignment should return 200
        assert response.status_code == 200, f"Unassignment should return 200, got {response.status_code}"

        ticket = Ticket.model_validate(response.json())

        # Invariant: Assignee should be None
        assert ticket.assignee_id is None, "Assignee should be None"

        # Update shadow state
        if ticket_id in self.ticket_data:
            self.ticket_data[ticket_id]["assignee_id"] = None

    @rule(project_id=projects)
    def list_tickets_by_project(self, project_id: str) -> None:
        """List all tickets for a project and verify count matches shadow state."""
        response = self.client.get(
            f"/api/tickets?project_id={project_id}",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )

        # Invariant: List should return 200
        assert response.status_code == 200, f"List should return 200, got {response.status_code}"

        tickets_list = [Ticket.model_validate(t) for t in response.json()]

        # Invariant: Count matches expected tickets in this project
        expected_ticket_ids = {
            ticket_id
            for ticket_id in self.ticket_data
            if ticket_id not in self.deleted_ticket_ids and self.ticket_data[ticket_id]["project_id"] == project_id
        }
        returned_ticket_ids = {t.id for t in tickets_list}

        assert returned_ticket_ids == expected_ticket_ids, (
            f"Project filter mismatch. Expected {len(expected_ticket_ids)} tickets in project {project_id}, "
            f"got {len(returned_ticket_ids)}"
        )

        # Invariant: All returned tickets belong to this project
        for ticket in tickets_list:
            assert ticket.project_id == project_id, f"Ticket {ticket.id} should be in project {project_id}"

    @rule(project_id=projects)
    def list_tickets_by_status(self, project_id: str) -> None:
        """List tickets filtered by status in a specific project."""
        # Get valid statuses for this project
        if project_id not in self.project_statuses:
            return

        valid_statuses = self.project_statuses[project_id]
        if not valid_statuses:
            return

        # Pick first valid status
        filter_status = valid_statuses[0]

        response = self.client.get(
            f"/api/tickets?project_id={project_id}&status={filter_status}",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )

        # Invariant: List should return 200
        assert response.status_code == 200, f"List with status filter should return 200, got {response.status_code}"

        tickets_list = [Ticket.model_validate(t) for t in response.json()]

        # Invariant: All returned tickets have the filtered status and belong to the project
        for ticket in tickets_list:
            assert ticket.status == filter_status, (
                f"Ticket {ticket.id} has status {ticket.status}, expected {filter_status}"
            )
            assert ticket.project_id == project_id, f"Ticket {ticket.id} should be in project {project_id}"

    @rule(assignee_id=users)
    def list_tickets_by_assignee(self, assignee_id: str) -> None:
        """List tickets filtered by assignee and verify only matching tickets are returned."""
        response = self.client.get(
            f"/api/tickets?assignee_id={assignee_id}",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )

        # Invariant: List should return 200
        assert response.status_code == 200, f"List with assignee filter should return 200, got {response.status_code}"

        tickets_list = [Ticket.model_validate(t) for t in response.json()]

        # Invariant: All returned tickets are assigned to this user
        for ticket in tickets_list:
            assert ticket.assignee_id == assignee_id, (
                f"Ticket {ticket.id} has assignee {ticket.assignee_id}, expected {assignee_id}"
            )

    @rule(ticket_id=tickets)
    def verify_ticket_timestamps(self, ticket_id: str) -> None:
        """Verify that timestamps follow correct ordering (updated_at >= created_at)."""
        # Skip if deleted
        if ticket_id in self.deleted_ticket_ids:
            return

        response = self.client.get(
            f"/api/tickets/{ticket_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        if response.status_code == 200:
            ticket = Ticket.model_validate(response.json())

            # Invariant: Timestamps exist and are valid
            assert ticket.created_at is not None, "Ticket should have created_at timestamp"
            assert ticket.updated_at is not None, "Ticket should have updated_at timestamp"

            created_at = ticket.created_at.isoformat()
            updated_at = ticket.updated_at.isoformat()

            # Invariant: updated_at >= created_at
            assert updated_at >= created_at, (
                f"updated_at ({updated_at}) should be >= created_at ({created_at}) for ticket {ticket_id}"
            )


# Test function that pytest will discover
def test_ticket_api_state_machine(client: TestClient, super_admin_token: str) -> None:
    """Run the Ticket API state machine test."""
    import uuid

    # Set up organization and admin user once (not in state machine __init__)
    org_name = f"Test Org {uuid.uuid4().hex[:8]}"
    organization_id = create_test_org(client, super_admin_token, name=org_name)

    # Create an admin user in the organization (super admin can't create projects)
    admin_username = f"admin{uuid.uuid4().hex[:8]}"
    _, admin_password = create_admin_user(client, super_admin_token, organization_id, username=admin_username)

    # Login as admin to get token
    login_response = client.post("/auth/login", json={"username": admin_username, "password": admin_password})
    admin_token = login_response.json()["access_token"]

    # Run state machine with test client and auth tokens
    run_state_machine_as_test(lambda: TicketAPIStateMachine(client, super_admin_token, organization_id, admin_token))
