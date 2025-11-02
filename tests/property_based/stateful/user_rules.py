"""User operation rules for the system API state machine.

This mixin provides all property-based test rules for user-related API operations.
Each rule tests a specific API operation and verifies invariants are maintained.
"""

from hypothesis import strategies as st
from hypothesis.stateful import rule

from .bundles import Bundles


class UserRulesMixin:
    """Mixin providing user-related PBT rules.

    This mixin expects the parent class to have:
    - self.state: StateTracker instance for shadow state
    - self.sdk: APITestSDK instance with super admin auth
    - self.organization_id: Primary organization ID for test

    All rules use Bundles.users for explicit, type-safe bundle references.
    """

    @rule(target=Bundles.users)
    def create_user_via_api(self) -> str:
        """Create a new user via API and add to bundle."""
        import uuid

        # Generate unique username and email using UUID to avoid collisions
        username = f"apiuser{uuid.uuid4().hex[:10]}"
        email = f"{username}@example.com"
        full_name = f"API User {username}"

        # Create user via SDK
        # Invariant: Create should succeed
        create_response = self.sdk.users.create(
            self.state.organization_id, username, email, full_name, role="read_access"
        ).assert_ok()

        user_id = create_response.user.id
        user_obj = create_response.user

        # Track in shadow state
        self.state.track_user(user_id, user_obj.model_dump())
        self.state.track_user_email(self.state.organization_id, email)

        # Invariant: Response has correct structure (validated by Pydantic automatically)
        assert create_response.generated_password is not None, "Create response should have generated_password"
        assert len(create_response.generated_password) > 0, "Generated password should not be empty"

        # Invariant: User data matches what we sent
        assert user_obj.email == email
        assert user_obj.full_name == full_name
        assert user_obj.role == "read_access"

        # Invariant: Just-created user should be retrievable
        retrieved_user = self.sdk.users.get(user_id).assert_ok()
        assert retrieved_user.id == user_id

        return user_id

    @rule(user_id=Bundles.users)
    def get_user_via_api(self, user_id: str) -> None:
        """Retrieve a user by ID via API."""
        result = self.sdk.users.get(user_id)

        # Invariant: Status code matches deletion state
        if user_id not in self.state.deleted_user_ids:
            # Invariant: Should succeed
            assert result.ok, f"Non-deleted user should return 200, got {result.status_code}"
            user_obj = result.data
            assert user_obj.id == user_id

            # Invariant: Retrieved data matches shadow state
            if user_id in self.state.user_data:
                shadow = self.state.user_data[user_id]
                assert user_obj.email == shadow["email"], f"Email mismatch for user {user_id}"
                assert user_obj.full_name == shadow["full_name"], f"Full name mismatch for user {user_id}"
                assert user_obj.role == shadow["role"], f"Role mismatch for user {user_id}"
                assert user_obj.is_active == shadow["is_active"], f"is_active mismatch for user {user_id}"

            # Invariant: Immutable fields never change
            self.state.verify_immutable_fields(user_id, user_obj.model_dump())
        else:
            # Invariant: Deleted user returns 404
            assert result.status_code == 404, f"Deleted user should return 404, got {result.status_code}"

    @rule(user_id=Bundles.users)
    def delete_user_via_api(self, user_id: str) -> None:
        """Delete a user via API."""
        # Skip if already deleted
        if user_id in self.state.deleted_user_ids:
            return

        # Get user data before deletion for cleanup
        user_data = self.state.user_data.get(user_id, {})
        user_email = user_data.get("email")
        user_org_id = str(user_data.get("organization_id", ""))

        # Delete user via SDK
        # Invariant: Delete should succeed
        self.sdk.users.delete(user_id).assert_ok()

        # Track deletion and clean up shadow state
        self.state.delete_user(user_id)

        # Remove email from organization's email set
        if user_email and user_org_id:
            self.state.untrack_user_email(user_org_id, user_email)

        # Invariant: Deleted user should return 404
        get_result = self.sdk.users.get(user_id)
        assert get_result.status_code == 404, "Deleted user should return 404"

    @rule(user_id=Bundles.users, new_full_name=st.text(min_size=1, max_size=50))
    def update_user_full_name(self, user_id: str, new_full_name: str) -> None:
        """Update a user's full name via API."""
        # Skip if deleted
        if user_id in self.state.deleted_user_ids:
            return

        # Update user via SDK
        # Invariant: Update should succeed
        user_obj = self.sdk.users.update(user_id, full_name=new_full_name).assert_ok()

        # Invariant: Updated field changed
        assert user_obj.full_name == new_full_name, "Full name should be updated"

        # Invariant: Other fields unchanged
        if user_id in self.state.user_data:
            shadow = self.state.user_data[user_id]
            assert user_obj.email == shadow["email"], "Email should not change"
            assert user_obj.role == shadow["role"], "Role should not change"
            assert user_obj.is_active == shadow["is_active"], "is_active should not change"

        # Invariant: Immutable fields never change
        self.state.verify_immutable_fields(user_id, user_obj.model_dump())

        # Update shadow state
        self.state.update_user_field(user_id, "full_name", new_full_name)

        # Invariant: GET reflects the update
        updated_user = self.sdk.users.get(user_id).assert_ok()
        assert updated_user.full_name == new_full_name

    @rule(
        user_id=Bundles.users,
        new_role=st.sampled_from(["read_access", "write_access", "project_manager", "admin"]),
    )
    def update_user_role(self, user_id: str, new_role: str) -> None:
        """Update a user's role via API."""
        # Skip if deleted
        if user_id in self.state.deleted_user_ids:
            return

        # Update user via SDK
        # Invariant: Update should succeed
        user_obj = self.sdk.users.update(user_id, role=new_role).assert_ok()

        # Invariant: Updated field changed
        assert user_obj.role == new_role, f"Role should be updated to {new_role}"

        # Invariant: Immutable fields never change
        self.state.verify_immutable_fields(user_id, user_obj.model_dump())

        # Update shadow state
        self.state.update_user_field(user_id, "role", new_role)

    @rule(user_id=Bundles.users)
    def deactivate_user(self, user_id: str) -> None:
        """Deactivate a user via API."""
        # Skip if deleted or already inactive
        if user_id in self.state.deleted_user_ids:
            return
        if user_id in self.state.user_data and not self.state.user_data[user_id]["is_active"]:
            return

        # Deactivate user using SDK
        # Invariant: Update should succeed
        user = self.sdk.users.deactivate(user_id).assert_ok()

        # Invariant: User is now inactive
        assert user.is_active is False, "User should be inactive"

        # Update shadow state
        self.state.update_user_field(user_id, "is_active", False)

        # Invariant: Inactive user still exists (not deleted)
        get_result = self.sdk.users.get(user_id)
        assert get_result.ok, "Inactive user should still be retrievable"

    @rule()
    def list_users_verify_count(self) -> None:
        """List all users in our organization and verify count matches shadow state."""
        # List users via SDK, filtering by organization
        users_list = self.sdk.users.list(organization_id=self.state.organization_id).assert_ok()

        # Invariant: Should return a list (validated by Pydantic)
        assert isinstance(users_list, list), "List endpoint should return a list"

        # Invariant: Count matches users in this organization (created - deleted)
        # Note: For users in user_data, check organization matches. For users NOT in user_data
        # (like the initial admin user), they're assumed to be in self.state.organization_id
        expected_user_ids = {
            user_id
            for user_id in self.state.created_user_ids
            if user_id not in self.state.deleted_user_ids
            and (
                user_id not in self.state.user_data  # Initial admin user (not tracked in user_data)
                or str(self.state.user_data[user_id].get("organization_id", "")) == self.state.organization_id
            )
        }
        expected_count = len(expected_user_ids)
        actual_count = len(users_list)
        assert actual_count == expected_count, f"User count mismatch: expected {expected_count}, got {actual_count}"

        # Invariant: All non-deleted users from this org appear in list
        returned_user_ids = {user.id for user in users_list}
        assert returned_user_ids == expected_user_ids, (
            f"User IDs mismatch. Expected: {expected_user_ids}, got: {returned_user_ids}"
        )

        # Invariant: No deleted users appear in list
        for user in users_list:
            assert user.id not in self.state.deleted_user_ids, f"Deleted user {user.id} should not appear in list"

        # Invariant: Each user's data matches shadow state
        for user in users_list:
            user_id = user.id
            if user_id in self.state.user_data:
                shadow = self.state.user_data[user_id]
                assert user.email == shadow["email"], f"Email mismatch in list for user {user_id}"
                assert user.full_name == shadow["full_name"], f"Full name mismatch in list for user {user_id}"
                assert user.role == shadow["role"], f"Role mismatch in list for user {user_id}"
                assert user.is_active == shadow["is_active"], f"is_active mismatch in list for user {user_id}"
