"""Tests for organization domain models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from project_management_crud_example.domain_models import (
    Organization,
    OrganizationCreateCommand,
    OrganizationData,
    OrganizationUpdateCommand,
)


class TestOrganizationData:
    """Tests for OrganizationData model validation."""

    def test_organization_data_with_valid_fields_validates(self) -> None:
        """Test that OrganizationData accepts valid name and description."""
        org_data = OrganizationData(
            name="Acme Corporation",
            description="A test organization",
        )

        assert org_data.name == "Acme Corporation"
        assert org_data.description == "A test organization"

    def test_organization_data_with_name_only_validates(self) -> None:
        """Test that OrganizationData accepts name without description."""
        org_data = OrganizationData(name="Minimal Org")

        assert org_data.name == "Minimal Org"
        assert org_data.description is None

    def test_organization_data_with_empty_name_fails(self) -> None:
        """Test that name cannot be empty string."""
        with pytest.raises(ValidationError) as exc_info:
            OrganizationData(name="", description="Test")

        assert isinstance(exc_info.value, ValidationError)
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)

    def test_organization_data_with_name_too_long_fails(self) -> None:
        """Test that name cannot exceed 255 characters."""
        with pytest.raises(ValidationError):
            OrganizationData(name="a" * 256, description="Test")

    def test_organization_data_with_max_length_name_validates(self) -> None:
        """Test that name can be exactly 255 characters."""
        max_name = "a" * 255
        org_data = OrganizationData(name=max_name)

        assert org_data.name == max_name
        assert len(org_data.name) == 255

    def test_organization_data_with_special_characters_validates(self) -> None:
        """Test that name accepts special characters."""
        org_data = OrganizationData(name="Acme Corp. & Partners!")

        assert org_data.name == "Acme Corp. & Partners!"

    def test_organization_data_with_unicode_validates(self) -> None:
        """Test that name accepts unicode characters."""
        org_data = OrganizationData(name="日本株式会社")

        assert org_data.name == "日本株式会社"

    def test_organization_data_without_name_fails(self) -> None:
        """Test that name is required."""
        with pytest.raises(ValidationError) as exc_info:
            OrganizationData(description="No name provided")  # type: ignore

        assert isinstance(exc_info.value, ValidationError)
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)

    def test_organization_data_with_description_too_long_fails(self) -> None:
        """Test that description cannot exceed 1000 characters."""
        with pytest.raises(ValidationError):
            OrganizationData(name="Test Org", description="a" * 1001)

    def test_organization_data_with_max_length_description_validates(self) -> None:
        """Test that description can be exactly 1000 characters."""
        max_description = "a" * 1000
        org_data = OrganizationData(name="Test Org", description=max_description)

        assert org_data.description == max_description
        assert len(org_data.description) == 1000


class TestOrganization:
    """Tests for Organization model."""

    def test_organization_model_includes_all_fields(self) -> None:
        """Test that Organization model has all required fields."""
        now = datetime.now(timezone.utc)
        org = Organization(
            id="org-123",
            name="Test Organization",
            description="A test organization",
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        assert org.id == "org-123"
        assert org.name == "Test Organization"
        assert org.description == "A test organization"
        assert org.is_active is True
        assert org.created_at == now
        assert org.updated_at == now

    def test_organization_is_active_defaults_to_true(self) -> None:
        """Test that is_active field defaults to True."""
        now = datetime.now(timezone.utc)
        org = Organization(
            id="org-456",
            name="Default Active Org",
            description="Test",
            created_at=now,
            updated_at=now,
        )

        assert org.is_active is True

    def test_organization_can_be_inactive(self) -> None:
        """Test that organization can be marked as inactive."""
        now = datetime.now(timezone.utc)
        org = Organization(
            id="org-789",
            name="Inactive Org",
            description="Deactivated organization",
            is_active=False,
            created_at=now,
            updated_at=now,
        )

        assert org.is_active is False

    def test_organization_description_can_be_none(self) -> None:
        """Test that description is optional."""
        now = datetime.now(timezone.utc)
        org = Organization(
            id="org-999",
            name="No Description Org",
            description=None,
            created_at=now,
            updated_at=now,
        )

        assert org.description is None


class TestOrganizationCreateCommand:
    """Tests for OrganizationCreateCommand model."""

    def test_organization_create_command_with_all_fields(self) -> None:
        """Test creating OrganizationCreateCommand with complete data."""
        org_data = OrganizationData(
            name="New Organization",
            description="A brand new organization",
        )
        command = OrganizationCreateCommand(organization_data=org_data)

        assert command.organization_data == org_data
        assert command.organization_data.name == "New Organization"
        assert command.organization_data.description == "A brand new organization"

    def test_organization_create_command_with_minimal_data(self) -> None:
        """Test creating OrganizationCreateCommand with only required fields."""
        org_data = OrganizationData(name="Minimal Org")
        command = OrganizationCreateCommand(organization_data=org_data)

        assert command.organization_data.name == "Minimal Org"
        assert command.organization_data.description is None


class TestOrganizationUpdateCommand:
    """Tests for OrganizationUpdateCommand model."""

    def test_organization_update_command_with_all_fields(self) -> None:
        """Test updating all fields of organization."""
        command = OrganizationUpdateCommand(
            name="Updated Name",
            description="Updated description",
            is_active=False,
        )

        assert command.name == "Updated Name"
        assert command.description == "Updated description"
        assert command.is_active is False

    def test_organization_update_command_with_partial_fields(self) -> None:
        """Test updating only some fields."""
        command = OrganizationUpdateCommand(name="New Name Only")

        assert command.name == "New Name Only"
        assert command.description is None
        assert command.is_active is None

    def test_organization_update_command_with_empty_fields(self) -> None:
        """Test that all fields are optional in update command."""
        command = OrganizationUpdateCommand()

        assert command.name is None
        assert command.description is None
        assert command.is_active is None

    def test_organization_update_command_name_validation(self) -> None:
        """Test that update command validates name length."""
        with pytest.raises(ValidationError):
            OrganizationUpdateCommand(name="")  # Empty name should fail

        with pytest.raises(ValidationError):
            OrganizationUpdateCommand(name="a" * 256)  # Too long should fail

    def test_organization_update_command_description_validation(self) -> None:
        """Test that update command validates description length."""
        with pytest.raises(ValidationError):
            OrganizationUpdateCommand(description="a" * 1001)  # Too long should fail

    def test_organization_update_command_activate(self) -> None:
        """Test setting organization to active."""
        command = OrganizationUpdateCommand(is_active=True)

        assert command.is_active is True

    def test_organization_update_command_deactivate(self) -> None:
        """Test setting organization to inactive."""
        command = OrganizationUpdateCommand(is_active=False)

        assert command.is_active is False
