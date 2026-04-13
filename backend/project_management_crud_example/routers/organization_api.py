"""Organization API endpoints (capability-based, scope-split)."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from project_management_crud_example.capabilities import (
    GlobalOrganizationWriteCapability,
    OrganizationReadCapability,
)
from project_management_crud_example.dependencies import (
    get_global_organization_write_capability,
    get_organization_read_capability,
)
from project_management_crud_example.domain_models import (
    Organization,
    OrganizationCreateCommand,
    OrganizationData,
    OrganizationUpdateCommand,
)
from project_management_crud_example.utils.activity_log_helpers import log_activity
from project_management_crud_example.utils.debug_helpers import log_diff_debug

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/organizations", tags=["organizations"])


@router.post("", response_model=Organization, status_code=status.HTTP_201_CREATED)
async def create_organization(
    organization_data: OrganizationData,
    cap: GlobalOrganizationWriteCapability = Depends(get_global_organization_write_capability),  # noqa: B008
) -> Organization:
    """Create organization (Super Admin only — enforced at DI factory)."""
    command = OrganizationCreateCommand(organization_data=organization_data)
    try:
        organization = cap.create(command)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization with this name already exists",
        ) from None

    try:
        cap.repo.workflows.create_default_workflow(organization.id)
    except Exception as e:
        logger.error(f"Failed to create default workflow for organization {organization.id}: {e}")

    log_activity(
        repo=cap.repo,
        command=command,
        entity_id=organization.id,
        actor_id=cap.user.id,
        organization_id=organization.id,
    )
    return organization


@router.get("/{organization_id}", response_model=Organization)
async def get_organization(
    organization_id: str,
    cap: OrganizationReadCapability = Depends(get_organization_read_capability),  # noqa: B008
) -> Organization:
    organization = cap.get_by_id(organization_id)
    if not organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return organization


@router.get("", response_model=List[Organization])
async def list_organizations(
    cap: OrganizationReadCapability = Depends(get_organization_read_capability),  # noqa: B008
) -> List[Organization]:
    return cap.list_visible()


@router.put("/{organization_id}", response_model=Organization)
async def update_organization(
    organization_id: str,
    update_data: OrganizationUpdateCommand,
    cap: GlobalOrganizationWriteCapability = Depends(get_global_organization_write_capability),  # noqa: B008
) -> Organization:
    """Update organization (Super Admin only — enforced at DI factory)."""
    existing_organization = cap.repo.organizations.get_by_id(organization_id)
    if not existing_organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    try:
        updated = cap.update(organization_id, update_data)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization with this name already exists",
        ) from None

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    log_diff_debug(existing_organization, updated, "organization", "update_organization")
    log_activity(
        repo=cap.repo,
        command=update_data,
        entity_id=organization_id,
        actor_id=cap.user.id,
        organization_id=organization_id,
    )
    return updated
