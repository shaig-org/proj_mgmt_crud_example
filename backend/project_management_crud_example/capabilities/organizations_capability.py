"""Organization capabilities — split by scope.

- `OrganizationReadCapability` — any member can read their own org; super
  admins can read any org.
- `GlobalOrganizationWriteCapability` — super-admin-only create/update/delete.
  Scope is GLOBAL, not org-bound. Admin role is enforced at the DI factory
  so non-super-admins cannot even construct it.
"""

from typing import List, Optional

from project_management_crud_example.capabilities.errors import CapabilityPermissionError
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    Organization,
    OrganizationCreateCommand,
    OrganizationUpdateCommand,
    User,
    UserRole,
)


class OrganizationReadCapability:
    """Read-side organization authorization."""

    def __init__(self, repo: Repository, current_user: User) -> None:
        self._repo = repo
        self._user = current_user

    @property
    def repo(self) -> Repository:
        return self._repo

    @property
    def user(self) -> User:
        return self._user

    def get_by_id(self, organization_id: str) -> Optional[Organization]:
        organization = self._repo.organizations.get_by_id(organization_id)
        if organization is None:
            return None
        if self._user.role != UserRole.SUPER_ADMIN:
            if self._user.organization_id != organization_id:
                raise CapabilityPermissionError("Cannot access other organizations")
        return organization

    def list_visible(self) -> List[Organization]:
        if self._user.role == UserRole.SUPER_ADMIN:
            return self._repo.organizations.get_all()
        if not self._user.organization_id:
            return []
        org = self._repo.organizations.get_by_id(self._user.organization_id)
        return [org] if org else []


class GlobalOrganizationWriteCapability:
    """Create / update / delete organizations.

    Scope is GLOBAL (super-admin only). Must be constructed via
    `get_global_organization_write_capability`, which enforces the role at
    the DI boundary so non-super-admins cannot even construct it.
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

    def create(self, command: OrganizationCreateCommand) -> Organization:
        return self._repo.organizations.create(command)

    def update(self, organization_id: str, command: OrganizationUpdateCommand) -> Optional[Organization]:
        return self._repo.organizations.update(organization_id, command)

    def delete(self, organization_id: str) -> bool:
        return self._repo.organizations.delete(organization_id)
