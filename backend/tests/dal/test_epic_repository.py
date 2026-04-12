"""Tests for Epic repository operations.

Tests verify complete CRUD functionality for epics through the Repository interface,
including organization scoping, data persistence, and edge cases.
"""

from datetime import datetime

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    EpicCreateCommand,
    EpicData,
    EpicUpdateCommand,
    TicketCreateCommand,
    TicketData,
    UserRole,
)
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import (
    create_test_epic_via_repo,
    create_test_org_via_repo,
    create_test_org_with_workflow_via_repo,
    create_test_project_via_repo,
    create_test_user_via_repo,
)


class TestEpicRepositoryCreate:
    """Test epic creation through repository."""

    def test_create_epic_with_all_fields(self, test_repo: Repository) -> None:
        """Test creating an epic with all fields through repository."""
        # Create organization first
        org = create_test_org_via_repo(test_repo)

        # Create epic
        epic_data = EpicData(name="Launch V1", description="MVP launch epic")
        command = EpicCreateCommand(epic_data=epic_data, organization_id=org.id)

        epic = test_repo.epics.create(command)

        assert epic.id is not None
        assert epic.name == "Launch V1"
        assert epic.description == "MVP launch epic"
        assert epic.organization_id == org.id
        assert isinstance(epic.created_at, datetime)
        assert isinstance(epic.updated_at, datetime)

    def test_create_epic_without_description(self, test_repo: Repository) -> None:
        """Test creating an epic without optional description."""
        # Create organization
        org = create_test_org_via_repo(test_repo)

        # Create epic without description
        epic_data = EpicData(name="Q1 Goals")
        command = EpicCreateCommand(epic_data=epic_data, organization_id=org.id)

        epic = test_repo.epics.create(command)

        assert epic.name == "Q1 Goals"
        assert epic.description is None
        assert epic.organization_id == org.id

    def test_create_epic_persists_to_database(self, test_repo: Repository) -> None:
        """Test that created epic can be retrieved from database."""
        # Create organization
        org = create_test_org_via_repo(test_repo)

        # Create epic
        epic_data = EpicData(name="Security Improvements")
        command = EpicCreateCommand(epic_data=epic_data, organization_id=org.id)
        created_epic = test_repo.epics.create(command)

        # Retrieve epic
        retrieved_epic = test_repo.epics.get_by_id(created_epic.id)

        assert retrieved_epic is not None
        assert retrieved_epic.id == created_epic.id
        assert retrieved_epic.name == created_epic.name
        assert retrieved_epic.organization_id == org.id


class TestEpicRepositoryGet:
    """Test epic retrieval operations."""

    def test_get_epic_by_id_found(self, test_repo: Repository) -> None:
        """Test retrieving an existing epic by ID."""
        # Create organization and epic
        org = create_test_org_via_repo(test_repo)
        epic = create_test_epic_via_repo(test_repo, org.id)

        # Retrieve epic
        retrieved = test_repo.epics.get_by_id(epic.id)

        assert retrieved is not None
        assert retrieved.id == epic.id
        assert retrieved.name == "Test Epic"

    def test_get_epic_by_id_not_found(self, test_repo: Repository) -> None:
        """Test retrieving a non-existent epic returns None."""
        result = test_repo.epics.get_by_id("non-existent-id")

        assert result is None

    def test_get_epics_by_organization_id(self, test_repo: Repository) -> None:
        """Test retrieving all epics for a specific organization."""
        # Create two organizations
        org1 = create_test_org_via_repo(test_repo, "Org 1")
        org2 = create_test_org_via_repo(test_repo, "Org 2")

        # Create epics for org1
        create_test_epic_via_repo(test_repo, org1.id, "Org1 Epic 1")
        create_test_epic_via_repo(test_repo, org1.id, "Org1 Epic 2")

        # Create epic for org2
        create_test_epic_via_repo(test_repo, org2.id, "Org2 Epic 1")

        # Get epics for org1
        org1_epics = test_repo.epics.get_by_organization_id(org1.id)

        assert len(org1_epics) == 2
        assert all(e.organization_id == org1.id for e in org1_epics)
        assert {e.name for e in org1_epics} == {"Org1 Epic 1", "Org1 Epic 2"}

    def test_get_all_epics(self, test_repo: Repository) -> None:
        """Test retrieving all epics across all organizations."""
        # Create two organizations
        org1 = create_test_org_via_repo(test_repo, "Org 1")
        org2 = create_test_org_via_repo(test_repo, "Org 2")

        # Create epics
        create_test_epic_via_repo(test_repo, org1.id, "Epic 1")
        create_test_epic_via_repo(test_repo, org2.id, "Epic 2")

        # Get all epics
        all_epics = test_repo.epics.get_all()

        assert len(all_epics) == 2
        assert {e.name for e in all_epics} == {"Epic 1", "Epic 2"}


class TestEpicRepositoryUpdate:
    """Test epic update operations."""

    def test_update_epic_name(self, test_repo: Repository) -> None:
        """Test updating epic name."""
        # Create organization and epic
        org = create_test_org_via_repo(test_repo)
        epic = create_test_epic_via_repo(test_repo, org.id, "Old Name")

        # Update name
        update_command = EpicUpdateCommand(name="New Name")
        updated_epic = test_repo.epics.update(epic.id, update_command)

        assert updated_epic is not None
        assert updated_epic.name == "New Name"
        assert updated_epic.description == epic.description  # Unchanged

    def test_update_epic_description(self, test_repo: Repository) -> None:
        """Test updating epic description."""
        # Create organization and epic
        org = create_test_org_via_repo(test_repo)
        epic = create_test_epic_via_repo(test_repo, org.id, "Epic", "Old description")

        # Update description
        update_command = EpicUpdateCommand(description="New description")
        updated_epic = test_repo.epics.update(epic.id, update_command)

        assert updated_epic is not None
        assert updated_epic.description == "New description"
        assert updated_epic.name == epic.name  # Unchanged

    def test_update_epic_all_fields(self, test_repo: Repository) -> None:
        """Test updating all epic fields."""
        # Create organization and epic
        org = create_test_org_via_repo(test_repo)
        epic = create_test_epic_via_repo(test_repo, org.id, "Old Name", "Old description")

        # Update all fields
        update_command = EpicUpdateCommand(name="New Name", description="New description")
        updated_epic = test_repo.epics.update(epic.id, update_command)

        assert updated_epic is not None
        assert updated_epic.name == "New Name"
        assert updated_epic.description == "New description"

    def test_update_epic_not_found(self, test_repo: Repository) -> None:
        """Test updating non-existent epic returns None."""
        update_command = EpicUpdateCommand(name="New Name")
        result = test_repo.epics.update("non-existent-id", update_command)

        assert result is None

    def test_update_epic_with_empty_command(self, test_repo: Repository) -> None:
        """Test updating epic with no fields succeeds (no-op)."""
        # Create organization and epic
        org = create_test_org_via_repo(test_repo)
        epic = create_test_epic_via_repo(test_repo, org.id, "Epic")

        # Update with empty command
        update_command = EpicUpdateCommand()
        updated_epic = test_repo.epics.update(epic.id, update_command)

        assert updated_epic is not None
        assert updated_epic.name == epic.name
        assert updated_epic.description == epic.description


class TestEpicRepositoryDelete:
    """Test epic deletion operations."""

    def test_delete_epic_succeeds(self, test_repo: Repository) -> None:
        """Test deleting an existing epic."""
        # Create organization and epic
        org = create_test_org_via_repo(test_repo)
        epic = create_test_epic_via_repo(test_repo, org.id, "To Delete")

        # Delete epic
        result = test_repo.epics.delete(epic.id)

        assert result is True

        # Verify deletion
        deleted_epic = test_repo.epics.get_by_id(epic.id)
        assert deleted_epic is None

    def test_delete_epic_not_found(self, test_repo: Repository) -> None:
        """Test deleting non-existent epic returns False."""
        result = test_repo.epics.delete("non-existent-id")

        assert result is False


class TestEpicRepositoryTimestamps:
    """Test epic timestamp behavior."""

    def test_created_at_and_updated_at_are_set_on_create(self, test_repo: Repository) -> None:
        """Test that both timestamps are set when creating an epic."""
        # Create organization and epic
        org = create_test_org_via_repo(test_repo)
        epic = create_test_epic_via_repo(test_repo, org.id)

        assert isinstance(epic.created_at, datetime)
        assert isinstance(epic.updated_at, datetime)

        # Initially, created_at and updated_at should be very close
        time_diff = abs((epic.updated_at - epic.created_at).total_seconds())
        assert time_diff < 1.0  # Less than 1 second difference


class TestEpicRepositoryWorkflows:
    """Test complete epic workflows."""

    def test_complete_epic_workflow(self, test_repo: Repository) -> None:
        """Test complete workflow: create, read, update, list, delete."""
        # 1. Create organization
        org = create_test_org_via_repo(test_repo, "Workflow Org")

        # 2. Create epic
        epic_data = EpicData(name="Workflow Epic", description="Initial description")
        create_command = EpicCreateCommand(epic_data=epic_data, organization_id=org.id)
        created_epic = test_repo.epics.create(create_command)

        assert created_epic.name == "Workflow Epic"
        assert created_epic.organization_id == org.id

        # 3. Read epic
        retrieved_epic = test_repo.epics.get_by_id(created_epic.id)
        assert retrieved_epic is not None
        assert retrieved_epic.name == "Workflow Epic"

        # 4. Update epic
        update_command = EpicUpdateCommand(name="Updated Epic", description="Updated description")
        updated_epic = test_repo.epics.update(created_epic.id, update_command)
        assert updated_epic is not None
        assert updated_epic.name == "Updated Epic"

        # 5. List epics for organization
        org_epics = test_repo.epics.get_by_organization_id(org.id)
        assert len(org_epics) == 1
        assert org_epics[0].name == "Updated Epic"

        # 6. Delete epic
        delete_result = test_repo.epics.delete(created_epic.id)
        assert delete_result is True

        # 7. Verify deletion
        deleted_epic = test_repo.epics.get_by_id(created_epic.id)
        assert deleted_epic is None

    def test_multiple_epics_in_same_organization(self, test_repo: Repository) -> None:
        """Test creating multiple epics within the same organization."""
        # Create organization
        org = create_test_org_via_repo(test_repo, "Multi-Epic Org")

        # Create multiple epics
        create_test_epic_via_repo(test_repo, org.id, "Backend")
        create_test_epic_via_repo(test_repo, org.id, "Frontend")
        create_test_epic_via_repo(test_repo, org.id, "Mobile")

        # List all epics for organization
        org_epics = test_repo.epics.get_by_organization_id(org.id)

        assert len(org_epics) == 3
        assert {e.name for e in org_epics} == {"Backend", "Frontend", "Mobile"}
        assert all(e.organization_id == org.id for e in org_epics)

    def test_epics_isolated_by_organization(self, test_repo: Repository) -> None:
        """Test that epics are properly isolated by organization."""
        # Create two organizations
        org1 = create_test_org_via_repo(test_repo, "Org 1")
        org2 = create_test_org_via_repo(test_repo, "Org 2")

        # Create epics for each organization
        create_test_epic_via_repo(test_repo, org1.id, "Org1 Backend")
        create_test_epic_via_repo(test_repo, org1.id, "Org1 Frontend")
        create_test_epic_via_repo(test_repo, org2.id, "Org2 Mobile")

        # Get epics for each organization
        org1_epics = test_repo.epics.get_by_organization_id(org1.id)
        org2_epics = test_repo.epics.get_by_organization_id(org2.id)

        # Verify isolation
        assert len(org1_epics) == 2
        assert len(org2_epics) == 1
        assert all(e.organization_id == org1.id for e in org1_epics)
        assert all(e.organization_id == org2.id for e in org2_epics)
        assert {e.name for e in org1_epics} == {"Org1 Backend", "Org1 Frontend"}
        assert {e.name for e in org2_epics} == {"Org2 Mobile"}


class TestEpicTicketAssociations:
    """Test epic-ticket relationship operations."""

    def test_add_ticket_to_epic(self, test_repo: Repository) -> None:
        """Test adding a ticket to an epic."""
        # Create organization, project, epic, user, and ticket
        org = create_test_org_with_workflow_via_repo(test_repo, "Test Org")
        project = create_test_project_via_repo(test_repo, org.id, "Test Project")
        epic = create_test_epic_via_repo(test_repo, org.id, "Test Epic")
        reporter = create_test_user_via_repo(test_repo, org.id, "reporter", role=UserRole.ADMIN)

        ticket_data = TicketData(title="Test Ticket", description="Test")
        ticket_command = TicketCreateCommand(ticket_data=ticket_data, project_id=project.id)
        ticket = test_repo.tickets.create(ticket_command, reporter.id)

        # Add ticket to epic
        result = test_repo.epics.add_ticket_to_epic(epic.id, ticket.id)
        assert result is True

        # Verify ticket is in epic
        tickets = test_repo.epics.get_tickets_in_epic(epic.id)
        assert tickets is not None
        assert len(tickets) == 1
        assert tickets[0].id == ticket.id

    def test_add_ticket_to_epic_idempotent(self, test_repo: Repository) -> None:
        """Test adding same ticket twice is idempotent."""
        org = create_test_org_with_workflow_via_repo(test_repo, "Test Org")
        project = create_test_project_via_repo(test_repo, org.id, "Test Project")
        epic = create_test_epic_via_repo(test_repo, org.id, "Test Epic")
        reporter = create_test_user_via_repo(test_repo, org.id, "reporter", role=UserRole.ADMIN)

        ticket_data = TicketData(title="Test Ticket", description="Test")
        ticket_command = TicketCreateCommand(ticket_data=ticket_data, project_id=project.id)
        ticket = test_repo.tickets.create(ticket_command, reporter.id)

        # Add ticket twice
        result1 = test_repo.epics.add_ticket_to_epic(epic.id, ticket.id)
        result2 = test_repo.epics.add_ticket_to_epic(epic.id, ticket.id)

        assert result1 is True
        assert result2 is True  # Idempotent

        # Verify only one association exists
        tickets = test_repo.epics.get_tickets_in_epic(epic.id)
        assert tickets is not None
        assert len(tickets) == 1

    def test_add_ticket_to_nonexistent_epic(self, test_repo: Repository) -> None:
        """Test adding ticket to non-existent epic returns False."""
        org = create_test_org_with_workflow_via_repo(test_repo, "Test Org")
        project = create_test_project_via_repo(test_repo, org.id, "Test Project")
        reporter = create_test_user_via_repo(test_repo, org.id, "reporter", role=UserRole.ADMIN)

        ticket_data = TicketData(title="Test Ticket", description="Test")
        ticket_command = TicketCreateCommand(ticket_data=ticket_data, project_id=project.id)
        ticket = test_repo.tickets.create(ticket_command, reporter.id)

        result = test_repo.epics.add_ticket_to_epic("nonexistent-epic", ticket.id)
        assert result is False

    def test_add_nonexistent_ticket_to_epic(self, test_repo: Repository) -> None:
        """Test adding non-existent ticket to epic returns False."""
        org = create_test_org_via_repo(test_repo, "Test Org")
        epic = create_test_epic_via_repo(test_repo, org.id, "Test Epic")

        result = test_repo.epics.add_ticket_to_epic(epic.id, "nonexistent-ticket")
        assert result is False

    def test_remove_ticket_from_epic(self, test_repo: Repository) -> None:
        """Test removing a ticket from an epic."""
        org = create_test_org_with_workflow_via_repo(test_repo, "Test Org")
        project = create_test_project_via_repo(test_repo, org.id, "Test Project")
        epic = create_test_epic_via_repo(test_repo, org.id, "Test Epic")
        reporter = create_test_user_via_repo(test_repo, org.id, "reporter", role=UserRole.ADMIN)

        ticket_data = TicketData(title="Test Ticket", description="Test")
        ticket_command = TicketCreateCommand(ticket_data=ticket_data, project_id=project.id)
        ticket = test_repo.tickets.create(ticket_command, reporter.id)

        # Add ticket to epic
        test_repo.epics.add_ticket_to_epic(epic.id, ticket.id)

        # Verify ticket is in epic
        tickets_before = test_repo.epics.get_tickets_in_epic(epic.id)
        assert tickets_before is not None
        assert len(tickets_before) == 1

        # Remove ticket from epic
        result = test_repo.epics.remove_ticket_from_epic(epic.id, ticket.id)
        assert result is True

        # Verify ticket is no longer in epic
        tickets_after = test_repo.epics.get_tickets_in_epic(epic.id)
        assert tickets_after is not None
        assert len(tickets_after) == 0

    def test_remove_ticket_from_epic_idempotent(self, test_repo: Repository) -> None:
        """Test removing ticket that's not in epic succeeds (idempotent)."""
        org = create_test_org_with_workflow_via_repo(test_repo, "Test Org")
        project = create_test_project_via_repo(test_repo, org.id, "Test Project")
        epic = create_test_epic_via_repo(test_repo, org.id, "Test Epic")
        reporter = create_test_user_via_repo(test_repo, org.id, "reporter", role=UserRole.ADMIN)

        ticket_data = TicketData(title="Test Ticket", description="Test")
        ticket_command = TicketCreateCommand(ticket_data=ticket_data, project_id=project.id)
        ticket = test_repo.tickets.create(ticket_command, reporter.id)

        # Remove ticket that was never added (idempotent)
        result = test_repo.epics.remove_ticket_from_epic(epic.id, ticket.id)
        assert result is True

    def test_remove_ticket_doesnt_delete_ticket(self, test_repo: Repository) -> None:
        """Test removing ticket from epic doesn't delete the ticket itself."""
        org = create_test_org_with_workflow_via_repo(test_repo, "Test Org")
        project = create_test_project_via_repo(test_repo, org.id, "Test Project")
        epic = create_test_epic_via_repo(test_repo, org.id, "Test Epic")
        reporter = create_test_user_via_repo(test_repo, org.id, "reporter", role=UserRole.ADMIN)

        ticket_data = TicketData(title="Test Ticket", description="Test")
        ticket_command = TicketCreateCommand(ticket_data=ticket_data, project_id=project.id)
        ticket = test_repo.tickets.create(ticket_command, reporter.id)

        # Add and remove ticket from epic
        test_repo.epics.add_ticket_to_epic(epic.id, ticket.id)
        test_repo.epics.remove_ticket_from_epic(epic.id, ticket.id)

        # Verify ticket still exists
        existing_ticket = test_repo.tickets.get_by_id(ticket.id)
        assert existing_ticket is not None
        assert existing_ticket.id == ticket.id

    def test_get_tickets_in_epic_empty(self, test_repo: Repository) -> None:
        """Test getting tickets from empty epic returns empty list."""
        org = create_test_org_via_repo(test_repo, "Test Org")
        epic = create_test_epic_via_repo(test_repo, org.id, "Test Epic")

        tickets = test_repo.epics.get_tickets_in_epic(epic.id)
        assert tickets is not None
        assert len(tickets) == 0

    def test_get_tickets_in_nonexistent_epic(self, test_repo: Repository) -> None:
        """Test getting tickets from non-existent epic returns None."""
        tickets = test_repo.epics.get_tickets_in_epic("nonexistent-epic")
        assert tickets is None

    def test_add_multiple_tickets_to_epic(self, test_repo: Repository) -> None:
        """Test adding multiple tickets to an epic."""
        org = create_test_org_with_workflow_via_repo(test_repo, "Test Org")
        project = create_test_project_via_repo(test_repo, org.id, "Test Project")
        epic = create_test_epic_via_repo(test_repo, org.id, "Test Epic")
        reporter = create_test_user_via_repo(test_repo, org.id, "reporter", role=UserRole.ADMIN)

        # Create multiple tickets
        tickets = []
        for i in range(3):
            ticket_data = TicketData(title=f"Ticket {i}", description="Test")
            ticket_command = TicketCreateCommand(ticket_data=ticket_data, project_id=project.id)
            ticket = test_repo.tickets.create(ticket_command, reporter.id)
            tickets.append(ticket)
            test_repo.epics.add_ticket_to_epic(epic.id, ticket.id)

        # Verify all tickets are in epic
        epic_tickets = test_repo.epics.get_tickets_in_epic(epic.id)
        assert epic_tickets is not None
        assert len(epic_tickets) == 3
        assert {t.id for t in epic_tickets} == {t.id for t in tickets}

    def test_tickets_from_multiple_projects_in_epic(self, test_repo: Repository) -> None:
        """Test epic can contain tickets from multiple projects."""
        org = create_test_org_with_workflow_via_repo(test_repo, "Test Org")
        project1 = create_test_project_via_repo(test_repo, org.id, "Backend")
        project2 = create_test_project_via_repo(test_repo, org.id, "Frontend")
        epic = create_test_epic_via_repo(test_repo, org.id, "Feature Epic")
        reporter = create_test_user_via_repo(test_repo, org.id, "reporter", role=UserRole.ADMIN)

        # Create ticket in project1
        ticket1_data = TicketData(title="Backend Ticket", description="Test")
        ticket1_command = TicketCreateCommand(ticket_data=ticket1_data, project_id=project1.id)
        ticket1 = test_repo.tickets.create(ticket1_command, reporter.id)

        # Create ticket in project2
        ticket2_data = TicketData(title="Frontend Ticket", description="Test")
        ticket2_command = TicketCreateCommand(ticket_data=ticket2_data, project_id=project2.id)
        ticket2 = test_repo.tickets.create(ticket2_command, reporter.id)

        # Add both tickets to epic
        test_repo.epics.add_ticket_to_epic(epic.id, ticket1.id)
        test_repo.epics.add_ticket_to_epic(epic.id, ticket2.id)

        # Verify both tickets are in epic
        epic_tickets = test_repo.epics.get_tickets_in_epic(epic.id)
        assert epic_tickets is not None
        assert len(epic_tickets) == 2
        assert {t.id for t in epic_tickets} == {ticket1.id, ticket2.id}
        assert {t.project_id for t in epic_tickets} == {project1.id, project2.id}

    def test_delete_epic_removes_ticket_associations(self, test_repo: Repository) -> None:
        """Test deleting epic removes ticket associations but not tickets."""
        org = create_test_org_with_workflow_via_repo(test_repo, "Test Org")
        project = create_test_project_via_repo(test_repo, org.id, "Test Project")
        epic = create_test_epic_via_repo(test_repo, org.id, "Test Epic")
        reporter = create_test_user_via_repo(test_repo, org.id, "reporter", role=UserRole.ADMIN)

        ticket_data = TicketData(title="Test Ticket", description="Test")
        ticket_command = TicketCreateCommand(ticket_data=ticket_data, project_id=project.id)
        ticket = test_repo.tickets.create(ticket_command, reporter.id)

        # Add ticket to epic
        test_repo.epics.add_ticket_to_epic(epic.id, ticket.id)

        # Delete epic
        test_repo.epics.delete(epic.id)

        # Verify epic is deleted
        deleted_epic = test_repo.epics.get_by_id(epic.id)
        assert deleted_epic is None

        # Verify ticket still exists
        existing_ticket = test_repo.tickets.get_by_id(ticket.id)
        assert existing_ticket is not None
        assert existing_ticket.id == ticket.id
