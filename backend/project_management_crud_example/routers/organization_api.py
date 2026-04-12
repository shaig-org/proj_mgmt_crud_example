"""Organization API endpoints.

This module provides organization CRUD endpoints with role-based permissions.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.dependencies import get_current_user, get_repository, get_super_admin_user
from project_management_crud_example.domain_models import (
    Organization,
    OrganizationCreateCommand,
    OrganizationData,
    OrganizationUpdateCommand,
    User,
)
from project_management_crud_example.exceptions import InsufficientPermissionsException
from project_management_crud_example.utils.activity_log_helpers import log_activity
from project_management_crud_example.utils.debug_helpers import log_diff_debug

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/organizations", tags=["organizations"])


@router.post("", response_model=Organization, status_code=status.HTTP_201_CREATED)
async def create_organization(
    organization_data: OrganizationData,
    repo: Repository = Depends(get_repository),  # noqa: B008
    super_admin: User = Depends(get_super_admin_user),  # noqa: B008
) -> Organization:
    """Create a new organization (Super Admin only).

    Args:
        organization_data: Organization data (name, description)
        repo: Repository instance for database access
        super_admin: Current Super Admin user (validates Super Admin permission)

    Returns:
        Created Organization with id and timestamps

    Raises:
        HTTP 403: User is not Super Admin
        HTTP 400: Organization with same name already exists
    """
    logger.info(f"Creating organization: {organization_data.name} (by user {super_admin.id})")

    command = OrganizationCreateCommand(organization_data=organization_data)

    try:
        organization = repo.organizations.create(command)

        # Create default workflow for the new organization
        try:
            default_workflow = repo.workflows.create_default_workflow(organization.id)
            logger.info(
                f"Default workflow created for organization: {organization.id} (workflow: {default_workflow.id})"
            )
        except Exception as e:
            # If default workflow creation fails, log but don't fail the organization creation
            # (this allows the system to remain functional even if workflow creation has issues)
            logger.error(f"Failed to create default workflow for organization {organization.id}: {e}")

        # Log activity - command-based
        log_activity(
            repo=repo,
            command=command,
            entity_id=organization.id,
            actor_id=super_admin.id,
            organization_id=organization.id,
        )

        logger.info(f"Organization created: {organization.id}")
        return organization
    except IntegrityError:
        logger.warning(f"Failed to create organization - duplicate name: {organization_data.name}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization with this name already exists",
        ) from None


@router.get("/{organization_id}", response_model=Organization)
async def get_organization(
    organization_id: str,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Organization:
    """Get organization by ID.

    Permission rules:
    - Super Admin: Can access any organization
    - Other users: Can only access their own organization

    Args:
        organization_id: ID of organization to retrieve
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        Organization if found and user has permission

    Raises:
        HTTP 403: User attempting to access different organization
        HTTP 404: Organization not found
    """
    logger.debug(f"Getting organization: {organization_id} (by user {current_user.id})")

    organization = repo.organizations.get_by_id(organization_id)

    if not organization:
        logger.debug(f"Organization not found: {organization_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Permission check: Super Admin can access any, others only their own
    from project_management_crud_example.domain_models import UserRole

    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.organization_id != organization_id:
            logger.warning(
                f"User {current_user.id} attempted to access organization {organization_id} "
                f"(belongs to {current_user.organization_id})"
            )
            raise InsufficientPermissionsException(detail="Cannot access other organizations")

    return organization


@router.get("", response_model=List[Organization])
async def list_organizations(
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> List[Organization]:
    """List organizations based on user permissions.

    Permission rules:
    - Super Admin: Returns all organizations
    - Other users: Returns only their assigned organization

    Args:
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        List of organizations user has access to
    """
    logger.debug(f"Listing organizations (by user {current_user.id})")

    from project_management_crud_example.domain_models import UserRole

    if current_user.role == UserRole.SUPER_ADMIN:
        # Super Admin sees all organizations
        organizations = repo.organizations.get_all()
        logger.debug(f"Super Admin retrieved {len(organizations)} organizations")
        return organizations
    else:
        # Regular users see only their organization
        if current_user.organization_id is None:
            logger.warning(f"User {current_user.id} has no organization_id")
            return []

        organization = repo.organizations.get_by_id(current_user.organization_id)
        if not organization:
            logger.warning(f"User {current_user.id} organization not found: {current_user.organization_id}")
            return []

        logger.debug(f"User retrieved their organization: {organization.id}")
        return [organization]


@router.put("/{organization_id}", response_model=Organization)
async def update_organization(
    organization_id: str,
    update_data: OrganizationUpdateCommand,
    repo: Repository = Depends(get_repository),  # noqa: B008
    super_admin: User = Depends(get_super_admin_user),  # noqa: B008
) -> Organization:
    """Update an organization (Super Admin only).

    Args:
        organization_id: ID of organization to update
        update_data: Fields to update (name, description, is_active)
        repo: Repository instance for database access
        super_admin: Current Super Admin user (validates Super Admin permission)

    Returns:
        Updated Organization

    Raises:
        HTTP 403: User is not Super Admin
        HTTP 404: Organization not found
        HTTP 400: Updating to duplicate name
    """
    logger.info(f"Updating organization: {organization_id} (by user {super_admin.id})")

    # Get existing organization for debug logging
    existing_organization = repo.organizations.get_by_id(organization_id)
    if not existing_organization:
        logger.debug(f"Organization not found for update: {organization_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    try:
        updated_organization = repo.organizations.update(organization_id, update_data)

        if not updated_organization:
            # Should not happen as we checked existence above
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            )

        # Debug logging: show what changed
        log_diff_debug(existing_organization, updated_organization, "organization", "update_organization")

        # Log activity - command-based
        log_activity(
            repo=repo,
            command=update_data,
            entity_id=organization_id,
            actor_id=super_admin.id,
            organization_id=organization_id,
        )

        logger.info(f"Organization updated: {organization_id}")
        return updated_organization
    except IntegrityError:
        logger.warning(f"Failed to update organization - duplicate name: {organization_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization with this name already exists",
        ) from None
