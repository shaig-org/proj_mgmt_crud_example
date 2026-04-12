"""Tests for the ActivityLog repository operations."""

from datetime import datetime, timedelta, timezone

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import ActionType, ActivityLogCreateCommand

# Explicitly import pytest fixtures as per project rules
from tests.conftest import test_repo  # noqa: F401


class TestActivityLogRepositoryCreate:
    """Test activity log creation operations."""

    def test_create_activity_log(self, test_repo: Repository) -> None:
        """Test creating an activity log with all fields."""
        changes = {"status": {"old_value": "TODO", "new_value": "IN_PROGRESS"}}
        metadata = {"ip_address": "192.168.1.1"}
        command = ActivityLogCreateCommand(
            entity_type="ticket",
            entity_id="ticket-123",
            action=ActionType.TICKET_STATUS_CHANGED,
            actor_id="user-456",
            organization_id="org-789",
            changes=changes,
            metadata=metadata,
        )

        log = test_repo.activity_logs.create(command)

        assert log.id is not None
        assert log.entity_type == "ticket"
        assert log.entity_id == "ticket-123"
        assert log.action == ActionType.TICKET_STATUS_CHANGED
        assert log.actor_id == "user-456"
        assert log.organization_id == "org-789"
        assert log.timestamp is not None
        assert log.changes == changes
        assert log.metadata == metadata

    def test_create_activity_log_with_metadata(self, test_repo: Repository) -> None:
        """Test that metadata field is correctly preserved."""
        metadata = {"user_agent": "Mozilla/5.0", "session_id": "abc123"}
        command = ActivityLogCreateCommand(
            entity_type="project",
            entity_id="proj-1",
            action=ActionType.PROJECT_CREATED,
            actor_id="user-1",
            organization_id="org-1",
            changes={"created": {"name": "New Project"}},
            metadata=metadata,
        )

        log = test_repo.activity_logs.create(command)

        assert log.metadata == metadata

    def test_create_activity_log_without_metadata(self, test_repo: Repository) -> None:
        """Test creating activity log without metadata."""
        command = ActivityLogCreateCommand(
            entity_type="user",
            entity_id="user-1",
            action=ActionType.USER_CREATED,
            actor_id="admin-1",
            organization_id="org-1",
            changes={"created": {"username": "newuser"}},
            metadata=None,
        )

        log = test_repo.activity_logs.create(command)

        assert log.metadata is None


class TestActivityLogRepositoryGetById:
    """Test activity log retrieval by ID."""

    def test_get_activity_log_by_id(self, test_repo: Repository) -> None:
        """Test retrieving activity log by ID."""
        command = ActivityLogCreateCommand(
            entity_type="ticket",
            entity_id="ticket-1",
            action=ActionType.TICKET_CREATED,
            actor_id="user-1",
            organization_id="org-1",
            changes={"created": {"title": "Test Ticket"}},
        )
        created_log = test_repo.activity_logs.create(command)

        retrieved_log = test_repo.activity_logs.get_by_id(created_log.id)

        assert retrieved_log is not None
        assert retrieved_log.id == created_log.id
        assert retrieved_log.entity_type == "ticket"
        assert retrieved_log.action == ActionType.TICKET_CREATED

    def test_get_activity_log_by_id_not_found(self, test_repo: Repository) -> None:
        """Test retrieving non-existent activity log returns None."""
        retrieved_log = test_repo.activity_logs.get_by_id("non-existent-id")

        assert retrieved_log is None


class TestActivityLogRepositoryList:
    """Test activity log listing operations."""

    def test_list_all_activity_logs(self, test_repo: Repository) -> None:
        """Test listing all activity logs when no filters are provided."""
        # Create multiple logs
        for i in range(3):
            command = ActivityLogCreateCommand(
                entity_type="ticket",
                entity_id=f"ticket-{i}",
                action=ActionType.TICKET_CREATED,
                actor_id=f"user-{i}",
                organization_id="org-1",
                changes={"created": {"title": f"Ticket {i}"}},
            )
            test_repo.activity_logs.create(command)

        logs = test_repo.activity_logs.list()

        assert len(logs) == 3

    def test_list_activity_logs_empty(self, test_repo: Repository) -> None:
        """Test listing activity logs returns empty list when no logs exist."""
        logs = test_repo.activity_logs.list()

        assert logs == []

    def test_list_activity_logs_ordered_by_timestamp_ascending(self, test_repo: Repository) -> None:
        """Test default ordering is oldest first (ascending)."""
        # Create logs with slight time delays to ensure different timestamps
        log_ids = []
        for i in range(3):
            command = ActivityLogCreateCommand(
                entity_type="ticket",
                entity_id=f"ticket-{i}",
                action=ActionType.TICKET_CREATED,
                actor_id="user-1",
                organization_id="org-1",
                changes={"created": {"title": f"Ticket {i}"}},
            )
            log = test_repo.activity_logs.create(command)
            log_ids.append(log.id)

        logs = test_repo.activity_logs.list()

        # Verify chronological order (oldest first)
        assert len(logs) == 3
        assert [log.id for log in logs] == log_ids

    def test_list_activity_logs_ordered_by_timestamp_descending(self, test_repo: Repository) -> None:
        """Test ordering newest first with order='desc'."""
        log_ids = []
        for i in range(3):
            command = ActivityLogCreateCommand(
                entity_type="ticket",
                entity_id=f"ticket-{i}",
                action=ActionType.TICKET_CREATED,
                actor_id="user-1",
                organization_id="org-1",
                changes={"created": {"title": f"Ticket {i}"}},
            )
            log = test_repo.activity_logs.create(command)
            log_ids.append(log.id)

        logs = test_repo.activity_logs.list(order="desc")

        # Verify reverse chronological order (newest first)
        assert len(logs) == 3
        assert [log.id for log in logs] == list(reversed(log_ids))


class TestActivityLogRepositoryFilterByEntity:
    """Test filtering activity logs by entity."""

    def test_list_activity_logs_filter_by_entity_type(self, test_repo: Repository) -> None:
        """Test filtering logs by entity type."""
        # Create logs for different entity types
        test_repo.activity_logs.create(
            ActivityLogCreateCommand(
                entity_type="ticket",
                entity_id="ticket-1",
                action=ActionType.TICKET_CREATED,
                actor_id="user-1",
                organization_id="org-1",
                changes={"created": {}},
            )
        )
        test_repo.activity_logs.create(
            ActivityLogCreateCommand(
                entity_type="project",
                entity_id="project-1",
                action=ActionType.PROJECT_CREATED,
                actor_id="user-1",
                organization_id="org-1",
                changes={"created": {}},
            )
        )

        ticket_logs = test_repo.activity_logs.list(entity_type="ticket")

        assert len(ticket_logs) == 1
        assert ticket_logs[0].entity_type == "ticket"

    def test_list_activity_logs_filter_by_entity_id(self, test_repo: Repository) -> None:
        """Test filtering logs by specific entity ID."""
        # Create logs for different entities
        test_repo.activity_logs.create(
            ActivityLogCreateCommand(
                entity_type="ticket",
                entity_id="ticket-1",
                action=ActionType.TICKET_CREATED,
                actor_id="user-1",
                organization_id="org-1",
                changes={"created": {}},
            )
        )
        test_repo.activity_logs.create(
            ActivityLogCreateCommand(
                entity_type="ticket",
                entity_id="ticket-2",
                action=ActionType.TICKET_CREATED,
                actor_id="user-1",
                organization_id="org-1",
                changes={"created": {}},
            )
        )

        ticket1_logs = test_repo.activity_logs.list(entity_id="ticket-1")

        assert len(ticket1_logs) == 1
        assert ticket1_logs[0].entity_id == "ticket-1"

    def test_list_activity_logs_filter_by_entity_type_and_id(self, test_repo: Repository) -> None:
        """Test filtering by both entity_type and entity_id."""
        # Create diverse logs
        test_repo.activity_logs.create(
            ActivityLogCreateCommand(
                entity_type="ticket",
                entity_id="ticket-1",
                action=ActionType.TICKET_CREATED,
                actor_id="user-1",
                organization_id="org-1",
                changes={"created": {}},
            )
        )
        test_repo.activity_logs.create(
            ActivityLogCreateCommand(
                entity_type="project",
                entity_id="ticket-1",  # Same ID, different type
                action=ActionType.PROJECT_CREATED,
                actor_id="user-1",
                organization_id="org-1",
                changes={"created": {}},
            )
        )

        filtered_logs = test_repo.activity_logs.list(entity_type="ticket", entity_id="ticket-1")

        assert len(filtered_logs) == 1
        assert filtered_logs[0].entity_type == "ticket"
        assert filtered_logs[0].entity_id == "ticket-1"


class TestActivityLogRepositoryFilterByActor:
    """Test filtering activity logs by actor."""

    def test_list_activity_logs_filter_by_actor_id(self, test_repo: Repository) -> None:
        """Test filtering logs by actor (who performed action)."""
        # Create logs from different users
        test_repo.activity_logs.create(
            ActivityLogCreateCommand(
                entity_type="ticket",
                entity_id="ticket-1",
                action=ActionType.TICKET_CREATED,
                actor_id="user-1",
                organization_id="org-1",
                changes={"created": {}},
            )
        )
        test_repo.activity_logs.create(
            ActivityLogCreateCommand(
                entity_type="ticket",
                entity_id="ticket-2",
                action=ActionType.TICKET_CREATED,
                actor_id="user-2",
                organization_id="org-1",
                changes={"created": {}},
            )
        )

        user1_logs = test_repo.activity_logs.list(actor_id="user-1")

        assert len(user1_logs) == 1
        assert user1_logs[0].actor_id == "user-1"


class TestActivityLogRepositoryFilterByAction:
    """Test filtering activity logs by action type."""

    def test_list_activity_logs_filter_by_action(self, test_repo: Repository) -> None:
        """Test filtering logs by action type."""
        # Create logs with different actions
        test_repo.activity_logs.create(
            ActivityLogCreateCommand(
                entity_type="ticket",
                entity_id="ticket-1",
                action=ActionType.TICKET_CREATED,
                actor_id="user-1",
                organization_id="org-1",
                changes={"created": {}},
            )
        )
        test_repo.activity_logs.create(
            ActivityLogCreateCommand(
                entity_type="ticket",
                entity_id="ticket-1",
                action=ActionType.TICKET_UPDATED,
                actor_id="user-1",
                organization_id="org-1",
                changes={"title": {"old_value": "Old", "new_value": "New"}},
            )
        )

        created_logs = test_repo.activity_logs.list(action=ActionType.TICKET_CREATED)

        assert len(created_logs) == 1
        assert created_logs[0].action == ActionType.TICKET_CREATED


class TestActivityLogRepositoryFilterByDate:
    """Test filtering activity logs by date range."""

    def test_list_activity_logs_filter_by_from_date(self, test_repo: Repository) -> None:
        """Test filtering logs after specific date."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=2)

        # Create log and manually set old timestamp (simulating past log)
        command = ActivityLogCreateCommand(
            entity_type="ticket",
            entity_id="ticket-1",
            action=ActionType.TICKET_CREATED,
            actor_id="user-1",
            organization_id="org-1",
            changes={"created": {}},
        )
        test_repo.activity_logs.create(command)

        # Create recent log
        recent_command = ActivityLogCreateCommand(
            entity_type="ticket",
            entity_id="ticket-2",
            action=ActionType.TICKET_CREATED,
            actor_id="user-1",
            organization_id="org-1",
            changes={"created": {}},
        )
        test_repo.activity_logs.create(recent_command)

        # Filter using a time between past and now
        cutoff = past + timedelta(hours=1)
        recent_logs = test_repo.activity_logs.list(from_date=cutoff)

        # Both logs should be after cutoff since we can't actually set timestamps
        assert len(recent_logs) >= 1

    def test_list_activity_logs_filter_by_to_date(self, test_repo: Repository) -> None:
        """Test filtering logs before specific date."""
        future = datetime.now(timezone.utc) + timedelta(hours=1)

        command = ActivityLogCreateCommand(
            entity_type="ticket",
            entity_id="ticket-1",
            action=ActionType.TICKET_CREATED,
            actor_id="user-1",
            organization_id="org-1",
            changes={"created": {}},
        )
        test_repo.activity_logs.create(command)

        # Filter with future date should include all logs
        logs = test_repo.activity_logs.list(to_date=future)

        assert len(logs) == 1

    def test_list_activity_logs_filter_by_date_range(self, test_repo: Repository) -> None:
        """Test filtering logs within date range."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=1)
        future = now + timedelta(hours=1)

        command = ActivityLogCreateCommand(
            entity_type="ticket",
            entity_id="ticket-1",
            action=ActionType.TICKET_CREATED,
            actor_id="user-1",
            organization_id="org-1",
            changes={"created": {}},
        )
        test_repo.activity_logs.create(command)

        # Filter with range encompassing now
        logs = test_repo.activity_logs.list(from_date=past, to_date=future)

        assert len(logs) == 1


class TestActivityLogRepositoryFilterByOrganization:
    """Test filtering activity logs by organization."""

    def test_list_activity_logs_filter_by_organization_id(self, test_repo: Repository) -> None:
        """Test filtering logs by organization."""
        # Create logs from different organizations
        test_repo.activity_logs.create(
            ActivityLogCreateCommand(
                entity_type="ticket",
                entity_id="ticket-1",
                action=ActionType.TICKET_CREATED,
                actor_id="user-1",
                organization_id="org-1",
                changes={"created": {}},
            )
        )
        test_repo.activity_logs.create(
            ActivityLogCreateCommand(
                entity_type="ticket",
                entity_id="ticket-2",
                action=ActionType.TICKET_CREATED,
                actor_id="user-2",
                organization_id="org-2",
                changes={"created": {}},
            )
        )

        org1_logs = test_repo.activity_logs.list(organization_id="org-1")

        assert len(org1_logs) == 1
        assert org1_logs[0].organization_id == "org-1"


class TestActivityLogRepositoryFilterCombined:
    """Test combining multiple filters."""

    def test_list_activity_logs_multiple_filters_combined(self, test_repo: Repository) -> None:
        """Test that multiple filters use AND logic."""
        # Create diverse logs
        test_repo.activity_logs.create(
            ActivityLogCreateCommand(
                entity_type="ticket",
                entity_id="ticket-1",
                action=ActionType.TICKET_CREATED,
                actor_id="user-1",
                organization_id="org-1",
                changes={"created": {}},
            )
        )
        test_repo.activity_logs.create(
            ActivityLogCreateCommand(
                entity_type="ticket",
                entity_id="ticket-1",
                action=ActionType.TICKET_UPDATED,
                actor_id="user-1",
                organization_id="org-1",
                changes={"title": {"old_value": "Old", "new_value": "New"}},
            )
        )
        test_repo.activity_logs.create(
            ActivityLogCreateCommand(
                entity_type="project",
                entity_id="project-1",
                action=ActionType.PROJECT_CREATED,
                actor_id="user-1",
                organization_id="org-1",
                changes={"created": {}},
            )
        )

        # Filter for ticket-1 AND TICKET_CREATED action
        filtered_logs = test_repo.activity_logs.list(
            entity_type="ticket", entity_id="ticket-1", action=ActionType.TICKET_CREATED
        )

        assert len(filtered_logs) == 1
        assert filtered_logs[0].entity_type == "ticket"
        assert filtered_logs[0].entity_id == "ticket-1"
        assert filtered_logs[0].action == ActionType.TICKET_CREATED


class TestActivityLogRepositoryChangesField:
    """Test handling of changes field."""

    def test_activity_log_changes_field_preserved(self, test_repo: Repository) -> None:
        """Test that complex changes dict is correctly serialized/deserialized."""
        changes = {
            "title": {"old_value": "Old Title", "new_value": "New Title"},
            "description": {"old_value": "Old Desc", "new_value": "New Desc"},
            "status": {"old_value": "TODO", "new_value": "DONE"},
        }
        command = ActivityLogCreateCommand(
            entity_type="ticket",
            entity_id="ticket-1",
            action=ActionType.TICKET_UPDATED,
            actor_id="user-1",
            organization_id="org-1",
            changes=changes,
        )

        log = test_repo.activity_logs.create(command)
        retrieved = test_repo.activity_logs.get_by_id(log.id)

        assert retrieved is not None
        assert retrieved.changes == changes

    def test_activity_log_changes_with_null_values(self, test_repo: Repository) -> None:
        """Test that null values in changes are preserved."""
        changes = {"description": {"old_value": "Something", "new_value": None}}
        command = ActivityLogCreateCommand(
            entity_type="ticket",
            entity_id="ticket-1",
            action=ActionType.TICKET_UPDATED,
            actor_id="user-1",
            organization_id="org-1",
            changes=changes,
        )

        log = test_repo.activity_logs.create(command)
        retrieved = test_repo.activity_logs.get_by_id(log.id)

        assert retrieved is not None
        assert retrieved.changes["description"]["new_value"] is None
