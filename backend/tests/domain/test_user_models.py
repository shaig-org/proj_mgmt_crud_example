"""Tests for user domain models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from project_management_crud_example.domain_models import User, UserCreateCommand, UserData, UserRole


class TestUserData:
    """Tests for UserData model validation."""

    def test_user_data_with_valid_fields_validates(self) -> None:
        """Test that UserData accepts valid username, email, and full_name."""
        user_data = UserData(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
        )

        assert user_data.username == "testuser"
        assert user_data.email == "test@example.com"
        assert user_data.full_name == "Test User"

    def test_user_data_with_invalid_username_too_short_fails(self) -> None:
        """Test that username must be at least 3 characters."""
        with pytest.raises(ValidationError) as exc_info:
            UserData(
                username="ab",
                email="test@example.com",
                full_name="Test User",
            )

        assert isinstance(exc_info.value, ValidationError)
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("username",) for error in errors)

    def test_user_data_with_invalid_username_too_long_fails(self) -> None:
        """Test that username cannot exceed 50 characters."""
        with pytest.raises(ValidationError):
            UserData(
                username="a" * 51,
                email="test@example.com",
                full_name="Test User",
            )

    def test_user_data_with_invalid_username_special_chars_fails(self) -> None:
        """Test that username only allows alphanumeric, underscore, dash."""
        with pytest.raises(ValidationError):
            UserData(
                username="test@user",
                email="test@example.com",
                full_name="Test User",
            )

    def test_user_data_with_invalid_email_fails(self) -> None:
        """Test that email validation rejects malformed emails."""
        with pytest.raises(ValidationError) as exc_info:
            UserData(
                username="testuser",
                email="not-an-email",
                full_name="Test User",
            )

        assert isinstance(exc_info.value, ValidationError)
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("email",) for error in errors)


class TestUser:
    """Tests for User model."""

    def test_user_model_includes_all_fields(self) -> None:
        """Test that User model has all required fields."""
        now = datetime.now(timezone.utc)
        user = User(
            id="123e4567-e89b-12d3-a456-426614174000",
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            organization_id="org-123",
            role=UserRole.ADMIN,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        assert user.id == "123e4567-e89b-12d3-a456-426614174000"
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.organization_id == "org-123"
        assert user.role == UserRole.ADMIN
        assert user.is_active is True
        assert user.created_at == now
        assert user.updated_at == now

    def test_user_organization_id_can_be_none(self) -> None:
        """Test that organization_id can be None for Super Admin."""
        now = datetime.now(timezone.utc)
        user = User(
            id="123e4567-e89b-12d3-a456-426614174000",
            username="superadmin",
            email="admin@example.com",
            full_name="Super Admin",
            organization_id=None,
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        assert user.organization_id is None
        assert user.role == UserRole.SUPER_ADMIN


class TestUserRole:
    """Tests for UserRole enum."""

    def test_user_role_enum_has_all_roles(self) -> None:
        """Test that UserRole enum has all 5 roles."""
        assert UserRole.SUPER_ADMIN == "super_admin"
        assert UserRole.ADMIN == "admin"
        assert UserRole.PROJECT_MANAGER == "project_manager"
        assert UserRole.WRITE_ACCESS == "write_access"
        assert UserRole.READ_ACCESS == "read_access"

        # Verify all roles are present
        all_roles = [role.value for role in UserRole]
        assert len(all_roles) == 5
        assert "super_admin" in all_roles
        assert "admin" in all_roles
        assert "project_manager" in all_roles
        assert "write_access" in all_roles
        assert "read_access" in all_roles


class TestUserCreateCommand:
    """Tests for UserCreateCommand model."""

    def test_user_create_command_with_organization(self) -> None:
        """Test creating UserCreateCommand with organization."""
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

        assert command.user_data == user_data
        assert command.organization_id == "org-123"
        assert command.role == UserRole.ADMIN

    def test_user_create_command_without_organization(self) -> None:
        """Test creating UserCreateCommand without organization for Super Admin."""
        user_data = UserData(
            username="superadmin",
            email="admin@example.com",
            full_name="Super Admin",
        )
        command = UserCreateCommand(
            user_data=user_data,
            password="TestPassword123",
            organization_id=None,
            role=UserRole.SUPER_ADMIN,
        )

        assert command.user_data == user_data
        assert command.organization_id is None
        assert command.role == UserRole.SUPER_ADMIN
