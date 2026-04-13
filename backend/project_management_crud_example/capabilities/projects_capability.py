"""Project capabilities.

Owns authorization decisions for project read and write endpoints.
Preserves the HTTP 403 detail strings the routers previously raised so existing
API tests remain green.
"""

from typing import List, Optional

from project_management_crud_example.capabilities.errors import CapabilityPermissionError
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    Project,
    ProjectCreateCommand,
    ProjectData,
    ProjectUpdateCommand,
    User,
    UserRole,
)

_WRITE_ROLES = {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.PROJECT_MANAGER}
_DELETE_ROLES = {UserRole.SUPER_ADMIN, UserRole.ADMIN}


class ProjectReadCapability:
    """Read-side project authorization."""

    def __init__(self, repo: Repository, current_user: User) -> None:
        self._repo = repo
        self._user = current_user

    @property
    def repo(self) -> Repository:
        return self._repo

    @property
    def user(self) -> User:
        return self._user

    def _ensure_same_org(self, project: Project, detail: str) -> None:
        if self._user.role == UserRole.SUPER_ADMIN:
            return
        if project.organization_id != self._user.organization_id:
            raise CapabilityPermissionError(detail)

    def get_by_id(self, project_id: str) -> Optional[Project]:
        """Return the project or None if not found. Raises on cross-org deny."""
        project = self._repo.projects.get_by_id(project_id)
        if project is None:
            return None
        self._ensure_same_org(project, "Access denied: project belongs to different organization")
        return project

    def list_projects(
        self,
        *,
        name: Optional[str] = None,
        is_active: Optional[bool] = None,
        include_archived: bool = False,
    ) -> List[Project]:
        """List projects visible to the current user with filters applied."""
        if self._user.role == UserRole.SUPER_ADMIN:
            organization_filter: Optional[str] = None
        else:
            if not self._user.organization_id:
                return []
            organization_filter = self._user.organization_id

        return self._repo.projects.get_by_filters(
            organization_id=organization_filter,
            name=name,
            is_active=is_active,
            include_archived=include_archived,
        )


class ProjectWriteCapability:
    """Write-side project authorization (create/update/delete/archive/unarchive)."""

    def __init__(self, repo: Repository, current_user: User) -> None:
        self._repo = repo
        self._user = current_user

    @property
    def repo(self) -> Repository:
        return self._repo

    @property
    def user(self) -> User:
        return self._user

    # ---- role gates --------------------------------------------------------
    def _require_write_role(self, action: str) -> None:
        if self._user.role not in _WRITE_ROLES:
            raise CapabilityPermissionError(f"Insufficient permissions to {action}")

    def _require_delete_role(self, action: str) -> None:
        if self._user.role not in _DELETE_ROLES:
            raise CapabilityPermissionError(f"Insufficient permissions to {action}")

    def _ensure_same_org(self, project: Project) -> None:
        if self._user.role == UserRole.SUPER_ADMIN:
            return
        if project.organization_id != self._user.organization_id:
            raise CapabilityPermissionError("Access denied: project belongs to different organization")

    # ---- verbs -------------------------------------------------------------
    def build_create_command(self, project_data: ProjectData) -> ProjectCreateCommand:
        """Validate permission and construct a create command scoped to the user's org."""
        self._require_write_role("create projects")
        if not self._user.organization_id:
            # Super admins without an org cannot create projects via this flow;
            # the router preserves this case as a 400, so we return a sentinel
            # by raising ValueError to signal 400.
            raise ValueError("Cannot create project: user has no organization")
        return ProjectCreateCommand(
            project_data=project_data,
            organization_id=self._user.organization_id,
        )

    def create(self, command: ProjectCreateCommand) -> Project:
        self._require_write_role("create projects")
        return self._repo.projects.create(command)

    def load_for_update(self, project_id: str) -> Optional[Project]:
        """Role-check + existence check + cross-org check. Returns None if not found."""
        self._require_write_role("update projects")
        project = self._repo.projects.get_by_id(project_id)
        if project is None:
            return None
        self._ensure_same_org(project)
        return project

    def update(self, project_id: str, command: ProjectUpdateCommand) -> Optional[Project]:
        # Caller is expected to have called load_for_update; defensive role-check anyway.
        self._require_write_role("update projects")
        return self._repo.projects.update(project_id, command)

    def load_for_delete(self, project_id: str) -> Optional[Project]:
        self._require_delete_role("delete projects")
        project = self._repo.projects.get_by_id(project_id)
        if project is None:
            return None
        self._ensure_same_org(project)
        return project

    def delete(self, project_id: str) -> bool:
        self._require_delete_role("delete projects")
        return self._repo.projects.delete(project_id)

    def load_for_archive(self, project_id: str) -> Optional[Project]:
        self._require_write_role("archive projects")
        project = self._repo.projects.get_by_id(project_id)
        if project is None:
            return None
        self._ensure_same_org(project)
        return project

    def archive(self, project_id: str) -> Optional[Project]:
        self._require_write_role("archive projects")
        return self._repo.projects.archive(project_id)

    def load_for_unarchive(self, project_id: str) -> Optional[Project]:
        self._require_delete_role("unarchive projects")
        project = self._repo.projects.get_by_id(project_id)
        if project is None:
            return None
        self._ensure_same_org(project)
        return project

    def unarchive(self, project_id: str) -> Optional[Project]:
        self._require_delete_role("unarchive projects")
        return self._repo.projects.unarchive(project_id)
