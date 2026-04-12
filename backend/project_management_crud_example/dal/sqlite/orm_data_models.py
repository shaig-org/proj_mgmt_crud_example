"""SQLAlchemy ORM data models for the project management application.

This module contains all SQLAlchemy ORM models for database operations.
This is part of the Data Access Layer (DAL) and should only contain
database-specific models and logic.

The StubEntityORM model serves as a template/scaffolding for creating real ORM models.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import declarative_base

# SQLAlchemy Base for all ORM models
Base = declarative_base()


def generate_uuid() -> str:
    """Generate a UUID string for use as primary key."""
    return str(uuid.uuid4())


# SQLAlchemy ORM Models
class StubEntityORM(Base):
    """SQLAlchemy ORM model for stub entities - template for creating real ORM models."""

    __tablename__ = "stub_entities"

    # Using String for UUID storage in SQLite (36 characters for standard UUID format)
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)

    # Timestamps for audit tracking
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<StubEntity(id='{self.id}', name='{self.name}')>"


class OrganizationORM(Base):
    """SQLAlchemy ORM model for organizations."""

    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(String(1000), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Organization(id='{self.id}', name='{self.name}')>"


class ProjectORM(Base):
    """SQLAlchemy ORM model for projects."""

    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    workflow_id = Column(String(36), ForeignKey("workflows.id"), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)
    archived_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Project(id='{self.id}', name='{self.name}', organization_id='{self.organization_id}')>"


class EpicORM(Base):
    """SQLAlchemy ORM model for epics."""

    __tablename__ = "epics"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Epic(id='{self.id}', name='{self.name}', organization_id='{self.organization_id}')>"


class WorkflowORM(Base):
    """SQLAlchemy ORM model for workflows."""

    __tablename__ = "workflows"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    statuses = Column(Text, nullable=False)  # JSON array of status strings
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    is_default = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Workflow(id='{self.id}', name='{self.name}', organization_id='{self.organization_id}', is_default={self.is_default})>"


class TicketORM(Base):
    """SQLAlchemy ORM model for tickets."""

    __tablename__ = "tickets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(500), nullable=False)
    description = Column(String(2000), nullable=True)
    status = Column(String(50), nullable=False, index=True)  # TODO, IN_PROGRESS, DONE
    priority = Column(String(50), nullable=True)  # LOW, MEDIUM, HIGH, CRITICAL
    assignee_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    reporter_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Ticket(id='{self.id}', title='{self.title}', status='{self.status}', project_id='{self.project_id}')>"


class EpicTicketORM(Base):
    """SQLAlchemy ORM model for epic-ticket associations (many-to-many)."""

    __tablename__ = "epic_tickets"

    epic_id = Column(String(36), ForeignKey("epics.id"), primary_key=True)
    ticket_id = Column(String(36), ForeignKey("tickets.id"), primary_key=True)

    # Timestamp for when the association was created
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self) -> str:
        return f"<EpicTicket(epic_id='{self.epic_id}', ticket_id='{self.ticket_id}')>"


class UserORM(Base):
    """SQLAlchemy ORM model for users."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    organization_id = Column(String(36), nullable=True)  # None for Super Admin
    role = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Composite unique constraint: email must be unique within organization
    # Note: Super Admin (organization_id=None) emails are not constrained by this
    __table_args__ = (Index("idx_users_org_email", "organization_id", "email", unique=True),)

    def __repr__(self) -> str:
        return f"<User(id='{self.id}', username='{self.username}', role='{self.role}')>"


class ActivityLogORM(Base):
    """SQLAlchemy ORM model for activity logs."""

    __tablename__ = "activity_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(36), nullable=False)
    action = Column(String(50), nullable=False)
    actor_id = Column(String(36), nullable=False)
    organization_id = Column(String(36), nullable=False, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Using Text for JSON storage (SQLite doesn't have native JSON type)
    changes = Column(Text, nullable=False)
    extra_metadata = Column(Text, nullable=True)

    # Define indexes for common query patterns
    __table_args__ = (
        Index("idx_activity_logs_entity", "entity_type", "entity_id"),
        Index("idx_activity_logs_actor", "actor_id"),
    )

    def __repr__(self) -> str:
        return f"<ActivityLog(id='{self.id}', entity_type='{self.entity_type}', entity_id='{self.entity_id}', action='{self.action}')>"


class CommentORM(Base):
    """SQLAlchemy ORM model for comments."""

    __tablename__ = "comments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    ticket_id = Column(String(36), ForeignKey("tickets.id"), nullable=False, index=True)
    author_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    content = Column(String(5000), nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Comment(id='{self.id}', ticket_id='{self.ticket_id}', author_id='{self.author_id}')>"
