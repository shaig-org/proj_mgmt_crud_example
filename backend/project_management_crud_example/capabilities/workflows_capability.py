"""Workflow capabilities."""

from typing import List, Optional

from project_management_crud_example.capabilities.errors import CapabilityPermissionError
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    User,
    UserRole,
    Workflow,
    WorkflowCreateCommand,
    WorkflowData,
    WorkflowUpdateCommand,
)

_WRITE_ROLES = {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.PROJECT_MANAGER}
_DELETE_ROLES = {UserRole.SUPER_ADMIN, UserRole.ADMIN}


class WorkflowReadCapability:
    """Read-side workflow authorization."""

    def __init__(self, repo: Repository, current_user: User) -> None:
        self._repo = repo
        self._user = current_user

    @property
    def repo(self) -> Repository:
        return self._repo

    @property
    def user(self) -> User:
        return self._user

    def get_by_id(self, workflow_id: str) -> Optional[Workflow]:
        """Returns None for not-found AND cross-org (existing behavior: 404)."""
        workflow = self._repo.workflows.get_by_id(workflow_id)
        if workflow is None:
            return None
        if self._user.role != UserRole.SUPER_ADMIN:
            if workflow.organization_id != self._user.organization_id:
                return None
        return workflow

    def list_workflows(self) -> List[Workflow]:
        if self._user.role == UserRole.SUPER_ADMIN:
            return self._repo.workflows.get_all()
        if not self._user.organization_id:
            raise ValueError("User has no organization")
        return self._repo.workflows.get_by_organization_id(self._user.organization_id)


class OrgWorkflowWriteCapability:
    """Write-side workflow authorization."""

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

    def _ensure_same_org_for_update(self, workflow: Workflow) -> None:
        if self._user.role == UserRole.SUPER_ADMIN:
            return
        if workflow.organization_id != self._user.organization_id:
            raise CapabilityPermissionError("Cannot update workflow from different organization")

    def _ensure_same_org_for_delete(self, workflow: Workflow) -> None:
        if self._user.role == UserRole.SUPER_ADMIN:
            return
        if workflow.organization_id != self._user.organization_id:
            raise CapabilityPermissionError("Cannot delete workflow from different organization")

    def build_create_command(self, workflow_data: WorkflowData) -> WorkflowCreateCommand:
        self._require_write_role("create workflows")
        if not self._user.organization_id:
            raise ValueError("User has no organization")
        return WorkflowCreateCommand(workflow_data=workflow_data, organization_id=self._user.organization_id)

    def create(self, command: WorkflowCreateCommand) -> Workflow:
        self._require_write_role("create workflows")
        return self._repo.workflows.create(command)

    def load_for_update(self, workflow_id: str) -> Optional[Workflow]:
        self._require_write_role("update workflows")
        workflow = self._repo.workflows.get_by_id(workflow_id)
        if workflow is None:
            return None
        self._ensure_same_org_for_update(workflow)
        return workflow

    def update(self, workflow_id: str, command: WorkflowUpdateCommand) -> Optional[Workflow]:
        self._require_write_role("update workflows")
        return self._repo.workflows.update(workflow_id, command)

    def load_for_delete(self, workflow_id: str) -> Optional[Workflow]:
        self._require_delete_role("delete workflows")
        workflow = self._repo.workflows.get_by_id(workflow_id)
        if workflow is None:
            return None
        self._ensure_same_org_for_delete(workflow)
        return workflow

    def delete(self, workflow_id: str) -> bool:
        self._require_delete_role("delete workflows")
        return self._repo.workflows.delete(workflow_id)
