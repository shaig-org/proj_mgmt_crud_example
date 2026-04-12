"""Tests for Ticket repository operations.

Tests verify complete CRUD functionality for tickets through the Repository interface,
including project scoping, filtering, status/assignment updates, and edge cases.
"""

from datetime import datetime

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    TicketCreateCommand,
    TicketData,
    TicketPriority,
    TicketStatus,
    TicketUpdateCommand,
    UserRole,
)
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import (
    create_test_org_with_workflow_via_repo,
    create_test_project_via_repo,
    create_test_user_via_repo,
)


class TestTicketRepositoryCreate:
    """Test ticket creation through repository."""

    def test_create_ticket_with_all_fields(self, test_repo: Repository) -> None:
        """Test creating a ticket with all fields through repository."""
        # Create organization, project, and users
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id)
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)
        assignee = create_test_user_via_repo(test_repo, org.id, username="assignee", role=UserRole.WRITE_ACCESS)

        # Create ticket
        ticket_data = TicketData(
            title="Implement feature X",
            description="This is a detailed description",
            priority=TicketPriority.HIGH,
        )
        command = TicketCreateCommand(
            ticket_data=ticket_data,
            project_id=project.id,
            assignee_id=assignee.id,
        )

        ticket = test_repo.tickets.create(command, reporter_id=reporter.id)

        assert ticket.id is not None
        assert ticket.title == "Implement feature X"
        assert ticket.description == "This is a detailed description"
        assert ticket.status == TicketStatus.TODO  # Default status
        assert ticket.priority == TicketPriority.HIGH
        assert ticket.assignee_id == assignee.id
        assert ticket.reporter_id == reporter.id
        assert ticket.project_id == project.id
        assert isinstance(ticket.created_at, datetime)
        assert isinstance(ticket.updated_at, datetime)

    def test_create_ticket_without_optional_fields(self, test_repo: Repository) -> None:
        """Test creating a ticket without optional fields (description, priority, assignee)."""
        # Create organization, project, and reporter
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Project")
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)

        # Create ticket without optional fields
        ticket_data = TicketData(title="Simple ticket")
        command = TicketCreateCommand(ticket_data=ticket_data, project_id=project.id)

        ticket = test_repo.tickets.create(command, reporter_id=reporter.id)

        assert ticket.title == "Simple ticket"
        assert ticket.description is None
        assert ticket.priority is None
        assert ticket.assignee_id is None
        assert ticket.status == TicketStatus.TODO
        assert ticket.reporter_id == reporter.id

    def test_create_ticket_persists_to_database(self, test_repo: Repository) -> None:
        """Test that created ticket can be retrieved from database."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Project")
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)

        # Create ticket
        ticket_data = TicketData(title="Persistent ticket")
        command = TicketCreateCommand(ticket_data=ticket_data, project_id=project.id)
        created_ticket = test_repo.tickets.create(command, reporter_id=reporter.id)

        # Retrieve ticket
        retrieved_ticket = test_repo.tickets.get_by_id(created_ticket.id)

        assert retrieved_ticket is not None
        assert retrieved_ticket.id == created_ticket.id
        assert retrieved_ticket.title == created_ticket.title
        assert retrieved_ticket.project_id == project.id


class TestTicketRepositoryGet:
    """Test ticket retrieval operations."""

    def test_get_ticket_by_id_found(self, test_repo: Repository) -> None:
        """Test retrieving an existing ticket by ID."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Project")
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)

        # Create ticket
        ticket_data = TicketData(title="Test Ticket")
        ticket = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=ticket_data, project_id=project.id),
            reporter_id=reporter.id,
        )

        # Retrieve ticket
        retrieved = test_repo.tickets.get_by_id(ticket.id)

        assert retrieved is not None
        assert retrieved.id == ticket.id
        assert retrieved.title == "Test Ticket"

    def test_get_ticket_by_id_not_found(self, test_repo: Repository) -> None:
        """Test retrieving a non-existent ticket returns None."""
        result = test_repo.tickets.get_by_id("non-existent-id")

        assert result is None

    def test_get_tickets_by_project_id(self, test_repo: Repository) -> None:
        """Test retrieving all tickets for a specific project."""
        # Create organization
        org = create_test_org_with_workflow_via_repo(test_repo)
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)

        # Create two projects
        project1 = create_test_project_via_repo(test_repo, org.id, "Project 1")
        project2 = create_test_project_via_repo(test_repo, org.id, "Project 2")

        # Create tickets for project1
        test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Project1 Ticket 1"), project_id=project1.id),
            reporter_id=reporter.id,
        )
        test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Project1 Ticket 2"), project_id=project1.id),
            reporter_id=reporter.id,
        )

        # Create ticket for project2
        test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Project2 Ticket 1"), project_id=project2.id),
            reporter_id=reporter.id,
        )

        # Get tickets for project1
        project1_tickets = test_repo.tickets.get_by_project_id(project1.id)

        assert len(project1_tickets) == 2
        assert all(t.project_id == project1.id for t in project1_tickets)
        assert {t.title for t in project1_tickets} == {"Project1 Ticket 1", "Project1 Ticket 2"}

    def test_get_all_tickets(self, test_repo: Repository) -> None:
        """Test retrieving all tickets across all projects."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Project")
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)

        # Create tickets
        test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Ticket 1"), project_id=project.id),
            reporter_id=reporter.id,
        )
        test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Ticket 2"), project_id=project.id),
            reporter_id=reporter.id,
        )

        # Get all tickets
        all_tickets = test_repo.tickets.get_all()

        assert len(all_tickets) == 2
        assert {t.title for t in all_tickets} == {"Ticket 1", "Ticket 2"}


class TestTicketRepositoryFilters:
    """Test ticket filtering operations."""

    def test_get_tickets_by_filters_project_id(self, test_repo: Repository) -> None:
        """Test filtering tickets by project ID."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project1 = create_test_project_via_repo(test_repo, org.id, "Project 1")
        project2 = create_test_project_via_repo(test_repo, org.id, "Project 2")
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)

        # Create tickets
        test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="P1 Ticket 1"), project_id=project1.id),
            reporter_id=reporter.id,
        )
        test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="P2 Ticket 1"), project_id=project2.id),
            reporter_id=reporter.id,
        )

        # Filter by project1
        filtered = test_repo.tickets.get_by_filters(project_id=project1.id)

        assert len(filtered) == 1
        assert filtered[0].project_id == project1.id

    def test_get_tickets_by_filters_status(self, test_repo: Repository) -> None:
        """Test filtering tickets by status."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Project")
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)

        # Create tickets with different statuses
        ticket1 = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Todo Ticket"), project_id=project.id),
            reporter_id=reporter.id,
        )
        ticket2 = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="In Progress Ticket"), project_id=project.id),
            reporter_id=reporter.id,
        )
        test_repo.tickets.update_status(ticket2.id, TicketStatus.IN_PROGRESS)

        # Filter by TODO status
        filtered = test_repo.tickets.get_by_filters(status=TicketStatus.TODO)

        assert len(filtered) == 1
        assert filtered[0].status == TicketStatus.TODO
        assert filtered[0].id == ticket1.id

    def test_get_tickets_by_filters_assignee_id(self, test_repo: Repository) -> None:
        """Test filtering tickets by assignee."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Project")
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)
        assignee = create_test_user_via_repo(test_repo, org.id, username="assignee", role=UserRole.WRITE_ACCESS)

        # Create tickets
        test_repo.tickets.create(
            TicketCreateCommand(
                ticket_data=TicketData(title="Assigned"), project_id=project.id, assignee_id=assignee.id
            ),
            reporter_id=reporter.id,
        )
        test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Unassigned"), project_id=project.id),
            reporter_id=reporter.id,
        )

        # Filter by assignee
        filtered = test_repo.tickets.get_by_filters(assignee_id=assignee.id)

        assert len(filtered) == 1
        assert filtered[0].assignee_id == assignee.id

    def test_get_tickets_by_filters_combined(self, test_repo: Repository) -> None:
        """Test filtering tickets by multiple criteria (AND logic)."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Project")
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)
        assignee = create_test_user_via_repo(test_repo, org.id, username="assignee", role=UserRole.WRITE_ACCESS)

        # Create tickets
        ticket1 = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Match"), project_id=project.id, assignee_id=assignee.id),
            reporter_id=reporter.id,
        )
        test_repo.tickets.update_status(ticket1.id, TicketStatus.IN_PROGRESS)

        # Create ticket with different status (won't match filter)
        test_repo.tickets.create(
            TicketCreateCommand(
                ticket_data=TicketData(title="No Match - Different Status"),
                project_id=project.id,
                assignee_id=assignee.id,
            ),
            reporter_id=reporter.id,
        )  # Status = TODO

        # Filter by project, status, and assignee
        filtered = test_repo.tickets.get_by_filters(
            project_id=project.id,
            status=TicketStatus.IN_PROGRESS,
            assignee_id=assignee.id,
        )

        assert len(filtered) == 1
        assert filtered[0].id == ticket1.id


class TestTicketRepositoryUpdate:
    """Test ticket update operations."""

    def test_update_ticket_title(self, test_repo: Repository) -> None:
        """Test updating ticket title."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Project")
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)
        ticket = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Old Title"), project_id=project.id),
            reporter_id=reporter.id,
        )

        # Update title
        update_command = TicketUpdateCommand(title="New Title")
        updated_ticket = test_repo.tickets.update(ticket.id, update_command)

        assert updated_ticket is not None
        assert updated_ticket.title == "New Title"
        assert updated_ticket.description == ticket.description  # Unchanged

    def test_update_ticket_all_fields(self, test_repo: Repository) -> None:
        """Test updating all ticket fields."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Project")
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)
        ticket = test_repo.tickets.create(
            TicketCreateCommand(
                ticket_data=TicketData(title="Old Title", description="Old desc", priority=TicketPriority.LOW),
                project_id=project.id,
            ),
            reporter_id=reporter.id,
        )

        # Update all fields
        update_command = TicketUpdateCommand(
            title="New Title",
            description="New desc",
            priority=TicketPriority.CRITICAL,
        )
        updated_ticket = test_repo.tickets.update(ticket.id, update_command)

        assert updated_ticket is not None
        assert updated_ticket.title == "New Title"
        assert updated_ticket.description == "New desc"
        assert updated_ticket.priority == TicketPriority.CRITICAL

    def test_update_ticket_not_found(self, test_repo: Repository) -> None:
        """Test updating non-existent ticket returns None."""
        update_command = TicketUpdateCommand(title="New Title")
        result = test_repo.tickets.update("non-existent-id", update_command)

        assert result is None

    def test_update_status(self, test_repo: Repository) -> None:
        """Test updating ticket status."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Project")
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)
        ticket = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Ticket"), project_id=project.id),
            reporter_id=reporter.id,
        )

        # Update status
        updated_ticket = test_repo.tickets.update_status(ticket.id, TicketStatus.IN_PROGRESS)

        assert updated_ticket is not None
        assert updated_ticket.status == TicketStatus.IN_PROGRESS

    def test_update_project(self, test_repo: Repository) -> None:
        """Test moving ticket to different project."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project1 = create_test_project_via_repo(test_repo, org.id, "Project 1")
        project2 = create_test_project_via_repo(test_repo, org.id, "Project 2")
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)
        ticket = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Ticket"), project_id=project1.id),
            reporter_id=reporter.id,
        )

        # Move to project2
        updated_ticket = test_repo.tickets.update_project(ticket.id, project2.id)

        assert updated_ticket is not None
        assert updated_ticket.project_id == project2.id

    def test_update_assignee_assign(self, test_repo: Repository) -> None:
        """Test assigning ticket to a user."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Project")
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)
        assignee = create_test_user_via_repo(test_repo, org.id, username="assignee", role=UserRole.WRITE_ACCESS)
        ticket = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Ticket"), project_id=project.id),
            reporter_id=reporter.id,
        )

        # Assign to user
        updated_ticket = test_repo.tickets.update_assignee(ticket.id, assignee.id)

        assert updated_ticket is not None
        assert updated_ticket.assignee_id == assignee.id

    def test_update_assignee_unassign(self, test_repo: Repository) -> None:
        """Test unassigning ticket (set to None)."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Project")
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)
        assignee = create_test_user_via_repo(test_repo, org.id, username="assignee", role=UserRole.WRITE_ACCESS)
        ticket = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Ticket"), project_id=project.id, assignee_id=assignee.id),
            reporter_id=reporter.id,
        )

        # Unassign
        updated_ticket = test_repo.tickets.update_assignee(ticket.id, None)

        assert updated_ticket is not None
        assert updated_ticket.assignee_id is None


class TestTicketRepositoryDelete:
    """Test ticket deletion operations."""

    def test_delete_ticket_succeeds(self, test_repo: Repository) -> None:
        """Test deleting an existing ticket."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Project")
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)
        ticket = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="To Delete"), project_id=project.id),
            reporter_id=reporter.id,
        )

        # Delete ticket
        result = test_repo.tickets.delete(ticket.id)

        assert result is True

        # Verify deletion
        deleted_ticket = test_repo.tickets.get_by_id(ticket.id)
        assert deleted_ticket is None

    def test_delete_ticket_not_found(self, test_repo: Repository) -> None:
        """Test deleting non-existent ticket returns False."""
        result = test_repo.tickets.delete("non-existent-id")

        assert result is False


class TestTicketRepositoryTimestamps:
    """Test ticket timestamp behavior."""

    def test_created_at_and_updated_at_are_set_on_create(self, test_repo: Repository) -> None:
        """Test that both timestamps are set when creating a ticket."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id, "Project")
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)

        ticket = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Test Ticket"), project_id=project.id),
            reporter_id=reporter.id,
        )

        assert isinstance(ticket.created_at, datetime)
        assert isinstance(ticket.updated_at, datetime)

        # Initially, created_at and updated_at should be very close
        time_diff = abs((ticket.updated_at - ticket.created_at).total_seconds())
        assert time_diff < 1.0  # Less than 1 second difference


class TestTicketRepositoryWorkflows:
    """Test complete ticket workflows."""

    def test_complete_ticket_workflow(self, test_repo: Repository) -> None:
        """Test complete workflow: create, read, update, change status, move project, assign, delete."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo, "Workflow Org")
        project1 = create_test_project_via_repo(test_repo, org.id, "Project 1")
        project2 = create_test_project_via_repo(test_repo, org.id, "Project 2")
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)
        assignee = create_test_user_via_repo(test_repo, org.id, username="assignee", role=UserRole.WRITE_ACCESS)

        # 1. Create ticket
        ticket_data = TicketData(
            title="Workflow Ticket", description="Initial description", priority=TicketPriority.LOW
        )
        created_ticket = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=ticket_data, project_id=project1.id),
            reporter_id=reporter.id,
        )

        assert created_ticket.title == "Workflow Ticket"
        assert created_ticket.status == TicketStatus.TODO

        # 2. Read ticket
        retrieved_ticket = test_repo.tickets.get_by_id(created_ticket.id)
        assert retrieved_ticket is not None
        assert retrieved_ticket.title == "Workflow Ticket"

        # 3. Update ticket
        update_command = TicketUpdateCommand(title="Updated Ticket", priority=TicketPriority.HIGH)
        updated_ticket = test_repo.tickets.update(created_ticket.id, update_command)
        assert updated_ticket is not None
        assert updated_ticket.title == "Updated Ticket"
        assert updated_ticket.priority == TicketPriority.HIGH

        # 4. Change status
        status_updated = test_repo.tickets.update_status(created_ticket.id, TicketStatus.IN_PROGRESS)
        assert status_updated is not None
        assert status_updated.status == TicketStatus.IN_PROGRESS

        # 5. Assign ticket
        assigned_ticket = test_repo.tickets.update_assignee(created_ticket.id, assignee.id)
        assert assigned_ticket is not None
        assert assigned_ticket.assignee_id == assignee.id

        # 6. Move to different project
        moved_ticket = test_repo.tickets.update_project(created_ticket.id, project2.id)
        assert moved_ticket is not None
        assert moved_ticket.project_id == project2.id

        # 7. Complete ticket
        completed_ticket = test_repo.tickets.update_status(created_ticket.id, TicketStatus.DONE)
        assert completed_ticket is not None
        assert completed_ticket.status == TicketStatus.DONE

        # 8. List tickets for new project
        project2_tickets = test_repo.tickets.get_by_project_id(project2.id)
        assert len(project2_tickets) == 1
        assert project2_tickets[0].id == created_ticket.id

        # 9. Delete ticket
        delete_result = test_repo.tickets.delete(created_ticket.id)
        assert delete_result is True

        # 10. Verify deletion
        deleted_ticket = test_repo.tickets.get_by_id(created_ticket.id)
        assert deleted_ticket is None

    def test_multiple_tickets_in_same_project(self, test_repo: Repository) -> None:
        """Test creating multiple tickets within the same project."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo, "Multi-Ticket Org")
        project = create_test_project_via_repo(test_repo, org.id, "Project")
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)

        # Create multiple tickets
        test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Bug Fix"), project_id=project.id),
            reporter_id=reporter.id,
        )
        test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Feature Request"), project_id=project.id),
            reporter_id=reporter.id,
        )
        test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Documentation"), project_id=project.id),
            reporter_id=reporter.id,
        )

        # List all tickets for project
        project_tickets = test_repo.tickets.get_by_project_id(project.id)

        assert len(project_tickets) == 3
        assert {t.title for t in project_tickets} == {"Bug Fix", "Feature Request", "Documentation"}
        assert all(t.project_id == project.id for t in project_tickets)

    def test_tickets_isolated_by_project(self, test_repo: Repository) -> None:
        """Test that tickets are properly isolated by project."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo, "Isolation Org")
        project1 = create_test_project_via_repo(test_repo, org.id, "Backend")
        project2 = create_test_project_via_repo(test_repo, org.id, "Frontend")
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)

        # Create tickets for each project
        test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Backend Bug"), project_id=project1.id),
            reporter_id=reporter.id,
        )
        test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Backend Feature"), project_id=project1.id),
            reporter_id=reporter.id,
        )
        test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Frontend UI"), project_id=project2.id),
            reporter_id=reporter.id,
        )

        # Get tickets for each project
        project1_tickets = test_repo.tickets.get_by_project_id(project1.id)
        project2_tickets = test_repo.tickets.get_by_project_id(project2.id)

        # Verify isolation
        assert len(project1_tickets) == 2
        assert len(project2_tickets) == 1
        assert all(t.project_id == project1.id for t in project1_tickets)
        assert all(t.project_id == project2.id for t in project2_tickets)
        assert {t.title for t in project1_tickets} == {"Backend Bug", "Backend Feature"}
        assert {t.title for t in project2_tickets} == {"Frontend UI"}
