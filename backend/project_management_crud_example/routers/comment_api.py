"""Comment API endpoints (capability-based, scope-split).

Scope is declared by the `Depends(...)` type on each endpoint:
- read endpoints use `CommentReadCapability`
- author-initiated create/update/delete use `OwnCommentWriteCapability`
- admin moderation uses `OrgCommentModerationCapability` (separate endpoint)
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from project_management_crud_example.capabilities import (
    CommentReadCapability,
    OrgCommentModerationCapability,
    OwnCommentWriteCapability,
)
from project_management_crud_example.dependencies import (
    get_comment_read_capability,
    get_org_comment_moderation_capability,
    get_own_comment_write_capability,
)
from project_management_crud_example.domain_models import (
    Comment,
    CommentCreateCommand,
    CommentData,
    CommentDeleteCommand,
    CommentUpdateCommand,
)
from project_management_crud_example.utils.activity_log_helpers import log_activity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["comments"])


def _org_id_for_ticket_id(
    cap: CommentReadCapability | OwnCommentWriteCapability | OrgCommentModerationCapability,
    ticket_id: str,
) -> str:
    """Helper: resolve the ticket's org_id for activity-log writes."""
    ticket = cap.repo.tickets.get_by_id(ticket_id)
    project = cap.repo.projects.get_by_id(ticket.project_id) if ticket else None
    return project.organization_id if project else (cap.user.organization_id or "")


@router.post("/tickets/{ticket_id}/comments", response_model=Comment, status_code=status.HTTP_201_CREATED)
async def create_comment(
    ticket_id: str,
    comment_data: CommentData,
    cap: OwnCommentWriteCapability = Depends(get_own_comment_write_capability),  # noqa: B008
) -> Comment:
    ticket = cap.load_ticket_for_create(ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    command = CommentCreateCommand(comment_data=comment_data, ticket_id=ticket_id)
    comment = cap.create(command)

    log_activity(
        repo=cap.repo,
        command=command,
        entity_id=comment.id,
        actor_id=cap.user.id,
        organization_id=_org_id_for_ticket_id(cap, ticket_id),
    )
    return comment


@router.get("/comments/{comment_id}", response_model=Comment)
async def get_comment(
    comment_id: str,
    cap: CommentReadCapability = Depends(get_comment_read_capability),  # noqa: B008
) -> Comment:
    comment = cap.load_comment_for_access(comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return comment


@router.get("/tickets/{ticket_id}/comments", response_model=List[Comment])
async def list_ticket_comments(
    ticket_id: str,
    cap: CommentReadCapability = Depends(get_comment_read_capability),  # noqa: B008
) -> List[Comment]:
    ticket = cap.load_ticket_for_access(ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return cap.list_for_ticket(ticket_id)


@router.put("/comments/{comment_id}", response_model=Comment)
async def update_comment(
    comment_id: str,
    comment_update: CommentUpdateCommand,
    cap: OwnCommentWriteCapability = Depends(get_own_comment_write_capability),  # noqa: B008
) -> Comment:
    comment = cap.load_own_comment(comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    updated = cap.update_own(comment_id, comment_update)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    log_activity(
        repo=cap.repo,
        command=comment_update,
        entity_id=comment_id,
        actor_id=cap.user.id,
        organization_id=_org_id_for_ticket_id(cap, comment.ticket_id),
    )
    return updated


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_own_comment(
    comment_id: str,
    cap: OwnCommentWriteCapability = Depends(get_own_comment_write_capability),  # noqa: B008
) -> None:
    """Delete one's OWN comment. For admin moderation of others' comments,
    use DELETE /api/admin/comments/{comment_id}."""
    comment = cap.load_own_comment(comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    org_id = _org_id_for_ticket_id(cap, comment.ticket_id)
    if not cap.delete_own(comment_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    log_activity(
        repo=cap.repo,
        command=CommentDeleteCommand(comment_id=comment_id),
        entity_id=comment_id,
        actor_id=cap.user.id,
        organization_id=org_id,
        snapshot=comment.model_dump(mode="json", exclude_none=True),
    )


@router.delete("/admin/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def moderate_delete_comment(
    comment_id: str,
    cap: OrgCommentModerationCapability = Depends(get_org_comment_moderation_capability),  # noqa: B008
) -> None:
    """Admin moderation: delete any comment in caller's organization.

    This endpoint is the ONLY route that takes `OrgCommentModerationCapability`.
    A capability-expansion diff on this endpoint would be a review signal.
    """
    comment = cap.load_comment_in_org(comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    org_id = _org_id_for_ticket_id(cap, comment.ticket_id)
    if not cap.delete_any_in_org(comment_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    log_activity(
        repo=cap.repo,
        command=CommentDeleteCommand(comment_id=comment_id),
        entity_id=comment_id,
        actor_id=cap.user.id,
        organization_id=org_id,
        snapshot=comment.model_dump(mode="json", exclude_none=True),
    )
