"""User repository operation rules for DAL state machine.

This mixin provides all property-based test rules for user repository operations.
Each rule tests a specific repository method and verifies invariants are maintained.
"""

from hypothesis import strategies as st
from hypothesis.stateful import rule

from project_management_crud_example.domain_models import UserCreateCommand, UserData, UserRole

from .bundles import Bundles


class UserRulesMixin:
    """Mixin providing user repository rules.

    This mixin expects the parent class to have:
    - self.state: StateTracker instance for shadow state
    - self.repo: Repository instance

    Bundle references use Bundles.users from bundles.py.
    """

    @rule(target=Bundles.users)
    def create_user(self) -> str:
        """Create a new user via repository and add to bundle."""
        import uuid

        # Generate unique username using UUID to avoid collisions
        username = f"user{uuid.uuid4().hex[:12]}"
        email = f"{username}@example.com"
        full_name = f"User {username}"

        # Create user using domain command
        user_data = UserData(
            username=username,
            email=email,
            full_name=full_name,
        )
        command = UserCreateCommand(
            user_data=user_data,
            password="test_password",
            organization_id=self.state.organization_id,
            role=UserRole.READ_ACCESS,
        )
        user = self.repo.users.create(command)

        # Track in shadow state
        self.state.track_user(user.id, user.model_dump())

        # Invariant: Created user should be retrievable
        retrieved = self.repo.users.get_by_id(user.id)
        assert retrieved is not None, f"Just-created user {user.id} should be retrievable"
        assert retrieved.username == username
        assert retrieved.email == email

        return user.id

    @rule(user_id=Bundles.users)
    def get_user_by_id(self, user_id: str) -> None:
        """Retrieve a user by ID via repository."""
        user = self.repo.users.get_by_id(user_id)

        # Invariant: If not deleted, user should exist
        if user_id not in self.state.deleted_user_ids:
            assert user is not None, f"User {user_id} should exist (not deleted)"
            assert user.id == user_id

            # Invariant: Retrieved data matches shadow state
            if user_id in self.state.user_data:
                shadow = self.state.user_data[user_id]
                assert user.username == shadow["username"], f"Username mismatch for user {user_id}"
                assert user.email == shadow["email"], f"Email mismatch for user {user_id}"
                assert user.full_name == shadow["full_name"], f"Full name mismatch for user {user_id}"
                assert user.role.value == shadow["role"], f"Role mismatch for user {user_id}"
                assert user.is_active == shadow["is_active"], f"is_active mismatch for user {user_id}"

            # Invariant: Immutable fields never change
            self.state.verify_immutable_fields(user_id, user.model_dump())
        else:
            # If deleted, get should return None
            assert user is None, f"Deleted user {user_id} should not be retrievable"

    @rule(user_id=Bundles.users)
    def delete_user(self, user_id: str) -> None:
        """Delete a user via repository."""
        # Skip if already deleted
        if user_id in self.state.deleted_user_ids:
            return

        # Delete user
        success = self.repo.users.delete(user_id)
        assert success is True, f"Delete should succeed for existing user {user_id}"

        # Track deletion in shadow state
        self.state.delete_user(user_id)

        # Invariant: Deleted user should not be retrievable
        retrieved = self.repo.users.get_by_id(user_id)
        assert retrieved is None, f"Deleted user {user_id} should not be retrievable"

    @rule(user_id=Bundles.users, new_full_name=st.text(min_size=1, max_size=50))
    def update_user_full_name(self, user_id: str, new_full_name: str) -> None:
        """Update a user's full name via repository."""
        # Skip if deleted
        if user_id in self.state.deleted_user_ids:
            return

        # Get current user to verify it exists
        user = self.repo.users.get_by_id(user_id)
        if user is None:
            return

        # Update user via repository using UserUpdateCommand
        from project_management_crud_example.domain_models import UserUpdateCommand

        update_command = UserUpdateCommand(full_name=new_full_name)
        updated_user = self.repo.users.update(user_id, update_command)

        # Invariant: Updated field changed
        assert updated_user.full_name == new_full_name, "Full name should be updated"

        # Invariant: Other fields unchanged
        if user_id in self.state.user_data:
            shadow = self.state.user_data[user_id]
            assert updated_user.username == shadow["username"], "Username should not change"
            assert updated_user.email == shadow["email"], "Email should not change"
            assert updated_user.role.value == shadow["role"], "Role should not change"
            assert updated_user.is_active == shadow["is_active"], "is_active should not change"

        # Invariant: Immutable fields never change
        self.state.verify_immutable_fields(user_id, updated_user.model_dump())

        # Update shadow state
        self.state.update_user_field(user_id, "full_name", new_full_name)

        # Invariant: GET reflects the update
        retrieved = self.repo.users.get_by_id(user_id)
        assert retrieved is not None
        assert retrieved.full_name == new_full_name

    @rule(user_id=Bundles.users)
    def deactivate_user(self, user_id: str) -> None:
        """Deactivate a user via repository update."""
        # Skip if deleted or already inactive
        if user_id in self.state.deleted_user_ids:
            return
        if user_id in self.state.user_data and not self.state.user_data[user_id]["is_active"]:
            return

        # Get current user
        user = self.repo.users.get_by_id(user_id)
        if user is None:
            return

        # Deactivate user via update with is_active=False
        from project_management_crud_example.domain_models import UserUpdateCommand

        update_command = UserUpdateCommand(is_active=False)
        updated_user = self.repo.users.update(user_id, update_command)

        # Invariant: Update succeeded
        assert updated_user is not None, "Update should succeed"

        # Invariant: User is now inactive
        assert updated_user.is_active is False, "User should be inactive"

        # Update shadow state
        self.state.update_user_field(user_id, "is_active", False)

        # Invariant: Inactive user still exists (not deleted)
        retrieved = self.repo.users.get_by_id(user_id)
        assert retrieved is not None, "Inactive user should still be retrievable"
        assert retrieved.is_active is False

    @rule(user_id=Bundles.users)
    def get_user_by_username(self, user_id: str) -> None:
        """Retrieve a user by username via repository."""
        # Skip if deleted
        if user_id in self.state.deleted_user_ids:
            return

        # Get username from shadow state
        if user_id not in self.state.user_data:
            return

        username = self.state.user_data[user_id]["username"]

        # Retrieve by username
        user = self.repo.users.get_by_username(username)

        # Invariant: User should be found
        assert user is not None, f"User with username {username} should be found"
        assert user.id == user_id, "Retrieved user should have correct ID"
        assert user.username == username, "Username should match"
