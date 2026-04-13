"""Unit tests for OrganizationCapability."""

from __future__ import annotations

from project_management_crud_example.capabilities.organizations_capability import OrganizationCapability
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    OrganizationCreateCommand,
    OrganizationData,
    OrganizationUpdateCommand,
    UserRole,
)
from tests.capabilities.helpers import assert_denied, make_user
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import create_test_org_via_repo


def test_org_get_by_id_allows_member(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    cap = OrganizationCapability(test_repo, admin)
    result = cap.get_by_id(org.id)
    assert result is not None
    assert result.id == org.id


def test_org_get_by_id_denies_non_member(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    org_b = create_test_org_via_repo(test_repo, name="Org B")
    admin_b = make_user(test_repo, org_b, UserRole.ADMIN, username="admin_b")
    cap = OrganizationCapability(test_repo, admin_b)
    assert_denied(cap.get_by_id, org_a.id)


def test_org_list_visible_super_admin_sees_all(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    org_b = create_test_org_via_repo(test_repo, name="Org B")
    sa = make_user(test_repo, org_a, UserRole.SUPER_ADMIN)
    cap = OrganizationCapability(test_repo, sa)
    ids = {o.id for o in cap.list_visible()}
    assert {org_a.id, org_b.id}.issubset(ids)


def test_org_list_visible_admin_sees_only_own(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    create_test_org_via_repo(test_repo, name="Org B")
    admin_a = make_user(test_repo, org_a, UserRole.ADMIN)
    cap = OrganizationCapability(test_repo, admin_a)
    visible = cap.list_visible()
    assert [o.id for o in visible] == [org_a.id]


def test_org_create_allows_super_admin(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    sa = make_user(test_repo, org, UserRole.SUPER_ADMIN)
    cap = OrganizationCapability(test_repo, sa)
    new_org = cap.create(OrganizationCreateCommand(organization_data=OrganizationData(name="New")))
    assert new_org.name == "New"


def test_org_create_denies_admin(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    cap = OrganizationCapability(test_repo, admin)
    assert_denied(cap.create, OrganizationCreateCommand(organization_data=OrganizationData(name="X")))


def test_org_update_allows_super_admin(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    sa = make_user(test_repo, org, UserRole.SUPER_ADMIN)
    cap = OrganizationCapability(test_repo, sa)
    updated = cap.update(org.id, OrganizationUpdateCommand(name="A2"))
    assert updated is not None and updated.name == "A2"


def test_org_update_denies_admin(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    cap = OrganizationCapability(test_repo, admin)
    assert_denied(cap.update, org.id, OrganizationUpdateCommand(name="A2"))


def test_org_delete_allows_super_admin(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    sa = make_user(test_repo, org, UserRole.SUPER_ADMIN)
    cap = OrganizationCapability(test_repo, sa)
    # SA may not be in same org as one being deleted; set up another org to delete
    target = create_test_org_via_repo(test_repo, name="Doomed")
    assert cap.delete(target.id) is True


def test_org_delete_denies_admin(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    cap = OrganizationCapability(test_repo, admin)
    assert_denied(cap.delete, org.id)
