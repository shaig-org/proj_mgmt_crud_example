"""Unit tests for UserReadCapability, SelfUserWriteCapability, OrgUserWriteCapability."""

from __future__ import annotations

import inspect

from project_management_crud_example.capabilities.users_capability import (
    OrgUserWriteCapability,
    SelfUserWriteCapability,
    UserReadCapability,
)
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import SelfUserUpdateCommand, UserRole, UserUpdateCommand
from tests.capabilities.helpers import assert_denied, make_user
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import create_test_org_via_repo

# ---------------------------------------------------------------------------
# UserReadCapability
# ---------------------------------------------------------------------------


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
    assert cap.get_by_id(other_b.id) is None


def test_user_read_list_users_scopes_to_user_org(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    org_b = create_test_org_via_repo(test_repo, name="Org B")
    admin_a = make_user(test_repo, org_a, UserRole.ADMIN, username="admin_a")
    make_user(test_repo, org_b, UserRole.WRITE_ACCESS, username="other_b")
    cap = UserReadCapability(test_repo, admin_a)
    users = cap.list_users()
    assert {u.organization_id for u in users} == {org_a.id}


# ---------------------------------------------------------------------------
# SelfUserWriteCapability — scope is baked in. No method accepts user_id.
# ---------------------------------------------------------------------------


def test_self_user_write_has_no_method_accepting_user_id() -> None:
    """Structural guard: no method on SelfUserWriteCapability takes a user_id.

    If someone adds a `user_id`-shaped parameter here, the capability has lost
    its bake-in property and this test must fail so the reviewer notices.
    """
    for name, member in inspect.getmembers(SelfUserWriteCapability, inspect.isfunction):
        if name.startswith("_"):
            continue
        params = inspect.signature(member).parameters
        for param_name in params:
            assert "user_id" not in param_name.lower(), (
                f"SelfUserWriteCapability.{name} accepts `{param_name}`; scope must stay baked into the instance."
            )


def test_self_user_write_update_profile_updates_only_self(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    writer = make_user(test_repo, org, UserRole.WRITE_ACCESS)
    other = make_user(test_repo, org, UserRole.WRITE_ACCESS, username="other")
    cap = SelfUserWriteCapability(test_repo, writer)
    updated = cap.update_profile(SelfUserUpdateCommand(full_name="Renamed"))
    assert updated is not None and updated.id == writer.id and updated.full_name == "Renamed"
    # `other` must be untouched
    other_refreshed = test_repo.users.get_by_id(other.id)
    assert other_refreshed is not None and other_refreshed.full_name != "Renamed"


def test_self_user_update_command_has_no_role_or_is_active_field() -> None:
    """Privilege-escalation guard: SelfUserUpdateCommand must NOT expose role/is_active."""
    fields = set(SelfUserUpdateCommand.model_fields.keys())
    assert "role" not in fields
    assert "is_active" not in fields


# ---------------------------------------------------------------------------
# OrgUserWriteCapability — admin-gated via DI factory; tested at capability
# level only for the same-org vs cross-org rule. Admin gate is tested in the
# API layer (test_user_api.py::test_update_user_as_regular_user_fails).
# ---------------------------------------------------------------------------


def test_org_user_write_authorize_create_allows_admin_in_own_org(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    cap = OrgUserWriteCapability(test_repo, admin)
    cap.authorize_create(org.id, UserRole.WRITE_ACCESS)  # no raise


def test_org_user_write_authorize_create_denies_cross_org_admin(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    org_b = create_test_org_via_repo(test_repo, name="Org B")
    admin_b = make_user(test_repo, org_b, UserRole.ADMIN, username="admin_b")
    cap = OrgUserWriteCapability(test_repo, admin_b)
    assert_denied(cap.authorize_create, org_a.id, UserRole.WRITE_ACCESS)


def test_org_user_write_authorize_update_allows_admin_same_org(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    target = make_user(test_repo, org, UserRole.WRITE_ACCESS, username="target")
    cap = OrgUserWriteCapability(test_repo, admin)
    cap.authorize_update(target)  # no raise


def test_org_user_write_authorize_update_denies_cross_org_admin(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    org_b = create_test_org_via_repo(test_repo, name="Org B")
    admin_b = make_user(test_repo, org_b, UserRole.ADMIN, username="admin_b")
    target_a = make_user(test_repo, org_a, UserRole.WRITE_ACCESS, username="target_a")
    cap = OrgUserWriteCapability(test_repo, admin_b)
    assert_denied(cap.authorize_update, target_a)


def test_org_user_write_update_returns_updated(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    target = make_user(test_repo, org, UserRole.WRITE_ACCESS, username="target")
    cap = OrgUserWriteCapability(test_repo, admin)
    updated = cap.update(target.id, UserUpdateCommand(full_name="New Name"))
    assert updated is not None and updated.full_name == "New Name"


def test_org_user_write_update_denies_cross_org(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    org_b = create_test_org_via_repo(test_repo, name="Org B")
    admin_b = make_user(test_repo, org_b, UserRole.ADMIN, username="admin_b")
    target_a = make_user(test_repo, org_a, UserRole.WRITE_ACCESS, username="target_a")
    cap = OrgUserWriteCapability(test_repo, admin_b)
    assert_denied(cap.update, target_a.id, UserUpdateCommand(full_name="Hacked"))


def test_org_user_write_require_super_admin_for_delete_allows_super_admin(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    sa = make_user(test_repo, org, UserRole.SUPER_ADMIN)
    cap = OrgUserWriteCapability(test_repo, sa)
    cap.require_super_admin_for_delete()  # no raise


def test_org_user_write_require_super_admin_for_delete_denies_admin(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    cap = OrgUserWriteCapability(test_repo, admin)
    assert_denied(cap.require_super_admin_for_delete)
