"""Comment API endpoints.

This module provides comment CRUD endpoints with role-based permissions and organization scoping.
Comments belong to tickets, and access is controlled through ticket's project organization membership.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.dependencies import get_current_user, get_repository
from project_management_crud_example.domain_models import (
    Comment,
    CommentCreateCommand,
    CommentData,
    CommentDeleteCommand,
    CommentUpdateCommand,
    Ticket,
    User,
    UserRole,
)
from project_management_crud_example.utils.activity_log_helpers import log_activity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["comments"])


def _get_ticket_and_check_access(
    ticket_id: str,
    repo: Repository,
    current_user: User,
    operation: str,
) -> Ticket:
    """Get ticket and verify user has access to it (via project organization).

    Args:
        ticket_id: ID of ticket to check
        repo: Repository instance
        current_user: Current authenticated user
        operation: Description of operation for logging

    Returns:
        Ticket if found and accessible

    Raises:
        HTTP 404: Ticket not found
        HTTP 403: User attempting to access ticket in different organization
    """
    ticket = repo.tickets.get_by_id(ticket_id)

    if not ticket:
        logger.debug(f"Ticket not found: {ticket_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    # Check project access (tickets inherit access from their project)
    project = repo.projects.get_by_id(ticket.project_id)
    if not project:
        logger.error(f"Project not found for ticket {ticket_id}: {ticket.project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Permission check: Super Admin can access any, others only their own org
    if current_user.role != UserRole.SUPER_ADMIN:
        if project.organization_id != current_user.organization_id:
            logger.warning(f"User {current_user.id} attempted to {operation} on ticket {ticket_id} from different org")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: ticket belongs to different organization",
            )

    return ticket


def _get_comment_and_check_access(
    comment_id: str,
    repo: Repository,
    current_user: User,
    operation: str,
) -> Comment:
    """Get comment and verify user has access to it (via ticket's project organization).

    Args:
        comment_id: ID of comment to check
        repo: Repository instance
        current_user: Current authenticated user
        operation: Description of operation for logging

    Returns:
        Comment if found and accessible

    Raises:
        HTTP 404: Comment not found
        HTTP 403: User attempting to access comment in different organization
    """
    comment = repo.comments.get_by_id(comment_id)

    if not comment:
        logger.debug(f"Comment not found: {comment_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    # Check ticket access (comments inherit access from their ticket)
    _get_ticket_and_check_access(comment.ticket_id, repo, current_user, operation)

    return comment


@router.post("/tickets/{ticket_id}/comments", response_model=Comment, status_code=status.HTTP_201_CREATED)
async def create_comment(
    ticket_id: str,
    comment_data: CommentData,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Comment:
    """Create a new comment on a ticket.

    Permission rules:
    - Admin/Project Manager/Write users: Can create comments in their org's tickets
    - Read users: Cannot create comments
    - Author is automatically set to current user

    Args:
        ticket_id: ID of the ticket to comment on
        comment_data: Comment content
        repo: Database repository
        current_user: Current authenticated user

    Returns:
        Created comment

    Raises:
        HTTP 403: User lacks permission to create comments
        HTTP 404: Ticket not found
    """
    logger.info(f"User {current_user.id} creating comment on ticket {ticket_id}")

    # Permission check: Read users cannot create comments
    if current_user.role == UserRole.READ_ACCESS:
        logger.warning(f"User {current_user.id} with READ role attempted to create comment")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: read-only users cannot create comments",
        )

    # Verify ticket exists and user has access to it
    _get_ticket_and_check_access(ticket_id, repo, current_user, "create comment")

    # Create comment (author is automatically set to current user)
    command = CommentCreateCommand(
        comment_data=comment_data,
        ticket_id=ticket_id,
    )
    comment = repo.comments.create(command, author_id=current_user.id)

    # Log activity
    ticket = repo.tickets.get_by_id(ticket_id)
    project = repo.projects.get_by_id(ticket.project_id) if ticket else None
    organization_id = project.organization_id if project else current_user.organization_id or ""

    log_activity(
        repo=repo,
        command=command,
        entity_id=comment.id,
        actor_id=current_user.id,
        organization_id=organization_id,
    )

    logger.info(f"Comment {comment.id} created on ticket {ticket_id}")
    return comment


@router.get("/comments/{comment_id}", response_model=Comment)
async def get_comment(
    comment_id: str,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Comment:
    """Get a comment by ID.

    Permission rules:
    - All authenticated users can read comments in their organization

    Args:
        comment_id: ID of the comment
        repo: Database repository
        current_user: Current authenticated user

    Returns:
        The requested comment

    Raises:
        HTTP 404: Comment not found
        HTTP 403: User attempting to access comment in different organization
    """
    logger.debug(f"User {current_user.id} retrieving comment {comment_id}")

    comment = _get_comment_and_check_access(comment_id, repo, current_user, "retrieve comment")

    return comment


@router.get("/tickets/{ticket_id}/comments", response_model=List[Comment])
async def list_ticket_comments(
    ticket_id: str,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> List[Comment]:
    """List all comments for a ticket (chronologically ordered, oldest first).

    Permission rules:
    - All authenticated users can list comments in their organization

    Args:
        ticket_id: ID of the ticket
        repo: Database repository
        current_user: Current authenticated user

    Returns:
        List of comments for the ticket (oldest first)

    Raises:
        HTTP 404: Ticket not found
        HTTP 403: User attempting to access ticket in different organization
    """
    logger.debug(f"User {current_user.id} listing comments for ticket {ticket_id}")

    # Verify ticket exists and user has access to it
    _get_ticket_and_check_access(ticket_id, repo, current_user, "list comments")

    # Get all comments for ticket
    comments = repo.comments.get_by_ticket_id(ticket_id)

    return comments


@router.put("/comments/{comment_id}", response_model=Comment)
async def update_comment(
    comment_id: str,
    comment_update: CommentUpdateCommand,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Comment:
    """Update a comment's content.

    Permission rules:
    - Only the comment author can update their own comments
    - Admins cannot update other users' comments (deliberate design choice)

    Args:
        comment_id: ID of the comment to update
        comment_update: New comment content
        repo: Database repository
        current_user: Current authenticated user

    Returns:
        Updated comment

    Raises:
        HTTP 403: User is not the comment author
        HTTP 404: Comment not found
    """
    logger.info(f"User {current_user.id} updating comment {comment_id}")

    # Get comment and check access
    comment = _get_comment_and_check_access(comment_id, repo, current_user, "update comment")

    # Permission check: Only author can update
    if comment.author_id != current_user.id:
        logger.warning(f"User {current_user.id} attempted to update comment {comment_id} by another author")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: only comment author can update their comments",
        )

    # Update comment
    updated_comment = repo.comments.update(comment_id, comment_update)

    if not updated_comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    # Log activity
    ticket = repo.tickets.get_by_id(comment.ticket_id)
    project = repo.projects.get_by_id(ticket.project_id) if ticket else None
    organization_id = project.organization_id if project else current_user.organization_id or ""

    log_activity(
        repo=repo,
        command=comment_update,
        entity_id=comment_id,
        actor_id=current_user.id,
        organization_id=organization_id,
    )

    logger.info(f"Comment {comment_id} updated")
    return updated_comment


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: str,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> None:
    """Delete a comment.

    Permission rules:
    - Comment author can delete their own comments
    - Admin/Super Admin can delete any comments in their organization
    - Project Manager/Write users cannot delete others' comments

    Args:
        comment_id: ID of the comment to delete
        repo: Database repository
        current_user: Current authenticated user

    Raises:
        HTTP 403: User lacks permission to delete comment
        HTTP 404: Comment not found
    """
    logger.info(f"User {current_user.id} deleting comment {comment_id}")

    # Get comment and check access
    comment = _get_comment_and_check_access(comment_id, repo, current_user, "delete comment")

    # Permission check: Author OR Admin/Super Admin
    is_author = comment.author_id == current_user.id
    is_admin = current_user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)

    if not (is_author or is_admin):
        logger.warning(f"User {current_user.id} attempted to delete comment {comment_id} without permission")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: only comment author or admins can delete comments",
        )

    # Get organization for activity log before deleting
    ticket = repo.tickets.get_by_id(comment.ticket_id)
    project = repo.projects.get_by_id(ticket.project_id) if ticket else None
    organization_id = project.organization_id if project else current_user.organization_id or ""

    # Delete comment
    deleted = repo.comments.delete(comment_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    # Log activity
    delete_command = CommentDeleteCommand(comment_id=comment_id)
    log_activity(
        repo=repo,
        command=delete_command,
        entity_id=comment_id,
        actor_id=current_user.id,
        organization_id=organization_id,
        snapshot=comment.model_dump(mode="json", exclude_none=True),
    )

    logger.info(f"Comment {comment_id} deleted")
