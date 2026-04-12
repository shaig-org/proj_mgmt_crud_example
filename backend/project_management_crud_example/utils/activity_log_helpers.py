"""High-level helpers for activity logging.

This module provides the primary interface for activity logging in the application.
Use log_activity() for one-line activity logging throughout the codebase.
"""

import logging
from typing import Optional

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    ActivityLogCreateCommand,
    AuditableCommand,
)

logger = logging.getLogger(__name__)

# Fields that should be redacted in activity logs for security
SENSITIVE_COMMAND_FIELDS = {"password", "current_password", "new_password"}


def _redact_sensitive_fields(command_dict: dict) -> dict:
    """
    Redact sensitive fields (passwords) from command dictionary.

    Args:
        command_dict: Command dictionary to redact

    Returns:
        New dictionary with sensitive fields redacted
    """
    redacted = command_dict.copy()
    for field in SENSITIVE_COMMAND_FIELDS:
        if field in redacted:
            redacted[field] = "[REDACTED]"
    return redacted


def log_activity(
    repo: Repository,
    command: AuditableCommand,
    entity_id: str,
    actor_id: str,
    organization_id: str,
    snapshot: Optional[dict] = None,
) -> None:
    """
    ONE-LINE ACTIVITY LOGGING: Create and persist activity log for a command.

    This is the PRIMARY interface for activity logging throughout the application.
    NEVER THROWS EXCEPTIONS - logs errors instead to prevent breaking operations.

    Usage Examples:
        # Create
        ticket = repo.tickets.create(command, reporter_id=current_user.id)
        log_activity(
            repo=repo,
            command=command,
            entity_id=ticket.id,
            actor_id=current_user.id,
            organization_id=project.organization_id,
        )

        # Update
        log_activity(
            repo=repo,
            command=update_command,
            entity_id=ticket_id,
            actor_id=current_user.id,
            organization_id=project.organization_id,
        )

        # Delete (with snapshot)
        delete_cmd = TicketDeleteCommand(ticket_id=ticket_id)
        log_activity(
            repo=repo,
            command=delete_cmd,
            entity_id=delete_cmd.ticket_id,
            actor_id=current_user.id,
            organization_id=project.organization_id,
            snapshot=ticket.model_dump(exclude_none=True),
        )

    Args:
        repo: Repository instance for database access
        command: Command that was executed (must inherit from AuditableCommand)
        entity_id: ID of the entity that was affected
        actor_id: ID of user who performed the action
        organization_id: Organization context for the action
        snapshot: Optional snapshot of entity (for deletes)
    """
    try:
        # Extract metadata from command
        entity_type = command._entity_type
        action = command._action_type

        # Build changes dict from command
        command_dict = command.model_dump(exclude_none=True, exclude={"_entity_type", "_action_type"})

        # Redact sensitive fields (passwords)
        command_dict = _redact_sensitive_fields(command_dict)

        changes: dict = {}
        if snapshot:
            # Delete operation - include snapshot
            changes = {
                "command": command_dict,
                "snapshot": snapshot,
            }
        else:
            # Create/Update operation - just the command
            changes = {
                "command": command_dict,
            }

        # Create activity log command
        activity_cmd = ActivityLogCreateCommand(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_id=actor_id,
            organization_id=organization_id,
            changes=changes,
        )

        # Persist to DB
        repo.activity_logs.create(activity_cmd)

        logger.debug(f"Activity logged: {action.value} for {entity_type} {entity_id}")

    except Exception as e:
        # CRITICAL: Activity logging must NEVER break the operation
        logger.error(
            f"Failed to log activity: {e}",
            exc_info=True,
            extra={
                "command_type": type(command).__name__ if command else None,
                "entity_id": entity_id,
                "actor_id": actor_id,
                "organization_id": organization_id,
            },
        )
