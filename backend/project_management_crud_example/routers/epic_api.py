"""Epic management API endpoints.

This module provides REST API endpoints for managing epics (groups of tickets).
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.dependencies import get_current_user, get_repository
from project_management_crud_example.domain_models import (
    Epic,
    EpicCreateCommand,
    EpicData,
    EpicDeleteCommand,
    EpicTicketAddCommand,
    EpicTicketRemoveCommand,
    EpicUpdateCommand,
    Ticket,
    User,
    UserRole,
)
from project_management_crud_example.utils.activity_log_helpers import log_activity
from project_management_crud_example.utils.debug_helpers import log_diff_debug

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/epics", tags=["epics"])


@router.post("", response_model=Epic, status_code=status.HTTP_201_CREATED)
async def create_epic(
    epic_data: EpicData,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Epic:
    """Create a new epic.

    Permission rules:
    - Super Admin: Can create epic in any organization
    - Admin, Project Manager: Can create epic in their organization
    - Other roles: Cannot create epics

    Args:
        epic_data: Epic data (name, description)
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        Created epic

    Raises:
        HTTP 403: User does not have permission to create epics
    """
    logger.debug(f"Creating epic: {epic_data.name} (by user {current_user.id})")

    # Permission check: Admin, PM, and Super Admin can create
    allowed_roles = {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.PROJECT_MANAGER}
    if current_user.role not in allowed_roles:
        logger.warning(f"User {current_user.id} ({current_user.role}) attempted to create epic without permission")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create epics",
        )

    # Determine organization (users always create in their own org unless Super Admin)
    organization_id = current_user.organization_id
    if not organization_id:
        logger.error(f"User {current_user.id} has no organization_id")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization",
        )

    # Create epic
    command = EpicCreateCommand(epic_data=epic_data, organization_id=organization_id)
    epic = repo.epics.create(command)

    # Log activity - command-based
    log_activity(
        repo=repo,
        command=command,
        entity_id=epic.id,
        actor_id=current_user.id,
        organization_id=organization_id,
    )

    logger.info(f"Epic created: {epic.id}")
    return epic


@router.get("/{epic_id}", response_model=Epic)
async def get_epic(
    epic_id: str,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Epic:
    """Get a specific epic by ID.

    Permission rules:
    - Super Admin: Can access any epic
    - Other users: Can only access epics in their organization

    Args:
        epic_id: ID of epic to retrieve
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        Epic data

    Raises:
        HTTP 403: User does not have permission to access this epic
        HTTP 404: Epic not found
    """
    logger.debug(f"Getting epic: {epic_id} (by user {current_user.id})")

    epic = repo.epics.get_by_id(epic_id)
    if not epic:
        logger.debug(f"Epic not found: {epic_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Epic not found",
        )

    # Permission check: Non-Super-Admin can only access their own org's epics
    if current_user.role != UserRole.SUPER_ADMIN:
        if epic.organization_id != current_user.organization_id:
            logger.warning(f"User {current_user.id} attempted to access epic {epic_id} from different org")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: epic belongs to different organization",
            )

    return epic


@router.get("", response_model=List[Epic])
async def list_epics(
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> List[Epic]:
    """List all epics accessible to the current user.

    Permission rules:
    - Super Admin: Can see all epics across all organizations
    - Other users: Can only see epics in their organization

    Args:
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        List of epics the user has permission to access
    """
    logger.debug(f"Listing epics (by user {current_user.id}, role {current_user.role})")

    # Super Admin sees all epics
    if current_user.role == UserRole.SUPER_ADMIN:
        epics = repo.epics.get_all()
    else:
        # Other users only see their organization's epics
        if not current_user.organization_id:
            logger.warning(f"User {current_user.id} has no organization_id")
            return []
        epics = repo.epics.get_by_organization_id(current_user.organization_id)

    logger.debug(f"Retrieved {len(epics)} epics")
    return epics


@router.put("/{epic_id}", response_model=Epic)
async def update_epic(
    epic_id: str,
    update_data: EpicUpdateCommand,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Epic:
    """Update an epic.

    Permission rules:
    - Super Admin: Can update any epic
    - Admin, Project Manager: Can update epics in their organization
    - Other roles: Cannot update epics

    Args:
        epic_id: ID of epic to update
        update_data: Fields to update
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        Updated epic

    Raises:
        HTTP 403: User does not have permission to update this epic
        HTTP 404: Epic not found
    """
    logger.debug(f"Updating epic: {epic_id} (by user {current_user.id})")

    # Permission check: Admin, PM, and Super Admin can update
    allowed_roles = {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.PROJECT_MANAGER}
    if current_user.role not in allowed_roles:
        logger.warning(f"User {current_user.id} ({current_user.role}) attempted to update epic without permission")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update epics",
        )

    # Verify epic exists
    epic = repo.epics.get_by_id(epic_id)
    if not epic:
        logger.debug(f"Epic not found: {epic_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Epic not found",
        )

    # Permission check: Non-Super-Admin can only update their own org's epics
    if current_user.role != UserRole.SUPER_ADMIN:
        if epic.organization_id != current_user.organization_id:
            logger.warning(f"User {current_user.id} attempted to update epic {epic_id} from different org")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: epic belongs to different organization",
            )

    # Capture old state for debug logging
    old_epic = epic

    # Update epic
    updated_epic = repo.epics.update(epic_id, update_data)
    if not updated_epic:
        # Should not happen since we verified existence, but defensive check
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Epic not found",
        )

    # Debug logging: show what changed
    log_diff_debug(old_epic, updated_epic, "epic", "update_epic")

    # Log activity - command-based
    log_activity(
        repo=repo,
        command=update_data,
        entity_id=epic_id,
        actor_id=current_user.id,
        organization_id=updated_epic.organization_id,
    )

    logger.info(f"Epic updated: {epic_id}")
    return updated_epic


@router.delete("/{epic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_epic(
    epic_id: str,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> None:
    """Delete an epic.

    Permission rules:
    - Super Admin: Can delete any epic
    - Admin: Can delete epics in their organization
    - Other roles: Cannot delete epics

    Args:
        epic_id: ID of epic to delete
        repo: Repository instance for database access
        current_user: Current authenticated user

    Raises:
        HTTP 403: User does not have permission to delete this epic
        HTTP 404: Epic not found
    """
    logger.debug(f"Deleting epic: {epic_id} (by user {current_user.id})")

    # Permission check: Only Admin and Super Admin can delete
    allowed_roles = {UserRole.SUPER_ADMIN, UserRole.ADMIN}
    if current_user.role not in allowed_roles:
        logger.warning(f"User {current_user.id} ({current_user.role}) attempted to delete epic without permission")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete epics",
        )

    # Verify epic exists
    epic = repo.epics.get_by_id(epic_id)
    if not epic:
        logger.debug(f"Epic not found: {epic_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Epic not found",
        )

    # Permission check: Non-Super-Admin can only delete their own org's epics
    if current_user.role != UserRole.SUPER_ADMIN:
        if epic.organization_id != current_user.organization_id:
            logger.warning(f"User {current_user.id} attempted to delete epic {epic_id} from different org")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: epic belongs to different organization",
            )

    success = repo.epics.delete(epic_id)
    if not success:
        # Should not happen since we verified existence, but defensive check
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Epic not found",
        )

    # Debug logging: show what was deleted
    log_diff_debug(epic, None, "epic", "delete_epic")

    # Log activity - command-based with snapshot
    delete_cmd = EpicDeleteCommand(epic_id=epic_id)
    log_activity(
        repo=repo,
        command=delete_cmd,
        entity_id=epic_id,
        actor_id=current_user.id,
        organization_id=epic.organization_id,
        snapshot=epic.model_dump(mode="json", exclude_none=True),
    )

    logger.info(f"Epic deleted: {epic_id}")


@router.post("/{epic_id}/tickets", status_code=status.HTTP_200_OK)
async def add_ticket_to_epic(
    epic_id: str,
    ticket_id: str,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> dict:
    """Add a ticket to an epic.

    Permission rules:
    - Super Admin: Can add tickets to any epic
    - Admin, Project Manager: Can add tickets to epics in their organization
    - Other roles: Cannot add tickets to epics

    Args:
        epic_id: ID of epic
        ticket_id: ID of ticket to add (passed as query parameter)
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        Success message

    Raises:
        HTTP 403: User does not have permission or cross-organization attempt
        HTTP 404: Epic or ticket not found
    """
    logger.debug(f"Adding ticket {ticket_id} to epic {epic_id} (by user {current_user.id})")

    # Permission check: Admin, PM, and Super Admin can add tickets
    allowed_roles = {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.PROJECT_MANAGER}
    if current_user.role not in allowed_roles:
        logger.warning(
            f"User {current_user.id} ({current_user.role}) attempted to add ticket to epic without permission"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to add tickets to epics",
        )

    # Verify epic exists
    epic = repo.epics.get_by_id(epic_id)
    if not epic:
        logger.debug(f"Epic not found: {epic_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Epic not found",
        )

    # Verify ticket exists
    ticket = repo.tickets.get_by_id(ticket_id)
    if not ticket:
        logger.debug(f"Ticket not found: {ticket_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    # Permission check: Non-Super-Admin can only add to their own org's epics
    if current_user.role != UserRole.SUPER_ADMIN:
        if epic.organization_id != current_user.organization_id:
            logger.warning(f"User {current_user.id} attempted to add ticket to epic {epic_id} from different org")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: epic belongs to different organization",
            )

    # Organization validation: epic and ticket must be in same organization
    # Get ticket's organization via its project
    project = repo.projects.get_by_id(ticket.project_id)
    if not project:
        logger.error(f"Project {ticket.project_id} not found for ticket {ticket_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ticket's project not found",
        )

    if project.organization_id != epic.organization_id:
        logger.warning(
            f"Cross-organization add attempt: epic {epic_id} org {epic.organization_id}, "
            f"ticket {ticket_id} org {project.organization_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot add ticket from different organization to epic",
        )

    # Add ticket to epic
    success = repo.epics.add_ticket_to_epic(epic_id, ticket_id)
    if not success:
        # Should not happen since we verified existence, but defensive check
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Epic or ticket not found",
        )

    # Log activity - command-based
    add_cmd = EpicTicketAddCommand(epic_id=epic_id, ticket_id=ticket_id)
    log_activity(
        repo=repo,
        command=add_cmd,
        entity_id=epic_id,
        actor_id=current_user.id,
        organization_id=epic.organization_id,
    )

    logger.info(f"Ticket {ticket_id} added to epic {epic_id}")
    return {"message": "Ticket added to epic successfully"}


@router.delete("/{epic_id}/tickets/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_ticket_from_epic(
    epic_id: str,
    ticket_id: str,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> None:
    """Remove a ticket from an epic.

    Permission rules:
    - Super Admin: Can remove tickets from any epic
    - Admin, Project Manager: Can remove tickets from epics in their organization
    - Other roles: Cannot remove tickets from epics

    Args:
        epic_id: ID of epic
        ticket_id: ID of ticket to remove
        repo: Repository instance for database access
        current_user: Current authenticated user

    Raises:
        HTTP 403: User does not have permission or cross-organization attempt
        HTTP 404: Epic or ticket not found
    """
    logger.debug(f"Removing ticket {ticket_id} from epic {epic_id} (by user {current_user.id})")

    # Permission check: Admin, PM, and Super Admin can remove tickets
    allowed_roles = {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.PROJECT_MANAGER}
    if current_user.role not in allowed_roles:
        logger.warning(
            f"User {current_user.id} ({current_user.role}) attempted to remove ticket from epic without permission"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to remove tickets from epics",
        )

    # Verify epic exists
    epic = repo.epics.get_by_id(epic_id)
    if not epic:
        logger.debug(f"Epic not found: {epic_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Epic not found",
        )

    # Verify ticket exists
    ticket = repo.tickets.get_by_id(ticket_id)
    if not ticket:
        logger.debug(f"Ticket not found: {ticket_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    # Permission check: Non-Super-Admin can only remove from their own org's epics
    if current_user.role != UserRole.SUPER_ADMIN:
        if epic.organization_id != current_user.organization_id:
            logger.warning(f"User {current_user.id} attempted to remove ticket from epic {epic_id} from different org")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: epic belongs to different organization",
            )

    # Organization validation: epic and ticket must be in same organization
    project = repo.projects.get_by_id(ticket.project_id)
    if not project:
        logger.error(f"Project {ticket.project_id} not found for ticket {ticket_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ticket's project not found",
        )

    if project.organization_id != epic.organization_id:
        logger.warning(
            f"Cross-organization remove attempt: epic {epic_id} org {epic.organization_id}, "
            f"ticket {ticket_id} org {project.organization_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot remove ticket from different organization from epic",
        )

    # Remove ticket from epic
    success = repo.epics.remove_ticket_from_epic(epic_id, ticket_id)
    if not success:
        # Should not happen since we verified existence, but defensive check
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Epic or ticket not found",
        )

    # Log activity - command-based
    remove_cmd = EpicTicketRemoveCommand(epic_id=epic_id, ticket_id=ticket_id)
    log_activity(
        repo=repo,
        command=remove_cmd,
        entity_id=epic_id,
        actor_id=current_user.id,
        organization_id=epic.organization_id,
    )

    logger.info(f"Ticket {ticket_id} removed from epic {epic_id}")


@router.get("/{epic_id}/tickets", response_model=List[Ticket])
async def get_epic_tickets(
    epic_id: str,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> List[Ticket]:
    """Get all tickets in an epic.

    Permission rules:
    - Super Admin: Can access tickets in any epic
    - Other users: Can only access tickets in epics from their organization

    Args:
        epic_id: ID of epic
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        List of tickets in the epic

    Raises:
        HTTP 403: User does not have permission to access this epic
        HTTP 404: Epic not found
    """
    logger.debug(f"Getting tickets for epic: {epic_id} (by user {current_user.id})")

    # Verify epic exists
    epic = repo.epics.get_by_id(epic_id)
    if not epic:
        logger.debug(f"Epic not found: {epic_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Epic not found",
        )

    # Permission check: Non-Super-Admin can only access their own org's epics
    if current_user.role != UserRole.SUPER_ADMIN:
        if epic.organization_id != current_user.organization_id:
            logger.warning(f"User {current_user.id} attempted to access tickets in epic {epic_id} from different org")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: epic belongs to different organization",
            )

    # Get tickets in epic
    tickets = repo.epics.get_tickets_in_epic(epic_id)
    if tickets is None:
        # Should not happen since we verified existence, but defensive check
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Epic not found",
        )

    logger.debug(f"Retrieved {len(tickets)} tickets for epic {epic_id}")
    return tickets
