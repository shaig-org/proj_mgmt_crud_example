"""User capabilities.

Write capabilities are split by SCOPE, baked in at construction:

- `SelfUserWriteCapability` — target is ALWAYS the authenticated user. Methods
  take no `user_id` argument. There is no way, via this capability, to reach
  another user's record. Body type is `SelfUserUpdateCommand` which omits
  `role` and `is_active`, so privilege escalation is blocked at the type level.

- `OrgUserWriteCapability` — target is any user in the caller's organization.
  Admin-gated at the DI factory: a non-admin cannot even construct it. Super
  admins bypass the org boundary. Methods take `user_id`.

The split is deliberate: the capability TYPE on each endpoint's `Depends(...)`
declares the maximum reach. Widening an endpoint from Self→Org is a visible
type change and shows up in `evidence/capabilities/baseline.json`.
"""

from typing import List, Optional

from project_management_crud_example.capabilities.errors import CapabilityPermissionError
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    SelfUserUpdateCommand,
    User,
    UserRole,
    UserUpdateCommand,
)

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


class SelfUserWriteCapability:
    """Write access to EXACTLY the authenticated user's own record.

    The target user id is captured at construction and is not a method
    parameter. No method on this class accepts `user_id`.
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

    def update_profile(self, command: SelfUserUpdateCommand) -> Optional[User]:
        """Update the authenticated user's own profile fields.

        Only fields present on `SelfUserUpdateCommand` (email, full_name) can
        be touched. `role` and `is_active` are not representable in this
        command type, so they cannot be set via this path.
        """
        wide_command = UserUpdateCommand(email=command.email, full_name=command.full_name)
        return self._repo.users.update(self._user.id, wide_command)


class OrgUserWriteCapability:
    """Write access to any user in the caller's organization.

    Must be constructed via `get_org_user_write_capability`, which enforces
    admin role at the DI boundary. Super admins bypass the org check.
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

    def _require_same_org_or_super(self, target: User) -> None:
        if self._user.role == UserRole.SUPER_ADMIN:
            return
        if target.organization_id != self._user.organization_id:
            raise CapabilityPermissionError("Can only write users in your own organization")

    def authorize_create(self, organization_id: str, role: UserRole) -> None:
        if self._user.role != UserRole.SUPER_ADMIN:
            if self._user.organization_id != organization_id:
                raise CapabilityPermissionError("Can only create users in your own organization")

    def authorize_update(self, existing_user: User) -> None:
        self._require_same_org_or_super(existing_user)

    def update(self, user_id: str, command: UserUpdateCommand) -> Optional[User]:
        target = self._repo.users.get_by_id(user_id)
        if target is None:
            return None
        self._require_same_org_or_super(target)
        return self._repo.users.update(user_id, command)

    def require_super_admin_for_delete(self) -> None:
        if self._user.role != UserRole.SUPER_ADMIN:
            raise CapabilityPermissionError("Super Admin access required")
