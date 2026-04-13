"""User capabilities."""

from typing import List, Optional

from project_management_crud_example.capabilities.errors import CapabilityPermissionError
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import User, UserRole, UserUpdateCommand

_ADMIN_ROLES = {UserRole.SUPER_ADMIN, UserRole.ADMIN}


class UserReadCapability:
    """Read-side user authorization."""

    def __init__(self, repo: Repository, current_user: User) -> None:
        self._repo = repo
        self._user = current_user

    @property
    def repo(self) -> Repository:
        return self._repo

    @property
    def user(self) -> User:
        return self._user

    def get_by_id(self, user_id: str) -> Optional[User]:
        """Return user or None. Cross-org reads return None (404-shaped)."""
        user = self._repo.users.get_by_id(user_id)
        if user is None:
            return None
        if self._user.role != UserRole.SUPER_ADMIN:
            if user.organization_id != self._user.organization_id:
                return None
        return user

    def list_users(
        self,
        *,
        organization_id: Optional[str] = None,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
    ) -> List[User]:
        if self._user.role != UserRole.SUPER_ADMIN:
            organization_id = self._user.organization_id
        return self._repo.users.get_by_filters(
            organization_id=organization_id,
            role=role,
            is_active=is_active,
        )


class UserWriteCapability:
    """Write-side user authorization."""

    def __init__(self, repo: Repository, current_user: User) -> None:
        self._repo = repo
        self._user = current_user

    @property
    def repo(self) -> Repository:
        return self._repo

    @property
    def user(self) -> User:
        return self._user

    def _require_admin(self) -> None:
        if self._user.role not in _ADMIN_ROLES:
            raise CapabilityPermissionError("Admin access required")

    def authorize_create(self, organization_id: str, role: UserRole) -> None:
        """Check role + cross-org write permission for user creation."""
        self._require_admin()
        if self._user.role != UserRole.SUPER_ADMIN:
            if self._user.organization_id != organization_id:
                raise CapabilityPermissionError("Can only create users in your own organization")

    def authorize_update(self, existing_user: User) -> None:
        """Check update permission for a target user that was already loaded."""
        self._require_admin()
        if self._user.role != UserRole.SUPER_ADMIN:
            if existing_user.organization_id != self._user.organization_id:
                raise CapabilityPermissionError("Can only update users in your own organization")

    def update(self, user_id: str, command: UserUpdateCommand) -> Optional[User]:
        self._require_admin()
        return self._repo.users.update(user_id, command)

    def require_super_admin_for_delete(self) -> None:
        if self._user.role != UserRole.SUPER_ADMIN:
            raise CapabilityPermissionError("Super Admin access required")
