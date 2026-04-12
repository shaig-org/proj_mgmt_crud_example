"""Tests for Workflow repository operations.

Tests verify complete CRUD functionality for workflows through the Repository interface,
including organization scoping, default workflow handling, and edge cases.
"""

from datetime import datetime

import pytest

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    WorkflowCreateCommand,
    WorkflowData,
    WorkflowUpdateCommand,
)
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import create_test_org_via_repo


class TestWorkflowRepositoryCreate:
    """Test workflow creation through repository."""

    def test_create_workflow_with_all_fields(self, test_repo: Repository) -> None:
        """Test creating a workflow with all fields through repository."""
        # Create organization first
        org = create_test_org_via_repo(test_repo)

        # Create workflow
        workflow_data = WorkflowData(
            name="Kanban Workflow",
            description="Standard Kanban workflow",
            statuses=["BACKLOG", "TODO", "IN_PROGRESS", "REVIEW", "DONE"],
        )
        command = WorkflowCreateCommand(workflow_data=workflow_data, organization_id=org.id)

        workflow = test_repo.workflows.create(command)

        assert workflow.id is not None
        assert workflow.name == "Kanban Workflow"
        assert workflow.description == "Standard Kanban workflow"
        assert workflow.statuses == ["BACKLOG", "TODO", "IN_PROGRESS", "REVIEW", "DONE"]
        assert workflow.organization_id == org.id
        assert workflow.is_default is False
        assert isinstance(workflow.created_at, datetime)
        assert isinstance(workflow.updated_at, datetime)

    def test_create_workflow_without_description(self, test_repo: Repository) -> None:
        """Test creating a workflow without optional description."""
        org = create_test_org_via_repo(test_repo)

        workflow_data = WorkflowData(name="Simple Workflow", statuses=["TODO", "DONE"])
        command = WorkflowCreateCommand(workflow_data=workflow_data, organization_id=org.id)

        workflow = test_repo.workflows.create(command)

        assert workflow.name == "Simple Workflow"
        assert workflow.description is None
        assert workflow.statuses == ["TODO", "DONE"]
        assert workflow.organization_id == org.id
        assert workflow.is_default is False

    def test_create_workflow_with_single_status(self, test_repo: Repository) -> None:
        """Test creating a workflow with minimum number of statuses (1)."""
        org = create_test_org_via_repo(test_repo)

        workflow_data = WorkflowData(name="Minimal Workflow", statuses=["ACTIVE"])
        command = WorkflowCreateCommand(workflow_data=workflow_data, organization_id=org.id)

        workflow = test_repo.workflows.create(command)

        assert workflow.statuses == ["ACTIVE"]
        assert len(workflow.statuses) == 1

    def test_create_workflow_with_many_statuses(self, test_repo: Repository) -> None:
        """Test creating a workflow with many statuses."""
        org = create_test_org_via_repo(test_repo)

        statuses = [
            "NEW",
            "TRIAGED",
            "ASSIGNED",
            "IN_PROGRESS",
            "CODE_REVIEW",
            "QA",
            "STAGING",
            "PRODUCTION",
            "RESOLVED",
            "CLOSED",
        ]
        workflow_data = WorkflowData(name="Complex Workflow", statuses=statuses)
        command = WorkflowCreateCommand(workflow_data=workflow_data, organization_id=org.id)

        workflow = test_repo.workflows.create(command)

        assert workflow.statuses == statuses
        assert len(workflow.statuses) == 10

    def test_create_workflow_persists_to_database(self, test_repo: Repository) -> None:
        """Test that created workflow can be retrieved from database."""
        org = create_test_org_via_repo(test_repo)

        workflow_data = WorkflowData(name="Test Workflow", statuses=["TODO", "IN_PROGRESS", "DONE"])
        command = WorkflowCreateCommand(workflow_data=workflow_data, organization_id=org.id)
        created_workflow = test_repo.workflows.create(command)

        # Retrieve workflow
        retrieved_workflow = test_repo.workflows.get_by_id(created_workflow.id)

        assert retrieved_workflow is not None
        assert retrieved_workflow.id == created_workflow.id
        assert retrieved_workflow.name == created_workflow.name
        assert retrieved_workflow.statuses == created_workflow.statuses
        assert retrieved_workflow.organization_id == org.id


class TestWorkflowRepositoryGet:
    """Test workflow retrieval operations."""

    def test_get_workflow_by_id_found(self, test_repo: Repository) -> None:
        """Test retrieving an existing workflow by ID."""
        org = create_test_org_via_repo(test_repo)
        workflow_data = WorkflowData(name="Test Workflow", statuses=["TODO", "DONE"])
        command = WorkflowCreateCommand(workflow_data=workflow_data, organization_id=org.id)
        workflow = test_repo.workflows.create(command)

        # Retrieve workflow
        retrieved = test_repo.workflows.get_by_id(workflow.id)

        assert retrieved is not None
        assert retrieved.id == workflow.id
        assert retrieved.name == "Test Workflow"
        assert retrieved.statuses == ["TODO", "DONE"]

    def test_get_workflow_by_id_not_found(self, test_repo: Repository) -> None:
        """Test retrieving a non-existent workflow returns None."""
        result = test_repo.workflows.get_by_id("non-existent-id")
        assert result is None

    def test_get_by_organization_id_returns_all_workflows(self, test_repo: Repository) -> None:
        """Test retrieving all workflows for an organization."""
        org = create_test_org_via_repo(test_repo)

        # Create multiple workflows
        workflow1_data = WorkflowData(name="Workflow 1", statuses=["TODO", "DONE"])
        command1 = WorkflowCreateCommand(workflow_data=workflow1_data, organization_id=org.id)
        test_repo.workflows.create(command1)

        workflow2_data = WorkflowData(name="Workflow 2", statuses=["NEW", "ACTIVE", "CLOSED"])
        command2 = WorkflowCreateCommand(workflow_data=workflow2_data, organization_id=org.id)
        test_repo.workflows.create(command2)

        # Retrieve all workflows for organization
        workflows = test_repo.workflows.get_by_organization_id(org.id)

        assert len(workflows) == 2
        workflow_names = {w.name for w in workflows}
        assert "Workflow 1" in workflow_names
        assert "Workflow 2" in workflow_names

    def test_get_by_organization_id_empty_for_org_without_workflows(self, test_repo: Repository) -> None:
        """Test retrieving workflows for organization with no custom workflows."""
        org = create_test_org_via_repo(test_repo)

        workflows = test_repo.workflows.get_by_organization_id(org.id)

        assert len(workflows) == 0

    def test_get_by_organization_id_filters_by_organization(self, test_repo: Repository) -> None:
        """Test that get_by_organization_id only returns workflows for that organization."""
        org1 = create_test_org_via_repo(test_repo, name="Org 1")
        org2 = create_test_org_via_repo(test_repo, name="Org 2")

        # Create workflows in different organizations
        workflow1_data = WorkflowData(name="Org 1 Workflow", statuses=["TODO", "DONE"])
        command1 = WorkflowCreateCommand(workflow_data=workflow1_data, organization_id=org1.id)
        test_repo.workflows.create(command1)

        workflow2_data = WorkflowData(name="Org 2 Workflow", statuses=["NEW", "CLOSED"])
        command2 = WorkflowCreateCommand(workflow_data=workflow2_data, organization_id=org2.id)
        test_repo.workflows.create(command2)

        # Retrieve workflows for org1
        org1_workflows = test_repo.workflows.get_by_organization_id(org1.id)
        assert len(org1_workflows) == 1
        assert org1_workflows[0].name == "Org 1 Workflow"

        # Retrieve workflows for org2
        org2_workflows = test_repo.workflows.get_by_organization_id(org2.id)
        assert len(org2_workflows) == 1
        assert org2_workflows[0].name == "Org 2 Workflow"

    def test_get_all_returns_workflows_from_all_organizations(self, test_repo: Repository) -> None:
        """Test that get_all returns workflows across all organizations."""
        org1 = create_test_org_via_repo(test_repo, name="Org 1")
        org2 = create_test_org_via_repo(test_repo, name="Org 2")

        # Create workflows in different organizations
        workflow1_data = WorkflowData(name="Org 1 Workflow", statuses=["TODO", "DONE"])
        command1 = WorkflowCreateCommand(workflow_data=workflow1_data, organization_id=org1.id)
        test_repo.workflows.create(command1)

        workflow2_data = WorkflowData(name="Org 2 Workflow", statuses=["NEW", "CLOSED"])
        command2 = WorkflowCreateCommand(workflow_data=workflow2_data, organization_id=org2.id)
        test_repo.workflows.create(command2)

        # Get all workflows
        all_workflows = test_repo.workflows.get_all()

        assert len(all_workflows) >= 2  # At least the two we created
        workflow_names = {w.name for w in all_workflows}
        assert "Org 1 Workflow" in workflow_names
        assert "Org 2 Workflow" in workflow_names


class TestWorkflowRepositoryDefaultWorkflow:
    """Test default workflow operations."""

    def test_create_default_workflow(self, test_repo: Repository) -> None:
        """Test creating default workflow for an organization."""
        org = create_test_org_via_repo(test_repo)

        workflow = test_repo.workflows.create_default_workflow(org.id)

        assert workflow.id is not None
        assert workflow.name == "Default Workflow"
        assert workflow.description == "Standard workflow with TODO, IN_PROGRESS, and DONE statuses"
        assert workflow.statuses == ["TODO", "IN_PROGRESS", "DONE"]
        assert workflow.organization_id == org.id
        assert workflow.is_default is True

    def test_get_default_workflow(self, test_repo: Repository) -> None:
        """Test retrieving default workflow for an organization."""
        org = create_test_org_via_repo(test_repo)

        # Create default workflow
        created_workflow = test_repo.workflows.create_default_workflow(org.id)

        # Retrieve default workflow
        default_workflow = test_repo.workflows.get_default_workflow(org.id)

        assert default_workflow is not None
        assert default_workflow.id == created_workflow.id
        assert default_workflow.is_default is True
        assert default_workflow.statuses == ["TODO", "IN_PROGRESS", "DONE"]

    def test_get_default_workflow_when_none_exists(self, test_repo: Repository) -> None:
        """Test get_default_workflow returns None when no default exists."""
        org = create_test_org_via_repo(test_repo)

        default_workflow = test_repo.workflows.get_default_workflow(org.id)

        assert default_workflow is None

    def test_create_default_workflow_fails_if_already_exists(self, test_repo: Repository) -> None:
        """Test that creating a second default workflow for same org fails."""
        org = create_test_org_via_repo(test_repo)

        # Create first default workflow
        test_repo.workflows.create_default_workflow(org.id)

        # Attempt to create second default workflow should fail
        with pytest.raises(ValueError, match="Default workflow already exists"):
            test_repo.workflows.create_default_workflow(org.id)

    def test_get_by_organization_id_includes_default_workflow(self, test_repo: Repository) -> None:
        """Test that get_by_organization_id includes default workflow."""
        org = create_test_org_via_repo(test_repo)

        # Create default workflow
        default_workflow = test_repo.workflows.create_default_workflow(org.id)

        # Create custom workflow
        workflow_data = WorkflowData(name="Custom Workflow", statuses=["TODO", "DONE"])
        command = WorkflowCreateCommand(workflow_data=workflow_data, organization_id=org.id)
        custom_workflow = test_repo.workflows.create(command)

        # Get all workflows for organization
        workflows = test_repo.workflows.get_by_organization_id(org.id)

        assert len(workflows) == 2
        workflow_ids = {w.id for w in workflows}
        assert default_workflow.id in workflow_ids
        assert custom_workflow.id in workflow_ids

        # Verify which one is default
        default_workflows = [w for w in workflows if w.is_default]
        assert len(default_workflows) == 1
        assert default_workflows[0].id == default_workflow.id


class TestWorkflowRepositoryUpdate:
    """Test workflow update operations."""

    def test_update_workflow_name(self, test_repo: Repository) -> None:
        """Test updating workflow name."""
        org = create_test_org_via_repo(test_repo)
        workflow_data = WorkflowData(name="Original Name", statuses=["TODO", "DONE"])
        command = WorkflowCreateCommand(workflow_data=workflow_data, organization_id=org.id)
        workflow = test_repo.workflows.create(command)

        # Update name
        update_command = WorkflowUpdateCommand(name="Updated Name")
        updated_workflow = test_repo.workflows.update(workflow.id, update_command)

        assert updated_workflow is not None
        assert updated_workflow.name == "Updated Name"
        assert updated_workflow.description == workflow.description
        assert updated_workflow.statuses == workflow.statuses

    def test_update_workflow_description(self, test_repo: Repository) -> None:
        """Test updating workflow description."""
        org = create_test_org_via_repo(test_repo)
        workflow_data = WorkflowData(
            name="Test Workflow", description="Original description", statuses=["TODO", "DONE"]
        )
        command = WorkflowCreateCommand(workflow_data=workflow_data, organization_id=org.id)
        workflow = test_repo.workflows.create(command)

        # Update description
        update_command = WorkflowUpdateCommand(description="Updated description")
        updated_workflow = test_repo.workflows.update(workflow.id, update_command)

        assert updated_workflow is not None
        assert updated_workflow.description == "Updated description"
        assert updated_workflow.name == workflow.name

    def test_update_workflow_statuses(self, test_repo: Repository) -> None:
        """Test updating workflow statuses."""
        org = create_test_org_via_repo(test_repo)
        workflow_data = WorkflowData(name="Test Workflow", statuses=["TODO", "DONE"])
        command = WorkflowCreateCommand(workflow_data=workflow_data, organization_id=org.id)
        workflow = test_repo.workflows.create(command)

        # Update statuses
        new_statuses = ["BACKLOG", "TODO", "IN_PROGRESS", "DONE"]
        update_command = WorkflowUpdateCommand(statuses=new_statuses)
        updated_workflow = test_repo.workflows.update(workflow.id, update_command)

        assert updated_workflow is not None
        assert updated_workflow.statuses == new_statuses
        assert updated_workflow.name == workflow.name

    def test_update_workflow_multiple_fields(self, test_repo: Repository) -> None:
        """Test updating multiple workflow fields simultaneously."""
        org = create_test_org_via_repo(test_repo)
        workflow_data = WorkflowData(name="Original", description="Old desc", statuses=["TODO", "DONE"])
        command = WorkflowCreateCommand(workflow_data=workflow_data, organization_id=org.id)
        workflow = test_repo.workflows.create(command)

        # Update multiple fields
        update_command = WorkflowUpdateCommand(
            name="Updated",
            description="New desc",
            statuses=["NEW", "ACTIVE", "CLOSED"],
        )
        updated_workflow = test_repo.workflows.update(workflow.id, update_command)

        assert updated_workflow is not None
        assert updated_workflow.name == "Updated"
        assert updated_workflow.description == "New desc"
        assert updated_workflow.statuses == ["NEW", "ACTIVE", "CLOSED"]

    def test_update_workflow_not_found(self, test_repo: Repository) -> None:
        """Test updating a non-existent workflow returns None."""
        update_command = WorkflowUpdateCommand(name="New Name")
        result = test_repo.workflows.update("non-existent-id", update_command)

        assert result is None

    def test_update_workflow_persists_to_database(self, test_repo: Repository) -> None:
        """Test that workflow updates persist to database."""
        org = create_test_org_via_repo(test_repo)
        workflow_data = WorkflowData(name="Original", statuses=["TODO", "DONE"])
        command = WorkflowCreateCommand(workflow_data=workflow_data, organization_id=org.id)
        workflow = test_repo.workflows.create(command)

        # Update workflow
        update_command = WorkflowUpdateCommand(name="Updated")
        test_repo.workflows.update(workflow.id, update_command)

        # Retrieve and verify update persisted
        retrieved = test_repo.workflows.get_by_id(workflow.id)
        assert retrieved is not None
        assert retrieved.name == "Updated"


class TestWorkflowRepositoryDelete:
    """Test workflow deletion operations."""

    def test_delete_workflow(self, test_repo: Repository) -> None:
        """Test deleting a workflow."""
        org = create_test_org_via_repo(test_repo)
        workflow_data = WorkflowData(name="To Delete", statuses=["TODO", "DONE"])
        command = WorkflowCreateCommand(workflow_data=workflow_data, organization_id=org.id)
        workflow = test_repo.workflows.create(command)

        # Delete workflow
        success = test_repo.workflows.delete(workflow.id)

        assert success is True

        # Verify workflow is deleted
        retrieved = test_repo.workflows.get_by_id(workflow.id)
        assert retrieved is None

    def test_delete_workflow_not_found(self, test_repo: Repository) -> None:
        """Test deleting a non-existent workflow returns False."""
        success = test_repo.workflows.delete("non-existent-id")

        assert success is False

    def test_delete_workflow_removes_from_organization_list(self, test_repo: Repository) -> None:
        """Test that deleted workflow doesn't appear in organization's workflow list."""
        org = create_test_org_via_repo(test_repo)

        # Create two workflows
        workflow1_data = WorkflowData(name="Workflow 1", statuses=["TODO", "DONE"])
        command1 = WorkflowCreateCommand(workflow_data=workflow1_data, organization_id=org.id)
        workflow1 = test_repo.workflows.create(command1)

        workflow2_data = WorkflowData(name="Workflow 2", statuses=["NEW", "CLOSED"])
        command2 = WorkflowCreateCommand(workflow_data=workflow2_data, organization_id=org.id)
        workflow2 = test_repo.workflows.create(command2)

        # Delete first workflow
        test_repo.workflows.delete(workflow1.id)

        # Verify only second workflow remains in list
        workflows = test_repo.workflows.get_by_organization_id(org.id)
        assert len(workflows) == 1
        assert workflows[0].id == workflow2.id
        assert workflows[0].name == "Workflow 2"
