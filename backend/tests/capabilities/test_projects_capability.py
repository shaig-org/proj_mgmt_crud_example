"""Unit tests for ProjectReadCapability and OrgProjectWriteCapability."""

from __future__ import annotations

from project_management_crud_example.capabilities.projects_capability import (
    OrgProjectWriteCapability,
    ProjectReadCapability,
)
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    ProjectData,
    ProjectUpdateCommand,
    UserRole,
)
from tests.capabilities.helpers import assert_denied, make_user
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import (
    create_test_org_with_workflow_via_repo,
    create_test_project_via_repo,
)


def test_project_read_get_by_id_allows_member(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    project = create_test_project_via_repo(test_repo, org.id, name="P")

    cap = ProjectReadCapability(test_repo, admin)
    result = cap.get_by_id(project.id)
    assert result is not None
    assert result.id == project.id


def test_project_read_get_by_id_returns_none_for_missing(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    cap = ProjectReadCapability(test_repo, admin)
    assert cap.get_by_id("missing-id") is None


def test_project_read_get_by_id_denies_cross_org_user(test_repo: Repository) -> None:
    org_a = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    org_b = create_test_org_with_workflow_via_repo(test_repo, name="Org B")
    cross_user = make_user(test_repo, org_b, UserRole.ADMIN, username="cross_admin")
    project = create_test_project_via_repo(test_repo, org_a.id, name="P")

    cap = ProjectReadCapability(test_repo, cross_user)
    assert_denied(cap.get_by_id, project.id)


def test_project_read_list_projects_scopes_to_user_org(test_repo: Repository) -> None:
    org_a = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    org_b = create_test_org_with_workflow_via_repo(test_repo, name="Org B")
    admin = make_user(test_repo, org_a, UserRole.ADMIN)
    create_test_project_via_repo(test_repo, org_a.id, name="A-proj")
    create_test_project_via_repo(test_repo, org_b.id, name="B-proj")

    cap = ProjectReadCapability(test_repo, admin)
    projects = cap.list_projects()
    names = {p.name for p in projects}
    assert "A-proj" in names
    assert "B-proj" not in names


def test_project_read_list_projects_super_admin_sees_all(test_repo: Repository) -> None:
    org_a = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    org_b = create_test_org_with_workflow_via_repo(test_repo, name="Org B")
    sa = make_user(test_repo, org_a, UserRole.SUPER_ADMIN)
    create_test_project_via_repo(test_repo, org_a.id, name="A-proj")
    create_test_project_via_repo(test_repo, org_b.id, name="B-proj")

    cap = ProjectReadCapability(test_repo, sa)
    names = {p.name for p in cap.list_projects()}
    assert {"A-proj", "B-proj"}.issubset(names)


def test_project_write_create_allows_admin(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    cap = OrgProjectWriteCapability(test_repo, admin)
    command = cap.build_create_command(ProjectData(name="New"))
    project = cap.create(command)
    assert project.organization_id == org.id


def test_project_write_create_denies_read_user(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    read_user = make_user(test_repo, org, UserRole.READ_ACCESS)
    cap = OrgProjectWriteCapability(test_repo, read_user)
    assert_denied(cap.build_create_command, ProjectData(name="nope"))


def test_project_write_update_allows_admin_same_org(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    project = create_test_project_via_repo(test_repo, org.id, name="P")

    cap = OrgProjectWriteCapability(test_repo, admin)
    loaded = cap.load_for_update(project.id)
    assert loaded is not None
    updated = cap.update(project.id, ProjectUpdateCommand(name="P2"))
    assert updated is not None and updated.name == "P2"


def test_project_write_update_denies_regular_user(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    writer = make_user(test_repo, org, UserRole.WRITE_ACCESS)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    cap = OrgProjectWriteCapability(test_repo, writer)
    assert_denied(cap.load_for_update, project.id)


def test_project_write_load_for_update_denies_cross_org_admin(test_repo: Repository) -> None:
    org_a = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    org_b = create_test_org_with_workflow_via_repo(test_repo, name="Org B")
    cross_admin = make_user(test_repo, org_b, UserRole.ADMIN, username="cross_admin")
    project = create_test_project_via_repo(test_repo, org_a.id, name="P")
    cap = OrgProjectWriteCapability(test_repo, cross_admin)
    assert_denied(cap.load_for_update, project.id)


def test_project_write_delete_allows_admin_same_org(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    cap = OrgProjectWriteCapability(test_repo, admin)
    assert cap.load_for_delete(project.id) is not None
    assert cap.delete(project.id) is True


def test_project_write_delete_denies_project_manager(test_repo: Repository) -> None:
    # PROJECT_MANAGER can write/archive but NOT delete
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    pm = make_user(test_repo, org, UserRole.PROJECT_MANAGER)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    cap = OrgProjectWriteCapability(test_repo, pm)
    assert_denied(cap.load_for_delete, project.id)


def test_project_write_archive_allows_pm(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    pm = make_user(test_repo, org, UserRole.PROJECT_MANAGER)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    cap = OrgProjectWriteCapability(test_repo, pm)
    assert cap.load_for_archive(project.id) is not None


def test_project_write_archive_denies_read_user(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    reader = make_user(test_repo, org, UserRole.READ_ACCESS)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    cap = OrgProjectWriteCapability(test_repo, reader)
    assert_denied(cap.load_for_archive, project.id)


def test_project_write_unarchive_denies_pm(test_repo: Repository) -> None:
    # unarchive requires delete-level roles (admin/super admin)
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    pm = make_user(test_repo, org, UserRole.PROJECT_MANAGER)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    cap = OrgProjectWriteCapability(test_repo, pm)
    assert_denied(cap.load_for_unarchive, project.id)
