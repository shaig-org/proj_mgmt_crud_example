"""Unit tests for TicketReadCapability and TicketWriteCapability."""

from __future__ import annotations

from project_management_crud_example.capabilities.tickets_capability import (
    TicketReadCapability,
    TicketWriteCapability,
)
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    TicketCreateCommand,
    TicketData,
    UserRole,
)
from tests.capabilities.helpers import assert_denied, make_user
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import create_test_org_with_workflow_via_repo, create_test_project_via_repo


def _make_ticket(test_repo: Repository, project_id: str, reporter_id: str, title: str = "T") -> str:
    cmd = TicketCreateCommand(
        ticket_data=TicketData(title=title),
        project_id=project_id,
    )
    ticket = test_repo.tickets.create(cmd, reporter_id=reporter_id)
    return ticket.id


def test_ticket_read_get_by_id_allows_member(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    tid = _make_ticket(test_repo, project.id, admin.id)
    cap = TicketReadCapability(test_repo, admin)
    result = cap.get_by_id(tid)
    assert result is not None
    assert result.id == tid


def test_ticket_read_get_by_id_denies_cross_org(test_repo: Repository) -> None:
    org_a = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    org_b = create_test_org_with_workflow_via_repo(test_repo, name="Org B")
    admin_a = make_user(test_repo, org_a, UserRole.ADMIN, username="admin_a")
    admin_b = make_user(test_repo, org_b, UserRole.ADMIN, username="admin_b")
    project_a = create_test_project_via_repo(test_repo, org_a.id, name="PA")
    tid = _make_ticket(test_repo, project_a.id, admin_a.id)
    cap = TicketReadCapability(test_repo, admin_b)
    assert_denied(cap.get_by_id, tid)


def test_ticket_read_list_scopes_to_user_org(test_repo: Repository) -> None:
    org_a = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    org_b = create_test_org_with_workflow_via_repo(test_repo, name="Org B")
    admin_a = make_user(test_repo, org_a, UserRole.ADMIN, username="admin_a")
    admin_b = make_user(test_repo, org_b, UserRole.ADMIN, username="admin_b")
    p_a = create_test_project_via_repo(test_repo, org_a.id, name="PA")
    p_b = create_test_project_via_repo(test_repo, org_b.id, name="PB")
    _make_ticket(test_repo, p_a.id, admin_a.id, title="A1")
    _make_ticket(test_repo, p_b.id, admin_b.id, title="B1")
    cap = TicketReadCapability(test_repo, admin_a)
    titles = {t.title for t in cap.list_tickets()}
    assert "A1" in titles and "B1" not in titles


def test_ticket_write_authorize_create_allows_write_user(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    writer = make_user(test_repo, org, UserRole.WRITE_ACCESS)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    cap = TicketWriteCapability(test_repo, writer)
    cap.authorize_create(project)  # no raise


def test_ticket_write_authorize_create_denies_read_user(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    reader = make_user(test_repo, org, UserRole.READ_ACCESS)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    cap = TicketWriteCapability(test_repo, reader)
    assert_denied(cap.authorize_create, project)


def test_ticket_write_authorize_create_denies_cross_org(test_repo: Repository) -> None:
    org_a = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    org_b = create_test_org_with_workflow_via_repo(test_repo, name="Org B")
    writer_b = make_user(test_repo, org_b, UserRole.WRITE_ACCESS, username="writer_b")
    project_a = create_test_project_via_repo(test_repo, org_a.id, name="PA")
    cap = TicketWriteCapability(test_repo, writer_b)
    assert_denied(cap.authorize_create, project_a)


def test_ticket_write_authorize_assignee_denies_cross_org(test_repo: Repository) -> None:
    org_a = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    org_b = create_test_org_with_workflow_via_repo(test_repo, name="Org B")
    admin_a = make_user(test_repo, org_a, UserRole.ADMIN, username="admin_a")
    cross_assignee = make_user(test_repo, org_b, UserRole.WRITE_ACCESS, username="cross")
    cap = TicketWriteCapability(test_repo, admin_a)
    assert_denied(cap.authorize_assignee, cross_assignee)


def test_ticket_write_authorize_move_requires_pm(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    writer = make_user(test_repo, org, UserRole.WRITE_ACCESS)
    p1 = create_test_project_via_repo(test_repo, org.id, name="P1")
    p2 = create_test_project_via_repo(test_repo, org.id, name="P2")
    cap = TicketWriteCapability(test_repo, writer)
    # WRITE_ACCESS is NOT in _MOVE_OR_ASSIGN_ROLES
    assert_denied(cap.authorize_move, p1, p2)


def test_ticket_write_authorize_assign_allows_pm(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    pm = make_user(test_repo, org, UserRole.PROJECT_MANAGER)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    cap = TicketWriteCapability(test_repo, pm)
    cap.authorize_assign(project)  # no raise


def test_ticket_write_authorize_delete_denies_pm(test_repo: Repository) -> None:
    # PM can update/move/assign but NOT delete
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    pm = make_user(test_repo, org, UserRole.PROJECT_MANAGER)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    cap = TicketWriteCapability(test_repo, pm)
    assert_denied(cap.authorize_delete, project)


def test_ticket_write_authorize_delete_allows_admin(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    cap = TicketWriteCapability(test_repo, admin)
    cap.authorize_delete(project)  # no raise
