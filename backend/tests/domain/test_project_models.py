"""Tests for Project domain models validation.

Tests verify Pydantic validation rules for Project models including field constraints,
required vs optional fields, and edge cases like max lengths and special characters.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from project_management_crud_example.domain_models import (
    Project,
    ProjectCreateCommand,
    ProjectData,
    ProjectUpdateCommand,
)


class TestProjectDataValidation:
    """Test ProjectData validation rules."""

    def test_valid_project_data_with_all_fields(self) -> None:
        """Test creating ProjectData with all valid fields."""
        data = ProjectData(
            name="Backend API",
            description="REST API for the application",
        )

        assert data.name == "Backend API"
        assert data.description == "REST API for the application"

    def test_valid_project_data_without_description(self) -> None:
        """Test creating ProjectData without optional description field."""
        data = ProjectData(name="Frontend")

        assert data.name == "Frontend"
        assert data.description is None

    def test_name_is_required(self) -> None:
        """Test that name field is required."""
        with pytest.raises(ValidationError) as exc_info:
            ProjectData()  # type: ignore

        assert isinstance(exc_info.value, ValidationError)
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)

    def test_empty_name_is_rejected(self) -> None:
        """Test that empty string name is rejected (min_length=1)."""
        with pytest.raises(ValidationError) as exc_info:
            ProjectData(name="")

        assert isinstance(exc_info.value, ValidationError)
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("name",) and "at least 1 character" in str(error["msg"]).lower() for error in errors
        )

    def test_name_max_length_255_is_accepted(self) -> None:
        """Test that name with exactly 255 characters is accepted."""
        long_name = "A" * 255
        data = ProjectData(name=long_name)

        assert data.name == long_name
        assert len(data.name) == 255

    def test_name_exceeding_max_length_is_rejected(self) -> None:
        """Test that name exceeding 255 characters is rejected."""
        too_long_name = "A" * 256

        with pytest.raises(ValidationError) as exc_info:
            ProjectData(name=too_long_name)

        assert isinstance(exc_info.value, ValidationError)
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("name",) and "at most 255 characters" in str(error["msg"]).lower() for error in errors
        )

    def test_description_max_length_1000_is_accepted(self) -> None:
        """Test that description with exactly 1000 characters is accepted."""
        long_description = "B" * 1000
        data = ProjectData(name="Test Project", description=long_description)

        assert data.description == long_description
        assert len(data.description) == 1000

    def test_description_exceeding_max_length_is_rejected(self) -> None:
        """Test that description exceeding 1000 characters is rejected."""
        too_long_description = "B" * 1001

        with pytest.raises(ValidationError) as exc_info:
            ProjectData(name="Test Project", description=too_long_description)

        assert isinstance(exc_info.value, ValidationError)
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("description",) and "at most 1000 characters" in str(error["msg"]).lower()
            for error in errors
        )

    def test_name_with_special_characters(self) -> None:
        """Test that name accepts special characters."""
        data = ProjectData(name="Project-2024 (Q1) #Main")

        assert data.name == "Project-2024 (Q1) #Main"

    def test_name_with_unicode_characters(self) -> None:
        """Test that name accepts unicode characters."""
        data = ProjectData(name="Proyecto Español 日本語 Проект")

        assert data.name == "Proyecto Español 日本語 Проект"

    def test_description_can_be_empty_string(self) -> None:
        """Test that description can be empty string (unlike name)."""
        data = ProjectData(name="Test", description="")

        assert data.description == ""


class TestProjectModel:
    """Test complete Project model with metadata."""

    def test_valid_project_with_all_fields(self) -> None:
        """Test creating a complete Project model."""
        now = datetime.now(timezone.utc)
        project = Project(
            id="proj-123",
            name="Backend",
            description="REST API",
            organization_id="org-456",
            workflow_id="workflow-789",
            created_at=now,
            updated_at=now,
        )

        assert project.id == "proj-123"
        assert project.name == "Backend"
        assert project.description == "REST API"
        assert project.organization_id == "org-456"
        assert project.workflow_id == "workflow-789"
        assert project.created_at == now
        assert project.updated_at == now

    def test_project_without_description(self) -> None:
        """Test creating Project without optional description."""
        now = datetime.now(timezone.utc)
        project = Project(
            id="proj-123",
            name="Backend",
            organization_id="org-456",
            workflow_id="workflow-789",
            created_at=now,
            updated_at=now,
        )

        assert project.description is None
        assert project.workflow_id == "workflow-789"

    def test_project_requires_organization_id(self) -> None:
        """Test that organization_id is required."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValidationError) as exc_info:
            Project(
                id="proj-123",
                name="Backend",
                created_at=now,
                updated_at=now,
            )  # type: ignore

        assert isinstance(exc_info.value, ValidationError)
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("organization_id",) for error in errors)


class TestProjectCreateCommand:
    """Test ProjectCreateCommand model."""

    def test_valid_create_command_with_all_fields(self) -> None:
        """Test creating ProjectCreateCommand with all fields."""
        project_data = ProjectData(name="Backend", description="REST API")
        command = ProjectCreateCommand(
            project_data=project_data,
            organization_id="org-123",
        )

        assert command.project_data.name == "Backend"
        assert command.project_data.description == "REST API"
        assert command.organization_id == "org-123"

    def test_valid_create_command_without_description(self) -> None:
        """Test creating ProjectCreateCommand without description."""
        project_data = ProjectData(name="Frontend")
        command = ProjectCreateCommand(
            project_data=project_data,
            organization_id="org-123",
        )

        assert command.project_data.name == "Frontend"
        assert command.project_data.description is None
        assert command.organization_id == "org-123"

    def test_create_command_requires_organization_id(self) -> None:
        """Test that organization_id is required in create command."""
        project_data = ProjectData(name="Backend")

        with pytest.raises(ValidationError) as exc_info:
            ProjectCreateCommand(project_data=project_data)  # type: ignore

        assert isinstance(exc_info.value, ValidationError)
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("organization_id",) for error in errors)

    def test_create_command_requires_project_data(self) -> None:
        """Test that project_data is required in create command."""
        with pytest.raises(ValidationError) as exc_info:
            ProjectCreateCommand(organization_id="org-123")  # type: ignore

        assert isinstance(exc_info.value, ValidationError)
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("project_data",) for error in errors)


class TestProjectUpdateCommand:
    """Test ProjectUpdateCommand model for partial updates."""

    def test_update_command_with_all_fields(self) -> None:
        """Test creating update command with all fields."""
        command = ProjectUpdateCommand(
            name="Updated Project",
            description="Updated description",
        )

        assert command.name == "Updated Project"
        assert command.description == "Updated description"

    def test_update_command_with_only_name(self) -> None:
        """Test updating only name field."""
        command = ProjectUpdateCommand(name="New Name")

        assert command.name == "New Name"
        assert command.description is None

    def test_update_command_with_only_description(self) -> None:
        """Test updating only description field."""
        command = ProjectUpdateCommand(description="New description")

        assert command.name is None
        assert command.description == "New description"

    def test_update_command_with_no_fields(self) -> None:
        """Test creating update command with no fields (all optional)."""
        command = ProjectUpdateCommand()

        assert command.name is None
        assert command.description is None

    def test_update_command_validates_name_length(self) -> None:
        """Test that update command validates name length."""
        too_long_name = "A" * 256

        with pytest.raises(ValidationError) as exc_info:
            ProjectUpdateCommand(name=too_long_name)

        assert isinstance(exc_info.value, ValidationError)
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("name",) and "at most 255 characters" in str(error["msg"]).lower() for error in errors
        )

    def test_update_command_validates_description_length(self) -> None:
        """Test that update command validates description length."""
        too_long_description = "B" * 1001

        with pytest.raises(ValidationError) as exc_info:
            ProjectUpdateCommand(description=too_long_description)

        assert isinstance(exc_info.value, ValidationError)
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("description",) and "at most 1000 characters" in str(error["msg"]).lower()
            for error in errors
        )

    def test_update_command_rejects_empty_name(self) -> None:
        """Test that update command rejects empty name string (min_length=1)."""
        with pytest.raises(ValidationError) as exc_info:
            ProjectUpdateCommand(name="")

        assert isinstance(exc_info.value, ValidationError)
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("name",) and "at least 1 character" in str(error["msg"]).lower() for error in errors
        )

    def test_update_command_allows_empty_description(self) -> None:
        """Test that update command allows empty description string."""
        command = ProjectUpdateCommand(description="")

        assert command.description == ""
