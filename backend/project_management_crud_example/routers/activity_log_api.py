"""Activity Log API endpoints (capability-based)."""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from project_management_crud_example.capabilities import ActivityLogReadCapability
from project_management_crud_example.dependencies import get_activity_log_read_capability
from project_management_crud_example.domain_models import ActionType, ActivityLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/activity-logs", tags=["activity-logs"])


@router.get("", response_model=List[ActivityLog])
async def list_activity_logs(
    entity_type: Optional[str] = Query(None),  # noqa: B008
    entity_id: Optional[str] = Query(None),  # noqa: B008
    actor_id: Optional[str] = Query(None),  # noqa: B008
    action: Optional[ActionType] = Query(None),  # noqa: B008
    from_date: Optional[datetime] = Query(None),  # noqa: B008
    to_date: Optional[datetime] = Query(None),  # noqa: B008
    organization_id: Optional[str] = Query(None),  # noqa: B008
    order: str = Query("desc", pattern="^(asc|desc)$"),  # noqa: B008
    cap: ActivityLogReadCapability = Depends(get_activity_log_read_capability),  # noqa: B008
) -> List[ActivityLog]:
    return cap.list_logs(
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        action=action,
        from_date=from_date,
        to_date=to_date,
        organization_id=organization_id,
        order=order,
    )


@router.get("/{log_id}", response_model=ActivityLog)
async def get_activity_log(
    log_id: str,
    cap: ActivityLogReadCapability = Depends(get_activity_log_read_capability),  # noqa: B008
) -> ActivityLog:
    log = cap.get_by_id(log_id)
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity log not found")
    return log
