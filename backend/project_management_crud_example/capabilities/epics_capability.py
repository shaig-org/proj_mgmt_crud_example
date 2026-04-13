"""Epic capabilities."""

from typing import List, Optional

from project_management_crud_example.capabilities.errors import CapabilityPermissionError
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    Epic,
    EpicCreateCommand,
    EpicData,
    EpicUpdateCommand,
    Ticket,
    User,
    UserRole,
)

_WRITE_ROLES = {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.PROJECT_MANAGER}
_DELETE_ROLES = {UserRole.SUPER_ADMIN, UserRole.ADMIN}


class EpicReadCapability:
    """Read-side epic authorization."""

    def __init__(self, repo: Repository, current_user: User) -> None:
        self._repo = repo
        self._user = current_user

    @property
    def repo(self) -> Repository:
        return self._repo

    @property
    def user(self) -> User:
        return self._user

    def _ensure_same_org(self, epic: Epic) -> None:
        if self._user.role == UserRole.SUPER_ADMIN:
            return
        if epic.organization_id != self._user.organization_id:
            raise CapabilityPermissionError("Access denied: epic belongs to different organization")

    def get_by_id(self, epic_id: str) -> Optional[Epic]:
        epic = self._repo.epics.get_by_id(epic_id)
        if epic is None:
            return None
        self._ensure_same_org(epic)
        return epic

    def list_epics(self) -> List[Epic]:
        if self._user.role == UserRole.SUPER_ADMIN:
            return self._repo.epics.get_all()
        if not self._user.organization_id:
            return []
        return self._repo.epics.get_by_organization_id(self._user.organization_id)

    def get_tickets_in_epic(self, epic_id: str) -> Optional[List[Ticket]]:
        epic = self._repo.epics.get_by_id(epic_id)
        if epic is None:
            return None
        self._ensure_same_org(epic)
        return self._repo.epics.get_tickets_in_epic(epic_id)


class EpicWriteCapability:
    """Write-side epic authorization."""

    def __init__(self, repo: Repository, current_user: User) -> None:
        self._repo = repo
        self._user = current_user

    @property
    def repo(self) -> Repository:
        return self._repo

    @property
    def user(self) -> User:
        return self._user

    def _require_write_role(self, action: str) -> None:
        if self._user.role not in _WRITE_ROLES:
            raise CapabilityPermissionError(f"Insufficient permissions to {action}")

    def _require_delete_role(self, action: str) -> None:
        if self._user.role not in _DELETE_ROLES:
            raise CapabilityPermissionError(f"Insufficient permissions to {action}")

    def _ensure_same_org(self, epic: Epic) -> None:
        if self._user.role == UserRole.SUPER_ADMIN:
            return
        if epic.organization_id != self._user.organization_id:
            raise CapabilityPermissionError("Access denied: epic belongs to different organization")

    def build_create_command(self, epic_data: EpicData) -> EpicCreateCommand:
        self._require_write_role("create epics")
        if not self._user.organization_id:
            raise ValueError("User has no organization")
        return EpicCreateCommand(epic_data=epic_data, organization_id=self._user.organization_id)

    def create(self, command: EpicCreateCommand) -> Epic:
        self._require_write_role("create epics")
        return self._repo.epics.create(command)

    def load_for_update(self, epic_id: str) -> Optional[Epic]:
        self._require_write_role("update epics")
        epic = self._repo.epics.get_by_id(epic_id)
        if epic is None:
            return None
        self._ensure_same_org(epic)
        return epic

    def update(self, epic_id: str, command: EpicUpdateCommand) -> Optional[Epic]:
        self._require_write_role("update epics")
        return self._repo.epics.update(epic_id, command)

    def load_for_delete(self, epic_id: str) -> Optional[Epic]:
        self._require_delete_role("delete epics")
        epic = self._repo.epics.get_by_id(epic_id)
        if epic is None:
            return None
        self._ensure_same_org(epic)
        return epic

    def delete(self, epic_id: str) -> bool:
        self._require_delete_role("delete epics")
        return self._repo.epics.delete(epic_id)

    def authorize_ticket_link(self, epic: Epic, action: str) -> None:
        """Role + same-org check when adding/removing a ticket from an epic."""
        if action == "add":
            self._require_write_role("add tickets to epics")
        else:
            self._require_write_role("remove tickets from epics")
        self._ensure_same_org(epic)

    def ensure_ticket_same_org(self, epic: Epic, ticket_org_id: str, action: str) -> None:
        if ticket_org_id != epic.organization_id:
            if action == "add":
                raise CapabilityPermissionError("Cannot add ticket from different organization to epic")
            raise CapabilityPermissionError("Cannot remove ticket from different organization from epic")

    def add_ticket(self, epic_id: str, ticket_id: str) -> bool:
        return self._repo.epics.add_ticket_to_epic(epic_id, ticket_id)

    def remove_ticket(self, epic_id: str, ticket_id: str) -> bool:
        return self._repo.epics.remove_ticket_from_epic(epic_id, ticket_id)
