"""Tests for Project repository operations.

Tests verify complete CRUD functionality for projects through the Repository interface,
including organization scoping, data persistence, and edge cases.
"""

from datetime import datetime

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    ProjectCreateCommand,
    ProjectData,
    ProjectUpdateCommand,
)
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import create_test_org_with_workflow_via_repo, create_test_project_via_repo


class TestProjectRepositoryCreate:
    """Test project creation through repository."""

    def test_create_project_with_all_fields(self, test_repo: Repository) -> None:
        """Test creating a project with all fields through repository."""
        # Create organization first
        org = create_test_org_with_workflow_via_repo(test_repo)

        # Create project
        project_data = ProjectData(name="Backend API", description="REST API for the application")
        command = ProjectCreateCommand(project_data=project_data, organization_id=org.id)

        project = test_repo.projects.create(command)

        assert project.id is not None
        assert project.name == "Backend API"
        assert project.description == "REST API for the application"
        assert project.organization_id == org.id
        assert isinstance(project.created_at, datetime)
        assert isinstance(project.updated_at, datetime)

    def test_create_project_without_description(self, test_repo: Repository) -> None:
        """Test creating a project without optional description."""
        # Create organization
        org = create_test_org_with_workflow_via_repo(test_repo)

        # Create project without description
        project_data = ProjectData(name="Frontend")
        command = ProjectCreateCommand(project_data=project_data, organization_id=org.id)

        project = test_repo.projects.create(command)

        assert project.name == "Frontend"
        assert project.description is None
        assert project.organization_id == org.id

    def test_create_project_persists_to_database(self, test_repo: Repository) -> None:
        """Test that created project can be retrieved from database."""
        # Create organization
        org = create_test_org_with_workflow_via_repo(test_repo)

        # Create project
        project_data = ProjectData(name="Mobile App")
        command = ProjectCreateCommand(project_data=project_data, organization_id=org.id)
        created_project = test_repo.projects.create(command)

        # Retrieve project
        retrieved_project = test_repo.projects.get_by_id(created_project.id)

        assert retrieved_project is not None
        assert retrieved_project.id == created_project.id
        assert retrieved_project.name == created_project.name
        assert retrieved_project.organization_id == org.id


class TestProjectRepositoryGet:
    """Test project retrieval operations."""

    def test_get_project_by_id_found(self, test_repo: Repository) -> None:
        """Test retrieving an existing project by ID."""
        # Create organization and project
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id)

        # Retrieve project
        retrieved = test_repo.projects.get_by_id(project.id)

        assert retrieved is not None
        assert retrieved.id == project.id
        assert retrieved.name == "Test Project"

    def test_get_project_by_id_not_found(self, test_repo: Repository) -> None:
        """Test retrieving a non-existent project returns None."""
        result = test_repo.projects.get_by_id("non-existent-id")

        assert result is None

    def test_get_projects_by_organization_id(self, test_repo: Repository) -> None:
        """Test retrieving all projects for a specific organization."""
        # Create two organizations
        org1 = create_test_org_with_workflow_via_repo(test_repo, "Org 1")
        org2 = create_test_org_with_workflow_via_repo(test_repo, "Org 2")

        # Create projects for org1
        create_test_project_via_repo(test_repo, org1.id, "Org1 Project 1")
        create_test_project_via_repo(test_repo, org1.id, "Org1 Project 2")

        # Create project for org2
        create_test_project_via_repo(test_repo, org2.id, "Org2 Project 1")

        # Get projects for org1
        org1_projects = test_repo.projects.get_by_organization_id(org1.id)

        assert len(org1_projects) == 2
        assert all(p.organization_id == org1.id for p in org1_projects)
        assert {p.name for p in org1_projects} == {"Org1 Project 1", "Org1 Project 2"}

    def test_get_all_projects(self, test_repo: Repository) -> None:
        """Test retrieving all projects across all organizations."""
        # Create two organizations
        org1 = create_test_org_with_workflow_via_repo(test_repo, "Org 1")
        org2 = create_test_org_with_workflow_via_repo(test_repo, "Org 2")

        # Create projects
        create_test_project_via_repo(test_repo, org1.id, "Project 1")
        create_test_project_via_repo(test_repo, org2.id, "Project 2")

        # Get all projects
        all_projects = test_repo.projects.get_all()

        assert len(all_projects) == 2
        assert {p.name for p in all_projects} == {"Project 1", "Project 2"}


class TestProjectRepositoryUpdate:
    """Test project update operations."""

    def test_update_project_name(self, test_repo: Repository) -> None:
        """Test updating project name."""
        # Create organization and project
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Old Name")

        # Update name
        update_command = ProjectUpdateCommand(name="New Name")
        updated_project = test_repo.projects.update(project.id, update_command)

        assert updated_project is not None
        assert updated_project.name == "New Name"
        assert updated_project.description == project.description  # Unchanged

    def test_update_project_description(self, test_repo: Repository) -> None:
        """Test updating project description."""
        # Create organization and project
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Project", "Old description")

        # Update description
        update_command = ProjectUpdateCommand(description="New description")
        updated_project = test_repo.projects.update(project.id, update_command)

        assert updated_project is not None
        assert updated_project.description == "New description"
        assert updated_project.name == project.name  # Unchanged

    def test_update_project_is_active(self, test_repo: Repository) -> None:
        """Test updating project is_active status."""
        # Create organization and project
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Project")

        # Verify project is active by default
        assert project.is_active is True

        # Deactivate project
        update_command = ProjectUpdateCommand(is_active=False)
        updated_project = test_repo.projects.update(project.id, update_command)

        assert updated_project is not None
        assert updated_project.is_active is False
        assert updated_project.name == project.name  # Unchanged

        # Reactivate project
        reactivate_command = ProjectUpdateCommand(is_active=True)
        reactivated_project = test_repo.projects.update(project.id, reactivate_command)

        assert reactivated_project is not None
        assert reactivated_project.is_active is True

    def test_update_project_all_fields(self, test_repo: Repository) -> None:
        """Test updating all project fields."""
        # Create organization and project
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Old Name", "Old description")

        # Update all fields
        update_command = ProjectUpdateCommand(name="New Name", description="New description", is_active=False)
        updated_project = test_repo.projects.update(project.id, update_command)

        assert updated_project is not None
        assert updated_project.name == "New Name"
        assert updated_project.description == "New description"
        assert updated_project.is_active is False

    def test_update_project_not_found(self, test_repo: Repository) -> None:
        """Test updating non-existent project returns None."""
        update_command = ProjectUpdateCommand(name="New Name")
        result = test_repo.projects.update("non-existent-id", update_command)

        assert result is None

    def test_update_project_with_empty_command(self, test_repo: Repository) -> None:
        """Test updating project with no fields succeeds (no-op)."""
        # Create organization and project
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Project")

        # Update with empty command
        update_command = ProjectUpdateCommand()
        updated_project = test_repo.projects.update(project.id, update_command)

        assert updated_project is not None
        assert updated_project.name == project.name
        assert updated_project.description == project.description


class TestProjectRepositoryDelete:
    """Test project deletion operations."""

    def test_delete_project_succeeds(self, test_repo: Repository) -> None:
        """Test deleting an existing project."""
        # Create organization and project
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "To Delete")

        # Delete project
        result = test_repo.projects.delete(project.id)

        assert result is True

        # Verify deletion
        deleted_project = test_repo.projects.get_by_id(project.id)
        assert deleted_project is None

    def test_delete_project_not_found(self, test_repo: Repository) -> None:
        """Test deleting non-existent project returns False."""
        result = test_repo.projects.delete("non-existent-id")

        assert result is False


class TestProjectRepositoryTimestamps:
    """Test project timestamp behavior."""

    def test_created_at_and_updated_at_are_set_on_create(self, test_repo: Repository) -> None:
        """Test that both timestamps are set when creating a project."""
        # Create organization and project
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id)

        assert isinstance(project.created_at, datetime)
        assert isinstance(project.updated_at, datetime)

        # Initially, created_at and updated_at should be very close
        time_diff = abs((project.updated_at - project.created_at).total_seconds())
        assert time_diff < 1.0  # Less than 1 second difference


class TestProjectRepositoryFilters:
    """Test project filtering operations."""

    def test_filter_by_name_substring(self, test_repo: Repository) -> None:
        """Test filtering projects by name substring."""
        org = create_test_org_with_workflow_via_repo(test_repo)

        # Create projects with different names
        create_test_project_via_repo(test_repo, org.id, "Backend API")
        create_test_project_via_repo(test_repo, org.id, "Frontend App")
        create_test_project_via_repo(test_repo, org.id, "Mobile Backend")

        # Filter by "backend"
        results = test_repo.projects.get_by_filters(organization_id=org.id, name="backend")

        assert len(results) == 2
        assert {p.name for p in results} == {"Backend API", "Mobile Backend"}

    def test_filter_by_name_case_insensitive(self, test_repo: Repository) -> None:
        """Test name filtering is case-insensitive."""
        org = create_test_org_with_workflow_via_repo(test_repo)
        create_test_project_via_repo(test_repo, org.id, "Backend API")

        # Test different case variations
        for search_term in ["BACKEND", "backend", "Backend", "BaCkEnD"]:
            results = test_repo.projects.get_by_filters(organization_id=org.id, name=search_term)
            assert len(results) == 1
            assert results[0].name == "Backend API"

    def test_filter_by_is_active(self, test_repo: Repository) -> None:
        """Test filtering projects by active status."""
        org = create_test_org_with_workflow_via_repo(test_repo)

        # Create active and inactive projects
        active_project = create_test_project_via_repo(test_repo, org.id, "Active Project")
        inactive_project = create_test_project_via_repo(test_repo, org.id, "Inactive Project")

        # Deactivate one project
        test_repo.projects.update(inactive_project.id, ProjectUpdateCommand(is_active=False))

        # Filter for active only
        active_results = test_repo.projects.get_by_filters(organization_id=org.id, is_active=True)
        assert len(active_results) == 1
        assert active_results[0].id == active_project.id

        # Filter for inactive only
        inactive_results = test_repo.projects.get_by_filters(organization_id=org.id, is_active=False)
        assert len(inactive_results) == 1
        assert inactive_results[0].id == inactive_project.id

    def test_filter_by_name_and_is_active(self, test_repo: Repository) -> None:
        """Test combining name and is_active filters."""
        org = create_test_org_with_workflow_via_repo(test_repo)

        # Create projects
        backend_active = create_test_project_via_repo(test_repo, org.id, "Backend API")
        backend_inactive = create_test_project_via_repo(test_repo, org.id, "Backend Service")

        # Deactivate backend service
        test_repo.projects.update(backend_inactive.id, ProjectUpdateCommand(is_active=False))

        # Filter by name="backend" and is_active=True
        results = test_repo.projects.get_by_filters(organization_id=org.id, name="backend", is_active=True)

        assert len(results) == 1
        assert results[0].id == backend_active.id

    def test_filter_by_organization_id(self, test_repo: Repository) -> None:
        """Test filtering projects by organization ID."""
        org1 = create_test_org_with_workflow_via_repo(test_repo, "Org 1")
        org2 = create_test_org_with_workflow_via_repo(test_repo, "Org 2")

        # Create projects in both orgs
        create_test_project_via_repo(test_repo, org1.id, "Org1 Project")
        create_test_project_via_repo(test_repo, org2.id, "Org2 Project")

        # Filter by org1
        org1_results = test_repo.projects.get_by_filters(organization_id=org1.id)
        assert len(org1_results) == 1
        assert org1_results[0].organization_id == org1.id

        # Filter by org2
        org2_results = test_repo.projects.get_by_filters(organization_id=org2.id)
        assert len(org2_results) == 1
        assert org2_results[0].organization_id == org2.id

    def test_filter_with_no_organization_filter_returns_all(self, test_repo: Repository) -> None:
        """Test filtering without organization_id returns all projects."""
        org1 = create_test_org_with_workflow_via_repo(test_repo, "Org 1")
        org2 = create_test_org_with_workflow_via_repo(test_repo, "Org 2")

        create_test_project_via_repo(test_repo, org1.id, "Project 1")
        create_test_project_via_repo(test_repo, org2.id, "Project 2")

        # Filter without organization_id
        results = test_repo.projects.get_by_filters()

        assert len(results) == 2
        assert {p.name for p in results} == {"Project 1", "Project 2"}

    def test_filter_with_no_matches_returns_empty_list(self, test_repo: Repository) -> None:
        """Test filtering with no matches returns empty list."""
        org = create_test_org_with_workflow_via_repo(test_repo)
        create_test_project_via_repo(test_repo, org.id, "Backend API")

        # Search for non-existent name
        results = test_repo.projects.get_by_filters(organization_id=org.id, name="nonexistent")

        assert results == []

    def test_filter_respects_organization_boundaries(self, test_repo: Repository) -> None:
        """Test filtering respects organization boundaries."""
        org1 = create_test_org_with_workflow_via_repo(test_repo, "Org 1")
        org2 = create_test_org_with_workflow_via_repo(test_repo, "Org 2")

        # Create projects with "backend" in both orgs
        create_test_project_via_repo(test_repo, org1.id, "Backend API")
        create_test_project_via_repo(test_repo, org2.id, "Backend Service")

        # Filter by name in org1
        org1_results = test_repo.projects.get_by_filters(organization_id=org1.id, name="backend")
        assert len(org1_results) == 1
        assert org1_results[0].organization_id == org1.id

        # Filter by name in org2
        org2_results = test_repo.projects.get_by_filters(organization_id=org2.id, name="backend")
        assert len(org2_results) == 1
        assert org2_results[0].organization_id == org2.id


class TestProjectRepositoryArchive:
    """Test project archive operations."""

    def test_archive_project_sets_fields(self, test_repo: Repository) -> None:
        """Test archiving project sets is_archived and archived_at."""
        # Create organization and project
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "To Archive")

        # Archive project
        archived = test_repo.projects.archive(project.id)

        assert archived is not None
        assert archived.is_archived is True
        assert archived.archived_at is not None
        assert archived.id == project.id

    def test_archive_project_not_found_returns_none(self, test_repo: Repository) -> None:
        """Test archiving non-existent project returns None."""
        result = test_repo.projects.archive("non-existent-id")

        assert result is None

    def test_archive_project_persists(self, test_repo: Repository) -> None:
        """Test archived state persists in database."""
        # Create and archive project
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Persist Archive")
        archived = test_repo.projects.archive(project.id)
        assert archived is not None

        # Retrieve and verify
        retrieved = test_repo.projects.get_by_id(project.id)
        assert retrieved is not None
        assert retrieved.is_archived is True
        assert retrieved.archived_at is not None

    def test_unarchive_project_clears_fields(self, test_repo: Repository) -> None:
        """Test unarchiving project clears is_archived and archived_at."""
        # Create and archive project
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "To Unarchive")
        archived = test_repo.projects.archive(project.id)
        assert archived is not None

        # Unarchive project
        unarchived = test_repo.projects.unarchive(project.id)

        assert unarchived is not None
        assert unarchived.is_archived is False
        assert unarchived.archived_at is None
        assert unarchived.id == project.id

    def test_unarchive_project_not_found_returns_none(self, test_repo: Repository) -> None:
        """Test unarchiving non-existent project returns None."""
        result = test_repo.projects.unarchive("non-existent-id")

        assert result is None

    def test_get_by_filters_excludes_archived_by_default(self, test_repo: Repository) -> None:
        """Test get_by_filters excludes archived projects by default."""
        org = create_test_org_with_workflow_via_repo(test_repo)

        # Create two projects, archive one
        active_project = create_test_project_via_repo(test_repo, org.id, "Active")
        archived_project = create_test_project_via_repo(test_repo, org.id, "Archived")
        test_repo.projects.archive(archived_project.id)

        # Filter without include_archived
        results = test_repo.projects.get_by_filters(organization_id=org.id)

        assert len(results) == 1
        assert results[0].id == active_project.id

    def test_get_by_filters_includes_archived_when_requested(self, test_repo: Repository) -> None:
        """Test get_by_filters includes archived when include_archived=True."""
        org = create_test_org_with_workflow_via_repo(test_repo)

        # Create two projects, archive one
        active_project = create_test_project_via_repo(test_repo, org.id, "Active")
        archived_project = create_test_project_via_repo(test_repo, org.id, "Archived")
        test_repo.projects.archive(archived_project.id)

        # Filter with include_archived=True
        results = test_repo.projects.get_by_filters(organization_id=org.id, include_archived=True)

        assert len(results) == 2
        project_ids = {p.id for p in results}
        assert active_project.id in project_ids
        assert archived_project.id in project_ids

    def test_get_by_filters_name_filter_with_archived(self, test_repo: Repository) -> None:
        """Test combining name filter with include_archived."""
        org = create_test_org_with_workflow_via_repo(test_repo)

        # Create projects
        create_test_project_via_repo(test_repo, org.id, "Backend API")
        archived_backend = create_test_project_via_repo(test_repo, org.id, "Backend Service")
        test_repo.projects.archive(archived_backend.id)

        # Filter by name without archived - should find 1
        results_no_archived = test_repo.projects.get_by_filters(organization_id=org.id, name="backend")
        assert len(results_no_archived) == 1

        # Filter by name with archived - should find 2
        results_with_archived = test_repo.projects.get_by_filters(
            organization_id=org.id, name="backend", include_archived=True
        )
        assert len(results_with_archived) == 2

    def test_get_all_excludes_archived_by_default(self, test_repo: Repository) -> None:
        """Test get_all excludes archived projects."""
        org = create_test_org_with_workflow_via_repo(test_repo)

        # Create two projects, archive one
        create_test_project_via_repo(test_repo, org.id, "Active")
        archived_project = create_test_project_via_repo(test_repo, org.id, "Archived")
        test_repo.projects.archive(archived_project.id)

        # Get all projects
        all_projects = test_repo.projects.get_all()

        assert len(all_projects) == 1
        assert all_projects[0].name == "Active"

    def test_get_by_organization_id_excludes_archived(self, test_repo: Repository) -> None:
        """Test get_by_organization_id excludes archived projects."""
        org = create_test_org_with_workflow_via_repo(test_repo)

        # Create two projects, archive one
        create_test_project_via_repo(test_repo, org.id, "Active")
        archived_project = create_test_project_via_repo(test_repo, org.id, "Archived")
        test_repo.projects.archive(archived_project.id)

        # Get by organization
        org_projects = test_repo.projects.get_by_organization_id(org.id)

        assert len(org_projects) == 1
        assert org_projects[0].name == "Active"


class TestProjectRepositoryWorkflows:
    """Test complete project workflows."""

    def test_complete_project_workflow(self, test_repo: Repository) -> None:
        """Test complete workflow: create, read, update, list, delete."""
        # 1. Create organization
        org = create_test_org_with_workflow_via_repo(test_repo, "Workflow Org")

        # 2. Create project
        project_data = ProjectData(name="Workflow Project", description="Initial description")
        create_command = ProjectCreateCommand(project_data=project_data, organization_id=org.id)
        created_project = test_repo.projects.create(create_command)

        assert created_project.name == "Workflow Project"
        assert created_project.organization_id == org.id

        # 3. Read project
        retrieved_project = test_repo.projects.get_by_id(created_project.id)
        assert retrieved_project is not None
        assert retrieved_project.name == "Workflow Project"

        # 4. Update project
        update_command = ProjectUpdateCommand(name="Updated Project", description="Updated description")
        updated_project = test_repo.projects.update(created_project.id, update_command)
        assert updated_project is not None
        assert updated_project.name == "Updated Project"

        # 5. List projects for organization
        org_projects = test_repo.projects.get_by_organization_id(org.id)
        assert len(org_projects) == 1
        assert org_projects[0].name == "Updated Project"

        # 6. Delete project
        delete_result = test_repo.projects.delete(created_project.id)
        assert delete_result is True

        # 7. Verify deletion
        deleted_project = test_repo.projects.get_by_id(created_project.id)
        assert deleted_project is None

    def test_multiple_projects_in_same_organization(self, test_repo: Repository) -> None:
        """Test creating multiple projects within the same organization."""
        # Create organization
        org = create_test_org_with_workflow_via_repo(test_repo, "Multi-Project Org")

        # Create multiple projects
        create_test_project_via_repo(test_repo, org.id, "Backend")
        create_test_project_via_repo(test_repo, org.id, "Frontend")
        create_test_project_via_repo(test_repo, org.id, "Mobile")

        # List all projects for organization
        org_projects = test_repo.projects.get_by_organization_id(org.id)

        assert len(org_projects) == 3
        assert {p.name for p in org_projects} == {"Backend", "Frontend", "Mobile"}
        assert all(p.organization_id == org.id for p in org_projects)

    def test_projects_isolated_by_organization(self, test_repo: Repository) -> None:
        """Test that projects are properly isolated by organization."""
        # Create two organizations
        org1 = create_test_org_with_workflow_via_repo(test_repo, "Org 1")
        org2 = create_test_org_with_workflow_via_repo(test_repo, "Org 2")

        # Create projects for each organization
        create_test_project_via_repo(test_repo, org1.id, "Org1 Backend")
        create_test_project_via_repo(test_repo, org1.id, "Org1 Frontend")
        create_test_project_via_repo(test_repo, org2.id, "Org2 Mobile")

        # Get projects for each organization
        org1_projects = test_repo.projects.get_by_organization_id(org1.id)
        org2_projects = test_repo.projects.get_by_organization_id(org2.id)

        # Verify isolation
        assert len(org1_projects) == 2
        assert len(org2_projects) == 1
        assert all(p.organization_id == org1.id for p in org1_projects)
        assert all(p.organization_id == org2.id for p in org2_projects)
        assert {p.name for p in org1_projects} == {"Org1 Backend", "Org1 Frontend"}
        assert {p.name for p in org2_projects} == {"Org2 Mobile"}


class TestProjectWorkflowIntegration:
    """Tests for project-workflow integration."""

    def test_create_project_uses_default_workflow_when_not_specified(self, test_repo: Repository) -> None:
        """Test that project uses organization's default workflow when workflow_id not specified."""
        # Create organization (with default workflow)
        org = create_test_org_with_workflow_via_repo(test_repo)

        # Get default workflow for org
        default_workflow = test_repo.workflows.get_default_workflow(org.id)
        assert default_workflow is not None

        # Create project without specifying workflow_id
        project_data = ProjectData(name="Test Project", description="Test")
        command = ProjectCreateCommand(project_data=project_data, organization_id=org.id)
        project = test_repo.projects.create(command)

        # Verify project uses default workflow
        assert project.workflow_id == default_workflow.id

    def test_create_project_with_explicit_workflow_id(self, test_repo: Repository) -> None:
        """Test creating project with explicitly specified workflow."""
        # Create organization and custom workflow
        org = create_test_org_with_workflow_via_repo(test_repo)

        from project_management_crud_example.domain_models import WorkflowCreateCommand, WorkflowData

        workflow_data = WorkflowData(name="Custom Workflow", statuses=["BACKLOG", "IN_PROGRESS", "DONE"])
        custom_workflow = test_repo.workflows.create(
            WorkflowCreateCommand(workflow_data=workflow_data, organization_id=org.id)
        )

        # Create project with custom workflow
        project_data = ProjectData(name="Test Project", workflow_id=custom_workflow.id)
        command = ProjectCreateCommand(project_data=project_data, organization_id=org.id)
        project = test_repo.projects.create(command)

        # Verify project uses custom workflow
        assert project.workflow_id == custom_workflow.id

    def test_create_project_with_nonexistent_workflow_fails(self, test_repo: Repository) -> None:
        """Test that creating project with non-existent workflow fails."""
        import pytest

        org = create_test_org_with_workflow_via_repo(test_repo)

        # Try to create project with non-existent workflow
        project_data = ProjectData(name="Test Project", workflow_id="non-existent-workflow-id")
        command = ProjectCreateCommand(project_data=project_data, organization_id=org.id)

        with pytest.raises(ValueError, match="Workflow not found"):
            test_repo.projects.create(command)

    def test_create_project_with_workflow_from_different_org_fails(self, test_repo: Repository) -> None:
        """Test that creating project with workflow from different org fails."""
        import pytest

        from project_management_crud_example.domain_models import WorkflowCreateCommand, WorkflowData

        # Create two organizations
        org1 = create_test_org_with_workflow_via_repo(test_repo, "Org 1")
        org2 = create_test_org_with_workflow_via_repo(test_repo, "Org 2")

        # Create workflow in org2
        workflow_data = WorkflowData(name="Org2 Workflow", statuses=["TODO", "DONE"])
        org2_workflow = test_repo.workflows.create(
            WorkflowCreateCommand(workflow_data=workflow_data, organization_id=org2.id)
        )

        # Try to create project in org1 with org2's workflow
        project_data = ProjectData(name="Test Project", workflow_id=org2_workflow.id)
        command = ProjectCreateCommand(project_data=project_data, organization_id=org1.id)

        with pytest.raises(ValueError, match="belongs to different organization"):
            test_repo.projects.create(command)

    def test_update_project_workflow_id(self, test_repo: Repository) -> None:
        """Test updating project's workflow."""
        from project_management_crud_example.domain_models import WorkflowCreateCommand, WorkflowData

        # Create organization with project
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Test Project")

        # Get initial workflow
        initial_workflow_id = project.workflow_id

        # Create new workflow
        workflow_data = WorkflowData(name="New Workflow", statuses=["BACKLOG", "TODO", "DONE"])
        new_workflow = test_repo.workflows.create(
            WorkflowCreateCommand(workflow_data=workflow_data, organization_id=org.id)
        )

        # Update project workflow
        update_command = ProjectUpdateCommand(workflow_id=new_workflow.id)
        updated_project = test_repo.projects.update(project.id, update_command)

        # Verify workflow changed
        assert updated_project is not None
        assert updated_project.workflow_id == new_workflow.id
        assert updated_project.workflow_id != initial_workflow_id

    def test_update_project_workflow_to_nonexistent_fails(self, test_repo: Repository) -> None:
        """Test that updating project to non-existent workflow fails."""
        import pytest

        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Test Project")

        # Try to update to non-existent workflow
        update_command = ProjectUpdateCommand(workflow_id="non-existent-workflow-id")

        with pytest.raises(ValueError, match="Workflow not found"):
            test_repo.projects.update(project.id, update_command)

    def test_update_project_workflow_to_different_org_fails(self, test_repo: Repository) -> None:
        """Test that updating project to workflow from different org fails."""
        import pytest

        from project_management_crud_example.domain_models import WorkflowCreateCommand, WorkflowData

        # Create two organizations
        org1 = create_test_org_with_workflow_via_repo(test_repo, "Org 1")
        org2 = create_test_org_with_workflow_via_repo(test_repo, "Org 2")

        # Create project in org1
        project = create_test_project_via_repo(test_repo, org1.id, "Test Project")

        # Create workflow in org2
        workflow_data = WorkflowData(name="Org2 Workflow", statuses=["TODO", "DONE"])
        org2_workflow = test_repo.workflows.create(
            WorkflowCreateCommand(workflow_data=workflow_data, organization_id=org2.id)
        )

        # Try to update org1 project to org2 workflow
        update_command = ProjectUpdateCommand(workflow_id=org2_workflow.id)

        with pytest.raises(ValueError, match="belongs to different organization"):
            test_repo.projects.update(project.id, update_command)

    def test_project_workflow_id_persists_across_retrieval(self, test_repo: Repository) -> None:
        """Test that workflow_id persists when project is retrieved."""
        from project_management_crud_example.domain_models import WorkflowCreateCommand, WorkflowData

        # Create organization and custom workflow
        org = create_test_org_with_workflow_via_repo(test_repo)
        workflow_data = WorkflowData(name="Custom Workflow", statuses=["TODO", "IN_PROGRESS", "DONE"])
        custom_workflow = test_repo.workflows.create(
            WorkflowCreateCommand(workflow_data=workflow_data, organization_id=org.id)
        )

        # Create project with custom workflow
        project_data = ProjectData(name="Test Project", workflow_id=custom_workflow.id)
        command = ProjectCreateCommand(project_data=project_data, organization_id=org.id)
        created_project = test_repo.projects.create(command)

        # Retrieve project
        retrieved_project = test_repo.projects.get_by_id(created_project.id)

        # Verify workflow_id persists
        assert retrieved_project is not None
        assert retrieved_project.workflow_id == custom_workflow.id
