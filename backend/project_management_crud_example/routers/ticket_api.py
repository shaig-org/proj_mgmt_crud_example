"""Ticket API endpoints (capability-based)."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from project_management_crud_example.capabilities import OrgTicketWriteCapability, TicketReadCapability
from project_management_crud_example.dependencies import (
    get_org_ticket_write_capability,
    get_ticket_read_capability,
)
from project_management_crud_example.domain_models import (
    Ticket,
    TicketAssignCommand,
    TicketCreateCommand,
    TicketData,
    TicketDeleteCommand,
    TicketMoveCommand,
    TicketStatusChangeCommand,
    TicketUpdateCommand,
)
from project_management_crud_example.utils.activity_log_helpers import log_activity
from project_management_crud_example.utils.debug_helpers import log_diff_debug

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


class TicketStatusUpdate(BaseModel):
    status: str = Field(..., min_length=1)


class TicketProjectUpdate(BaseModel):
    project_id: str


class TicketAssigneeUpdate(BaseModel):
    assignee_id: Optional[str] = None


@router.post("", response_model=Ticket, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    ticket_data: TicketData,
    project_id: str = Query(...),
    assignee_id: Optional[str] = Query(None),
    cap: OrgTicketWriteCapability = Depends(get_org_ticket_write_capability),  # noqa: B008
) -> Ticket:
    # Original order: role check first, then existence check, then cross-org check.
    from project_management_crud_example.capabilities import CapabilityPermissionError
    from project_management_crud_example.capabilities.tickets_capability import _CREATE_ROLES

    if cap.user.role not in _CREATE_ROLES:
        raise CapabilityPermissionError("Insufficient permissions to create tickets")

    project = cap.repo.projects.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    cap.authorize_create(project)

    if assignee_id:
        assignee = cap.repo.users.get_by_id(assignee_id)
        if not assignee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee user not found")
        if not assignee.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot assign to inactive user")
        cap.authorize_assignee(assignee)

    command = TicketCreateCommand(ticket_data=ticket_data, project_id=project_id, assignee_id=assignee_id)
    try:
        ticket = cap.create(command, reporter_id=cap.user.id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None

    log_activity(
        repo=cap.repo,
        command=command,
        entity_id=ticket.id,
        actor_id=cap.user.id,
        organization_id=project.organization_id,
    )
    return ticket


@router.get("/{ticket_id}", response_model=Ticket)
async def get_ticket(
    ticket_id: str,
    cap: TicketReadCapability = Depends(get_ticket_read_capability),  # noqa: B008
) -> Ticket:
    ticket = cap.get_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


@router.get("", response_model=List[Ticket])
async def list_tickets(
    project_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    assignee_id: Optional[str] = Query(None),
    cap: TicketReadCapability = Depends(get_ticket_read_capability),  # noqa: B008
) -> List[Ticket]:
    return cap.list_tickets(project_id=project_id, status=status, assignee_id=assignee_id)


def _require_role_for_write(cap: OrgTicketWriteCapability, allowed_roles: set, action: str) -> None:
    from project_management_crud_example.capabilities import CapabilityPermissionError

    if cap.user.role not in allowed_roles:
        raise CapabilityPermissionError(f"Insufficient permissions to {action}")


def _load_ticket_and_project(cap: OrgTicketWriteCapability, ticket_id: str) -> tuple:
    """Helper: returns (ticket, project) with 404 if missing."""
    ticket = cap.repo.tickets.get_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    project = cap.repo.projects.get_by_id(ticket.project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ticket, project


@router.put("/{ticket_id}", response_model=Ticket)
async def update_ticket(
    ticket_id: str,
    update_data: TicketUpdateCommand,
    cap: OrgTicketWriteCapability = Depends(get_org_ticket_write_capability),  # noqa: B008
) -> Ticket:
    from project_management_crud_example.capabilities.tickets_capability import _UPDATE_ROLES

    _require_role_for_write(cap, _UPDATE_ROLES, "update tickets")
    ticket, project = _load_ticket_and_project(cap, ticket_id)
    cap.authorize_update(project)
    old_ticket = ticket
    updated = cap.update(ticket_id, update_data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    log_diff_debug(old_ticket, updated, "ticket", "update_ticket")
    log_activity(
        repo=cap.repo,
        command=update_data,
        entity_id=ticket_id,
        actor_id=cap.user.id,
        organization_id=project.organization_id,
    )
    return updated


@router.put("/{ticket_id}/status", response_model=Ticket)
async def update_ticket_status(
    ticket_id: str,
    status_update: TicketStatusUpdate,
    cap: OrgTicketWriteCapability = Depends(get_org_ticket_write_capability),  # noqa: B008
) -> Ticket:
    from project_management_crud_example.capabilities.tickets_capability import _UPDATE_ROLES

    _require_role_for_write(cap, _UPDATE_ROLES, "change ticket status")
    ticket, project = _load_ticket_and_project(cap, ticket_id)
    cap.authorize_status_change(project)
    try:
        updated = cap.update_status(ticket_id, status_update.status)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    status_cmd = TicketStatusChangeCommand(ticket_id=ticket_id, status=status_update.status)
    log_activity(
        repo=cap.repo,
        command=status_cmd,
        entity_id=ticket_id,
        actor_id=cap.user.id,
        organization_id=project.organization_id,
    )
    # Suppress the imported `ticket` var lint
    _ = ticket
    return updated


@router.put("/{ticket_id}/project", response_model=Ticket)
async def move_ticket_to_project(
    ticket_id: str,
    project_update: TicketProjectUpdate,
    cap: OrgTicketWriteCapability = Depends(get_org_ticket_write_capability),  # noqa: B008
) -> Ticket:
    from project_management_crud_example.capabilities.tickets_capability import _MOVE_OR_ASSIGN_ROLES

    _require_role_for_write(cap, _MOVE_OR_ASSIGN_ROLES, "move tickets")
    ticket, source_project = _load_ticket_and_project(cap, ticket_id)

    target_project = cap.repo.projects.get_by_id(project_update.project_id)
    if not target_project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    cap.authorize_move(source_project, target_project)

    try:
        updated = cap.update_project(ticket_id, project_update.project_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    move_cmd = TicketMoveCommand(ticket_id=ticket_id, target_project_id=project_update.project_id)
    log_activity(
        repo=cap.repo,
        command=move_cmd,
        entity_id=ticket_id,
        actor_id=cap.user.id,
        organization_id=source_project.organization_id,
    )
    _ = ticket
    return updated


@router.put("/{ticket_id}/assignee", response_model=Ticket)
async def update_ticket_assignee(
    ticket_id: str,
    assignee_update: TicketAssigneeUpdate,
    cap: OrgTicketWriteCapability = Depends(get_org_ticket_write_capability),  # noqa: B008
) -> Ticket:
    from project_management_crud_example.capabilities.tickets_capability import _MOVE_OR_ASSIGN_ROLES

    _require_role_for_write(cap, _MOVE_OR_ASSIGN_ROLES, "assign tickets")
    ticket, project = _load_ticket_and_project(cap, ticket_id)
    cap.authorize_assign(project)

    if assignee_update.assignee_id:
        assignee = cap.repo.users.get_by_id(assignee_update.assignee_id)
        if not assignee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee user not found")
        if not assignee.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot assign to inactive user")
        cap.authorize_assignee(assignee)

    updated = cap.update_assignee(ticket_id, assignee_update.assignee_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    assign_cmd = TicketAssignCommand(ticket_id=ticket_id, assignee_id=assignee_update.assignee_id)
    log_activity(
        repo=cap.repo,
        command=assign_cmd,
        entity_id=ticket_id,
        actor_id=cap.user.id,
        organization_id=project.organization_id,
    )
    _ = ticket
    return updated


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket(
    ticket_id: str,
    cap: OrgTicketWriteCapability = Depends(get_org_ticket_write_capability),  # noqa: B008
) -> None:
    from project_management_crud_example.capabilities.tickets_capability import _DELETE_ROLES

    _require_role_for_write(cap, _DELETE_ROLES, "delete tickets")
    ticket, project = _load_ticket_and_project(cap, ticket_id)
    cap.authorize_delete(project)

    if not cap.delete(ticket_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    log_diff_debug(ticket, None, "ticket", "delete_ticket")
    delete_cmd = TicketDeleteCommand(ticket_id=ticket_id)
    log_activity(
        repo=cap.repo,
        command=delete_cmd,
        entity_id=ticket_id,
        actor_id=cap.user.id,
        organization_id=project.organization_id,
        snapshot=ticket.model_dump(mode="json", exclude_none=True),
    )
