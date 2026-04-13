"""Activity log read capability (writes are internal only)."""

from datetime import datetime
from typing import List, Optional

from project_management_crud_example.capabilities.errors import CapabilityPermissionError  # noqa: F401  (reserved)
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import ActionType, ActivityLog, User, UserRole


class ActivityLogReadCapability:
    """Read-only activity log capability.

    Cross-org reads are surfaced as not-found (None), consistent with the
    existing routers' 404-on-cross-org behavior.
    """

    def __init__(self, repo: Repository, current_user: User) -> None:
        self._repo = repo
        self._user = current_user

    @property
    def repo(self) -> Repository:
        return self._repo

    @property
    def user(self) -> User:
        return self._user

    def get_by_id(self, log_id: str) -> Optional[ActivityLog]:
        log = self._repo.activity_logs.get_by_id(log_id)
        if log is None:
            return None
        if self._user.role != UserRole.SUPER_ADMIN:
            if log.organization_id != self._user.organization_id:
                return None
        return log

    def list_logs(
        self,
        *,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        action: Optional[ActionType] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        organization_id: Optional[str] = None,
        order: str = "desc",
    ) -> List[ActivityLog]:
        if self._user.role != UserRole.SUPER_ADMIN:
            organization_id = self._user.organization_id
        return self._repo.activity_logs.list(
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            action=action,
            from_date=from_date,
            to_date=to_date,
            organization_id=organization_id,
            order=order,
        )
