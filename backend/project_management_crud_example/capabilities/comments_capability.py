"""Comment capabilities — split by scope.

- `CommentReadCapability` — org-scoped reads.
- `OwnCommentWriteCapability` — create (authored by self) + update+delete on the
  caller's OWN comments. The `author_id` is NOT a method argument — it is
  captured at construction. A non-author cannot, via this capability, mutate
  someone else's comment.
- `OrgCommentModerationCapability` — admin-only; delete any comment in the
  caller's org. Admin-gated at the DI factory so non-admins cannot construct
  it. Has no `update` verb: admins are not authors, they are moderators.
"""

from typing import List, Optional

from project_management_crud_example.capabilities.errors import CapabilityPermissionError
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    Comment,
    CommentCreateCommand,
    CommentUpdateCommand,
    Ticket,
    User,
    UserRole,
)


def _ensure_same_org_via_ticket(repo: Repository, actor: User, ticket: Ticket) -> Optional[str]:
    """Verify the ticket belongs to the actor's org (super admin bypass).

    Returns the owning org_id on success; None if the parent project is missing.
    Raises CapabilityPermissionError on cross-org.
    """
    project = repo.projects.get_by_id(ticket.project_id)
    if project is None:
        return None
    if actor.role != UserRole.SUPER_ADMIN:
        if project.organization_id != actor.organization_id:
            raise CapabilityPermissionError("Access denied: ticket belongs to different organization")
    return project.organization_id


class CommentReadCapability:
    """Read-side comment authorization. Org-scoped."""

    def __init__(self, repo: Repository, current_user: User) -> None:
        self._repo = repo
        self._user = current_user

    @property
    def repo(self) -> Repository:
        return self._repo

    @property
    def user(self) -> User:
        return self._user

    def load_ticket_for_access(self, ticket_id: str) -> Optional[Ticket]:
        ticket = self._repo.tickets.get_by_id(ticket_id)
        if ticket is None:
            return None
        _ensure_same_org_via_ticket(self._repo, self._user, ticket)
        return ticket

    def load_comment_for_access(self, comment_id: str) -> Optional[Comment]:
        comment = self._repo.comments.get_by_id(comment_id)
        if comment is None:
            return None
        ticket = self._repo.tickets.get_by_id(comment.ticket_id)
        if ticket is None:
            return None
        _ensure_same_org_via_ticket(self._repo, self._user, ticket)
        return comment

    def list_for_ticket(self, ticket_id: str) -> List[Comment]:
        return self._repo.comments.get_by_ticket_id(ticket_id)


class OwnCommentWriteCapability:
    """Create / update-own / delete-own comments. `author_id` is baked in.

    Methods do NOT accept an `author_id` parameter. `update` and `delete_own`
    verify the target comment's author matches the captured user and raise
    otherwise. A structural test in tests/capabilities keeps this invariant
    honest.
    """

    def __init__(self, repo: Repository, current_user: User) -> None:
        self._repo = repo
        self._user = current_user

    @property
    def repo(self) -> Repository:
        return self._repo

    @property
    def user(self) -> User:
        return self._user

    def load_ticket_for_create(self, ticket_id: str) -> Optional[Ticket]:
        ticket = self._repo.tickets.get_by_id(ticket_id)
        if ticket is None:
            return None
        _ensure_same_org_via_ticket(self._repo, self._user, ticket)
        if self._user.role == UserRole.READ_ACCESS:
            raise CapabilityPermissionError("Permission denied: read-only users cannot create comments")
        return ticket

    def create(self, command: CommentCreateCommand) -> Comment:
        """Create a comment authored by the captured user. No author arg."""
        return self._repo.comments.create(command, author_id=self._user.id)

    def load_own_comment(self, comment_id: str) -> Optional[Comment]:
        """Return the comment only if authored by the captured user."""
        comment = self._repo.comments.get_by_id(comment_id)
        if comment is None:
            return None
        if comment.author_id != self._user.id:
            raise CapabilityPermissionError("Permission denied: only the comment author can modify this comment")
        ticket = self._repo.tickets.get_by_id(comment.ticket_id)
        if ticket is None:
            return None
        _ensure_same_org_via_ticket(self._repo, self._user, ticket)
        return comment

    def update_own(self, comment_id: str, command: CommentUpdateCommand) -> Optional[Comment]:
        self.load_own_comment(comment_id)  # raises on non-author
        return self._repo.comments.update(comment_id, command)

    def delete_own(self, comment_id: str) -> bool:
        self.load_own_comment(comment_id)  # raises on non-author
        return self._repo.comments.delete(comment_id)


class OrgCommentModerationCapability:
    """Admin moderation: delete any comment in the caller's organization.

    Must be constructed via `get_org_comment_moderation_capability`, which
    enforces admin role at the DI boundary. No update verb — moderators do
    not edit other users' words. Super admins bypass the org check.
    """

    def __init__(self, repo: Repository, current_user: User) -> None:
        self._repo = repo
        self._user = current_user

    @property
    def repo(self) -> Repository:
        return self._repo

    @property
    def user(self) -> User:
        return self._user

    def load_comment_in_org(self, comment_id: str) -> Optional[Comment]:
        comment = self._repo.comments.get_by_id(comment_id)
        if comment is None:
            return None
        ticket = self._repo.tickets.get_by_id(comment.ticket_id)
        if ticket is None:
            return None
        _ensure_same_org_via_ticket(self._repo, self._user, ticket)  # raises on cross-org
        return comment

    def delete_any_in_org(self, comment_id: str) -> bool:
        """Delete a comment. Org membership verified by load_comment_in_org caller."""
        return self._repo.comments.delete(comment_id)
