"""Debug helpers for development visibility.

This module provides debugging utilities that log detailed change information
to help developers understand what's happening in the application.
"""

import logging
from typing import Optional

from pydantic import BaseModel

from project_management_crud_example.utils.debug_diff_helpers import (
    generate_changes_dict,
    strip_sensitive_fields,
)

logger = logging.getLogger(__name__)


def log_diff_debug(
    old_value: Optional[BaseModel],
    new_value: Optional[BaseModel],
    entity_type: str,
    operation: str,
) -> None:
    """
    Log a human-readable diff for debugging purposes.

    This outputs to logger.debug() to help developers see what changed
    during an operation without needing to query the database.

    Args:
        old_value: Domain model before change (None for creates)
        new_value: Domain model after change (None for deletes)
        entity_type: Type of entity (e.g., "ticket", "project")
        operation: Description of operation (e.g., "update_ticket", "delete_project")

    Examples:
        >>> log_diff_debug(old_ticket, updated_ticket, "ticket", "update_ticket")
        # DEBUG: update_ticket changes: title: "Old" -> "New", priority: LOW -> HIGH
    """
    try:
        # Convert models to dicts
        old_dict = strip_sensitive_fields(old_value, entity_type) if old_value else None
        new_dict = strip_sensitive_fields(new_value, entity_type) if new_value else None

        # Generate diff
        changes = generate_changes_dict(old_dict, new_dict)

        # Format for logging
        if "created" in changes:
            logger.debug(f"{operation}: Created {entity_type} with {len(changes['created'])} fields")
        elif "deleted" in changes:
            logger.debug(f"{operation}: Deleted {entity_type} with {len(changes['deleted'])} fields")
        elif changes:
            # Format changes in human-readable way
            change_summary = []
            for field, change_info in changes.items():
                old_val = change_info.get("old_value")
                new_val = change_info.get("new_value")
                change_summary.append(f"{field}: {old_val!r} -> {new_val!r}")
            logger.debug(f"{operation} changes: {', '.join(change_summary)}")
        else:
            logger.debug(f"{operation}: No changes detected")

    except Exception as e:
        # Don't break if debug logging fails
        logger.warning(f"Failed to log diff for {operation}: {e}")
