"""Domain business data models for the project management application.

This module contains Pydantic models for representing the domain, API data validation and serialization.

The StubEntity models serve as a template/scaffolding for creating real domain entities.
"""

import re
from datetime import datetime
from enum import Enum
from typing import ClassVar, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class AuditableEntity(BaseModel):
    """Base class for entities that support activity logging.

    All entities that need activity logging should inherit from this class.
    Subclasses must define _entity_type as a ClassVar and must have an id field.
    """

    # Subclasses MUST override this with their entity type
    _entity_type: ClassVar[str]


class AuditableCommand(BaseModel):
    """Base class for all commands that create activity logs.

    All commands that should be logged must inherit from this class.
    Subclasses must define _entity_type and _action_type as ClassVars.
    """

    _entity_type: ClassVar[str]
    _action_type: ClassVar["ActionType"]


class ActionType(str, Enum):
    """Action types for activity logging."""

    # Ticket actions
    TICKET_CREATED = "ticket_created"
    TICKET_UPDATED = "ticket_updated"
    TICKET_STATUS_CHANGED = "ticket_status_changed"
    TICKET_ASSIGNED = "ticket_assigned"
    TICKET_MOVED = "ticket_moved"
    TICKET_DELETED = "ticket_deleted"

    # Project actions
    PROJECT_CREATED = "project_created"
    PROJECT_UPDATED = "project_updated"
    PROJECT_ARCHIVED = "project_archived"
    PROJECT_UNARCHIVED = "project_unarchived"
    PROJECT_DELETED = "project_deleted"

    # User actions
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_ROLE_CHANGED = "user_role_changed"
    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"
    USER_PASSWORD_CHANGED = "user_password_changed"
    USER_DELETED = "user_deleted"

    # Epic actions
    EPIC_CREATED = "epic_created"
    EPIC_UPDATED = "epic_updated"
    EPIC_DELETED = "epic_deleted"
    EPIC_TICKET_ADDED = "epic_ticket_added"
    EPIC_TICKET_REMOVED = "epic_ticket_removed"

    # Organization actions
    ORGANIZATION_CREATED = "organization_created"
    ORGANIZATION_UPDATED = "organization_updated"

    # Comment actions
    COMMENT_CREATED = "comment_created"
    COMMENT_UPDATED = "comment_updated"
    COMMENT_DELETED = "comment_deleted"

    # Workflow actions
    WORKFLOW_CREATED = "workflow_created"
    WORKFLOW_UPDATED = "workflow_updated"
    WORKFLOW_DELETED = "workflow_deleted"


class StubEntityData(BaseModel):
    """Base data structure for stub entity - template for creating real entities."""

    name: str = Field(..., min_length=1, max_length=255, description="Stub entity name")
    description: Optional[str] = Field(None, max_length=1000, description="Stub entity description")


class StubEntity(StubEntityData):
    """Complete stub entity with metadata - template for creating real entities."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Stub entity ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class StubEntityCreateCommand(BaseModel):
    """Command model for creating a new stub entity - template for real create commands."""

    stub_entity_data: StubEntityData


class StubEntityUpdateCommand(BaseModel):
    """Command model for updating an existing stub entity - template for real update commands."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Stub entity name")
    description: Optional[str] = Field(None, max_length=1000, description="Stub entity description")


# Organization Models


class OrganizationData(BaseModel):
    """Base organization data structure."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Organization name (must be unique)",
    )
    description: Optional[str] = Field(None, max_length=1000, description="Organization description")


class Organization(OrganizationData):
    """Complete organization model with metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Organization ID")
    is_active: bool = Field(True, description="Whether organization is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class OrganizationCreateCommand(AuditableCommand):
    """Command model for creating a new organization."""

    _entity_type: ClassVar[str] = "organization"
    _action_type: ClassVar[ActionType] = ActionType.ORGANIZATION_CREATED

    organization_data: OrganizationData


class OrganizationUpdateCommand(AuditableCommand):
    """Command model for updating an existing organization."""

    _entity_type: ClassVar[str] = "organization"
    _action_type: ClassVar[ActionType] = ActionType.ORGANIZATION_UPDATED

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Organization name")
    description: Optional[str] = Field(None, max_length=1000, description="Organization description")
    is_active: Optional[bool] = Field(None, description="Whether organization is active")


# Project Models


class ProjectData(BaseModel):
    """Base project data structure."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Project name",
    )
    description: Optional[str] = Field(None, max_length=1000, description="Project description")
    workflow_id: Optional[str] = Field(
        None, description="Workflow ID for this project (defaults to org's default workflow)"
    )


class Project(ProjectData, AuditableEntity):
    """Complete project model with metadata."""

    model_config = ConfigDict(from_attributes=True)

    _entity_type: ClassVar[str] = "project"

    id: str = Field(..., description="Project ID")
    organization_id: str = Field(..., description="Organization ID this project belongs to")
    workflow_id: str = Field(..., description="Workflow ID for this project")  # Override to make required
    is_active: bool = Field(True, description="Whether project is active")
    is_archived: bool = Field(False, description="Whether project is archived")
    archived_at: Optional[datetime] = Field(None, description="Timestamp when project was archived")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class ProjectCreateCommand(AuditableCommand):
    """Command model for creating a new project."""

    _entity_type: ClassVar[str] = "project"
    _action_type: ClassVar[ActionType] = ActionType.PROJECT_CREATED

    project_data: ProjectData
    organization_id: str = Field(..., description="Organization ID this project belongs to")


class ProjectUpdateCommand(AuditableCommand):
    """Command model for updating an existing project."""

    _entity_type: ClassVar[str] = "project"
    _action_type: ClassVar[ActionType] = ActionType.PROJECT_UPDATED

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, max_length=1000, description="Project description")
    workflow_id: Optional[str] = Field(None, description="Workflow ID for this project")
    is_active: Optional[bool] = Field(None, description="Whether project is active")


class ProjectDeleteCommand(AuditableCommand):
    """Command model for deleting a project."""

    _entity_type: ClassVar[str] = "project"
    _action_type: ClassVar[ActionType] = ActionType.PROJECT_DELETED

    project_id: str = Field(..., description="ID of project to delete")


class ProjectArchiveCommand(AuditableCommand):
    """Command model for archiving a project."""

    _entity_type: ClassVar[str] = "project"
    _action_type: ClassVar[ActionType] = ActionType.PROJECT_ARCHIVED

    project_id: str = Field(..., description="ID of project to archive")


class ProjectUnarchiveCommand(AuditableCommand):
    """Command model for unarchiving a project."""

    _entity_type: ClassVar[str] = "project"
    _action_type: ClassVar[ActionType] = ActionType.PROJECT_UNARCHIVED

    project_id: str = Field(..., description="ID of project to unarchive")


# Epic Models


class EpicData(BaseModel):
    """Base epic data structure."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Epic name",
    )
    description: Optional[str] = Field(None, max_length=1000, description="Epic description")


class Epic(EpicData):
    """Complete epic model with metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Epic ID")
    organization_id: str = Field(..., description="Organization ID this epic belongs to")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class EpicCreateCommand(AuditableCommand):
    """Command model for creating a new epic."""

    _entity_type: ClassVar[str] = "epic"
    _action_type: ClassVar[ActionType] = ActionType.EPIC_CREATED

    epic_data: EpicData
    organization_id: str = Field(..., description="Organization ID this epic belongs to")


class EpicUpdateCommand(AuditableCommand):
    """Command model for updating an existing epic."""

    _entity_type: ClassVar[str] = "epic"
    _action_type: ClassVar[ActionType] = ActionType.EPIC_UPDATED

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Epic name")
    description: Optional[str] = Field(None, max_length=1000, description="Epic description")


class EpicDeleteCommand(AuditableCommand):
    """Command model for deleting an epic."""

    _entity_type: ClassVar[str] = "epic"
    _action_type: ClassVar[ActionType] = ActionType.EPIC_DELETED

    epic_id: str = Field(..., description="ID of epic to delete")


class EpicTicketAddCommand(AuditableCommand):
    """Command model for adding a ticket to an epic."""

    _entity_type: ClassVar[str] = "epic"
    _action_type: ClassVar[ActionType] = ActionType.EPIC_TICKET_ADDED

    epic_id: str = Field(..., description="ID of epic")
    ticket_id: str = Field(..., description="ID of ticket to add")


class EpicTicketRemoveCommand(AuditableCommand):
    """Command model for removing a ticket from an epic."""

    _entity_type: ClassVar[str] = "epic"
    _action_type: ClassVar[ActionType] = ActionType.EPIC_TICKET_REMOVED

    epic_id: str = Field(..., description="ID of epic")
    ticket_id: str = Field(..., description="ID of ticket to remove")


# Workflow Models


class WorkflowData(BaseModel):
    """Base workflow data structure."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Workflow name",
    )
    description: Optional[str] = Field(None, max_length=1000, description="Workflow description")
    statuses: List[str] = Field(
        ...,
        min_length=1,
        description="List of valid status names for this workflow (non-empty)",
    )

    @field_validator("statuses")
    @classmethod
    def validate_statuses(cls, v: List[str]) -> List[str]:
        """Validate workflow statuses.

        Rules:
        - Must be non-empty list
        - Each status must match pattern ^[A-Z0-9_-]+$
        - No duplicate statuses allowed
        """
        if not v:
            raise ValueError("Statuses list cannot be empty")

        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValueError("Duplicate status names are not allowed")

        # Validate each status name format
        status_pattern = re.compile(r"^[A-Z0-9_-]+$")
        for status in v:
            if not status_pattern.match(status):
                raise ValueError(
                    f"Invalid status name '{status}'. Status names must contain only uppercase letters, "
                    f"numbers, underscores, and hyphens (pattern: ^[A-Z0-9_-]+$)"
                )

        return v


class Workflow(WorkflowData):
    """Complete workflow model with metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Workflow ID")
    organization_id: str = Field(..., description="Organization ID this workflow belongs to")
    is_default: bool = Field(False, description="Whether this is the organization's default workflow")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class WorkflowCreateCommand(AuditableCommand):
    """Command model for creating a new workflow."""

    _entity_type: ClassVar[str] = "workflow"
    _action_type: ClassVar[ActionType] = ActionType.WORKFLOW_CREATED

    workflow_data: WorkflowData
    organization_id: str = Field(..., description="Organization ID this workflow belongs to")


class WorkflowUpdateCommand(AuditableCommand):
    """Command model for updating an existing workflow."""

    _entity_type: ClassVar[str] = "workflow"
    _action_type: ClassVar[ActionType] = ActionType.WORKFLOW_UPDATED

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Workflow name")
    description: Optional[str] = Field(None, max_length=1000, description="Workflow description")
    statuses: Optional[List[str]] = Field(
        None,
        min_length=1,
        description="List of valid status names for this workflow",
    )

    @field_validator("statuses")
    @classmethod
    def validate_statuses(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate workflow statuses if provided."""
        if v is None:
            return v

        if not v:
            raise ValueError("Statuses list cannot be empty")

        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValueError("Duplicate status names are not allowed")

        # Validate each status name format
        status_pattern = re.compile(r"^[A-Z0-9_-]+$")
        for status in v:
            if not status_pattern.match(status):
                raise ValueError(
                    f"Invalid status name '{status}'. Status names must contain only uppercase letters, "
                    f"numbers, underscores, and hyphens (pattern: ^[A-Z0-9_-]+$)"
                )

        return v


class WorkflowDeleteCommand(AuditableCommand):
    """Command model for deleting a workflow."""

    _entity_type: ClassVar[str] = "workflow"
    _action_type: ClassVar[ActionType] = ActionType.WORKFLOW_DELETED

    workflow_id: str = Field(..., description="ID of workflow to delete")


# Ticket Models


class TicketStatus(str, Enum):
    """Ticket status workflow states."""

    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


class TicketPriority(str, Enum):
    """Ticket priority levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TicketData(BaseModel):
    """Base ticket data structure."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Ticket title",
    )
    description: Optional[str] = Field(None, max_length=2000, description="Ticket description")
    priority: Optional[TicketPriority] = Field(None, description="Ticket priority level")
    status: Optional[str] = Field(None, min_length=1, description="Ticket status (validated against workflow)")


class Ticket(TicketData, AuditableEntity):
    """Complete ticket model with metadata."""

    model_config = ConfigDict(from_attributes=True)

    _entity_type: ClassVar[str] = "ticket"

    id: str = Field(..., description="Ticket ID")
    status: str = Field(..., min_length=1, description="Ticket status (validated against project's workflow)")
    assignee_id: Optional[str] = Field(None, description="ID of user assigned to this ticket")
    reporter_id: str = Field(..., description="ID of user who created this ticket")
    project_id: str = Field(..., description="Project ID this ticket belongs to")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class TicketCreateCommand(AuditableCommand):
    """Command model for creating a new ticket."""

    _entity_type: ClassVar[str] = "ticket"
    _action_type: ClassVar[ActionType] = ActionType.TICKET_CREATED

    ticket_data: TicketData
    project_id: str = Field(..., description="Project ID this ticket belongs to")
    assignee_id: Optional[str] = Field(None, description="ID of user to assign to this ticket")


class TicketUpdateCommand(AuditableCommand):
    """Command model for updating an existing ticket."""

    _entity_type: ClassVar[str] = "ticket"
    _action_type: ClassVar[ActionType] = ActionType.TICKET_UPDATED

    title: Optional[str] = Field(None, min_length=1, max_length=500, description="Ticket title")
    description: Optional[str] = Field(None, max_length=2000, description="Ticket description")
    priority: Optional[TicketPriority] = Field(None, description="Ticket priority level")


class TicketDeleteCommand(AuditableCommand):
    """Command model for deleting a ticket."""

    _entity_type: ClassVar[str] = "ticket"
    _action_type: ClassVar[ActionType] = ActionType.TICKET_DELETED

    ticket_id: str = Field(..., description="ID of ticket to delete")


class TicketStatusChangeCommand(AuditableCommand):
    """Command model for changing ticket status."""

    _entity_type: ClassVar[str] = "ticket"
    _action_type: ClassVar[ActionType] = ActionType.TICKET_STATUS_CHANGED

    ticket_id: str = Field(..., description="ID of ticket to update")
    status: str = Field(..., min_length=1, description="New status (must be valid in project's workflow)")


class TicketMoveCommand(AuditableCommand):
    """Command model for moving ticket to different project."""

    _entity_type: ClassVar[str] = "ticket"
    _action_type: ClassVar[ActionType] = ActionType.TICKET_MOVED

    ticket_id: str = Field(..., description="ID of ticket to move")
    target_project_id: str = Field(..., description="ID of target project")


class TicketAssignCommand(AuditableCommand):
    """Command model for assigning/unassigning ticket."""

    _entity_type: ClassVar[str] = "ticket"
    _action_type: ClassVar[ActionType] = ActionType.TICKET_ASSIGNED

    ticket_id: str = Field(..., description="ID of ticket to assign")
    assignee_id: Optional[str] = Field(None, description="ID of user to assign (None to unassign)")


# User Management Models


class UserRole(str, Enum):
    """User roles for role-based access control."""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    PROJECT_MANAGER = "project_manager"
    WRITE_ACCESS = "write_access"
    READ_ACCESS = "read_access"


class UserData(BaseModel):
    """Base user data structure."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Username (alphanumeric, underscore, dash only)",
    )
    email: EmailStr = Field(..., description="User email address")
    full_name: str = Field(..., min_length=1, max_length=255, description="User full name")


class User(UserData, AuditableEntity):
    """Complete user model with metadata."""

    model_config = ConfigDict(from_attributes=True)

    _entity_type: ClassVar[str] = "user"

    id: str = Field(..., description="User ID")
    organization_id: Optional[str] = Field(None, description="Organization ID (None for Super Admin)")
    role: UserRole = Field(..., description="User role")
    is_active: bool = Field(True, description="Whether user is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class UserAuthData(BaseModel):
    """User authentication data including password hash.

    This model is used exclusively for authentication purposes where password
    verification is required. It should NEVER be exposed outside the authentication
    layer.

    Note: This is a domain model, not an ORM model. Repository methods must return
    this domain model, never ORM objects.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    password_hash: str = Field(..., description="Hashed password for verification")
    organization_id: Optional[str] = Field(None, description="Organization ID")
    role: UserRole = Field(..., description="User role")
    is_active: bool = Field(..., description="Whether user is active")


class UserCreateCommand(AuditableCommand):
    """Command model for creating a new user."""

    _entity_type: ClassVar[str] = "user"
    _action_type: ClassVar[ActionType] = ActionType.USER_CREATED

    user_data: UserData
    password: str = Field(..., min_length=1, description="Plain text password (will be hashed)")
    organization_id: Optional[str] = Field(None, description="Organization ID (None for Super Admin)")
    role: UserRole = Field(..., description="User role")


class UserUpdateCommand(AuditableCommand):
    """Command model for updating an existing user.

    Only specified fields will be updated. username, organization_id, and password
    cannot be changed via this command.
    """

    _entity_type: ClassVar[str] = "user"
    _action_type: ClassVar[ActionType] = ActionType.USER_UPDATED

    email: Optional[EmailStr] = Field(None, description="User email address")
    full_name: Optional[str] = Field(None, min_length=1, max_length=255, description="User full name")
    role: Optional[UserRole] = Field(None, description="User role")
    is_active: Optional[bool] = Field(None, description="Whether user is active")


class UserDeleteCommand(AuditableCommand):
    """Command model for deleting a user."""

    _entity_type: ClassVar[str] = "user"
    _action_type: ClassVar[ActionType] = ActionType.USER_DELETED

    user_id: str = Field(..., description="ID of user to delete")


class UserCreateResponse(BaseModel):
    """Response model for user creation including generated password.

    The generated_password is ONLY returned on creation and cannot be retrieved later.
    """

    user: User = Field(..., description="Created user details")
    generated_password: str = Field(..., description="Generated password (returned only once)")


# Authentication models


class LoginRequest(BaseModel):
    """Login request with username and password."""

    username: str = Field(..., min_length=1, description="Username (case-insensitive)")
    password: str = Field(..., min_length=1, description="Password (case-sensitive)")


class LoginResponse(BaseModel):
    """Successful login response with token and user info."""

    access_token: str = Field(..., description="JWT bearer token")
    token_type: str = Field("bearer", description="Token type (always 'bearer')")
    expires_in: int = Field(..., description="Token lifetime in seconds")
    user_id: str = Field(..., description="ID of authenticated user")
    organization_id: Optional[str] = Field(None, description="User's organization ID")
    role: UserRole = Field(..., description="User's current role")


class ChangePasswordRequest(BaseModel):
    """Request to change user's password."""

    current_password: str = Field(..., min_length=1, description="Current password for verification")
    new_password: str = Field(..., min_length=8, description="New password (must meet strength requirements)")


class PasswordChangeCommand(AuditableCommand):
    """Command for logging password changes (passwords are NOT included for security)."""

    _entity_type: ClassVar[str] = "user"
    _action_type: ClassVar[ActionType] = ActionType.USER_PASSWORD_CHANGED

    user_id: str = Field(..., description="ID of user changing password")


# Activity Log Models


class ActivityLog(BaseModel):
    """Complete activity log entry with metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Activity log entry ID")
    entity_type: str = Field(..., description="Type of entity (ticket, project, user, etc.)")
    entity_id: str = Field(..., description="ID of the entity that changed")
    action: ActionType = Field(..., description="Action that was performed")
    actor_id: str = Field(..., description="ID of user who performed the action")
    organization_id: str = Field(..., description="Organization ID for scoping")
    timestamp: datetime = Field(..., description="When the action occurred")
    changes: dict = Field(..., description="Details of what changed")
    metadata: Optional[dict] = Field(None, description="Additional metadata (optional)")


class ActivityLogCreateCommand(BaseModel):
    """Command model for creating a new activity log entry."""

    entity_type: str = Field(..., min_length=1, max_length=50, description="Type of entity")
    entity_id: str = Field(..., description="ID of the entity")
    action: ActionType = Field(..., description="Action performed")
    actor_id: str = Field(..., description="User who performed the action")
    organization_id: str = Field(..., description="Organization ID")
    changes: dict = Field(..., description="Details of what changed")
    metadata: Optional[dict] = Field(None, description="Additional metadata (optional)")


# Comment Models


class CommentData(BaseModel):
    """Base comment data structure."""

    content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Comment content/text",
    )


class Comment(CommentData, AuditableEntity):
    """Complete comment model with metadata."""

    model_config = ConfigDict(from_attributes=True)

    _entity_type: ClassVar[str] = "comment"

    id: str = Field(..., description="Comment ID")
    ticket_id: str = Field(..., description="Ticket ID this comment belongs to")
    author_id: str = Field(..., description="ID of user who created this comment")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class CommentCreateCommand(AuditableCommand):
    """Command model for creating a new comment."""

    _entity_type: ClassVar[str] = "comment"
    _action_type: ClassVar[ActionType] = ActionType.COMMENT_CREATED

    comment_data: CommentData
    ticket_id: str = Field(..., description="Ticket ID this comment belongs to")


class CommentUpdateCommand(AuditableCommand):
    """Command model for updating an existing comment."""

    _entity_type: ClassVar[str] = "comment"
    _action_type: ClassVar[ActionType] = ActionType.COMMENT_UPDATED

    content: str = Field(..., min_length=1, max_length=5000, description="Comment content")


class CommentDeleteCommand(AuditableCommand):
    """Command model for deleting a comment."""

    _entity_type: ClassVar[str] = "comment"
    _action_type: ClassVar[ActionType] = ActionType.COMMENT_DELETED

    comment_id: str = Field(..., description="ID of comment to delete")
