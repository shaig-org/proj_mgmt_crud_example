"""Project capabilities.

Owns authorization decisions for project read and write endpoints, and absorbs
the post-write side-effects (activity log, debug diff log) so route handlers
never reach back into the repository.
"""

from typing import List, Optional

from project_management_crud_example.capabilities.errors import (
    CapabilityNotFoundError,
    CapabilityPermissionError,
)
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    Project,
    ProjectArchiveCommand,
    ProjectCreateCommand,
    ProjectData,
    ProjectDeleteCommand,
    ProjectUnarchiveCommand,
    ProjectUpdateCommand,
    User,
    UserRole,
)
from project_management_crud_example.utils.activity_log_helpers import log_activity
from project_management_crud_example.utils.debug_helpers import log_diff_debug

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


class OrgProjectWriteCapability:
    """Org-scoped project write capability (collection-level).

    Verbs and roles:
      - build_create_command: SUPER_ADMIN, ADMIN, PROJECT_MANAGER
      - create:               SUPER_ADMIN, ADMIN, PROJECT_MANAGER
      - bind:                 SUPER_ADMIN, ADMIN, PROJECT_MANAGER
                              (returns a `BoundProjectWriteCapability` for a
                              specific project; per-verb role checks happen on
                              the bound capability)

    Scope: the user's organization (cross-org access rejected; super-admins
    bypass cross-org).

    Encapsulation rule: the underlying `Repository` and current `User` are
    private (`_repo`, `_user`). Routes do not access them — every side-effect
    a route needs (e.g. activity logging on create) is absorbed into the verb.
    """

    def __init__(self, repo: Repository, current_user: User) -> None:
        self._repo = repo
        self._user = current_user

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
        """Create the project and emit an activity-log entry."""
        self._require_write_role("create projects")
        project = self._repo.projects.create(command)
        log_activity(
            repo=self._repo,
            command=command,
            entity_id=project.id,
            actor_id=self._user.id,
            organization_id=project.organization_id,
        )
        return project

    def bind(self, project_id: str) -> "BoundProjectWriteCapability":
        """Resolve auth + existence and return a capability scoped to this project.

        Raises:
            CapabilityPermissionError: role gate or cross-org check fails (-> 403).
            CapabilityNotFoundError: project does not exist (-> 404).
        """
        self._require_write_role("update projects")
        project = self._repo.projects.get_by_id(project_id)
        if project is None:
            raise CapabilityNotFoundError("Project not found")
        self._ensure_same_org(project)
        return BoundProjectWriteCapability(self._repo, self._user, project)


class BoundProjectWriteCapability:
    """Project write operations scoped to a specific, already-authorized project.

    Verbs and roles:
      - update:    SUPER_ADMIN, ADMIN, PROJECT_MANAGER
      - archive:   SUPER_ADMIN, ADMIN, PROJECT_MANAGER
      - delete:    SUPER_ADMIN, ADMIN
      - unarchive: SUPER_ADMIN, ADMIN

    Scope: the project passed to `OrgProjectWriteCapability.bind()`. Role and
    cross-org checks have already run by the time this object exists; verbs
    re-check the role defensively (cheap, preserves defense-in-depth).

    Encapsulation rule: the only public state is `current` — a snapshot of the
    project as fetched at bind-time, used for diff logging and for the route's
    response shape. The repository and current user are intentionally not
    exposed; verbs absorb every side-effect a route used to perform via
    `cap.repo` / `cap.user`.

    `current` is the pre-mutation snapshot; verbs return the post-mutation
    `Project` (caller may shadow `current` if they want the new state, but the
    bound cap itself does not mutate `current`).
    """

    def __init__(self, repo: Repository, current_user: User, project: Project) -> None:
        self._repo = repo
        self._user = current_user
        self.current: Project = project

    # ---- defensive role checks --------------------------------------------
    def _require_write_role(self) -> None:
        if self._user.role not in _WRITE_ROLES:
            raise CapabilityPermissionError("Insufficient permissions to update projects")

    def _require_delete_role(self) -> None:
        if self._user.role not in _DELETE_ROLES:
            raise CapabilityPermissionError("Insufficient permissions to update projects")

    # ---- verbs -------------------------------------------------------------
    def update(self, command: ProjectUpdateCommand) -> Project:
        """Update the bound project, emitting activity + diff debug logs."""
        self._require_write_role()
        updated = self._repo.projects.update(self.current.id, command)
        if updated is None:
            raise CapabilityNotFoundError("Project not found")
        log_diff_debug(self.current, updated, "project", "update_project")
        log_activity(
            repo=self._repo,
            command=command,
            entity_id=self.current.id,
            actor_id=self._user.id,
            organization_id=updated.organization_id,
        )
        return updated

    def delete(self) -> None:
        """Delete the bound project, emitting activity + diff debug logs."""
        self._require_delete_role()
        deleted = self._repo.projects.delete(self.current.id)
        if not deleted:
            raise CapabilityNotFoundError("Project not found")
        log_diff_debug(self.current, None, "project", "delete_project")
        log_activity(
            repo=self._repo,
            command=ProjectDeleteCommand(project_id=self.current.id),
            entity_id=self.current.id,
            actor_id=self._user.id,
            organization_id=self.current.organization_id,
            snapshot=self.current.model_dump(mode="json", exclude_none=True),
        )

    def archive(self) -> Project:
        """Archive the bound project, emitting an activity-log entry."""
        self._require_write_role()
        archived = self._repo.projects.archive(self.current.id)
        if archived is None:
            raise CapabilityNotFoundError("Project not found")
        log_activity(
            repo=self._repo,
            command=ProjectArchiveCommand(project_id=self.current.id),
            entity_id=self.current.id,
            actor_id=self._user.id,
            organization_id=archived.organization_id,
        )
        return archived

    def unarchive(self) -> Project:
        """Unarchive the bound project, emitting an activity-log entry."""
        self._require_delete_role()
        unarchived = self._repo.projects.unarchive(self.current.id)
        if unarchived is None:
            raise CapabilityNotFoundError("Project not found")
        log_activity(
            repo=self._repo,
            command=ProjectUnarchiveCommand(project_id=self.current.id),
            entity_id=self.current.id,
            actor_id=self._user.id,
            organization_id=unarchived.organization_id,
        )
        return unarchived
