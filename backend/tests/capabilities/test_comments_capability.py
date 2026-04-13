"""Unit tests for CommentReadCapability, OwnCommentWriteCapability, OrgCommentModerationCapability."""

from __future__ import annotations

import inspect

from project_management_crud_example.capabilities.comments_capability import (
    CommentReadCapability,
    OrgCommentModerationCapability,
    OwnCommentWriteCapability,
)
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


# ---------------------------------------------------------------------------
# CommentReadCapability
# ---------------------------------------------------------------------------


def test_read_load_ticket_for_access_allows_member(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    ticket = _make_ticket(test_repo, project.id, admin.id)
    cap = CommentReadCapability(test_repo, admin)
    result = cap.load_ticket_for_access(ticket.id)
    assert result is not None and result.id == ticket.id


def test_read_load_ticket_for_access_denies_cross_org(test_repo: Repository) -> None:
    org_a = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    org_b = create_test_org_with_workflow_via_repo(test_repo, name="Org B")
    admin_a = make_user(test_repo, org_a, UserRole.ADMIN, username="admin_a")
    admin_b = make_user(test_repo, org_b, UserRole.ADMIN, username="admin_b")
    project_a = create_test_project_via_repo(test_repo, org_a.id, name="PA")
    ticket = _make_ticket(test_repo, project_a.id, admin_a.id)
    cap = CommentReadCapability(test_repo, admin_b)
    assert_denied(cap.load_ticket_for_access, ticket.id)


# ---------------------------------------------------------------------------
# OwnCommentWriteCapability — structural guard on scope invariant
# ---------------------------------------------------------------------------


def test_own_comment_write_has_no_author_id_or_user_id_arg() -> None:
    """Scope-in-type invariant: no public method accepts author_id/user_id."""
    for name, member in inspect.getmembers(OwnCommentWriteCapability, inspect.isfunction):
        if name.startswith("_"):
            continue
        params = inspect.signature(member).parameters
        for param_name in params:
            lower = param_name.lower()
            assert "author_id" not in lower, f"OwnCommentWriteCapability.{name} accepts `{param_name}`"
            assert "user_id" not in lower, f"OwnCommentWriteCapability.{name} accepts `{param_name}`"


def test_own_create_denies_read_only_user(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    reader = make_user(test_repo, org, UserRole.READ_ACCESS)
    admin = make_user(test_repo, org, UserRole.ADMIN, username="admin")
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    ticket = _make_ticket(test_repo, project.id, admin.id)
    cap = OwnCommentWriteCapability(test_repo, reader)
    assert_denied(cap.load_ticket_for_create, ticket.id)


def test_own_create_persists_authored_by_self(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    writer = make_user(test_repo, org, UserRole.WRITE_ACCESS)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    ticket = _make_ticket(test_repo, project.id, writer.id)
    cap = OwnCommentWriteCapability(test_repo, writer)
    comment = cap.create(CommentCreateCommand(comment_data=CommentData(content="hi"), ticket_id=ticket.id))
    assert comment.content == "hi"
    assert comment.author_id == writer.id


def test_own_update_own_succeeds(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    writer = make_user(test_repo, org, UserRole.WRITE_ACCESS)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    ticket = _make_ticket(test_repo, project.id, writer.id)
    cap = OwnCommentWriteCapability(test_repo, writer)
    comment = cap.create(CommentCreateCommand(comment_data=CommentData(content="hi"), ticket_id=ticket.id))
    updated = cap.update_own(comment.id, CommentUpdateCommand(content="edited"))
    assert updated is not None and updated.content == "edited"


def test_own_update_of_others_comment_denied_even_for_admin(test_repo: Repository) -> None:
    """Admin cannot use OwnCommentWriteCapability to edit another user's comment."""
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    writer = make_user(test_repo, org, UserRole.WRITE_ACCESS)
    admin = make_user(test_repo, org, UserRole.ADMIN, username="admin")
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    ticket = _make_ticket(test_repo, project.id, writer.id)
    writer_cap = OwnCommentWriteCapability(test_repo, writer)
    comment = writer_cap.create(CommentCreateCommand(comment_data=CommentData(content="mine"), ticket_id=ticket.id))
    admin_cap = OwnCommentWriteCapability(test_repo, admin)
    assert_denied(admin_cap.update_own, comment.id, CommentUpdateCommand(content="hacked"))


def test_own_delete_own_succeeds(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    writer = make_user(test_repo, org, UserRole.WRITE_ACCESS)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    ticket = _make_ticket(test_repo, project.id, writer.id)
    cap = OwnCommentWriteCapability(test_repo, writer)
    comment = cap.create(CommentCreateCommand(comment_data=CommentData(content="hi"), ticket_id=ticket.id))
    assert cap.delete_own(comment.id) is True


def test_own_delete_of_others_comment_denied(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    writer1 = make_user(test_repo, org, UserRole.WRITE_ACCESS, username="writer1")
    writer2 = make_user(test_repo, org, UserRole.WRITE_ACCESS, username="writer2")
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    ticket = _make_ticket(test_repo, project.id, writer1.id)
    cap1 = OwnCommentWriteCapability(test_repo, writer1)
    comment = cap1.create(CommentCreateCommand(comment_data=CommentData(content="hi"), ticket_id=ticket.id))
    cap2 = OwnCommentWriteCapability(test_repo, writer2)
    assert_denied(cap2.delete_own, comment.id)


# ---------------------------------------------------------------------------
# OrgCommentModerationCapability — admin-gated at DI factory; tested here for
# same-org vs cross-org rule. Admin gate is tested at the API layer.
# ---------------------------------------------------------------------------


def test_moderation_delete_any_in_org_succeeds(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    writer = make_user(test_repo, org, UserRole.WRITE_ACCESS)
    admin = make_user(test_repo, org, UserRole.ADMIN, username="admin")
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    ticket = _make_ticket(test_repo, project.id, writer.id)
    writer_cap = OwnCommentWriteCapability(test_repo, writer)
    comment = writer_cap.create(CommentCreateCommand(comment_data=CommentData(content="hi"), ticket_id=ticket.id))
    mod_cap = OrgCommentModerationCapability(test_repo, admin)
    loaded = mod_cap.load_comment_in_org(comment.id)
    assert loaded is not None
    assert mod_cap.delete_any_in_org(comment.id) is True


def test_moderation_load_comment_in_org_denies_cross_org(test_repo: Repository) -> None:
    org_a = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    org_b = create_test_org_with_workflow_via_repo(test_repo, name="Org B")
    writer_a = make_user(test_repo, org_a, UserRole.WRITE_ACCESS, username="writer_a")
    admin_b = make_user(test_repo, org_b, UserRole.ADMIN, username="admin_b")
    project_a = create_test_project_via_repo(test_repo, org_a.id, name="PA")
    ticket = _make_ticket(test_repo, project_a.id, writer_a.id)
    writer_cap = OwnCommentWriteCapability(test_repo, writer_a)
    comment = writer_cap.create(CommentCreateCommand(comment_data=CommentData(content="hi"), ticket_id=ticket.id))
    mod_cap = OrgCommentModerationCapability(test_repo, admin_b)
    assert_denied(mod_cap.load_comment_in_org, comment.id)


def test_moderation_capability_has_no_update_verb() -> None:
    """Moderators are not authors — no update verb should exist."""
    method_names = {
        n for n, _ in inspect.getmembers(OrgCommentModerationCapability, inspect.isfunction) if not n.startswith("_")
    }
    assert "update" not in method_names
    assert "update_any_in_org" not in method_names
