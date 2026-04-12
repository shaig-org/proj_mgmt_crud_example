"""Tests for ORM to domain model converters."""

from sqlalchemy.orm import Session

from project_management_crud_example.dal.sqlite.converters import (
    orm_ticket_to_domain_ticket,
    orm_user_to_domain_user,
)
from project_management_crud_example.dal.sqlite.orm_data_models import TicketORM, UserORM
from project_management_crud_example.domain_models import TicketPriority, TicketStatus, UserRole
from tests.conftest import test_db, test_session  # noqa: F401


class TestUserConverter:
    """Tests for ORM to domain User converter."""

    def test_orm_to_domain_user_excludes_password_hash(self, test_session: Session) -> None:
        """Test that domain User doesn't include password_hash."""
        # Use fake hash for converter tests - no need for real password hashing
        password_hash = "fake_hash_for_converter_test"

        user_orm = UserORM(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            password_hash=password_hash,
            organization_id="org-123",
            role=UserRole.ADMIN.value,
        )
        test_session.add(user_orm)
        test_session.commit()
        test_session.refresh(user_orm)

        # Convert to domain User
        domain_user = orm_user_to_domain_user(user_orm)

        # Verify conversion
        assert domain_user.id == user_orm.id
        assert domain_user.username == "testuser"
        assert domain_user.email == "test@example.com"
        assert domain_user.full_name == "Test User"
        assert domain_user.organization_id == "org-123"
        assert domain_user.role == UserRole.ADMIN
        assert domain_user.is_active is True

        # Verify password_hash is NOT in domain User
        assert not hasattr(domain_user, "password_hash")

    def test_orm_to_domain_user_with_null_organization(self, test_session: Session) -> None:
        """Test conversion for Super Admin with no organization."""
        # Use fake hash for converter tests - no need for real password hashing
        password_hash = "fake_hash_for_converter_test"

        user_orm = UserORM(
            username="superadmin",
            email="admin@example.com",
            full_name="Super Admin",
            password_hash=password_hash,
            organization_id=None,
            role=UserRole.SUPER_ADMIN.value,
        )
        test_session.add(user_orm)
        test_session.commit()
        test_session.refresh(user_orm)

        domain_user = orm_user_to_domain_user(user_orm)

        assert domain_user.organization_id is None
        assert domain_user.role == UserRole.SUPER_ADMIN


class TestTicketConverter:
    """Tests for ORM to domain Ticket converter."""

    def test_orm_to_domain_ticket_with_all_fields(self, test_session: Session) -> None:
        """Test converting ticket ORM with all fields to domain model."""
        ticket_orm = TicketORM(
            title="Test Ticket",
            description="Test description",
            status=TicketStatus.IN_PROGRESS.value,
            priority=TicketPriority.HIGH.value,
            assignee_id="user-123",
            reporter_id="user-456",
            project_id="project-789",
        )
        test_session.add(ticket_orm)
        test_session.commit()
        test_session.refresh(ticket_orm)

        # Convert to domain Ticket
        domain_ticket = orm_ticket_to_domain_ticket(ticket_orm)

        # Verify conversion
        assert domain_ticket.id == ticket_orm.id
        assert domain_ticket.title == "Test Ticket"
        assert domain_ticket.description == "Test description"
        assert domain_ticket.status == TicketStatus.IN_PROGRESS
        assert domain_ticket.priority == TicketPriority.HIGH
        assert domain_ticket.assignee_id == "user-123"
        assert domain_ticket.reporter_id == "user-456"
        assert domain_ticket.project_id == "project-789"
        assert domain_ticket.created_at == ticket_orm.created_at
        assert domain_ticket.updated_at == ticket_orm.updated_at

    def test_orm_to_domain_ticket_with_null_optional_fields(self, test_session: Session) -> None:
        """Test converting ticket ORM with null optional fields."""
        ticket_orm = TicketORM(
            title="Minimal Ticket",
            description=None,
            status=TicketStatus.TODO.value,
            priority=None,
            assignee_id=None,
            reporter_id="user-456",
            project_id="project-789",
        )
        test_session.add(ticket_orm)
        test_session.commit()
        test_session.refresh(ticket_orm)

        domain_ticket = orm_ticket_to_domain_ticket(ticket_orm)

        assert domain_ticket.title == "Minimal Ticket"
        assert domain_ticket.description is None
        assert domain_ticket.priority is None
        assert domain_ticket.assignee_id is None
        assert domain_ticket.status == TicketStatus.TODO
        assert domain_ticket.reporter_id == "user-456"


class TestActivityLogConverters:
    """Test activity log ORM to domain model converters."""

    def test_orm_activity_log_to_domain_activity_log(self, test_session: Session) -> None:
        """Test converting ActivityLogORM to domain ActivityLog."""
        import json

        from project_management_crud_example.dal.sqlite.converters import orm_activity_log_to_domain_activity_log
        from project_management_crud_example.dal.sqlite.orm_data_models import ActivityLogORM
        from project_management_crud_example.domain_models import ActionType

        changes = {"status": {"old_value": "TODO", "new_value": "DONE"}}
        metadata = {"ip": "127.0.0.1"}

        activity_log_orm = ActivityLogORM(
            entity_type="ticket",
            entity_id="ticket-123",
            action=ActionType.TICKET_STATUS_CHANGED.value,
            actor_id="user-456",
            organization_id="org-789",
            changes=json.dumps(changes),
            extra_metadata=json.dumps(metadata),
        )
        test_session.add(activity_log_orm)
        test_session.commit()
        test_session.refresh(activity_log_orm)

        domain_log = orm_activity_log_to_domain_activity_log(activity_log_orm)

        assert domain_log.id == str(activity_log_orm.id)
        assert domain_log.entity_type == "ticket"
        assert domain_log.entity_id == "ticket-123"
        assert domain_log.action == ActionType.TICKET_STATUS_CHANGED
        assert domain_log.actor_id == "user-456"
        assert domain_log.organization_id == "org-789"
        assert domain_log.changes == changes
        assert domain_log.metadata == metadata

    def test_orm_activity_log_to_domain_with_null_metadata(self, test_session: Session) -> None:
        """Test converting activity log ORM with null metadata."""
        import json

        from project_management_crud_example.dal.sqlite.converters import orm_activity_log_to_domain_activity_log
        from project_management_crud_example.dal.sqlite.orm_data_models import ActivityLogORM
        from project_management_crud_example.domain_models import ActionType

        activity_log_orm = ActivityLogORM(
            entity_type="project",
            entity_id="proj-1",
            action=ActionType.PROJECT_CREATED.value,
            actor_id="user-1",
            organization_id="org-1",
            changes=json.dumps({"created": {}}),
            extra_metadata=None,
        )
        test_session.add(activity_log_orm)
        test_session.commit()
        test_session.refresh(activity_log_orm)

        domain_log = orm_activity_log_to_domain_activity_log(activity_log_orm)

        assert domain_log.metadata is None

    def test_orm_activity_logs_list_conversion(self, test_session: Session) -> None:
        """Test converting list of ActivityLogORM to domain ActivityLogs."""
        import json

        from project_management_crud_example.dal.sqlite.converters import orm_activity_logs_to_domain_activity_logs
        from project_management_crud_example.dal.sqlite.orm_data_models import ActivityLogORM
        from project_management_crud_example.domain_models import ActionType

        log1 = ActivityLogORM(
            entity_type="ticket",
            entity_id="ticket-1",
            action=ActionType.TICKET_CREATED.value,
            actor_id="user-1",
            organization_id="org-1",
            changes=json.dumps({"created": {}}),
        )
        log2 = ActivityLogORM(
            entity_type="project",
            entity_id="project-1",
            action=ActionType.PROJECT_CREATED.value,
            actor_id="user-1",
            organization_id="org-1",
            changes=json.dumps({"created": {}}),
        )
        test_session.add(log1)
        test_session.add(log2)
        test_session.commit()

        domain_logs = orm_activity_logs_to_domain_activity_logs([log1, log2])

        assert len(domain_logs) == 2
        assert domain_logs[0].entity_type == "ticket"
        assert domain_logs[1].entity_type == "project"
