"""State tracking for the DAL state machine.

This module manages all shadow state for verifying repository consistency.
The StateTracker maintains parallel state to what the repository should have,
allowing us to verify invariants after each operation.

Unlike the API state tracker, this version is simpler:
- No HTTP status code tracking
- No authentication/token management
- Focus on domain models and database state
- Direct repository verification
"""


class StateTracker:
    """Tracks shadow state for all entities in the repository.

    This class manages all tracking dictionaries and provides methods
    for verifying state consistency. It serves as the "expected state"
    that we compare against actual repository responses.

    Attributes:
        organization_id: Primary organization ID for this test run
        created_org_ids: Set of all organization IDs created
        created_user_ids: Set of all user IDs created
        deleted_user_ids: Set of user IDs that have been deleted
        user_data: Shadow state for user fields
        created_project_ids: Set of all project IDs created
        project_statuses: Valid workflow statuses per project
        created_ticket_ids: Set of all ticket IDs created
        deleted_ticket_ids: Set of ticket IDs that have been deleted
        ticket_data: Shadow state for ticket fields
    """

    # Define immutable fields once for reuse across all checks
    IMMUTABLE_USER_FIELDS = ["username", "organization_id"]

    def __init__(self, organization_id: str) -> None:
        """Initialize state tracker with initial organization.

        Args:
            organization_id: Primary organization ID for this test run
        """
        # Organizations
        self.created_org_ids: set[str] = {organization_id}
        self.organization_id = organization_id  # Primary org

        # Users
        self.created_user_ids: set[str] = set()
        self.deleted_user_ids: set[str] = set()

        # Shadow state for user data
        self.user_data: dict[
            str, dict[str, str | bool]
        ] = {}  # user_id -> {username, email, full_name, role, is_active}

        # Track immutable fields (username, organization_id) for invariant checking
        self.immutable_fields: dict[str, dict[str, str]] = {}  # user_id -> {username, organization_id}

        # Projects
        self.created_project_ids: set[str] = set()
        self.project_statuses: dict[str, list[str]] = {}  # project_id -> list of valid statuses

        # Tickets
        self.created_ticket_ids: set[str] = set()
        self.deleted_ticket_ids: set[str] = set()
        self.ticket_data: dict[str, dict] = {}  # ticket_id -> {title, description, priority, status, ...}

    def verify_immutable_fields(self, user_id: str, user_obj: dict) -> None:
        """Verify that immutable user fields haven't changed.

        This is a critical invariant - certain fields like username and
        organization_id should never change once set.

        Args:
            user_id: User ID to verify
            user_obj: User object dict with current values

        Raises:
            AssertionError: If any immutable field has changed
        """
        if user_id not in self.immutable_fields:
            return  # First time seeing this user, nothing to verify

        original = self.immutable_fields[user_id]
        for field in self.IMMUTABLE_USER_FIELDS:
            original_value = original.get(field)
            current_value = user_obj.get(field)
            assert original_value == current_value, (
                f"Immutable field {field} changed for user {user_id}: {original_value} -> {current_value}"
            )

    def track_user(self, user_id: str, user_obj: dict) -> None:
        """Track a new user in shadow state.

        Args:
            user_id: User ID to track
            user_obj: User object dict with all fields
        """
        self.created_user_ids.add(user_id)
        self.user_data[user_id] = {
            "username": user_obj["username"],
            "full_name": user_obj["full_name"],
            "email": user_obj["email"],
            "role": user_obj["role"],
            "is_active": user_obj.get("is_active", True),
            "organization_id": user_obj["organization_id"],
        }
        self.immutable_fields[user_id] = {
            "username": user_obj["username"],
            "organization_id": user_obj["organization_id"],
        }

    def update_user_field(self, user_id: str, field: str, value: str | bool) -> None:
        """Update a mutable user field in shadow state.

        Args:
            user_id: User ID to update
            field: Field name to update
            value: New value for the field
        """
        if user_id in self.user_data:
            self.user_data[user_id][field] = value

    def delete_user(self, user_id: str) -> None:
        """Mark user as deleted and clean up shadow state.

        Args:
            user_id: User ID to delete
        """
        self.deleted_user_ids.add(user_id)
        if user_id in self.user_data:
            del self.user_data[user_id]
        if user_id in self.immutable_fields:
            del self.immutable_fields[user_id]

    def track_ticket(self, ticket_id: str, ticket_obj: dict) -> None:
        """Track a new ticket in shadow state.

        Args:
            ticket_id: Ticket ID to track
            ticket_obj: Ticket object dict with all fields
        """
        self.created_ticket_ids.add(ticket_id)
        self.ticket_data[ticket_id] = {
            "title": ticket_obj["title"],
            "description": ticket_obj["description"],
            "priority": ticket_obj["priority"],
            "status": ticket_obj["status"],
            "assignee_id": ticket_obj.get("assignee_id"),
            "reporter_id": ticket_obj.get("reporter_id"),
            "project_id": ticket_obj["project_id"],
        }

    def update_ticket_field(self, ticket_id: str, field: str, value: str | None) -> None:
        """Update a ticket field in shadow state.

        Args:
            ticket_id: Ticket ID to update
            field: Field name to update
            value: New value for the field
        """
        if ticket_id in self.ticket_data:
            self.ticket_data[ticket_id][field] = value

    def delete_ticket(self, ticket_id: str) -> None:
        """Mark ticket as deleted and clean up shadow state.

        Args:
            ticket_id: Ticket ID to delete
        """
        self.deleted_ticket_ids.add(ticket_id)
        if ticket_id in self.ticket_data:
            del self.ticket_data[ticket_id]
