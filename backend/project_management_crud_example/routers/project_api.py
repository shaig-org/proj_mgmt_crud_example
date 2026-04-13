"""Project API endpoints.

This module provides project CRUD endpoints. Authorization decisions are
delegated to the Project capabilities; 403 responses are produced by the
CapabilityPermissionError exception handler.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from project_management_crud_example.capabilities import OrgProjectWriteCapability, ProjectReadCapability
from project_management_crud_example.dependencies import (
    get_org_project_write_capability,
    get_project_read_capability,
)
from project_management_crud_example.domain_models import (
    Project,
    ProjectArchiveCommand,
    ProjectData,
    ProjectDeleteCommand,
    ProjectUnarchiveCommand,
    ProjectUpdateCommand,
)
from project_management_crud_example.utils.activity_log_helpers import log_activity
from project_management_crud_example.utils.debug_helpers import log_diff_debug

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectData,
    cap: OrgProjectWriteCapability = Depends(get_org_project_write_capability),  # noqa: B008
) -> Project:
    """Create a new project within the user's organization."""
    try:
        command = cap.build_create_command(project_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    try:
        project = cap.create(command)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None

    log_activity(
        repo=cap.repo,
        command=command,
        entity_id=project.id,
        actor_id=cap.user.id,
        organization_id=project.organization_id,
    )
    logger.info(f"Project created: {project.id}")
    return project


@router.get("/{project_id}", response_model=Project)
async def get_project(
    project_id: str,
    cap: ProjectReadCapability = Depends(get_project_read_capability),  # noqa: B008
) -> Project:
    """Get project by ID."""
    project = cap.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.get("", response_model=List[Project])
async def list_projects(
    name: Optional[str] = None,
    is_active: Optional[bool] = None,
    include_archived: bool = False,
    cap: ProjectReadCapability = Depends(get_project_read_capability),  # noqa: B008
) -> List[Project]:
    """List projects accessible to the current user with filters."""
    return cap.list_projects(name=name, is_active=is_active, include_archived=include_archived)


@router.put("/{project_id}", response_model=Project)
async def update_project(
    project_id: str,
    update_data: ProjectUpdateCommand,
    cap: OrgProjectWriteCapability = Depends(get_org_project_write_capability),  # noqa: B008
) -> Project:
    """Update an existing project."""
    old_project = cap.load_for_update(project_id)
    if not old_project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        updated = cap.update(project_id, update_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    log_diff_debug(old_project, updated, "project", "update_project")
    log_activity(
        repo=cap.repo,
        command=update_data,
        entity_id=project_id,
        actor_id=cap.user.id,
        organization_id=updated.organization_id,
    )
    logger.info(f"Project updated: {project_id}")
    return updated


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    cap: OrgProjectWriteCapability = Depends(get_org_project_write_capability),  # noqa: B008
) -> None:
    """Delete a project."""
    project = cap.load_for_delete(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if not cap.delete(project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    log_diff_debug(project, None, "project", "delete_project")
    delete_cmd = ProjectDeleteCommand(project_id=project_id)
    log_activity(
        repo=cap.repo,
        command=delete_cmd,
        entity_id=project_id,
        actor_id=cap.user.id,
        organization_id=project.organization_id,
        snapshot=project.model_dump(mode="json", exclude_none=True),
    )
    logger.info(f"Project deleted: {project_id}")


@router.patch("/{project_id}/archive", response_model=Project)
async def archive_project(
    project_id: str,
    cap: OrgProjectWriteCapability = Depends(get_org_project_write_capability),  # noqa: B008
) -> Project:
    """Archive a project."""
    project = cap.load_for_archive(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    archived = cap.archive(project_id)
    if not archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    archive_cmd = ProjectArchiveCommand(project_id=project_id)
    log_activity(
        repo=cap.repo,
        command=archive_cmd,
        entity_id=project_id,
        actor_id=cap.user.id,
        organization_id=archived.organization_id,
    )
    logger.info(f"Project archived: {project_id}")
    return archived


@router.patch("/{project_id}/unarchive", response_model=Project)
async def unarchive_project(
    project_id: str,
    cap: OrgProjectWriteCapability = Depends(get_org_project_write_capability),  # noqa: B008
) -> Project:
    """Unarchive a project."""
    project = cap.load_for_unarchive(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    unarchived = cap.unarchive(project_id)
    if not unarchived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    unarchive_cmd = ProjectUnarchiveCommand(project_id=project_id)
    log_activity(
        repo=cap.repo,
        command=unarchive_cmd,
        entity_id=project_id,
        actor_id=cap.user.id,
        organization_id=unarchived.organization_id,
    )
    logger.info(f"Project unarchived: {project_id}")
    return unarchived
