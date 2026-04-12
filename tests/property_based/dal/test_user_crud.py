"""Stateful property-based tests for User repository CRUD operations.

Location: tests/property_based/dal/ - DAL-level (repository) tests
Counterpart: tests/property_based/api/ - API-level (system) tests

This tests the User repository layer directly, without HTTP/API overhead.
"""

from hypothesis.stateful import Bundle, RuleBasedStateMachine, rule, run_state_machine_as_test

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import UserCreateCommand, UserData, UserRole
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import create_test_org_via_repo


class UserCRUDStateMachine(RuleBasedStateMachine):
    """Minimal state machine testing User CRUD operations.

    This tests that basic CRUD operations maintain consistent state:
    - Created users can be retrieved
    - Deleted users cannot be retrieved
    - Shadow state matches repository state
    """

    users = Bundle("users")

    def __init__(self, repo: Repository) -> None:
        import uuid

        super().__init__()
        self.repo = repo
        self.created_user_ids: set[str] = set()
        self.deleted_user_ids: set[str] = set()
        # Create organization once for all users with unique name
        org_name = f"Test Org {uuid.uuid4().hex[:8]}"
        org = create_test_org_via_repo(repo, name=org_name)
        self.organization_id = org.id

    @rule(target=users)
    def create_user(self) -> str:
        """Create a new user and add to bundle."""
        import uuid

        # Generate unique username using UUID to avoid collisions
        username = f"user{uuid.uuid4().hex[:12]}"

        # Create user using domain command
        user_data = UserData(
            username=username,
            email=f"{username}@example.com",
            full_name=f"User {username}",
        )
        command = UserCreateCommand(
            user_data=user_data,
            password="test_password",
            organization_id=self.organization_id,
            role=UserRole.READ_ACCESS,
        )
        user = self.repo.users.create(command)

        # Track in shadow state
        self.created_user_ids.add(user.id)

        # Invariant: Created user should be retrievable
        retrieved = self.repo.users.get_by_id(user.id)
        assert retrieved is not None, f"Just-created user {user.id} should be retrievable"
        assert retrieved.username == username

        return user.id

    @rule(user_id=users)
    def get_user(self, user_id: str) -> None:
        """Retrieve a user by ID."""
        user = self.repo.users.get_by_id(user_id)

        # Invariant: If not deleted, user should exist
        if user_id not in self.deleted_user_ids:
            assert user is not None, f"User {user_id} should exist (not deleted)"
            assert user.id == user_id
        else:
            # If deleted, get should return None
            assert user is None, f"Deleted user {user_id} should not be retrievable"

    @rule(user_id=users)
    def delete_user(self, user_id: str) -> None:
        """Delete a user."""
        # Skip if already deleted
        if user_id in self.deleted_user_ids:
            return

        # Delete user
        success = self.repo.users.delete(user_id)
        assert success is True, f"Delete should succeed for existing user {user_id}"

        # Track deletion
        self.deleted_user_ids.add(user_id)

        # Invariant: Deleted user should not be retrievable
        retrieved = self.repo.users.get_by_id(user_id)
        assert retrieved is None, f"Deleted user {user_id} should not be retrievable"


# Test function that pytest will discover
def test_user_crud_state_machine(test_repo: Repository) -> None:
    """Run the User CRUD state machine test."""
    # Run state machine with the test repository
    run_state_machine_as_test(lambda: UserCRUDStateMachine(test_repo))
