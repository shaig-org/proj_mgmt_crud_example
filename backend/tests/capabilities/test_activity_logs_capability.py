"""Unit tests for ActivityLogReadCapability."""

from __future__ import annotations

from project_management_crud_example.capabilities.activity_logs_capability import (
    ActivityLogReadCapability,
)
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import ActionType, UserRole
from tests.capabilities.helpers import make_user
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import create_test_activity_log_via_repo, create_test_org_via_repo


def test_activity_log_get_by_id_allows_member(test_repo: Repository) -> None:
    org = create_test_org_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    log = create_test_activity_log_via_repo(
        test_repo,
        organization_id=org.id,
        actor_id=admin.id,
        entity_id="some-ticket",
        action=ActionType.TICKET_CREATED,
    )
    cap = ActivityLogReadCapability(test_repo, admin)
    result = cap.get_by_id(log.id)
    assert result is not None
    assert result.id == log.id


def test_activity_log_get_by_id_cross_org_returns_none(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    org_b = create_test_org_via_repo(test_repo, name="Org B")
    admin_b = make_user(test_repo, org_b, UserRole.ADMIN, username="admin_b")
    admin_a = make_user(test_repo, org_a, UserRole.ADMIN, username="admin_a")
    log = create_test_activity_log_via_repo(
        test_repo,
        organization_id=org_a.id,
        actor_id=admin_a.id,
        entity_id="t",
        action=ActionType.TICKET_CREATED,
    )
    cap = ActivityLogReadCapability(test_repo, admin_b)
    assert cap.get_by_id(log.id) is None


def test_activity_log_get_by_id_super_admin_can_read_any_org(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    org_sa = create_test_org_via_repo(test_repo, name="SA Org")
    sa = make_user(test_repo, org_sa, UserRole.SUPER_ADMIN)
    admin_a = make_user(test_repo, org_a, UserRole.ADMIN, username="admin_a")
    log = create_test_activity_log_via_repo(
        test_repo,
        organization_id=org_a.id,
        actor_id=admin_a.id,
        entity_id="t",
        action=ActionType.TICKET_CREATED,
    )
    cap = ActivityLogReadCapability(test_repo, sa)
    result = cap.get_by_id(log.id)
    assert result is not None
    assert result.id == log.id


def test_activity_log_list_logs_scopes_to_user_org(test_repo: Repository) -> None:
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    org_b = create_test_org_via_repo(test_repo, name="Org B")
    admin_a = make_user(test_repo, org_a, UserRole.ADMIN, username="admin_a")
    admin_b = make_user(test_repo, org_b, UserRole.ADMIN, username="admin_b")
    create_test_activity_log_via_repo(
        test_repo,
        organization_id=org_a.id,
        actor_id=admin_a.id,
        entity_id="ta",
        action=ActionType.TICKET_CREATED,
    )
    create_test_activity_log_via_repo(
        test_repo,
        organization_id=org_b.id,
        actor_id=admin_b.id,
        entity_id="tb",
        action=ActionType.TICKET_CREATED,
    )
    cap = ActivityLogReadCapability(test_repo, admin_a)
    logs = cap.list_logs()
    assert all(log.organization_id == org_a.id for log in logs)


def test_activity_log_list_logs_admin_filter_ignored_for_other_org(test_repo: Repository) -> None:
    # Even if a non-super-admin asks for another org explicitly, the capability
    # should override organization_id to their own org.
    org_a = create_test_org_via_repo(test_repo, name="Org A")
    org_b = create_test_org_via_repo(test_repo, name="Org B")
    admin_a = make_user(test_repo, org_a, UserRole.ADMIN, username="admin_a")
    admin_b = make_user(test_repo, org_b, UserRole.ADMIN, username="admin_b")
    create_test_activity_log_via_repo(
        test_repo,
        organization_id=org_b.id,
        actor_id=admin_b.id,
        entity_id="tb",
        action=ActionType.TICKET_CREATED,
    )
    cap = ActivityLogReadCapability(test_repo, admin_a)
    logs = cap.list_logs(organization_id=org_b.id)
    assert all(log.organization_id == org_a.id for log in logs)
