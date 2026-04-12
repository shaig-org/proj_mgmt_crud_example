"""Tests for user operations through Repository interface."""

from sqlalchemy.exc import IntegrityError

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    TicketCreateCommand,
    TicketData,
    TicketPriority,
    UserCreateCommand,
    UserData,
    UserRole,
    UserUpdateCommand,
)
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import (
    create_test_org_with_workflow_via_repo,
    create_test_project_via_repo,
)


class TestUserOperations:
    """Test user operations through Repository interface."""

    def test_create_user(self, test_repo: Repository) -> None:
        """Test creating a user through repository."""
        user_data = UserData(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
        )
        command = UserCreateCommand(
            user_data=user_data,
            password="TestPassword123",
            organization_id="org-123",
            role=UserRole.ADMIN,
        )

        user = test_repo.users.create(command)

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.organization_id == "org-123"
        assert user.role == UserRole.ADMIN
        assert user.is_active is True
        assert user.id is not None
        assert user.created_at is not None
        assert user.updated_at is not None
        # Verify password_hash is NOT exposed in domain model
        assert not hasattr(user, "password_hash")

    def test_create_super_admin_without_organization(self, test_repo: Repository) -> None:
        """Test creating Super Admin user without organization."""
        user_data = UserData(
            username="superadmin",
            email="admin@example.com",
            full_name="Super Administrator",
        )
        command = UserCreateCommand(
            user_data=user_data,
            password="TestPassword123",
            organization_id=None,
            role=UserRole.SUPER_ADMIN,
        )

        user = test_repo.users.create(command)

        assert user.username == "superadmin"
        assert user.organization_id is None
        assert user.role == UserRole.SUPER_ADMIN
        assert user.id is not None

    def test_get_user_by_id(self, test_repo: Repository) -> None:
        """Test retrieving user by ID through repository."""
        # Create user
        user_data = UserData(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
        )
        command = UserCreateCommand(
            user_data=user_data,
            password="TestPassword123",
            organization_id="org-123",
            role=UserRole.ADMIN,
        )
        created_user = test_repo.users.create(command)

        # Retrieve user
        retrieved_user = test_repo.users.get_by_id(created_user.id)

        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.username == "testuser"
        assert retrieved_user.email == "test@example.com"

    def test_get_user_by_id_not_found(self, test_repo: Repository) -> None:
        """Test retrieving non-existent user returns None."""
        retrieved_user = test_repo.users.get_by_id("non-existent-id")

        assert retrieved_user is None

    def test_get_user_by_username(self, test_repo: Repository) -> None:
        """Test retrieving user by username through repository."""
        # Create user
        user_data = UserData(
            username="findme",
            email="findme@example.com",
            full_name="Find Me",
        )
        command = UserCreateCommand(
            user_data=user_data,
            password="TestPassword123",
            organization_id="org-123",
            role=UserRole.WRITE_ACCESS,
        )
        created_user = test_repo.users.create(command)

        # Retrieve by username
        retrieved_user = test_repo.users.get_by_username("findme")

        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.username == "findme"

    def test_get_user_by_username_not_found(self, test_repo: Repository) -> None:
        """Test retrieving user by non-existent username returns None."""
        retrieved_user = test_repo.users.get_by_username("nonexistent")

        assert retrieved_user is None

    def test_get_all_users(self, test_repo: Repository) -> None:
        """Test retrieving all users through repository."""
        # Create multiple users
        user1_data = UserData(username="user1", email="user1@example.com", full_name="User 1")
        user2_data = UserData(username="user2", email="user2@example.com", full_name="User 2")

        test_repo.users.create(
            UserCreateCommand(
                user_data=user1_data, password="TestPassword123", organization_id="org-123", role=UserRole.ADMIN
            )
        )
        test_repo.users.create(
            UserCreateCommand(
                user_data=user2_data, password="TestPassword123", organization_id="org-456", role=UserRole.READ_ACCESS
            )
        )

        # Get all users
        all_users = test_repo.users.get_all()

        assert len(all_users) == 2
        usernames = {user.username for user in all_users}
        assert usernames == {"user1", "user2"}

    def test_get_all_users_empty(self, test_repo: Repository) -> None:
        """Test retrieving all users when database is empty."""
        all_users = test_repo.users.get_all()

        assert all_users == []

    def test_delete_user(self, test_repo: Repository) -> None:
        """Test deleting a user through repository."""
        # Create user
        user_data = UserData(
            username="deleteme",
            email="deleteme@example.com",
            full_name="Delete Me",
        )
        command = UserCreateCommand(
            user_data=user_data,
            password="TestPassword123",
            organization_id="org-123",
            role=UserRole.WRITE_ACCESS,
        )
        created_user = test_repo.users.create(command)

        # Delete user
        success = test_repo.users.delete(created_user.id)

        assert success is True

        # Verify user is gone
        retrieved_user = test_repo.users.get_by_id(created_user.id)
        assert retrieved_user is None

    def test_delete_user_not_found(self, test_repo: Repository) -> None:
        """Test deleting non-existent user returns False."""
        success = test_repo.users.delete("non-existent-id")

        assert success is False

    def test_update_user(self, test_repo: Repository) -> None:
        """Test updating user fields through repository."""
        # Create user
        user_data = UserData(username="updateme", email="old@example.com", full_name="Old Name")
        command = UserCreateCommand(
            user_data=user_data, password="TestPassword123", organization_id="org-123", role=UserRole.WRITE_ACCESS
        )
        created_user = test_repo.users.create(command)

        # Update user
        update_command = UserUpdateCommand(
            email="new@example.com", full_name="New Name", role=UserRole.PROJECT_MANAGER, is_active=False
        )
        updated_user = test_repo.users.update(created_user.id, update_command)

        assert updated_user is not None
        assert updated_user.id == created_user.id
        assert updated_user.email == "new@example.com"
        assert updated_user.full_name == "New Name"
        assert updated_user.role == UserRole.PROJECT_MANAGER
        assert updated_user.is_active is False
        # Verify unchanged fields
        assert updated_user.username == "updateme"
        assert updated_user.organization_id == "org-123"

    def test_update_user_partial_fields(self, test_repo: Repository) -> None:
        """Test updating only some user fields."""
        # Create user
        user_data = UserData(username="partial", email="partial@example.com", full_name="Partial User")
        command = UserCreateCommand(
            user_data=user_data, password="TestPassword123", organization_id="org-123", role=UserRole.ADMIN
        )
        created_user = test_repo.users.create(command)

        # Update only email
        update_command = UserUpdateCommand(email="updated@example.com")
        updated_user = test_repo.users.update(created_user.id, update_command)

        assert updated_user is not None
        assert updated_user.email == "updated@example.com"
        # Verify other fields unchanged
        assert updated_user.full_name == "Partial User"
        assert updated_user.role == UserRole.ADMIN
        assert updated_user.is_active is True

    def test_update_user_not_found(self, test_repo: Repository) -> None:
        """Test updating non-existent user returns None."""
        update_command = UserUpdateCommand(email="new@example.com")
        updated_user = test_repo.users.update("non-existent-id", update_command)

        assert updated_user is None

    def test_get_by_filters_organization_id(self, test_repo: Repository) -> None:
        """Test filtering users by organization ID."""
        # Create users in different organizations
        user1_data = UserData(username="user1", email="user1@example.com", full_name="User 1")
        user2_data = UserData(username="user2", email="user2@example.com", full_name="User 2")
        user3_data = UserData(username="user3", email="user3@example.com", full_name="User 3")

        test_repo.users.create(
            UserCreateCommand(
                user_data=user1_data, password="TestPassword123", organization_id="org-1", role=UserRole.ADMIN
            )
        )
        test_repo.users.create(
            UserCreateCommand(
                user_data=user2_data, password="TestPassword123", organization_id="org-2", role=UserRole.ADMIN
            )
        )
        test_repo.users.create(
            UserCreateCommand(
                user_data=user3_data, password="TestPassword123", organization_id="org-1", role=UserRole.READ_ACCESS
            )
        )

        # Filter by organization
        org1_users = test_repo.users.get_by_filters(organization_id="org-1")

        assert len(org1_users) == 2
        usernames = {user.username for user in org1_users}
        assert usernames == {"user1", "user3"}

    def test_get_by_filters_role(self, test_repo: Repository) -> None:
        """Test filtering users by role."""
        # Create users with different roles
        user1_data = UserData(username="admin1", email="admin1@example.com", full_name="Admin 1")
        user2_data = UserData(username="reader1", email="reader1@example.com", full_name="Reader 1")
        user3_data = UserData(username="admin2", email="admin2@example.com", full_name="Admin 2")

        test_repo.users.create(
            UserCreateCommand(
                user_data=user1_data, password="TestPassword123", organization_id="org-1", role=UserRole.ADMIN
            )
        )
        test_repo.users.create(
            UserCreateCommand(
                user_data=user2_data, password="TestPassword123", organization_id="org-1", role=UserRole.READ_ACCESS
            )
        )
        test_repo.users.create(
            UserCreateCommand(
                user_data=user3_data, password="TestPassword123", organization_id="org-1", role=UserRole.ADMIN
            )
        )

        # Filter by role
        admin_users = test_repo.users.get_by_filters(role=UserRole.ADMIN)

        assert len(admin_users) == 2
        usernames = {user.username for user in admin_users}
        assert usernames == {"admin1", "admin2"}

    def test_get_by_filters_is_active(self, test_repo: Repository) -> None:
        """Test filtering users by active status."""
        # Create active and inactive users
        user1_data = UserData(username="active", email="active@example.com", full_name="Active User")
        user2_data = UserData(username="inactive", email="inactive@example.com", full_name="Inactive User")

        test_repo.users.create(
            UserCreateCommand(
                user_data=user1_data, password="TestPassword123", organization_id="org-1", role=UserRole.ADMIN
            )
        )
        created_user2 = test_repo.users.create(
            UserCreateCommand(
                user_data=user2_data, password="TestPassword123", organization_id="org-1", role=UserRole.ADMIN
            )
        )

        # Deactivate user2
        test_repo.users.update(created_user2.id, UserUpdateCommand(is_active=False))

        # Filter by active status
        active_users = test_repo.users.get_by_filters(is_active=True)
        inactive_users = test_repo.users.get_by_filters(is_active=False)

        assert len(active_users) == 1
        assert active_users[0].username == "active"
        assert len(inactive_users) == 1
        assert inactive_users[0].username == "inactive"

    def test_get_by_filters_multiple_criteria(self, test_repo: Repository) -> None:
        """Test filtering users by multiple criteria."""
        # Create various users
        user1_data = UserData(username="user1", email="user1@example.com", full_name="User 1")
        user2_data = UserData(username="user2", email="user2@example.com", full_name="User 2")
        user3_data = UserData(username="user3", email="user3@example.com", full_name="User 3")

        test_repo.users.create(
            UserCreateCommand(
                user_data=user1_data, password="TestPassword123", organization_id="org-1", role=UserRole.ADMIN
            )
        )
        test_repo.users.create(
            UserCreateCommand(
                user_data=user2_data, password="TestPassword123", organization_id="org-1", role=UserRole.READ_ACCESS
            )
        )
        test_repo.users.create(
            UserCreateCommand(
                user_data=user3_data, password="TestPassword123", organization_id="org-2", role=UserRole.ADMIN
            )
        )

        # Filter by organization AND role
        filtered_users = test_repo.users.get_by_filters(organization_id="org-1", role=UserRole.ADMIN)

        assert len(filtered_users) == 1
        assert filtered_users[0].username == "user1"

    def test_get_by_filters_no_results(self, test_repo: Repository) -> None:
        """Test filtering with criteria that matches no users."""
        # Create a user
        user_data = UserData(username="user1", email="user1@example.com", full_name="User 1")
        test_repo.users.create(
            UserCreateCommand(
                user_data=user_data, password="TestPassword123", organization_id="org-1", role=UserRole.ADMIN
            )
        )

        # Filter with non-matching criteria
        filtered_users = test_repo.users.get_by_filters(organization_id="non-existent-org")

        assert filtered_users == []

    def test_delete_user_with_created_tickets_fails(self, test_repo: Repository) -> None:
        """Test that deleting user who created tickets raises IntegrityError."""
        # Create organization
        org = create_test_org_with_workflow_via_repo(test_repo)

        # Create user
        user_data = UserData(username="creator", email="creator@example.com", full_name="Creator User")
        user = test_repo.users.create(
            UserCreateCommand(
                user_data=user_data, password="TestPassword123", organization_id=org.id, role=UserRole.ADMIN
            )
        )

        # Create project
        project = create_test_project_via_repo(test_repo, org.id)

        # Create ticket with user as reporter
        ticket_data = TicketData(title="Test Ticket", description="Test", priority=TicketPriority.MEDIUM)
        test_repo.tickets.create(
            TicketCreateCommand(ticket_data=ticket_data, project_id=project.id, assignee_id=None),
            reporter_id=user.id,
        )

        # Attempt to delete user should fail
        try:
            test_repo.users.delete(user.id)
            raise AssertionError("Expected IntegrityError to be raised")
        except IntegrityError as e:
            assert "Cannot delete user" in str(e)
            assert "ticket(s)" in str(e)

    def test_delete_user_without_created_tickets_succeeds(self, test_repo: Repository) -> None:
        """Test that deleting user who has not created tickets succeeds."""
        # Create user
        user_data = UserData(username="nodatuser", email="nodatuser@example.com", full_name="No Data User")
        user = test_repo.users.create(
            UserCreateCommand(
                user_data=user_data, password="TestPassword123", organization_id="org-1", role=UserRole.ADMIN
            )
        )

        # Delete should succeed
        success = test_repo.users.delete(user.id)

        assert success is True
        # Verify user is deleted
        retrieved_user = test_repo.users.get_by_id(user.id)
        assert retrieved_user is None

    def test_get_by_username_with_password(self, test_repo: Repository) -> None:
        """Test retrieving user with password hash for authentication."""
        # Create user
        user_data = UserData(username="authuser", email="authuser@example.com", full_name="Auth User")
        command = UserCreateCommand(
            user_data=user_data, password="SecurePassword123", organization_id="org-123", role=UserRole.ADMIN
        )
        created_user = test_repo.users.create(command)

        # Retrieve user with password for authentication
        auth_data = test_repo.users.get_by_username_with_password("authuser")

        assert auth_data is not None
        assert auth_data.id == created_user.id
        assert auth_data.username == "authuser"
        assert auth_data.role == UserRole.ADMIN
        assert auth_data.organization_id == "org-123"
        assert auth_data.is_active is True
        # Verify password_hash is included in UserAuthData
        assert auth_data.password_hash is not None
        assert len(auth_data.password_hash) > 0
        # Verify it contains a salt (format: salt$hash for test hasher)
        assert "$" in auth_data.password_hash

    def test_get_by_username_with_password_case_insensitive(self, test_repo: Repository) -> None:
        """Test retrieving user with password is case-insensitive."""
        # Create user with lowercase username
        user_data = UserData(username="authuser", email="authuser@example.com", full_name="Auth User")
        command = UserCreateCommand(
            user_data=user_data, password="SecurePassword123", organization_id="org-123", role=UserRole.ADMIN
        )
        test_repo.users.create(command)

        # Retrieve with different case variations
        for username_variant in ["authuser", "AUTHUSER", "AuthUser", "aUtHuSeR"]:
            auth_data = test_repo.users.get_by_username_with_password(username_variant)
            assert auth_data is not None
            assert auth_data.username == "authuser"

    def test_get_by_username_with_password_not_found(self, test_repo: Repository) -> None:
        """Test retrieving non-existent user for authentication returns None."""
        auth_data = test_repo.users.get_by_username_with_password("nonexistent")

        assert auth_data is None

    def test_update_password(self, test_repo: Repository) -> None:
        """Test updating user password."""
        # Create user
        user_data = UserData(username="changepass", email="changepass@example.com", full_name="Change Pass User")
        command = UserCreateCommand(
            user_data=user_data, password="OldPassword123", organization_id="org-123", role=UserRole.ADMIN
        )
        created_user = test_repo.users.create(command)

        # Get original password hash
        original_auth_data = test_repo.users.get_by_username_with_password("changepass")
        assert original_auth_data is not None
        original_hash = original_auth_data.password_hash

        # Update password
        success = test_repo.users.update_password(created_user.id, "NewPassword456")

        assert success is True

        # Verify password hash has changed
        updated_auth_data = test_repo.users.get_by_username_with_password("changepass")
        assert updated_auth_data is not None
        assert updated_auth_data.password_hash != original_hash
        # Verify new hash is still valid (contains salt$hash format)
        assert "$" in updated_auth_data.password_hash

    def test_update_password_user_not_found(self, test_repo: Repository) -> None:
        """Test updating password for non-existent user returns False."""
        success = test_repo.users.update_password("non-existent-id", "NewPassword123")

        assert success is False

    def test_create_super_admin_if_needed_creates_when_none_exists(self, test_repo: Repository) -> None:
        """Test creating Super Admin when none exists."""
        # Verify no Super Admin exists initially
        all_users = test_repo.users.get_all()
        assert len(all_users) == 0

        # Create Super Admin if needed
        created, user = test_repo.users.create_super_admin_if_needed(
            username="superadmin",
            email="admin@example.com",
            full_name="Super Administrator",
            password="SuperSecure123!",
        )

        assert created is True
        assert user is not None
        assert user.username == "superadmin"
        assert user.role == UserRole.SUPER_ADMIN
        assert user.organization_id is None
        assert user.is_active is True

        # Verify user can authenticate
        auth_data = test_repo.users.get_by_username_with_password("superadmin")
        assert auth_data is not None
        assert auth_data.password_hash is not None

    def test_create_super_admin_if_needed_idempotent(self, test_repo: Repository) -> None:
        """Test creating Super Admin is idempotent - doesn't create duplicates."""
        # Create Super Admin first time
        created1, user1 = test_repo.users.create_super_admin_if_needed(
            username="superadmin",
            email="admin@example.com",
            full_name="Super Administrator",
            password="SuperSecure123!",
        )
        assert created1 is True
        assert user1 is not None
        first_user_id = user1.id

        # Try to create again - should return False and None
        created2, user2 = test_repo.users.create_super_admin_if_needed(
            username="superadmin",
            email="admin@example.com",
            full_name="Super Administrator",
            password="SuperSecure123!",
        )
        assert created2 is False
        assert user2 is None

        # Verify only one Super Admin exists
        all_users = test_repo.users.get_all()
        super_admins = [u for u in all_users if u.role == UserRole.SUPER_ADMIN]
        assert len(super_admins) == 1
        assert super_admins[0].id == first_user_id

    def test_create_super_admin_if_needed_does_not_create_when_one_exists(self, test_repo: Repository) -> None:
        """Test that Super Admin is not created if one already exists with different username."""
        # Manually create a Super Admin with custom username
        user_data = UserData(username="customadmin", email="custom@example.com", full_name="Custom Admin")
        test_repo.users.create(
            UserCreateCommand(
                user_data=user_data, password="CustomPassword123", organization_id=None, role=UserRole.SUPER_ADMIN
            )
        )

        # Try to create default Super Admin - should not create
        created, user = test_repo.users.create_super_admin_if_needed(
            username="superadmin",
            email="admin@example.com",
            full_name="Super Administrator",
            password="SuperSecure123!",
        )

        assert created is False
        assert user is None

        # Verify only the custom Super Admin exists (no "superadmin" user)
        all_users = test_repo.users.get_all()
        assert len(all_users) == 1
        assert all_users[0].username == "customadmin"
