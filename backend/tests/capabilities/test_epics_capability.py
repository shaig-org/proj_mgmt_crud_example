"""Unit tests for EpicReadCapability and OrgEpicWriteCapability."""

from __future__ import annotations

from project_management_crud_example.capabilities.epics_capability import (
    EpicReadCapability,
    OrgEpicWriteCapability,
)
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import EpicData, EpicUpdateCommand, UserRole
from tests.capabilities.helpers import assert_denied, make_user
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import create_test_epic_via_repo, create_test_org_via_repo


def test_epic_read_get_by_id_allows_member(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    epic = create_test_epic_via_repo(test_repo, org.id, name="E")
    cap = EpicReadCapability(test_repo, admin)
    result = cap.get_by_id(epic.id)
    assert result is not None
    assert result.id == epic.id


def test_epic_read_get_by_id_denies_cross_org(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    org_b = create_test_org_via_repo(test_repo, name="Org B")
    admin_b = make_user(test_repo, org_b, UserRole.ADMIN, username="admin_b")
    epic = create_test_epic_via_repo(test_repo, org_a.id, name="E")
    cap = EpicReadCapability(test_repo, admin_b)
    assert_denied(cap.get_by_id, epic.id)


def test_epic_read_list_scopes_to_user_org(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    org_b = create_test_org_via_repo(test_repo, name="Org B")
    admin_a = make_user(test_repo, org_a, UserRole.ADMIN, username="admin_a")
    create_test_epic_via_repo(test_repo, org_a.id, name="A-epic")
    create_test_epic_via_repo(test_repo, org_b.id, name="B-epic")
    cap = EpicReadCapability(test_repo, admin_a)
    names = {e.name for e in cap.list_epics()}
    assert "A-epic" in names and "B-epic" not in names


def test_epic_read_list_super_admin_sees_all(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    org_b = create_test_org_via_repo(test_repo, name="Org B")
    sa = make_user(test_repo, org_a, UserRole.SUPER_ADMIN)
    create_test_epic_via_repo(test_repo, org_a.id, name="A-epic")
    create_test_epic_via_repo(test_repo, org_b.id, name="B-epic")
    cap = EpicReadCapability(test_repo, sa)
    names = {e.name for e in cap.list_epics()}
    assert {"A-epic", "B-epic"}.issubset(names)


def test_epic_write_create_allows_pm(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    pm = make_user(test_repo, org, UserRole.PROJECT_MANAGER)
    cap = OrgEpicWriteCapability(test_repo, pm)
    command = cap.build_create_command(EpicData(name="New"))
    epic = cap.create(command)
    assert epic.organization_id == org.id


def test_epic_write_create_denies_write_user(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    writer = make_user(test_repo, org, UserRole.WRITE_ACCESS)
    cap = OrgEpicWriteCapability(test_repo, writer)
    assert_denied(cap.build_create_command, EpicData(name="x"))


def test_epic_write_load_for_update_allows_admin(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    epic = create_test_epic_via_repo(test_repo, org.id, name="E")
    cap = OrgEpicWriteCapability(test_repo, admin)
    assert cap.load_for_update(epic.id) is not None


def test_epic_write_load_for_update_denies_cross_org(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    org_b = create_test_org_via_repo(test_repo, name="Org B")
    admin_b = make_user(test_repo, org_b, UserRole.ADMIN, username="admin_b")
    epic = create_test_epic_via_repo(test_repo, org_a.id, name="E")
    cap = OrgEpicWriteCapability(test_repo, admin_b)
    assert_denied(cap.load_for_update, epic.id)


def test_epic_write_update_returns_updated(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    epic = create_test_epic_via_repo(test_repo, org.id, name="E")
    cap = OrgEpicWriteCapability(test_repo, admin)
    updated = cap.update(epic.id, EpicUpdateCommand(name="E2"))
    assert updated is not None and updated.name == "E2"


def test_epic_write_load_for_delete_denies_pm(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    pm = make_user(test_repo, org, UserRole.PROJECT_MANAGER)
    epic = create_test_epic_via_repo(test_repo, org.id, name="E")
    cap = OrgEpicWriteCapability(test_repo, pm)
    assert_denied(cap.load_for_delete, epic.id)


def test_epic_write_delete_allows_admin(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    epic = create_test_epic_via_repo(test_repo, org.id, name="E")
    cap = OrgEpicWriteCapability(test_repo, admin)
    cap.load_for_delete(epic.id)
    assert cap.delete(epic.id) is True
