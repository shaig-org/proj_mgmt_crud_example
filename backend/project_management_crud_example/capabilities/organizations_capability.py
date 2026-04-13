"""Organization capability (single class; super-admin-only writes)."""

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


class OrganizationCapability:
    """Organization read + write. Writes are Super-Admin-only."""

    def __init__(self, repo: Repository, current_user: User) -> None:
        self._repo = repo
        self._user = current_user

    @property
    def repo(self) -> Repository:
        return self._repo

    @property
    def user(self) -> User:
        return self._user

    def _require_super_admin(self) -> None:
        if self._user.role != UserRole.SUPER_ADMIN:
            raise CapabilityPermissionError("Super Admin access required")

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

    def create(self, command: OrganizationCreateCommand) -> Organization:
        self._require_super_admin()
        return self._repo.organizations.create(command)

    def update(self, organization_id: str, command: OrganizationUpdateCommand) -> Optional[Organization]:
        self._require_super_admin()
        return self._repo.organizations.update(organization_id, command)

    def delete(self, organization_id: str) -> bool:
        self._require_super_admin()
        return self._repo.organizations.delete(organization_id)
