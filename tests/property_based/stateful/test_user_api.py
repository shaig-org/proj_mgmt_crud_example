"""Stateful property-based tests for User API endpoints."""

from fastapi.testclient import TestClient
from hypothesis import strategies as st
from hypothesis.stateful import Bundle, RuleBasedStateMachine, rule, run_state_machine_as_test

from project_management_crud_example.domain_models import User, UserCreateResponse, UserData, UserUpdateCommand
from tests.conftest import client  # noqa: F401
from tests.fixtures.auth_fixtures import super_admin_token  # noqa: F401
from tests.helpers import create_test_org


class UserAPIStateMachine(RuleBasedStateMachine):
    """Stateful property-based tests for User API endpoints.

    This tests that API operations maintain consistent state:
    - Created users return 201 and can be retrieved with 200
    - Deleted users return 404 on GET
    - Updated users persist changes correctly
    - List endpoint count matches created - deleted users
    - Email uniqueness is enforced
    - HTTP responses are consistent with state
    """

    users = Bundle("users")

    # Define immutable fields once for reuse across all checks
    IMMUTABLE_FIELDS = ["username", "organization_id"]

    def __init__(self, client: TestClient, super_admin_token: str) -> None:
        import uuid

        super().__init__()
        self.client = client
        self.super_admin_token = super_admin_token
        # Create organization for all users with unique name
        org_name = f"Test Org {uuid.uuid4().hex[:8]}"
        org_id = create_test_org(client, super_admin_token, name=org_name)
        self.organization_id = org_id

        # Track user IDs
        self.created_user_ids: set[str] = set()
        self.deleted_user_ids: set[str] = set()

        # Shadow state for user data
        self.user_data: dict[str, dict[str, str | bool]] = {}  # user_id -> {email, full_name, role, is_active}

        # Track immutable fields (username, organization_id) for invariant checking
        self.immutable_fields: dict[str, dict[str, str]] = {}  # user_id -> {username, organization_id}

        # Track emails in use (for uniqueness testing)
        self.emails_in_use: set[str] = set()

    def _verify_immutable_fields(self, user_id: str, user_obj: dict) -> None:
        """Helper to verify immutable fields haven't changed.

        Args:
            user_id: ID of the user to check
            user_obj: User object from API response
        """
        if user_id in self.immutable_fields:
            for field in self.IMMUTABLE_FIELDS:
                expected = self.immutable_fields[user_id][field]
                actual = user_obj[field]
                assert actual == expected, f"{field} changed for user {user_id}: expected {expected}, got {actual}"

    @rule(target=users)
    def create_user_via_api(self) -> str:
        """Create a new user via API and add to bundle."""
        import uuid

        # Generate unique username and email using UUID to avoid collisions
        username = f"apiuser{uuid.uuid4().hex[:10]}"
        email = f"{username}@example.com"
        full_name = f"API User {username}"

        # Create Pydantic model for request
        user_data = UserData(username=username, email=email, full_name=full_name)

        # Create user via API (serialize Pydantic model to JSON)
        response = self.client.post(
            f"/api/users?organization_id={self.organization_id}&role=read_access",
            json=user_data.model_dump(mode="json"),
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Create should return 201
        assert response.status_code == 201, f"Create should return 201, got {response.status_code}"

        # Deserialize response to Pydantic model (validates structure)
        create_response = UserCreateResponse.model_validate(response.json())
        user_id = create_response.user.id
        user_obj = create_response.user

        # Track in shadow state
        self.created_user_ids.add(user_id)
        self.user_data[user_id] = {
            "email": email,
            "full_name": full_name,
            "role": "read_access",
            "is_active": True,
        }
        # Track immutable fields
        self.immutable_fields[user_id] = {
            "username": username,
            "organization_id": self.organization_id,
        }
        self.emails_in_use.add(email)

        # Invariant: Response has correct structure (validated by Pydantic automatically)
        assert create_response.generated_password is not None, "Create response should have generated_password"
        assert len(create_response.generated_password) > 0, "Generated password should not be empty"

        # Invariant: User data matches what we sent
        assert user_obj.email == email
        assert user_obj.full_name == full_name
        assert user_obj.role == "read_access"

        # Invariant: Just-created user should be retrievable
        get_response = self.client.get(
            f"/api/users/{user_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )
        assert get_response.status_code == 200, "Just-created user should return 200 on GET"
        retrieved_user = User.model_validate(get_response.json())
        assert retrieved_user.id == user_id

        return user_id

    @rule(user_id=users)
    def get_user_via_api(self, user_id: str) -> None:
        """Retrieve a user by ID via API."""
        response = self.client.get(
            f"/api/users/{user_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Status code matches deletion state
        if user_id not in self.deleted_user_ids:
            assert response.status_code == 200, f"Non-deleted user should return 200, got {response.status_code}"

            # Deserialize to Pydantic model (validates structure)
            user_obj = User.model_validate(response.json())
            assert user_obj.id == user_id

            # Invariant: Retrieved data matches shadow state
            if user_id in self.user_data:
                shadow = self.user_data[user_id]
                assert user_obj.email == shadow["email"], f"Email mismatch for user {user_id}"
                assert user_obj.full_name == shadow["full_name"], f"Full name mismatch for user {user_id}"
                assert user_obj.role == shadow["role"], f"Role mismatch for user {user_id}"
                assert user_obj.is_active == shadow["is_active"], f"is_active mismatch for user {user_id}"

            # Invariant: Immutable fields never change
            # Convert Pydantic model to dict for the helper
            self._verify_immutable_fields(user_id, user_obj.model_dump())
        else:
            assert response.status_code == 404, f"Deleted user should return 404, got {response.status_code}"

    @rule(user_id=users)
    def delete_user_via_api(self, user_id: str) -> None:
        """Delete a user via API."""
        # Skip if already deleted
        if user_id in self.deleted_user_ids:
            return

        # Get user data before deletion for cleanup
        user_email = self.user_data.get(user_id, {}).get("email")

        # Delete user
        response = self.client.delete(
            f"/api/users/{user_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Delete should return 204
        assert response.status_code == 204, f"Delete should return 204, got {response.status_code}"

        # Track deletion and clean up shadow state
        self.deleted_user_ids.add(user_id)
        if user_id in self.user_data:
            del self.user_data[user_id]
        if user_email and user_email in self.emails_in_use:
            self.emails_in_use.remove(user_email)

        # Invariant: Deleted user should return 404
        get_response = self.client.get(
            f"/api/users/{user_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )
        assert get_response.status_code == 404, "Deleted user should return 404"

    @rule(user_id=users, new_full_name=st.text(min_size=1, max_size=50))
    def update_user_full_name(self, user_id: str, new_full_name: str) -> None:
        """Update a user's full name via API."""
        # Skip if deleted
        if user_id in self.deleted_user_ids:
            return

        # Create Pydantic update command
        update_cmd = UserUpdateCommand(full_name=new_full_name)

        # Update user (serialize to JSON)
        response = self.client.put(
            f"/api/users/{user_id}",
            json=update_cmd.model_dump(mode="json", exclude_unset=True),
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Update should return 200
        assert response.status_code == 200, f"Update should return 200, got {response.status_code}"

        # Deserialize response
        user_obj = User.model_validate(response.json())

        # Invariant: Updated field changed
        assert user_obj.full_name == new_full_name, "Full name should be updated"

        # Invariant: Other fields unchanged
        if user_id in self.user_data:
            shadow = self.user_data[user_id]
            assert user_obj.email == shadow["email"], "Email should not change"
            assert user_obj.role == shadow["role"], "Role should not change"
            assert user_obj.is_active == shadow["is_active"], "is_active should not change"

        # Invariant: Immutable fields never change
        self._verify_immutable_fields(user_id, user_obj.model_dump())

        # Update shadow state
        if user_id in self.user_data:
            self.user_data[user_id]["full_name"] = new_full_name

        # Invariant: GET reflects the update
        get_response = self.client.get(
            f"/api/users/{user_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )
        assert get_response.status_code == 200
        updated_user = User.model_validate(get_response.json())
        assert updated_user.full_name == new_full_name

    @rule(
        user_id=users,
        new_role=st.sampled_from(["read_access", "write_access", "project_manager", "admin"]),
    )
    def update_user_role(self, user_id: str, new_role: str) -> None:
        """Update a user's role via API."""
        # Skip if deleted
        if user_id in self.deleted_user_ids:
            return

        # Update user
        response = self.client.put(
            f"/api/users/{user_id}",
            json={"role": new_role},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Update should return 200
        assert response.status_code == 200, f"Update should return 200, got {response.status_code}"

        user_obj = User.model_validate(response.json())

        # Invariant: Updated field changed
        assert user_obj.role == new_role, f"Role should be updated to {new_role}"

        # Invariant: Immutable fields never change
        self._verify_immutable_fields(user_id, user_obj.model_dump())

        # Update shadow state
        if user_id in self.user_data:
            self.user_data[user_id]["role"] = new_role

    @rule(
        user_id=users,
        new_full_name=st.text(min_size=1, max_size=50),
        new_role=st.sampled_from(["read_access", "write_access", "project_manager", "admin"]),
    )
    def update_multiple_fields(self, user_id: str, new_full_name: str, new_role: str) -> None:
        """Update multiple user fields simultaneously via API."""
        import uuid

        # Skip if deleted
        if user_id in self.deleted_user_ids:
            return

        # Generate unique email for multi-field update
        new_email = f"multi{uuid.uuid4().hex[:10]}@example.com"

        # Get old email for cleanup
        old_email = self.user_data.get(user_id, {}).get("email")

        # Update multiple fields
        response = self.client.put(
            f"/api/users/{user_id}",
            json={"email": new_email, "full_name": new_full_name, "role": new_role},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Update should return 200
        assert response.status_code == 200, f"Multi-field update should return 200, got {response.status_code}"

        user_obj = User.model_validate(response.json())

        # Invariant: All updated fields changed
        assert user_obj.email == new_email, "Email should be updated"
        assert user_obj.full_name == new_full_name, "Full name should be updated"
        assert user_obj.role == new_role, "Role should be updated"

        # Invariant: Unchanged fields remain unchanged
        if user_id in self.user_data:
            shadow = self.user_data[user_id]
            assert user_obj.is_active == shadow["is_active"], "is_active should not change"

        # Invariant: Immutable fields never change
        self._verify_immutable_fields(user_id, user_obj.model_dump())

        # Update shadow state
        if user_id in self.user_data:
            self.user_data[user_id]["email"] = new_email
            self.user_data[user_id]["full_name"] = new_full_name
            self.user_data[user_id]["role"] = new_role

        # Update email tracking
        if old_email and old_email in self.emails_in_use:
            self.emails_in_use.remove(old_email)
        self.emails_in_use.add(new_email)

    @rule(user_id=users)
    def deactivate_user(self, user_id: str) -> None:
        """Deactivate a user via API."""
        # Skip if deleted or already inactive
        if user_id in self.deleted_user_ids:
            return
        if user_id in self.user_data and not self.user_data[user_id]["is_active"]:
            return

        # Deactivate user
        response = self.client.put(
            f"/api/users/{user_id}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Update should return 200
        assert response.status_code == 200, f"Deactivate should return 200, got {response.status_code}"

        user_obj = User.model_validate(response.json())

        # Invariant: User is now inactive
        assert user_obj.is_active is False, "User should be inactive"

        # Update shadow state
        if user_id in self.user_data:
            self.user_data[user_id]["is_active"] = False

        # Invariant: Inactive user still exists (not deleted)
        get_response = self.client.get(
            f"/api/users/{user_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )
        assert get_response.status_code == 200, "Inactive user should still return 200"

    @rule(user_id=users)
    def reactivate_user(self, user_id: str) -> None:
        """Reactivate an inactive user via API."""
        # Skip if deleted or already active
        if user_id in self.deleted_user_ids:
            return
        if user_id in self.user_data and self.user_data[user_id]["is_active"]:
            return

        # Reactivate user
        response = self.client.put(
            f"/api/users/{user_id}",
            json={"is_active": True},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Update should return 200
        assert response.status_code == 200, f"Reactivate should return 200, got {response.status_code}"

        user_obj = User.model_validate(response.json())

        # Invariant: User is now active
        assert user_obj.is_active is True, "User should be active"

        # Update shadow state
        if user_id in self.user_data:
            self.user_data[user_id]["is_active"] = True

        # Invariant: Reactivated user is retrievable
        get_response = self.client.get(
            f"/api/users/{user_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )
        assert get_response.status_code == 200, "Reactivated user should return 200"
        reactivated_user = User.model_validate(get_response.json())
        assert reactivated_user.is_active is True, "GET should show user as active"

    @rule()
    def list_users_verify_count(self) -> None:
        """List all users in our organization and verify count matches shadow state."""
        # Filter by our organization since super admin sees all users
        response = self.client.get(
            f"/api/users?organization_id={self.organization_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: List should return 200
        assert response.status_code == 200, f"List should return 200, got {response.status_code}"

        # Deserialize to list of User models (validates structure for each user)
        users_list = [User.model_validate(u) for u in response.json()]

        # Invariant: Should return a list (validated by Pydantic)
        assert isinstance(users_list, list), "List endpoint should return a list"

        # Invariant: Count matches (created - deleted)
        expected_count = len(self.created_user_ids - self.deleted_user_ids)
        actual_count = len(users_list)
        assert actual_count == expected_count, f"User count mismatch: expected {expected_count}, got {actual_count}"

        # Invariant: All non-deleted users appear in list
        returned_user_ids = {user.id for user in users_list}
        active_user_ids = self.created_user_ids - self.deleted_user_ids
        assert returned_user_ids == active_user_ids, (
            f"User IDs mismatch. Expected: {active_user_ids}, got: {returned_user_ids}"
        )

        # Invariant: No deleted users appear in list
        for user in users_list:
            assert user.id not in self.deleted_user_ids, f"Deleted user {user.id} should not appear in list"

        # Invariant: Each user's data matches shadow state
        for user in users_list:
            user_id = user.id
            if user_id in self.user_data:
                shadow = self.user_data[user_id]
                assert user.email == shadow["email"], f"Email mismatch in list for user {user_id}"
                assert user.full_name == shadow["full_name"], f"Full name mismatch in list for user {user_id}"
                assert user.role == shadow["role"], f"Role mismatch in list for user {user_id}"
                assert user.is_active == shadow["is_active"], f"is_active mismatch in list for user {user_id}"

    @rule(filter_role=st.sampled_from(["read_access", "write_access", "project_manager", "admin"]))
    def list_with_role_filter(self, filter_role: str) -> None:
        """List users filtered by role and verify only matching users are returned."""
        response = self.client.get(
            f"/api/users?organization_id={self.organization_id}&role={filter_role}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: List should return 200
        assert response.status_code == 200, f"List with role filter should return 200, got {response.status_code}"

        # Deserialize to List[User]
        users_list = [User.model_validate(u) for u in response.json()]
        assert isinstance(users_list, list), "List endpoint should return a list"

        # Invariant: All returned users have the filtered role
        for user in users_list:
            assert user.role == filter_role, f"User {user.id} has role {user.role}, expected {filter_role}"

        # Invariant: Count matches expected users with this role
        expected_user_ids = {
            user_id
            for user_id in self.user_data
            if user_id not in self.deleted_user_ids and self.user_data[user_id].get("role") == filter_role
        }
        returned_user_ids = {user.id for user in users_list}
        assert returned_user_ids == expected_user_ids, (
            f"Role filter mismatch. Expected {len(expected_user_ids)} users with role {filter_role}, "
            f"got {len(returned_user_ids)}"
        )

    @rule(filter_is_active=st.booleans())
    def list_with_is_active_filter(self, filter_is_active: bool) -> None:
        """List users filtered by is_active status and verify only matching users are returned."""
        response = self.client.get(
            f"/api/users?organization_id={self.organization_id}&is_active={str(filter_is_active).lower()}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: List should return 200
        assert response.status_code == 200, f"List with is_active filter should return 200, got {response.status_code}"

        # Deserialize to List[User]
        users_list = [User.model_validate(u) for u in response.json()]
        assert isinstance(users_list, list), "List endpoint should return a list"

        # Invariant: All returned users have the filtered is_active status
        for user in users_list:
            assert user.is_active == filter_is_active, (
                f"User {user.id} has is_active={user.is_active}, expected {filter_is_active}"
            )

        # Invariant: Count matches expected users with this is_active status
        expected_user_ids = {
            user_id
            for user_id in self.user_data
            if user_id not in self.deleted_user_ids and self.user_data[user_id].get("is_active") == filter_is_active
        }
        returned_user_ids = {user.id for user in users_list}
        assert returned_user_ids == expected_user_ids, (
            f"is_active filter mismatch. Expected {len(expected_user_ids)} users with is_active={filter_is_active}, "
            f"got {len(returned_user_ids)}"
        )

    @rule(user_id=users)
    def update_email_to_unique(self, user_id: str) -> None:
        """Update a user's email to a unique value."""
        import uuid

        # Skip if deleted
        if user_id in self.deleted_user_ids:
            return

        # Generate new unique email
        new_email = f"unique{uuid.uuid4().hex[:10]}@example.com"

        # Get old email for cleanup
        old_email = self.user_data.get(user_id, {}).get("email")

        # Update email
        response = self.client.put(
            f"/api/users/{user_id}",
            json={"email": new_email},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Update should succeed with unique email
        assert response.status_code == 200, f"Update with unique email should return 200, got {response.status_code}"

        user_obj = User.model_validate(response.json())
        assert user_obj.email == new_email, "Email should be updated"

        # Update shadow state and email tracking
        if user_id in self.user_data:
            self.user_data[user_id]["email"] = new_email
        if old_email and old_email in self.emails_in_use:
            self.emails_in_use.remove(old_email)
        self.emails_in_use.add(new_email)

    @rule(user_id=users)
    def attempt_duplicate_email_update(self, user_id: str) -> None:
        """Attempt to update a user's email to a duplicate value (should fail)."""
        # Skip if deleted
        if user_id in self.deleted_user_ids:
            return

        # Find another non-deleted user with a different email
        duplicate_email = None
        for other_id in self.user_data:
            if other_id != user_id and other_id not in self.deleted_user_ids:
                other_email = self.user_data[other_id].get("email")
                my_email = self.user_data[user_id].get("email")
                if other_email and other_email != my_email:
                    duplicate_email = other_email
                    break

        if not duplicate_email:
            return  # No other user to test with

        # Attempt to update to duplicate email
        response = self.client.put(
            f"/api/users/{user_id}",
            json={"email": duplicate_email},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Update should fail with 400 for duplicate email
        assert response.status_code == 400, f"Duplicate email should return 400, got {response.status_code}"
        assert "email" in response.json()["detail"].lower(), "Error message should mention email"

        # Invariant: User's email should remain unchanged
        get_response = self.client.get(
            f"/api/users/{user_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )
        if get_response.status_code == 200:
            user_obj = User.model_validate(get_response.json())
            original_email = self.user_data.get(user_id, {}).get("email")
            assert user_obj.email == original_email, "Email should not change after failed update"

    @rule(user_id=users)
    def verify_timestamp_ordering(self, user_id: str) -> None:
        """Verify that timestamps follow correct ordering (updated_at >= created_at)."""
        # Skip if deleted
        if user_id in self.deleted_user_ids:
            return

        response = self.client.get(
            f"/api/users/{user_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        if response.status_code == 200:
            user_obj = User.model_validate(response.json())

            # Invariant: Timestamps exist and are valid ISO format (Pydantic validates this)
            assert user_obj.created_at is not None, "User should have created_at timestamp"
            assert user_obj.updated_at is not None, "User should have updated_at timestamp"

            created_at = user_obj.created_at.isoformat()
            updated_at = user_obj.updated_at.isoformat()

            # Invariant: updated_at >= created_at (updated_at should never be before created_at)
            # Comparing ISO 8601 strings works lexicographically
            assert updated_at >= created_at, (
                f"updated_at ({updated_at}) should be >= created_at ({created_at}) for user {user_id}"
            )


# Test function that pytest will discover
def test_user_api_state_machine(client: TestClient, super_admin_token: str) -> None:
    """Run the User API state machine test."""
    # Run state machine with test client and auth token
    run_state_machine_as_test(lambda: UserAPIStateMachine(client, super_admin_token))
