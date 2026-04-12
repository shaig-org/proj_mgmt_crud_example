"""Validation testing rules for the system API state machine.

This mixin provides property-based test rules that intentionally attempt invalid
operations to verify the API rejects them correctly with appropriate error codes
and messages.
"""

from typing import TYPE_CHECKING

from hypothesis.stateful import rule

from .bundles import Bundles

if TYPE_CHECKING:
    from tests.sdk.test_sdk import APITestSDK

    from .state_tracker import StateTracker


class ValidationRulesMixin:
    """Mixin providing validation testing rules for PBT.

    These rules are different from normal operation rules - they intentionally
    attempt INVALID operations and verify the API rejects them correctly.

    This mixin expects the parent class to have:
    - self.state: StateTracker instance for shadow state
    - self.sdk: APITestSDK instance with super admin auth

    Bundle references use Bundles.tickets, Bundles.users from bundles.py.
    """

    # Type hints for mixin - these are provided by the parent class
    sdk: "APITestSDK"
    state: "StateTracker"

    @rule(ticket_id=Bundles.tickets, assignee_id=Bundles.users)
    def attempt_assign_to_inactive_user(self, ticket_id: str, assignee_id: str) -> None:
        """Test that assigning ticket to inactive user returns 400.

        This rule tests VALIDATION - it intentionally attempts an invalid operation
        and verifies the API rejects it correctly.
        """
        # Precondition: Only run if user IS inactive (opposite of assign_ticket_to_user)
        if assignee_id not in self.state.user_data:
            return
        if self.state.user_data[assignee_id].get("is_active", True):
            return  # Skip if user is active

        # Precondition: Skip if ticket or user is deleted
        if ticket_id in self.state.deleted_ticket_ids:
            return
        if assignee_id in self.state.deleted_user_ids:
            return

        # Attempt to assign ticket to inactive user via SDK
        result = self.sdk.tickets.assign(ticket_id, assignee_id)

        # Invariant: Assignment to inactive user should return 400
        result.assert_status(400)

        # Invariant: Error message should mention "inactive"
        result.assert_error_contains("inactive")

    @rule(ticket_id=Bundles.tickets, assignee_id=Bundles.users)
    def attempt_assign_to_deleted_user(self, ticket_id: str, assignee_id: str) -> None:
        """Test that assigning ticket to deleted user returns 404.

        This rule tests VALIDATION - it intentionally attempts an invalid operation
        and verifies the API rejects it correctly.
        """
        # Precondition: Only run if user IS deleted (opposite of assign_ticket_to_user)
        if assignee_id not in self.state.deleted_user_ids:
            return  # Skip if user is not deleted

        # Precondition: Skip if ticket is deleted
        if ticket_id in self.state.deleted_ticket_ids:
            return

        # Attempt to assign ticket to deleted user via SDK
        result = self.sdk.tickets.assign(ticket_id, assignee_id)

        # Invariant: Assignment to deleted user should return 404
        result.assert_status(404)

        # Invariant: Error message should mention user not found
        assert result.error is not None, "Error message should be present for 404 response"
        assert "not found" in result.error.lower() or "user" in result.error.lower(), (
            f"Error message should mention user not found, got: {result.error}"
        )

    @rule(ticket_id=Bundles.tickets)
    def attempt_invalid_status_transition(self, ticket_id: str) -> None:
        """Test that setting an invalid status returns 422.

        This rule tests VALIDATION - it intentionally attempts an invalid operation
        and verifies the API rejects it correctly.
        """
        # Precondition: Skip if ticket is deleted
        if ticket_id in self.state.deleted_ticket_ids:
            return

        # Precondition: Get ticket's project to know valid statuses
        if ticket_id not in self.state.ticket_data:
            return

        project_id = self.state.ticket_data[ticket_id]["project_id"]

        # Get valid statuses for this project
        if project_id not in self.state.project_statuses:
            return

        valid_statuses = self.state.project_statuses[project_id]
        if not valid_statuses:
            return

        # Use an invalid status that is definitely not in the workflow
        # Common workflow statuses are TODO, IN_PROGRESS, DONE, etc.
        # We'll use something that should never be valid
        invalid_status = "DEFINITELY_NOT_A_VALID_STATUS_XYZ123"

        # Make sure this isn't somehow valid
        if invalid_status in valid_statuses:
            return  # Skip if by some chance this status is valid

        # Attempt to set invalid status via SDK
        result = self.sdk.tickets.update_status(ticket_id, invalid_status)

        # Invariant: Invalid status should return 422 (validation error) or 400 (business logic error)
        # Both are acceptable as different layers may catch the validation
        assert result.status_code in [400, 422], f"Invalid status should return 400 or 422, got {result.status_code}"
