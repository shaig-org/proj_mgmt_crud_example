"""Core debug diff utilities.

This module provides pure functions for comparing objects and generating diffs
for debug logging purposes. All functions are heavily tested and have comprehensive error handling.
"""

import logging
import re
from typing import Any, Dict, Optional, Set, TypeVar

from deepdiff import DeepDiff
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Global registry of sensitive fields per entity type
# These fields are EXCLUDED from diffs to prevent leaking sensitive data
SENSITIVE_FIELDS: Dict[str, Set[str]] = {
    "user": {"password_hash"},
    # Add more as needed
}


def generate_changes_dict(
    old_dict: Optional[Dict[str, Any]],
    new_dict: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Generate changes dictionary from old and new state dictionaries.

    This is a PURE FUNCTION with no side effects. Heavily tested.

    Args:
        old_dict: State before change (None for creation)
        new_dict: State after change (None for deletion)

    Returns:
        - {"created": {...}} if old_dict is None
        - {"deleted": {...}} if new_dict is None
        - {field: {"old_value": ..., "new_value": ...}, ...} if both present
        - {"error": "message"} if diff fails (fallback, never throws)

    Examples:
        >>> generate_changes_dict(None, {"name": "New Project"})
        {"created": {"name": "New Project"}}

        >>> generate_changes_dict({"status": "TODO"}, {"status": "DONE"})
        {"status": {"old_value": "TODO", "new_value": "DONE"}}

        >>> generate_changes_dict(
        ...     {"metadata": {"version": 1}},
        ...     {"metadata": {"version": 2}}
        ... )
        {"metadata.version": {"old_value": 1, "new_value": 2}}
    """
    try:
        # Creation
        if old_dict is None and new_dict is not None:
            return {"created": new_dict}

        # Deletion
        if old_dict is not None and new_dict is None:
            return {"deleted": old_dict}

        # Update - use DeepDiff
        if old_dict is not None and new_dict is not None:
            return _deep_diff_dicts(old_dict, new_dict)

        # Both None - invalid
        raise ValueError("Both old_dict and new_dict are None")

    except Exception as e:
        # CRITICAL: Never fail activity logging
        # Return error marker and log the exception
        logger.error(
            f"Failed to generate changes dict: {e}",
            exc_info=True,
            extra={
                "old_dict_keys": list(old_dict.keys()) if old_dict else None,
                "new_dict_keys": list(new_dict.keys()) if new_dict else None,
            },
        )
        return {
            "error": "Failed to identify changes",
            "error_detail": str(e),
        }


def strip_sensitive_fields(model: T, entity_type: str) -> Dict[str, Any]:
    """
    Convert Pydantic model to dict, excluding sensitive fields.

    This ensures sensitive data NEVER makes it into the diff.

    Args:
        model: Pydantic model instance
        entity_type: Type of entity ("user", "ticket", "project", etc.)

    Returns:
        Dictionary with sensitive fields excluded

    Examples:
        >>> user = User(id="1", username="alice", password_hash="hashed")
        >>> strip_sensitive_fields(user, "user")
        {"id": "1", "username": "alice"}  # password_hash excluded
    """
    # Serialize to dict with JSON mode (handles datetime, nested models, etc.)
    # IMPORTANT: exclude_none=False ensures None values are included in diff
    data = model.model_dump(mode="json", exclude_none=False)

    # Get sensitive fields for this entity type
    sensitive = SENSITIVE_FIELDS.get(entity_type, set())

    # Remove sensitive fields
    for field in sensitive:
        data.pop(field, None)  # Safe removal (no error if field doesn't exist)

    return data


def _deep_diff_dicts(old_dict: Dict[str, Any], new_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Core DeepDiff logic - converts DeepDiff output to our format.

    Args:
        old_dict: Dictionary before change
        new_dict: Dictionary after change

    Returns:
        Dictionary with changed fields in format: {field: {"old_value": ..., "new_value": ...}}
    """
    diff = DeepDiff(
        old_dict,
        new_dict,
        ignore_order=False,  # Order matters for our use case
        view="text",  # Use text view for simpler parsing
    )

    # No changes
    if not diff:
        return {}

    changes = {}

    # type_changes: Handle changes where type changed (e.g., None -> str)
    if "type_changes" in diff:
        for path, change in diff["type_changes"].items():
            field = _parse_path(path)
            changes[field] = {
                "old_value": change["old_value"],
                "new_value": change["new_value"],
            }

    # values_changed: {"root['field']": {"old_value": ..., "new_value": ...}}
    if "values_changed" in diff:
        for path, change in diff["values_changed"].items():
            field = _parse_path(path)
            changes[field] = {
                "old_value": change["old_value"],
                "new_value": change["new_value"],
            }

    # dictionary_item_added: ["root['new_field']"]
    if "dictionary_item_added" in diff:
        for path in diff["dictionary_item_added"]:
            field = _parse_path(path)
            changes[field] = {
                "old_value": None,
                "new_value": _get_nested_value(new_dict, field),
            }

    # dictionary_item_removed: ["root['removed_field']"]
    if "dictionary_item_removed" in diff:
        for path in diff["dictionary_item_removed"]:
            field = _parse_path(path)
            changes[field] = {
                "old_value": _get_nested_value(old_dict, field),
                "new_value": None,
            }

    # iterable_item_added: {"root['items'][2]": new_item}
    if "iterable_item_added" in diff:
        for path, value in diff["iterable_item_added"].items():
            field = _parse_path(path)
            changes[field] = {
                "old_value": None,
                "new_value": value,
            }

    # iterable_item_removed: {"root['items'][0]": removed_item}
    if "iterable_item_removed" in diff:
        for path, value in diff["iterable_item_removed"].items():
            field = _parse_path(path)
            changes[field] = {
                "old_value": value,
                "new_value": None,
            }

    return changes


def _parse_path(deepdiff_path: str) -> str:
    """
    Convert DeepDiff path format to our field notation.

    Examples:
        "root['name']" -> "name"
        "root['metadata']['version']" -> "metadata.version"
        "root['items'][0]" -> "items[0]"
    """
    # Remove 'root'
    path = deepdiff_path.replace("root", "").strip()

    # Convert ['field'] to field, ['nested']['field'] to nested.field
    # Keep [0] as is for array indices
    path = re.sub(r"\['([^']+)'\]", r".\1", path)
    path = path.lstrip(".")

    return path


def _get_nested_value(data: Dict[str, Any], field_path: str) -> object:
    """
    Get value from nested dict using dot notation path.

    Args:
        data: Dictionary to extract value from
        field_path: Dot-notation path (e.g., "metadata.version", "items[0]")

    Returns:
        Value at the specified path

    Examples:
        >>> _get_nested_value({"a": {"b": 5}}, "a.b")
        5
        >>> _get_nested_value({"items": [1, 2, 3]}, "items[1]")
        2
    """
    keys = field_path.replace("[", ".").replace("]", "").split(".")
    value: Any = data
    for key in keys:
        if key.isdigit():
            value = value[int(key)]  # type: ignore[index]
        else:
            value = value[key]
    return value
