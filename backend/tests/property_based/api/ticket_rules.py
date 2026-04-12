"""Ticket operation rules for the system API state machine.

This mixin provides all property-based test rules for ticket-related API operations.
Each rule tests a specific API operation and verifies invariants are maintained.
"""

from typing import TYPE_CHECKING

from hypothesis import strategies as st
from hypothesis.stateful import rule

from project_management_crud_example.domain_models import TicketPriority

from .bundles import Bundles

if TYPE_CHECKING:
    from tests.sdk.test_sdk import APITestSDK

    from .state_tracker import StateTracker


class TicketRulesMixin:
    """Mixin providing ticket-related PBT rules.

    This mixin expects the parent class to have:
    - self.state: StateTracker instance for shadow state
    - self.sdk: APITestSDK instance with super admin auth
    - self.admin_sdk: APITestSDK instance with admin auth (for list operations)

    Bundle references use Bundles.tickets, Bundles.projects, Bundles.users from bundles.py.
    """

    # Type hints for mixin - these are provided by the parent class
    sdk: "APITestSDK"
    admin_sdk: "APITestSDK"
    state: "StateTracker"

    @rule(target=Bundles.tickets, project_id=Bundles.projects, reporter_id=Bundles.users)
    def create_ticket_via_api(self, project_id: str, reporter_id: str) -> str:
        """Create a new ticket via API and add to bundle."""
        import uuid

        title = f"Ticket {uuid.uuid4().hex[:8]}"
        description = f"Description for {title}"
        priority = "HIGH"

        # Create ticket via SDK
        ticket = self.sdk.tickets.create(project_id, title, description, priority).assert_ok()
        ticket_id = ticket.id

        # Track in shadow state
        self.state.created_ticket_ids.add(ticket_id)
        self.state.ticket_data[ticket_id] = {
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
        retrieved_ticket = self.sdk.tickets.get(ticket_id).assert_ok()
        assert retrieved_ticket is not None, "Just-created ticket should be retrievable"

        return ticket_id

    @rule(ticket_id=Bundles.tickets)
    def get_ticket_via_api(self, ticket_id: str) -> None:
        """Retrieve a ticket by ID via API."""
        result = self.sdk.tickets.get(ticket_id)

        # Invariant: Status code matches deletion state
        if ticket_id not in self.state.deleted_ticket_ids:
            assert result.ok, f"Non-deleted ticket should return 200, got {result.status_code}"

            ticket = result.data
            assert ticket is not None, "Ticket data should not be None for successful request"
            assert ticket.id == ticket_id

            # Invariant: Retrieved data matches shadow state
            if ticket_id in self.state.ticket_data:
                shadow = self.state.ticket_data[ticket_id]
                assert ticket.title == shadow["title"], f"Title mismatch for ticket {ticket_id}"
                assert ticket.description == shadow["description"], f"Description mismatch for ticket {ticket_id}"
                assert ticket.priority is not None, f"Priority should not be None for ticket {ticket_id}"
                assert ticket.priority.value == shadow["priority"], f"Priority mismatch for ticket {ticket_id}"
                assert ticket.status == shadow["status"], f"Status mismatch for ticket {ticket_id}"
                assert ticket.project_id == shadow["project_id"], f"Project ID mismatch for ticket {ticket_id}"
        else:
            assert result.status_code == 404, f"Deleted ticket should return 404, got {result.status_code}"

    @rule(ticket_id=Bundles.tickets)
    def delete_ticket_via_api(self, ticket_id: str) -> None:
        """Delete a ticket via API."""
        # Skip if already deleted
        if ticket_id in self.state.deleted_ticket_ids:
            return

        # Delete ticket via SDK
        self.sdk.tickets.delete(ticket_id).assert_ok()

        # Track deletion and clean up shadow state
        self.state.deleted_ticket_ids.add(ticket_id)
        if ticket_id in self.state.ticket_data:
            del self.state.ticket_data[ticket_id]

        # Invariant: Deleted ticket should return 404
        result = self.sdk.tickets.get(ticket_id)
        assert result.status_code == 404, "Deleted ticket should return 404"

    @rule(ticket_id=Bundles.tickets, new_title=st.text(min_size=1, max_size=100))
    def update_ticket_title(self, ticket_id: str, new_title: str) -> None:
        """Update a ticket's title via API."""
        # Skip if deleted
        if ticket_id in self.state.deleted_ticket_ids:
            return

        # Update ticket via SDK
        ticket = self.sdk.tickets.update(ticket_id, title=new_title).assert_ok()

        # Invariant: Updated field changed
        assert ticket.title == new_title, "Title should be updated"

        # Update shadow state
        if ticket_id in self.state.ticket_data:
            self.state.ticket_data[ticket_id]["title"] = new_title

    @rule(ticket_id=Bundles.tickets, new_priority=st.sampled_from(["LOW", "MEDIUM", "HIGH", "CRITICAL"]))
    def update_ticket_priority(self, ticket_id: str, new_priority: str) -> None:
        """Update a ticket's priority via API."""
        # Skip if deleted
        if ticket_id in self.state.deleted_ticket_ids:
            return

        # Update ticket via SDK
        ticket = self.sdk.tickets.update(ticket_id, priority=new_priority).assert_ok()

        # Invariant: Updated field changed
        assert ticket.priority is not None, "Priority should not be None after update"
        assert ticket.priority.value == new_priority, "Priority should be updated"

        # Update shadow state
        if ticket_id in self.state.ticket_data:
            self.state.ticket_data[ticket_id]["priority"] = new_priority

    @rule(ticket_id=Bundles.tickets)
    def update_ticket_status(self, ticket_id: str) -> None:
        """Update a ticket's status to a valid status from its project's workflow."""
        # Skip if deleted
        if ticket_id in self.state.deleted_ticket_ids:
            return

        # Get ticket's project
        if ticket_id not in self.state.ticket_data:
            return

        project_id = self.state.ticket_data[ticket_id]["project_id"]

        # Get valid statuses for this project
        if project_id not in self.state.project_statuses:
            return

        valid_statuses = self.state.project_statuses[project_id]
        if not valid_statuses:
            return

        # Pick first valid status for simplicity
        new_status = valid_statuses[0]

        # Update status via SDK
        ticket = self.sdk.tickets.update_status(ticket_id, new_status).assert_ok()

        # Invariant: Status should be updated
        assert ticket.status == new_status, f"Status should be {new_status}, got {ticket.status}"

        # Update shadow state
        if ticket_id in self.state.ticket_data:
            self.state.ticket_data[ticket_id]["status"] = new_status

    @rule(ticket_id=Bundles.tickets, assignee_id=Bundles.users)
    def assign_ticket_to_user(self, ticket_id: str, assignee_id: str) -> None:
        """Assign a ticket to a user via API."""
        # Skip if ticket or user is deleted
        if ticket_id in self.state.deleted_ticket_ids:
            return
        if assignee_id in self.state.deleted_user_ids:
            return
        # Skip if user is inactive (cannot assign to inactive users)
        if assignee_id in self.state.user_data and not self.state.user_data[assignee_id].get("is_active", True):
            return

        # Assign ticket via SDK
        ticket = self.sdk.tickets.assign(ticket_id, assignee_id).assert_ok()

        # Invariant: Assignee should be updated
        assert ticket.assignee_id == assignee_id, f"Assignee should be {assignee_id}"

        # Update shadow state
        if ticket_id in self.state.ticket_data:
            self.state.ticket_data[ticket_id]["assignee_id"] = assignee_id

    @rule(ticket_id=Bundles.tickets)
    def unassign_ticket(self, ticket_id: str) -> None:
        """Unassign a ticket via API."""
        # Skip if deleted
        if ticket_id in self.state.deleted_ticket_ids:
            return

        # Unassign ticket via SDK
        ticket = self.sdk.tickets.assign(ticket_id, None).assert_ok()

        # Invariant: Assignee should be None
        assert ticket.assignee_id is None, "Assignee should be None"

        # Update shadow state
        if ticket_id in self.state.ticket_data:
            self.state.ticket_data[ticket_id]["assignee_id"] = None

    @rule(project_id=Bundles.projects)
    def list_tickets_by_project(self, project_id: str) -> None:
        """List all tickets for a project and verify count matches shadow state."""
        # List tickets via SDK (using admin SDK for list operation)
        tickets_list = self.admin_sdk.tickets.list(project_id=project_id).assert_ok()

        # Invariant: Count matches expected tickets in this project
        expected_ticket_ids = {
            ticket_id
            for ticket_id in self.state.ticket_data
            if ticket_id not in self.state.deleted_ticket_ids
            and self.state.ticket_data[ticket_id]["project_id"] == project_id
        }
        returned_ticket_ids = {t.id for t in tickets_list}

        assert returned_ticket_ids == expected_ticket_ids, (
            f"Project filter mismatch. Expected {len(expected_ticket_ids)} tickets in project {project_id}, "
            f"got {len(returned_ticket_ids)}"
        )

        # Invariant: All returned tickets belong to this project
        for ticket in tickets_list:
            assert ticket.project_id == project_id, f"Ticket {ticket.id} should be in project {project_id}"
