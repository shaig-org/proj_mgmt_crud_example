"""Comment capability (single class; author-or-admin policy)."""

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


class CommentCapability:
    """Authorization for all comment verbs."""

    def __init__(self, repo: Repository, current_user: User) -> None:
        self._repo = repo
        self._user = current_user

    @property
    def repo(self) -> Repository:
        return self._repo

    @property
    def user(self) -> User:
        return self._user

    def _ensure_ticket_access(self, ticket: Ticket) -> Optional[str]:
        """Returns organization_id for the ticket, or raises on cross-org."""
        project = self._repo.projects.get_by_id(ticket.project_id)
        if project is None:
            return None
        if self._user.role != UserRole.SUPER_ADMIN:
            if project.organization_id != self._user.organization_id:
                raise CapabilityPermissionError("Access denied: ticket belongs to different organization")
        return project.organization_id

    def load_ticket_for_access(self, ticket_id: str) -> Optional[Ticket]:
        ticket = self._repo.tickets.get_by_id(ticket_id)
        if ticket is None:
            return None
        self._ensure_ticket_access(ticket)
        return ticket

    def authorize_create(self, ticket: Ticket) -> None:
        if self._user.role == UserRole.READ_ACCESS:
            raise CapabilityPermissionError("Permission denied: read-only users cannot create comments")
        self._ensure_ticket_access(ticket)

    def create(self, command: CommentCreateCommand, author_id: str) -> Comment:
        return self._repo.comments.create(command, author_id=author_id)

    def load_comment_for_access(self, comment_id: str) -> Optional[Comment]:
        comment = self._repo.comments.get_by_id(comment_id)
        if comment is None:
            return None
        ticket = self._repo.tickets.get_by_id(comment.ticket_id)
        if ticket is None:
            return None
        self._ensure_ticket_access(ticket)
        return comment

    def list_for_ticket(self, ticket_id: str) -> List[Comment]:
        return self._repo.comments.get_by_ticket_id(ticket_id)

    def authorize_update(self, comment: Comment) -> None:
        if comment.author_id != self._user.id:
            raise CapabilityPermissionError("Permission denied: only comment author can update their comments")

    def update(self, comment_id: str, command: CommentUpdateCommand) -> Optional[Comment]:
        return self._repo.comments.update(comment_id, command)

    def authorize_delete(self, comment: Comment) -> None:
        is_author = comment.author_id == self._user.id
        is_admin = self._user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
        if not (is_author or is_admin):
            raise CapabilityPermissionError("Permission denied: only comment author or admins can delete comments")

    def delete(self, comment_id: str) -> bool:
        return self._repo.comments.delete(comment_id)
