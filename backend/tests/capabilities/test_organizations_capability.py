"""Unit tests for OrganizationReadCapability and GlobalOrganizationWriteCapability.

The super-admin gate on writes is enforced by the DI factory, not inside the
capability methods. The class-level tests here cover behavior on valid calls
plus the cross-org read rule. Factory-level role enforcement is covered by
API tests that hit the routes as non-super-admin roles.
"""

from __future__ import annotations

from project_management_crud_example.capabilities.organizations_capability import (
    GlobalOrganizationWriteCapability,
    OrganizationReadCapability,
)
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

# ---------------------------------------------------------------------------
# OrganizationReadCapability
# ---------------------------------------------------------------------------


def test_org_read_get_by_id_allows_member(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    cap = OrganizationReadCapability(test_repo, admin)
    result = cap.get_by_id(org.id)
    assert result is not None and result.id == org.id


def test_org_read_get_by_id_denies_non_member(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    org_b = create_test_org_via_repo(test_repo, name="Org B")
    admin_b = make_user(test_repo, org_b, UserRole.ADMIN, username="admin_b")
    cap = OrganizationReadCapability(test_repo, admin_b)
    assert_denied(cap.get_by_id, org_a.id)


def test_org_read_list_visible_super_admin_sees_all(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    org_b = create_test_org_via_repo(test_repo, name="Org B")
    sa = make_user(test_repo, org_a, UserRole.SUPER_ADMIN)
    cap = OrganizationReadCapability(test_repo, sa)
    ids = {o.id for o in cap.list_visible()}
    assert {org_a.id, org_b.id}.issubset(ids)


def test_org_read_list_visible_admin_sees_only_own(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    create_test_org_via_repo(test_repo, name="Org B")
    admin_a = make_user(test_repo, org_a, UserRole.ADMIN)
    cap = OrganizationReadCapability(test_repo, admin_a)
    visible = cap.list_visible()
    assert [o.id for o in visible] == [org_a.id]


# ---------------------------------------------------------------------------
# GlobalOrganizationWriteCapability — SA-gated at DI factory
# ---------------------------------------------------------------------------


def test_global_org_write_create_persists(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    sa = make_user(test_repo, org, UserRole.SUPER_ADMIN)
    cap = GlobalOrganizationWriteCapability(test_repo, sa)
    new_org = cap.create(OrganizationCreateCommand(organization_data=OrganizationData(name="New")))
    assert new_org.name == "New"


def test_global_org_write_update_persists(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    sa = make_user(test_repo, org, UserRole.SUPER_ADMIN)
    cap = GlobalOrganizationWriteCapability(test_repo, sa)
    updated = cap.update(org.id, OrganizationUpdateCommand(name="A2"))
    assert updated is not None and updated.name == "A2"


def test_global_org_write_delete_persists(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    sa = make_user(test_repo, org, UserRole.SUPER_ADMIN)
    target = create_test_org_via_repo(test_repo, name="Doomed")
    cap = GlobalOrganizationWriteCapability(test_repo, sa)
    assert cap.delete(target.id) is True
