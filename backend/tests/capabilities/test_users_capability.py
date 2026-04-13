"""Unit tests for UserReadCapability and UserWriteCapability."""

from __future__ import annotations

from project_management_crud_example.capabilities.users_capability import (
    UserReadCapability,
    UserWriteCapability,
)
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import UserRole, UserUpdateCommand
from tests.capabilities.helpers import assert_denied, make_user
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import create_test_org_via_repo


def test_user_read_get_by_id_returns_self_for_any_role(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    reader = make_user(test_repo, org, UserRole.READ_ACCESS)
    cap = UserReadCapability(test_repo, reader)
    result = cap.get_by_id(reader.id)
    assert result is not None
    assert result.id == reader.id


def test_user_read_get_by_id_other_in_same_org_allowed(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    other = make_user(test_repo, org, UserRole.WRITE_ACCESS, username="other")
    cap = UserReadCapability(test_repo, admin)
    result = cap.get_by_id(other.id)
    assert result is not None
    assert result.id == other.id


def test_user_read_get_by_id_cross_org_returns_none(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    org_b = create_test_org_via_repo(test_repo, name="Org B")
    admin_a = make_user(test_repo, org_a, UserRole.ADMIN, username="admin_a")
    other_b = make_user(test_repo, org_b, UserRole.WRITE_ACCESS, username="other_b")
    cap = UserReadCapability(test_repo, admin_a)
    # Cross-org reads return None (404-shaped) — preserves existing router behavior
    assert cap.get_by_id(other_b.id) is None


def test_user_read_list_users_scopes_to_user_org(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    org_b = create_test_org_via_repo(test_repo, name="Org B")
    admin_a = make_user(test_repo, org_a, UserRole.ADMIN, username="admin_a")
    make_user(test_repo, org_b, UserRole.WRITE_ACCESS, username="other_b")
    cap = UserReadCapability(test_repo, admin_a)
    users = cap.list_users()
    org_ids = {u.organization_id for u in users}
    assert org_ids == {org_a.id}


def test_user_write_authorize_create_allows_admin_in_own_org(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    cap = UserWriteCapability(test_repo, admin)
    cap.authorize_create(org.id, UserRole.WRITE_ACCESS)  # no raise


def test_user_write_authorize_create_denies_non_admin(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    pm = make_user(test_repo, org, UserRole.PROJECT_MANAGER)
    cap = UserWriteCapability(test_repo, pm)
    assert_denied(cap.authorize_create, org.id, UserRole.WRITE_ACCESS)


def test_user_write_authorize_create_denies_cross_org_admin(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    org_b = create_test_org_via_repo(test_repo, name="Org B")
    admin_b = make_user(test_repo, org_b, UserRole.ADMIN, username="admin_b")
    cap = UserWriteCapability(test_repo, admin_b)
    assert_denied(cap.authorize_create, org_a.id, UserRole.WRITE_ACCESS)


def test_user_write_authorize_update_allows_admin_same_org(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    target = make_user(test_repo, org, UserRole.WRITE_ACCESS, username="target")
    cap = UserWriteCapability(test_repo, admin)
    cap.authorize_update(target)  # no raise


def test_user_write_authorize_update_denies_cross_org_admin(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    org_b = create_test_org_via_repo(test_repo, name="Org B")
    admin_b = make_user(test_repo, org_b, UserRole.ADMIN, username="admin_b")
    target_a = make_user(test_repo, org_a, UserRole.WRITE_ACCESS, username="target_a")
    cap = UserWriteCapability(test_repo, admin_b)
    assert_denied(cap.authorize_update, target_a)


def test_user_write_authorize_update_denies_regular_user(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    writer = make_user(test_repo, org, UserRole.WRITE_ACCESS)
    target = make_user(test_repo, org, UserRole.READ_ACCESS, username="reader")
    cap = UserWriteCapability(test_repo, writer)
    assert_denied(cap.authorize_update, target)


def test_user_write_update_returns_updated(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    target = make_user(test_repo, org, UserRole.WRITE_ACCESS, username="target")
    cap = UserWriteCapability(test_repo, admin)
    updated = cap.update(target.id, UserUpdateCommand(full_name="New Name"))
    assert updated is not None and updated.full_name == "New Name"


def test_user_write_require_super_admin_for_delete_allows_super_admin(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    sa = make_user(test_repo, org, UserRole.SUPER_ADMIN)
    cap = UserWriteCapability(test_repo, sa)
    cap.require_super_admin_for_delete()  # no raise


def test_user_write_require_super_admin_for_delete_denies_admin(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    cap = UserWriteCapability(test_repo, admin)
    assert_denied(cap.require_super_admin_for_delete)
