"""Unit tests for WorkflowReadCapability and WorkflowWriteCapability."""

from __future__ import annotations

from project_management_crud_example.capabilities.workflows_capability import (
    WorkflowReadCapability,
    WorkflowWriteCapability,
)
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import UserRole, WorkflowData, WorkflowUpdateCommand
from tests.capabilities.helpers import assert_denied, make_user
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import create_test_org_with_workflow_via_repo


def _default_workflow_id(test_repo: Repository, org_id: str) -> str:
    workflows = test_repo.workflows.get_by_organization_id(org_id)
    assert workflows, "expected at least one workflow"
    return workflows[0].id


def test_workflow_read_get_by_id_allows_member(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    wid = _default_workflow_id(test_repo, org.id)
    cap = WorkflowReadCapability(test_repo, admin)
    result = cap.get_by_id(wid)
    assert result is not None
    assert result.id == wid


def test_workflow_read_get_by_id_cross_org_returns_none(test_repo: Repository) -> None:
    org_a = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    org_b = create_test_org_with_workflow_via_repo(test_repo, name="Org B")
    admin_b = make_user(test_repo, org_b, UserRole.ADMIN, username="admin_b")
    wid_a = _default_workflow_id(test_repo, org_a.id)
    cap = WorkflowReadCapability(test_repo, admin_b)
    assert cap.get_by_id(wid_a) is None


def test_workflow_read_list_scopes_to_user_org(test_repo: Repository) -> None:
    org_a = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    org_b = create_test_org_with_workflow_via_repo(test_repo, name="Org B")
    admin_a = make_user(test_repo, org_a, UserRole.ADMIN, username="admin_a")
    cap = WorkflowReadCapability(test_repo, admin_a)
    workflows = cap.list_workflows()
    org_ids = {w.organization_id for w in workflows}
    assert org_ids == {org_a.id}
    assert org_b.id not in org_ids


def test_workflow_write_create_allows_pm(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    pm = make_user(test_repo, org, UserRole.PROJECT_MANAGER)
    cap = WorkflowWriteCapability(test_repo, pm)
    cmd = cap.build_create_command(WorkflowData(name="Custom", statuses=["A", "B"]))
    wf = cap.create(cmd)
    assert wf.organization_id == org.id


def test_workflow_write_create_denies_write_user(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    writer = make_user(test_repo, org, UserRole.WRITE_ACCESS)
    cap = WorkflowWriteCapability(test_repo, writer)
    assert_denied(cap.build_create_command, WorkflowData(name="x", statuses=["A", "B"]))


def test_workflow_write_load_for_update_allows_admin(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    wid = _default_workflow_id(test_repo, org.id)
    cap = WorkflowWriteCapability(test_repo, admin)
    assert cap.load_for_update(wid) is not None


def test_workflow_write_load_for_update_denies_cross_org(test_repo: Repository) -> None:
    org_a = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    org_b = create_test_org_with_workflow_via_repo(test_repo, name="Org B")
    admin_b = make_user(test_repo, org_b, UserRole.ADMIN, username="admin_b")
    wid = _default_workflow_id(test_repo, org_a.id)
    cap = WorkflowWriteCapability(test_repo, admin_b)
    assert_denied(cap.load_for_update, wid)


def test_workflow_write_update_returns_updated(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    wid = _default_workflow_id(test_repo, org.id)
    cap = WorkflowWriteCapability(test_repo, admin)
    updated = cap.update(wid, WorkflowUpdateCommand(name="Renamed"))
    assert updated is not None and updated.name == "Renamed"


def test_workflow_write_load_for_delete_denies_pm(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    pm = make_user(test_repo, org, UserRole.PROJECT_MANAGER)
    wid = _default_workflow_id(test_repo, org.id)
    cap = WorkflowWriteCapability(test_repo, pm)
    assert_denied(cap.load_for_delete, wid)


def test_workflow_write_load_for_delete_denies_read_user(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    reader = make_user(test_repo, org, UserRole.READ_ACCESS)
    wid = _default_workflow_id(test_repo, org.id)
    cap = WorkflowWriteCapability(test_repo, reader)
    assert_denied(cap.load_for_delete, wid)
