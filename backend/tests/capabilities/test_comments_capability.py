"""Unit tests for CommentCapability."""

from __future__ import annotations

from project_management_crud_example.capabilities.comments_capability import CommentCapability
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    CommentCreateCommand,
    CommentData,
    CommentUpdateCommand,
    Ticket,
    TicketCreateCommand,
    TicketData,
    UserRole,
)
from tests.capabilities.helpers import assert_denied, make_user
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import create_test_org_with_workflow_via_repo, create_test_project_via_repo


def _make_ticket(test_repo: Repository, project_id: str, reporter_id: str) -> Ticket:
    return test_repo.tickets.create(
        TicketCreateCommand(ticket_data=TicketData(title="T"), project_id=project_id),
        reporter_id=reporter_id,
    )


def test_comment_load_ticket_for_access_allows_member(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    ticket = _make_ticket(test_repo, project.id, admin.id)
    cap = CommentCapability(test_repo, admin)
    result = cap.load_ticket_for_access(ticket.id)
    assert result is not None
    assert result.id == ticket.id


def test_comment_load_ticket_for_access_denies_cross_org(test_repo: Repository) -> None:
    org_a = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    org_b = create_test_org_with_workflow_via_repo(test_repo, name="Org B")
    admin_a = make_user(test_repo, org_a, UserRole.ADMIN, username="admin_a")
    admin_b = make_user(test_repo, org_b, UserRole.ADMIN, username="admin_b")
    project_a = create_test_project_via_repo(test_repo, org_a.id, name="PA")
    ticket = _make_ticket(test_repo, project_a.id, admin_a.id)
    cap = CommentCapability(test_repo, admin_b)
    assert_denied(cap.load_ticket_for_access, ticket.id)


def test_comment_authorize_create_denies_read_user(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    reader = make_user(test_repo, org, UserRole.READ_ACCESS)
    admin = make_user(test_repo, org, UserRole.ADMIN, username="admin")
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    ticket = _make_ticket(test_repo, project.id, admin.id)
    cap = CommentCapability(test_repo, reader)
    assert_denied(cap.authorize_create, ticket)


def test_comment_authorize_create_allows_write_user(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    writer = make_user(test_repo, org, UserRole.WRITE_ACCESS)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    ticket = _make_ticket(test_repo, project.id, writer.id)
    cap = CommentCapability(test_repo, writer)
    cap.authorize_create(ticket)  # no raise


def test_comment_create_persists(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    writer = make_user(test_repo, org, UserRole.WRITE_ACCESS)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    ticket = _make_ticket(test_repo, project.id, writer.id)
    cap = CommentCapability(test_repo, writer)
    comment = cap.create(
        CommentCreateCommand(comment_data=CommentData(content="hi"), ticket_id=ticket.id),
        author_id=writer.id,
    )
    assert comment.content == "hi"


def test_comment_authorize_update_allows_author(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    writer = make_user(test_repo, org, UserRole.WRITE_ACCESS)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    ticket = _make_ticket(test_repo, project.id, writer.id)
    cap = CommentCapability(test_repo, writer)
    comment = cap.create(
        CommentCreateCommand(comment_data=CommentData(content="hi"), ticket_id=ticket.id),
        author_id=writer.id,
    )
    cap.authorize_update(comment)  # no raise


def test_comment_authorize_update_denies_non_author_admin(test_repo: Repository) -> None:
    # update is author-only — even admin cannot update someone else's comment
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    writer = make_user(test_repo, org, UserRole.WRITE_ACCESS)
    admin = make_user(test_repo, org, UserRole.ADMIN, username="admin")
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    ticket = _make_ticket(test_repo, project.id, writer.id)
    write_cap = CommentCapability(test_repo, writer)
    comment = write_cap.create(
        CommentCreateCommand(comment_data=CommentData(content="mine"), ticket_id=ticket.id),
        author_id=writer.id,
    )
    admin_cap = CommentCapability(test_repo, admin)
    assert_denied(admin_cap.authorize_update, comment)


def test_comment_update_persists(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    writer = make_user(test_repo, org, UserRole.WRITE_ACCESS)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    ticket = _make_ticket(test_repo, project.id, writer.id)
    cap = CommentCapability(test_repo, writer)
    comment = cap.create(
        CommentCreateCommand(comment_data=CommentData(content="hi"), ticket_id=ticket.id),
        author_id=writer.id,
    )
    updated = cap.update(comment.id, CommentUpdateCommand(content="edited"))
    assert updated is not None and updated.content == "edited"


def test_comment_authorize_delete_allows_author(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    writer = make_user(test_repo, org, UserRole.WRITE_ACCESS)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    ticket = _make_ticket(test_repo, project.id, writer.id)
    cap = CommentCapability(test_repo, writer)
    comment = cap.create(
        CommentCreateCommand(comment_data=CommentData(content="hi"), ticket_id=ticket.id),
        author_id=writer.id,
    )
    cap.authorize_delete(comment)  # no raise


def test_comment_authorize_delete_allows_admin_override(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    writer = make_user(test_repo, org, UserRole.WRITE_ACCESS)
    admin = make_user(test_repo, org, UserRole.ADMIN, username="admin")
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    ticket = _make_ticket(test_repo, project.id, writer.id)
    write_cap = CommentCapability(test_repo, writer)
    comment = write_cap.create(
        CommentCreateCommand(comment_data=CommentData(content="hi"), ticket_id=ticket.id),
        author_id=writer.id,
    )
    admin_cap = CommentCapability(test_repo, admin)
    admin_cap.authorize_delete(comment)  # no raise — admin can delete others' comments


def test_comment_authorize_delete_denies_non_author_non_admin(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    writer1 = make_user(test_repo, org, UserRole.WRITE_ACCESS, username="writer1")
    writer2 = make_user(test_repo, org, UserRole.WRITE_ACCESS, username="writer2")
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    ticket = _make_ticket(test_repo, project.id, writer1.id)
    cap1 = CommentCapability(test_repo, writer1)
    comment = cap1.create(
        CommentCreateCommand(comment_data=CommentData(content="hi"), ticket_id=ticket.id),
        author_id=writer1.id,
    )
    cap2 = CommentCapability(test_repo, writer2)
    assert_denied(cap2.authorize_delete, comment)
