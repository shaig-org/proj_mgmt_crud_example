"""Tests for debug diff utilities.

Tests the pure functions that generate change diffs for debug logging.
"""

from datetime import datetime

from project_management_crud_example.utils.debug_diff_helpers import (
    SENSITIVE_FIELDS,
    generate_changes_dict,
    strip_sensitive_fields,
)


class TestGenerateChangesDict:
    """Test generate_changes_dict function."""

    def test_generate_changes_dict_for_creation(self) -> None:
        """Test diff generation when old_dict is None (creation)."""
        new_dict = {
            "name": "New Project",
            "description": "A new project",
            "is_active": True,
        }

        changes = generate_changes_dict(None, new_dict)

        assert "created" in changes
        assert changes["created"] == new_dict

    def test_generate_changes_dict_for_deletion(self) -> None:
        """Test diff generation when new_dict is None (deletion)."""
        old_dict = {
            "name": "Old Project",
            "description": "A project to delete",
            "is_active": True,
        }

        changes = generate_changes_dict(old_dict, None)

        assert "deleted" in changes
        assert changes["deleted"] == old_dict

    def test_generate_changes_dict_for_simple_field_change(self) -> None:
        """Test diff generation for simple field value changes."""
        old_dict = {"name": "Old Name", "status": "TODO"}
        new_dict = {"name": "New Name", "status": "TODO"}

        changes = generate_changes_dict(old_dict, new_dict)

        assert "name" in changes
        assert changes["name"]["old_value"] == "Old Name"
        assert changes["name"]["new_value"] == "New Name"
        assert "status" not in changes  # Unchanged field should not appear

    def test_generate_changes_dict_for_multiple_field_changes(self) -> None:
        """Test diff generation when multiple fields change."""
        old_dict = {"name": "Old", "description": "Old desc", "priority": "LOW"}
        new_dict = {"name": "New", "description": "New desc", "priority": "HIGH"}

        changes = generate_changes_dict(old_dict, new_dict)

        assert len(changes) == 3
        assert changes["name"]["old_value"] == "Old"
        assert changes["name"]["new_value"] == "New"
        assert changes["description"]["old_value"] == "Old desc"
        assert changes["description"]["new_value"] == "New desc"
        assert changes["priority"]["old_value"] == "LOW"
        assert changes["priority"]["new_value"] == "HIGH"

    def test_generate_changes_dict_for_field_addition(self) -> None:
        """Test diff generation when a field is added."""
        old_dict = {"name": "Project"}
        new_dict = {"name": "Project", "description": "Added description"}

        changes = generate_changes_dict(old_dict, new_dict)

        assert "description" in changes
        assert changes["description"]["old_value"] is None
        assert changes["description"]["new_value"] == "Added description"

    def test_generate_changes_dict_for_field_removal(self) -> None:
        """Test diff generation when a field is removed."""
        old_dict = {"name": "Project", "description": "To be removed"}
        new_dict = {"name": "Project"}

        changes = generate_changes_dict(old_dict, new_dict)

        assert "description" in changes
        assert changes["description"]["old_value"] == "To be removed"
        assert changes["description"]["new_value"] is None

    def test_generate_changes_dict_for_nested_field_changes(self) -> None:
        """Test diff generation for nested dictionary changes."""
        old_dict = {"metadata": {"version": 1, "status": "draft"}}
        new_dict = {"metadata": {"version": 2, "status": "draft"}}

        changes = generate_changes_dict(old_dict, new_dict)

        assert "metadata.version" in changes
        assert changes["metadata.version"]["old_value"] == 1
        assert changes["metadata.version"]["new_value"] == 2

    def test_generate_changes_dict_no_changes(self) -> None:
        """Test diff generation when nothing changed."""
        same_dict = {"name": "Unchanged", "status": "TODO"}

        changes = generate_changes_dict(same_dict, same_dict)

        assert changes == {}

    def test_generate_changes_dict_type_change(self) -> None:
        """Test diff generation when field type changes."""
        old_dict = {"priority": None}
        new_dict = {"priority": "HIGH"}

        changes = generate_changes_dict(old_dict, new_dict)

        assert "priority" in changes
        assert changes["priority"]["old_value"] is None
        assert changes["priority"]["new_value"] == "HIGH"

    def test_generate_changes_dict_both_none_returns_error(self) -> None:
        """Test that passing both None returns error dict."""
        changes = generate_changes_dict(None, None)

        assert "error" in changes


class TestStripSensitiveFields:
    """Test strip_sensitive_fields function."""

    def test_strip_sensitive_fields_removes_password_hash(self) -> None:
        """Test that password_hash is removed from user dicts."""
        from project_management_crud_example.domain_models import User, UserRole

        user = User(
            id="user-123",
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            organization_id="org-123",
            role=UserRole.ADMIN,
            is_active=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Manually add password_hash for testing (normally not in User model)
        user_dict = user.model_dump(mode="json", exclude_none=False)
        user_dict["password_hash"] = "hashed_password_123"

        # Create a mock user model with password_hash
        from pydantic import BaseModel

        class UserWithHash(BaseModel):
            id: str
            username: str
            password_hash: str

        user_with_hash = UserWithHash(id="user-123", username="testuser", password_hash="hashed_password_123")

        # Verify password_hash is in SENSITIVE_FIELDS
        assert "password_hash" in SENSITIVE_FIELDS.get("user", set())

        # Strip sensitive fields
        stripped = strip_sensitive_fields(user_with_hash, "user")

        # Verify password_hash was removed
        assert "password_hash" not in stripped
        assert stripped["id"] == "user-123"
        assert stripped["username"] == "testuser"

    def test_strip_sensitive_fields_preserves_non_sensitive(self) -> None:
        """Test that non-sensitive fields are preserved."""
        from project_management_crud_example.domain_models import Project

        project = Project(
            id="proj-123",
            name="Test Project",
            description="Test description",
            organization_id="org-123",
            workflow_id="workflow-123",
            is_active=True,
            is_archived=False,
            archived_at=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        stripped = strip_sensitive_fields(project, "project")

        # All fields should be preserved for projects (no sensitive fields)
        assert stripped["id"] == "proj-123"
        assert stripped["name"] == "Test Project"
        assert stripped["description"] == "Test description"

    def test_strip_sensitive_fields_handles_none_values(self) -> None:
        """Test that None values are preserved (exclude_none=False)."""
        from project_management_crud_example.domain_models import Project

        project = Project(
            id="proj-123",
            name="Test Project",
            description=None,  # Explicitly None
            organization_id="org-123",
            workflow_id="workflow-123",
            is_active=True,
            is_archived=False,
            archived_at=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        stripped = strip_sensitive_fields(project, "project")

        # None values should be preserved
        assert "description" in stripped
        assert stripped["description"] is None

    def test_strip_sensitive_fields_handles_unknown_entity_type(self) -> None:
        """Test that unknown entity types don't break (no sensitive fields assumed)."""
        from project_management_crud_example.domain_models import Project

        project = Project(
            id="proj-123",
            name="Test Project",
            description="Test description",
            organization_id="org-123",
            workflow_id="workflow-123",
            is_active=True,
            is_archived=False,
            archived_at=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        stripped = strip_sensitive_fields(project, "unknown_entity")

        # Should preserve all fields since no sensitive fields defined for unknown_entity
        assert stripped["id"] == "proj-123"
        assert stripped["name"] == "Test Project"
