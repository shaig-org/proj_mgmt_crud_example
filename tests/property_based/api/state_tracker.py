"""State tracking for the system API state machine.

This module manages all shadow state for verifying API consistency across
the entire system. The StateTracker maintains parallel state to what the
API should have, allowing us to verify invariants after each operation.
"""


class StateTracker:
    """Tracks shadow state for all entities in the system.

    This class manages all tracking dictionaries and provides methods
    for verifying state consistency. It serves as the "expected state"
    that we compare against actual API responses.

    Attributes:
        organization_id: Primary organization ID for this test run
        created_org_ids: Set of all organization IDs created
        created_user_ids: Set of all user IDs created
        deleted_user_ids: Set of user IDs that have been deleted
        user_data: Shadow state for mutable user fields
        immutable_fields: Shadow state for immutable user fields
        emails_in_use_per_org: Track email uniqueness per organization
        created_project_ids: Set of all project IDs created
        project_statuses: Valid workflow statuses per project
        created_ticket_ids: Set of all ticket IDs created
        deleted_ticket_ids: Set of ticket IDs that have been deleted
        ticket_data: Shadow state for ticket fields
    """

    # Define immutable fields once for reuse across all checks
    IMMUTABLE_USER_FIELDS = ["username", "organization_id"]

    def __init__(self, organization_id: str, admin_user_id: str) -> None:
        """Initialize state tracker with initial entities.

        Args:
            organization_id: Primary organization ID for this test run
            admin_user_id: Admin user ID created during setup (for infrastructure)
        """
        # Organizations
        self.created_org_ids: set[str] = {organization_id}
        self.organization_id = organization_id  # Primary org

        # Users
        self.created_user_ids: set[str] = {admin_user_id}  # Include admin user
        self.deleted_user_ids: set[str] = set()
        # Note: We don't track admin user in user_data/immutable_fields because
        # we won't be testing operations on it (it's just for infrastructure)

        # Shadow state for user data
        self.user_data: dict[str, dict[str, str | bool]] = {}  # user_id -> {email, full_name, role, is_active}

        # Track immutable fields (username, organization_id) for invariant checking
        self.immutable_fields: dict[str, dict[str, str]] = {}  # user_id -> {username, organization_id}

        # Track emails in use per organization (for uniqueness testing within org)
        self.emails_in_use_per_org: dict[str, set[str]] = {}  # org_id -> set of emails

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

    def track_user_email(self, org_id: str, email: str) -> None:
        """Track email usage for uniqueness checking.

        Args:
            org_id: Organization ID
            email: Email address to track
        """
        if org_id not in self.emails_in_use_per_org:
            self.emails_in_use_per_org[org_id] = set()
        self.emails_in_use_per_org[org_id].add(email)

    def untrack_user_email(self, org_id: str, email: str) -> None:
        """Remove email from tracking when user is deleted.

        Args:
            org_id: Organization ID
            email: Email address to remove
        """
        if org_id in self.emails_in_use_per_org:
            self.emails_in_use_per_org[org_id].discard(email)

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
