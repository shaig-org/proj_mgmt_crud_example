"""Epic management API endpoints (capability-based)."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from project_management_crud_example.capabilities import EpicReadCapability, OrgEpicWriteCapability
from project_management_crud_example.dependencies import get_epic_read_capability, get_org_epic_write_capability
from project_management_crud_example.domain_models import (
    Epic,
    EpicData,
    EpicDeleteCommand,
    EpicTicketAddCommand,
    EpicTicketRemoveCommand,
    EpicUpdateCommand,
    Ticket,
)
from project_management_crud_example.utils.activity_log_helpers import log_activity
from project_management_crud_example.utils.debug_helpers import log_diff_debug

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/epics", tags=["epics"])


@router.post("", response_model=Epic, status_code=status.HTTP_201_CREATED)
async def create_epic(
    epic_data: EpicData,
    cap: OrgEpicWriteCapability = Depends(get_org_epic_write_capability),  # noqa: B008
) -> Epic:
    try:
        command = cap.build_create_command(epic_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    epic = cap.create(command)
    log_activity(
        repo=cap.repo,
        command=command,
        entity_id=epic.id,
        actor_id=cap.user.id,
        organization_id=command.organization_id,
    )
    return epic


@router.get("/{epic_id}", response_model=Epic)
async def get_epic(
    epic_id: str,
    cap: EpicReadCapability = Depends(get_epic_read_capability),  # noqa: B008
) -> Epic:
    epic = cap.get_by_id(epic_id)
    if not epic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Epic not found")
    return epic


@router.get("", response_model=List[Epic])
async def list_epics(
    cap: EpicReadCapability = Depends(get_epic_read_capability),  # noqa: B008
) -> List[Epic]:
    return cap.list_epics()


@router.put("/{epic_id}", response_model=Epic)
async def update_epic(
    epic_id: str,
    update_data: EpicUpdateCommand,
    cap: OrgEpicWriteCapability = Depends(get_org_epic_write_capability),  # noqa: B008
) -> Epic:
    old_epic = cap.load_for_update(epic_id)
    if not old_epic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Epic not found")
    updated = cap.update(epic_id, update_data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Epic not found")
    log_diff_debug(old_epic, updated, "epic", "update_epic")
    log_activity(
        repo=cap.repo,
        command=update_data,
        entity_id=epic_id,
        actor_id=cap.user.id,
        organization_id=updated.organization_id,
    )
    return updated


@router.delete("/{epic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_epic(
    epic_id: str,
    cap: OrgEpicWriteCapability = Depends(get_org_epic_write_capability),  # noqa: B008
) -> None:
    epic = cap.load_for_delete(epic_id)
    if not epic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Epic not found")
    if not cap.delete(epic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Epic not found")
    log_diff_debug(epic, None, "epic", "delete_epic")
    delete_cmd = EpicDeleteCommand(epic_id=epic_id)
    log_activity(
        repo=cap.repo,
        command=delete_cmd,
        entity_id=epic_id,
        actor_id=cap.user.id,
        organization_id=epic.organization_id,
        snapshot=epic.model_dump(mode="json", exclude_none=True),
    )


@router.post("/{epic_id}/tickets", status_code=status.HTTP_200_OK)
async def add_ticket_to_epic(
    epic_id: str,
    ticket_id: str,
    cap: OrgEpicWriteCapability = Depends(get_org_epic_write_capability),  # noqa: B008
) -> dict:
    epic = cap.repo.epics.get_by_id(epic_id)
    if not epic:
        # Role check still needs to run to preserve 403-before-404 where applicable,
        # but original router checked role first then existence, so replicate:
        cap._require_write_role("add tickets to epics")  # type: ignore[attr-defined]
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Epic not found")

    ticket = cap.repo.tickets.get_by_id(ticket_id)
    if not ticket:
        cap._require_write_role("add tickets to epics")  # type: ignore[attr-defined]
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    cap.authorize_ticket_link(epic, action="add")

    project = cap.repo.projects.get_by_id(ticket.project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ticket's project not found",
        )

    cap.ensure_ticket_same_org(epic, project.organization_id, action="add")

    if not cap.add_ticket(epic_id, ticket_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Epic or ticket not found")

    add_cmd = EpicTicketAddCommand(epic_id=epic_id, ticket_id=ticket_id)
    log_activity(
        repo=cap.repo,
        command=add_cmd,
        entity_id=epic_id,
        actor_id=cap.user.id,
        organization_id=epic.organization_id,
    )
    return {"message": "Ticket added to epic successfully"}


@router.delete("/{epic_id}/tickets/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_ticket_from_epic(
    epic_id: str,
    ticket_id: str,
    cap: OrgEpicWriteCapability = Depends(get_org_epic_write_capability),  # noqa: B008
) -> None:
    epic = cap.repo.epics.get_by_id(epic_id)
    if not epic:
        cap._require_write_role("remove tickets from epics")  # type: ignore[attr-defined]
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Epic not found")

    ticket = cap.repo.tickets.get_by_id(ticket_id)
    if not ticket:
        cap._require_write_role("remove tickets from epics")  # type: ignore[attr-defined]
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    cap.authorize_ticket_link(epic, action="remove")

    project = cap.repo.projects.get_by_id(ticket.project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ticket's project not found",
        )

    cap.ensure_ticket_same_org(epic, project.organization_id, action="remove")

    if not cap.remove_ticket(epic_id, ticket_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Epic or ticket not found")

    remove_cmd = EpicTicketRemoveCommand(epic_id=epic_id, ticket_id=ticket_id)
    log_activity(
        repo=cap.repo,
        command=remove_cmd,
        entity_id=epic_id,
        actor_id=cap.user.id,
        organization_id=epic.organization_id,
    )


@router.get("/{epic_id}/tickets", response_model=List[Ticket])
async def get_epic_tickets(
    epic_id: str,
    cap: EpicReadCapability = Depends(get_epic_read_capability),  # noqa: B008
) -> List[Ticket]:
    tickets = cap.get_tickets_in_epic(epic_id)
    if tickets is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Epic not found")
    return tickets
