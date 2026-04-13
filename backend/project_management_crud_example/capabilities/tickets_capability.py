"""Ticket capabilities."""

from typing import List, Optional

from project_management_crud_example.capabilities.errors import CapabilityPermissionError
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    Project,
    Ticket,
    TicketCreateCommand,
    TicketUpdateCommand,
    User,
    UserRole,
)

_CREATE_ROLES = {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.PROJECT_MANAGER, UserRole.WRITE_ACCESS}
_UPDATE_ROLES = _CREATE_ROLES
_MOVE_OR_ASSIGN_ROLES = {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.PROJECT_MANAGER}
_DELETE_ROLES = {UserRole.SUPER_ADMIN, UserRole.ADMIN}


class TicketReadCapability:
    """Read-side ticket authorization."""

    def __init__(self, repo: Repository, current_user: User) -> None:
        self._repo = repo
        self._user = current_user

    @property
    def repo(self) -> Repository:
        return self._repo

    @property
    def user(self) -> User:
        return self._user

    def _ensure_project_access(self, project: Project) -> None:
        if self._user.role == UserRole.SUPER_ADMIN:
            return
        if project.organization_id != self._user.organization_id:
            raise CapabilityPermissionError("Access denied: project belongs to different organization")

    def get_by_id(self, ticket_id: str) -> Optional[Ticket]:
        ticket = self._repo.tickets.get_by_id(ticket_id)
        if ticket is None:
            return None
        project = self._repo.projects.get_by_id(ticket.project_id)
        if project is None:
            return None
        self._ensure_project_access(project)
        return ticket

    def list_tickets(
        self,
        *,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
        assignee_id: Optional[str] = None,
    ) -> List[Ticket]:
        if self._user.role == UserRole.SUPER_ADMIN:
            return self._repo.tickets.get_by_filters(
                project_id=project_id,
                status=status,
                assignee_id=assignee_id,
            )
        if not self._user.organization_id:
            return []
        user_org_projects = self._repo.projects.get_by_organization_id(self._user.organization_id)
        user_project_ids = {p.id for p in user_org_projects}

        if project_id is not None:
            if project_id not in user_project_ids:
                return []
            return self._repo.tickets.get_by_filters(project_id=project_id, status=status, assignee_id=assignee_id)
        all_org_tickets: List[Ticket] = []
        for proj_id in user_project_ids:
            all_org_tickets.extend(
                self._repo.tickets.get_by_filters(project_id=proj_id, status=status, assignee_id=assignee_id)
            )
        all_org_tickets.sort(key=lambda t: t.created_at, reverse=True)
        return all_org_tickets


class TicketWriteCapability:
    """Write-side ticket authorization."""

    def __init__(self, repo: Repository, current_user: User) -> None:
        self._repo = repo
        self._user = current_user

    @property
    def repo(self) -> Repository:
        return self._repo

    @property
    def user(self) -> User:
        return self._user

    def _ensure_project_access(self, project: Project, action_detail: str) -> None:
        if self._user.role == UserRole.SUPER_ADMIN:
            return
        if project.organization_id != self._user.organization_id:
            raise CapabilityPermissionError(action_detail)

    def _require_role(self, roles: set, action: str) -> None:
        if self._user.role not in roles:
            raise CapabilityPermissionError(f"Insufficient permissions to {action}")

    # -- create --
    def authorize_create(self, project: Project) -> None:
        self._require_role(_CREATE_ROLES, "create tickets")
        self._ensure_project_access(project, "Access denied: project belongs to different organization")

    def authorize_assignee(self, assignee: User) -> None:
        if self._user.role == UserRole.SUPER_ADMIN:
            return
        if assignee.organization_id != self._user.organization_id:
            raise CapabilityPermissionError("Cannot assign to user in different organization")

    def create(self, command: TicketCreateCommand, reporter_id: str) -> Ticket:
        return self._repo.tickets.create(command, reporter_id=reporter_id)

    # -- update --
    def authorize_update(self, project: Project) -> None:
        self._require_role(_UPDATE_ROLES, "update tickets")
        self._ensure_project_access(project, "Access denied: project belongs to different organization")

    def update(self, ticket_id: str, command: TicketUpdateCommand) -> Optional[Ticket]:
        return self._repo.tickets.update(ticket_id, command)

    # -- status change --
    def authorize_status_change(self, project: Project) -> None:
        self._require_role(_UPDATE_ROLES, "change ticket status")
        self._ensure_project_access(project, "Access denied: project belongs to different organization")

    def update_status(self, ticket_id: str, status: str) -> Optional[Ticket]:
        return self._repo.tickets.update_status(ticket_id, status)

    # -- move --
    def authorize_move(self, source_project: Project, target_project: Project) -> None:
        self._require_role(_MOVE_OR_ASSIGN_ROLES, "move tickets")
        self._ensure_project_access(source_project, "Access denied: project belongs to different organization")
        self._ensure_project_access(target_project, "Access denied: project belongs to different organization")

    def update_project(self, ticket_id: str, project_id: str) -> Optional[Ticket]:
        return self._repo.tickets.update_project(ticket_id, project_id)

    # -- assign --
    def authorize_assign(self, project: Project) -> None:
        self._require_role(_MOVE_OR_ASSIGN_ROLES, "assign tickets")
        self._ensure_project_access(project, "Access denied: project belongs to different organization")

    def update_assignee(self, ticket_id: str, assignee_id: Optional[str]) -> Optional[Ticket]:
        return self._repo.tickets.update_assignee(ticket_id, assignee_id)

    # -- delete --
    def authorize_delete(self, project: Project) -> None:
        self._require_role(_DELETE_ROLES, "delete tickets")
        self._ensure_project_access(project, "Access denied: project belongs to different organization")

    def delete(self, ticket_id: str) -> bool:
        return self._repo.tickets.delete(ticket_id)
