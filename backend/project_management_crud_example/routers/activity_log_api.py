"""Activity Log API endpoints.

This module provides read-only endpoints for querying activity logs (audit trail).
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.dependencies import get_current_user, get_repository
from project_management_crud_example.domain_models import ActionType, ActivityLog, User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/activity-logs", tags=["activity-logs"])


@router.get("", response_model=List[ActivityLog])
async def list_activity_logs(
    entity_type: Optional[str] = Query(None, description="Filter by entity type (e.g., 'ticket', 'project')"),  # noqa: B008
    entity_id: Optional[str] = Query(None, description="Filter by specific entity ID"),  # noqa: B008
    actor_id: Optional[str] = Query(None, description="Filter by user who performed action"),  # noqa: B008
    action: Optional[ActionType] = Query(None, description="Filter by action type"),  # noqa: B008
    from_date: Optional[datetime] = Query(None, description="Filter logs after this timestamp (inclusive)"),  # noqa: B008
    to_date: Optional[datetime] = Query(None, description="Filter logs before this timestamp (inclusive)"),  # noqa: B008
    organization_id: Optional[str] = Query(None, description="Filter by organization (Super Admin only)"),  # noqa: B008
    order: str = Query(
        "desc", pattern="^(asc|desc)$", description="Sort order: 'asc' (oldest first) or 'desc' (newest first)"
    ),  # noqa: B008
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> List[ActivityLog]:
    """List activity logs with optional filtering.

    Permission rules:
    - Super Admin: Can access all activity logs, can filter by organization_id
    - Admin: Can only access logs for their organization, organization_id filter ignored
    - Project Manager, Write Access, Read Access: Can only access logs for their organization

    Args:
        entity_type: Filter by entity type
        entity_id: Filter by specific entity ID
        actor_id: Filter by user who performed action
        action: Filter by action type
        from_date: Filter logs after this timestamp (inclusive)
        to_date: Filter logs before this timestamp (inclusive)
        organization_id: Filter by organization (Super Admin only)
        order: Sort order ('asc' or 'desc')
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        List of ActivityLog entries matching filters and permissions

    Note:
        - Logs are read-only and cannot be modified or deleted
        - All users can access logs within their permission scope
        - Timestamps use ISO 8601 format
    """
    logger.debug(f"Listing activity logs (by user {current_user.id})")

    # Permission check: Non-Super Admin users can only see their organization's logs
    if current_user.role != UserRole.SUPER_ADMIN:
        # Override organization_id filter for non-Super Admins
        organization_id = current_user.organization_id
        logger.debug(f"Non-Super Admin, restricting to organization: {organization_id}")

    # Get filtered activity logs
    logs = repo.activity_logs.list(
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        action=action,
        from_date=from_date,
        to_date=to_date,
        organization_id=organization_id,
        order=order,
    )

    logger.debug(f"Retrieved {len(logs)} activity logs")
    return logs


@router.get("/{log_id}", response_model=ActivityLog)
async def get_activity_log(
    log_id: str,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> ActivityLog:
    """Get a specific activity log by ID.

    Permission rules:
    - Super Admin: Can access any activity log
    - Other users: Can only access logs from their organization

    Args:
        log_id: ID of activity log to retrieve
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        ActivityLog if found and user has permission

    Raises:
        HTTP 404: Activity log not found or user doesn't have permission
    """
    logger.debug(f"Getting activity log: {log_id} (by user {current_user.id})")

    log = repo.activity_logs.get_by_id(log_id)

    if not log:
        logger.debug(f"Activity log not found: {log_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity log not found",
        )

    # Permission check: Non-Super Admin can only access logs from their organization
    if current_user.role != UserRole.SUPER_ADMIN:
        if log.organization_id != current_user.organization_id:
            logger.warning(
                f"User {current_user.id} attempted to access activity log {log_id} from different organization"
            )
            # Return 404 to avoid leaking cross-organization log existence
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Activity log not found",
            )

    return log
