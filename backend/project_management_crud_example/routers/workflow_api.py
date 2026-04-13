"""Workflow management API endpoints (capability-based)."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from project_management_crud_example.capabilities import WorkflowReadCapability, WorkflowWriteCapability
from project_management_crud_example.dependencies import (
    get_workflow_read_capability,
    get_workflow_write_capability,
)
from project_management_crud_example.domain_models import (
    Workflow,
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
    cap: WorkflowWriteCapability = Depends(get_workflow_write_capability),  # noqa: B008
) -> Workflow:
    try:
        command = cap.build_create_command(workflow_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    workflow = cap.create(command)
    log_activity(
        repo=cap.repo,
        command=command,
        entity_id=workflow.id,
        actor_id=cap.user.id,
        organization_id=command.organization_id,
    )
    return workflow


@router.get("/{workflow_id}", response_model=Workflow)
async def get_workflow(
    workflow_id: str,
    cap: WorkflowReadCapability = Depends(get_workflow_read_capability),  # noqa: B008
) -> Workflow:
    workflow = cap.get_by_id(workflow_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return workflow


@router.get("", response_model=List[Workflow])
async def list_workflows(
    cap: WorkflowReadCapability = Depends(get_workflow_read_capability),  # noqa: B008
) -> List[Workflow]:
    try:
        return cap.list_workflows()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None


@router.put("/{workflow_id}", response_model=Workflow)
async def update_workflow(
    workflow_id: str,
    update_data: WorkflowUpdateCommand,
    cap: WorkflowWriteCapability = Depends(get_workflow_write_capability),  # noqa: B008
) -> Workflow:
    workflow = cap.load_for_update(workflow_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    if update_data.statuses is not None:
        old_statuses = set(workflow.statuses)
        new_statuses = set(update_data.statuses)
        removed_statuses = old_statuses - new_statuses
        if removed_statuses:
            invalid_statuses = cap.repo.workflows.check_status_usage(workflow_id, list(removed_statuses))
            if invalid_statuses:
                status_list = ", ".join(sorted(invalid_statuses))
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Cannot update workflow: statuses {{{status_list}}} are currently used by tickets. "
                        "Please update the tickets first before removing these statuses from the workflow."
                    ),
                )

    updated = cap.update(workflow_id, update_data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    log_activity(
        repo=cap.repo,
        command=update_data,
        entity_id=workflow_id,
        actor_id=cap.user.id,
        organization_id=workflow.organization_id,
    )
    return updated


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: str,
    cap: WorkflowWriteCapability = Depends(get_workflow_write_capability),  # noqa: B008
) -> None:
    workflow = cap.load_for_delete(workflow_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    if workflow.is_default:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete default workflow")

    projects_using_workflow = cap.repo.projects.count_by_workflow_id(workflow_id)
    if projects_using_workflow > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete workflow: {projects_using_workflow} project(s) are using it",
        )

    if not cap.delete(workflow_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    command = WorkflowDeleteCommand(workflow_id=workflow_id)
    log_activity(
        repo=cap.repo,
        command=command,
        entity_id=workflow_id,
        actor_id=cap.user.id,
        organization_id=workflow.organization_id,
    )
