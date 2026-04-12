"""Workflow management API endpoints.

This module provides REST API endpoints for managing custom workflows.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.dependencies import get_current_user, get_repository
from project_management_crud_example.domain_models import (
    User,
    UserRole,
    Workflow,
    WorkflowCreateCommand,
    WorkflowData,
    WorkflowDeleteCommand,
    WorkflowUpdateCommand,
)
from project_management_crud_example.utils.activity_log_helpers import log_activity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.post("", response_model=Workflow, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    workflow_data: WorkflowData,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Workflow:
    """Create a new workflow.

    Permission rules:
    - Super Admin: Can create workflow in any organization
    - Admin, Project Manager: Can create workflow in their organization
    - Other roles: Cannot create workflows

    Args:
        workflow_data: Workflow data (name, description, statuses)
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        Created workflow

    Raises:
        HTTP 403: User does not have permission to create workflows
    """
    logger.debug(f"Creating workflow: {workflow_data.name} (by user {current_user.id})")

    # Permission check: Admin, PM, and Super Admin can create
    allowed_roles = {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.PROJECT_MANAGER}
    if current_user.role not in allowed_roles:
        logger.warning(f"User {current_user.id} ({current_user.role}) attempted to create workflow without permission")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create workflows",
        )

    # Determine organization (users always create in their own org)
    organization_id = current_user.organization_id
    if not organization_id:
        logger.error(f"User {current_user.id} has no organization_id")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization",
        )

    # Create workflow
    command = WorkflowCreateCommand(workflow_data=workflow_data, organization_id=organization_id)
    workflow = repo.workflows.create(command)

    # Log activity
    log_activity(
        repo=repo,
        command=command,
        entity_id=workflow.id,
        actor_id=current_user.id,
        organization_id=organization_id,
    )

    logger.info(f"Workflow created: {workflow.id}")
    return workflow


@router.get("/{workflow_id}", response_model=Workflow)
async def get_workflow(
    workflow_id: str,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Workflow:
    """Get a specific workflow by ID.

    Permission rules:
    - Super Admin: Can access any workflow
    - Other users: Can only access workflows in their organization

    Args:
        workflow_id: ID of workflow to retrieve
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        Workflow data

    Raises:
        HTTP 403: User does not have permission to access this workflow
        HTTP 404: Workflow not found
    """
    logger.debug(f"Getting workflow: {workflow_id} (by user {current_user.id})")

    workflow = repo.workflows.get_by_id(workflow_id)
    if not workflow:
        logger.debug(f"Workflow not found: {workflow_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Permission check: Non-Super-Admin can only access their own org's workflows
    if current_user.role != UserRole.SUPER_ADMIN:
        if workflow.organization_id != current_user.organization_id:
            logger.warning(f"User {current_user.id} attempted to access workflow {workflow_id} from different org")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,  # Return 404 to prevent information leakage
                detail="Workflow not found",
            )

    return workflow


@router.get("", response_model=List[Workflow])
async def list_workflows(
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> List[Workflow]:
    """List all workflows accessible to the current user.

    Permission rules:
    - Super Admin: Can see all workflows across all organizations
    - Other users: Can only see workflows in their organization

    Args:
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        List of workflows (including default workflow)
    """
    logger.debug(f"Listing workflows (by user {current_user.id})")

    # Super Admin sees all workflows
    if current_user.role == UserRole.SUPER_ADMIN:
        logger.debug("Super Admin listing all workflows")
        return repo.workflows.get_all()

    # Other users see workflows in their organization
    organization_id = current_user.organization_id
    if not organization_id:
        logger.error(f"User {current_user.id} has no organization_id")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization",
        )

    workflows = repo.workflows.get_by_organization_id(organization_id)
    logger.debug(f"Found {len(workflows)} workflows for organization {organization_id}")
    return workflows


@router.put("/{workflow_id}", response_model=Workflow)
async def update_workflow(
    workflow_id: str,
    update_data: WorkflowUpdateCommand,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Workflow:
    """Update an existing workflow.

    Permission rules:
    - Super Admin: Can update any workflow
    - Admin, Project Manager: Can update workflows in their organization
    - Other roles: Cannot update workflows

    Note: Cannot change is_default flag.

    Args:
        workflow_id: ID of workflow to update
        update_data: Fields to update (name, description, statuses)
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        Updated workflow

    Raises:
        HTTP 403: User does not have permission to update this workflow
        HTTP 404: Workflow not found
        HTTP 400: Update would break existing tickets
    """
    logger.debug(f"Updating workflow: {workflow_id} (by user {current_user.id})")

    # Permission check: Admin, PM, and Super Admin can update
    allowed_roles = {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.PROJECT_MANAGER}
    if current_user.role not in allowed_roles:
        logger.warning(f"User {current_user.id} ({current_user.role}) attempted to update workflow without permission")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update workflows",
        )

    # Get workflow
    workflow = repo.workflows.get_by_id(workflow_id)
    if not workflow:
        logger.debug(f"Workflow not found: {workflow_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Permission check: Non-Super-Admin can only update workflows in their org
    if current_user.role != UserRole.SUPER_ADMIN:
        if workflow.organization_id != current_user.organization_id:
            logger.warning(f"User {current_user.id} attempted to update workflow {workflow_id} from different org")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update workflow from different organization",
            )

    # Validate status update won't break existing tickets
    if update_data.statuses is not None:
        # Check if we're removing any statuses
        old_statuses = set(workflow.statuses)
        new_statuses = set(update_data.statuses)
        removed_statuses = old_statuses - new_statuses

        if removed_statuses:
            # Check if any tickets are using the statuses being removed
            invalid_statuses = repo.workflows.check_status_usage(workflow_id, list(removed_statuses))
            if invalid_statuses:
                status_list = ", ".join(sorted(invalid_statuses))
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot update workflow: statuses {{{status_list}}} are currently used by tickets. "
                    f"Please update the tickets first before removing these statuses from the workflow.",
                )

    # Update workflow
    updated_workflow = repo.workflows.update(workflow_id, update_data)
    if not updated_workflow:
        # This shouldn't happen since we already checked existence
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Log activity
    log_activity(
        repo=repo,
        command=update_data,
        entity_id=workflow_id,
        actor_id=current_user.id,
        organization_id=workflow.organization_id,
    )

    logger.info(f"Workflow updated: {workflow_id}")
    return updated_workflow


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: str,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> None:
    """Delete a workflow.

    Permission rules:
    - Super Admin: Can delete any workflow (except default workflows)
    - Admin: Can delete workflows in their organization (except default workflows)
    - Other roles: Cannot delete workflows

    Cannot delete workflows that:
    - Are default workflows (is_default=true)
    - Are currently used by any projects

    Args:
        workflow_id: ID of workflow to delete
        repo: Repository instance for database access
        current_user: Current authenticated user

    Raises:
        HTTP 403: User does not have permission to delete this workflow
        HTTP 404: Workflow not found
        HTTP 400: Cannot delete (is default or in use)
    """
    logger.debug(f"Deleting workflow: {workflow_id} (by user {current_user.id})")

    # Permission check: Only Admin and Super Admin can delete
    allowed_roles = {UserRole.SUPER_ADMIN, UserRole.ADMIN}
    if current_user.role not in allowed_roles:
        logger.warning(f"User {current_user.id} ({current_user.role}) attempted to delete workflow without permission")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete workflows",
        )

    # Get workflow
    workflow = repo.workflows.get_by_id(workflow_id)
    if not workflow:
        logger.debug(f"Workflow not found: {workflow_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Permission check: Non-Super-Admin can only delete workflows in their org
    if current_user.role != UserRole.SUPER_ADMIN:
        if workflow.organization_id != current_user.organization_id:
            logger.warning(f"User {current_user.id} attempted to delete workflow {workflow_id} from different org")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete workflow from different organization",
            )

    # Cannot delete default workflow
    if workflow.is_default:
        logger.warning(f"Attempt to delete default workflow: {workflow_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete default workflow",
        )

    # Check if workflow is used by any projects
    projects_using_workflow = repo.projects.count_by_workflow_id(workflow_id)
    if projects_using_workflow > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete workflow: {projects_using_workflow} project(s) are using it",
        )

    # Delete workflow
    command = WorkflowDeleteCommand(workflow_id=workflow_id)
    success = repo.workflows.delete(workflow_id)
    if not success:
        # This shouldn't happen since we already checked existence
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Log activity
    log_activity(
        repo=repo,
        command=command,
        entity_id=workflow_id,
        actor_id=current_user.id,
        organization_id=workflow.organization_id,
    )

    logger.info(f"Workflow deleted: {workflow_id}")
