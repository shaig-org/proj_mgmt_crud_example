"""Comment API endpoints (capability-based)."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from project_management_crud_example.capabilities import CommentCapability
from project_management_crud_example.dependencies import get_comment_capability
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


def _org_id_for_ticket(cap: CommentCapability, ticket_id: str) -> str:
    ticket = cap.repo.tickets.get_by_id(ticket_id)
    project = cap.repo.projects.get_by_id(ticket.project_id) if ticket else None
    return project.organization_id if project else (cap.user.organization_id or "")


@router.post("/tickets/{ticket_id}/comments", response_model=Comment, status_code=status.HTTP_201_CREATED)
async def create_comment(
    ticket_id: str,
    comment_data: CommentData,
    cap: CommentCapability = Depends(get_comment_capability),  # noqa: B008
) -> Comment:
    ticket = cap.load_ticket_for_access(ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    cap.authorize_create(ticket)

    command = CommentCreateCommand(comment_data=comment_data, ticket_id=ticket_id)
    comment = cap.create(command, author_id=cap.user.id)

    log_activity(
        repo=cap.repo,
        command=command,
        entity_id=comment.id,
        actor_id=cap.user.id,
        organization_id=_org_id_for_ticket(cap, ticket_id),
    )
    return comment


@router.get("/comments/{comment_id}", response_model=Comment)
async def get_comment(
    comment_id: str,
    cap: CommentCapability = Depends(get_comment_capability),  # noqa: B008
) -> Comment:
    comment = cap.load_comment_for_access(comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return comment


@router.get("/tickets/{ticket_id}/comments", response_model=List[Comment])
async def list_ticket_comments(
    ticket_id: str,
    cap: CommentCapability = Depends(get_comment_capability),  # noqa: B008
) -> List[Comment]:
    ticket = cap.load_ticket_for_access(ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return cap.list_for_ticket(ticket_id)


@router.put("/comments/{comment_id}", response_model=Comment)
async def update_comment(
    comment_id: str,
    comment_update: CommentUpdateCommand,
    cap: CommentCapability = Depends(get_comment_capability),  # noqa: B008
) -> Comment:
    comment = cap.load_comment_for_access(comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    cap.authorize_update(comment)

    updated = cap.update(comment_id, comment_update)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    log_activity(
        repo=cap.repo,
        command=comment_update,
        entity_id=comment_id,
        actor_id=cap.user.id,
        organization_id=_org_id_for_ticket(cap, comment.ticket_id),
    )
    return updated


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: str,
    cap: CommentCapability = Depends(get_comment_capability),  # noqa: B008
) -> None:
    comment = cap.load_comment_for_access(comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    cap.authorize_delete(comment)

    org_id = _org_id_for_ticket(cap, comment.ticket_id)

    if not cap.delete(comment_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    delete_command = CommentDeleteCommand(comment_id=comment_id)
    log_activity(
        repo=cap.repo,
        command=delete_command,
        entity_id=comment_id,
        actor_id=cap.user.id,
        organization_id=org_id,
        snapshot=comment.model_dump(mode="json", exclude_none=True),
    )
