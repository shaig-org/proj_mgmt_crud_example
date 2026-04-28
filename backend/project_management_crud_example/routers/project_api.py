"""Project API endpoints.

Authorization decisions are delegated to the Project capabilities; 403 / 404
responses are produced by the CapabilityPermissionError / CapabilityNotFoundError
exception handlers. Routes that operate on a single project depend on the
`BoundProjectWriteCapability`, which is already scoped (auth + existence
resolved) before the handler runs.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from project_management_crud_example.capabilities import (
    BoundProjectWriteCapability,
    OrgProjectWriteCapability,
    ProjectReadCapability,
)
from project_management_crud_example.dependencies import (
    get_bound_project_write_capability,
    get_org_project_write_capability,
    get_project_read_capability,
)
from project_management_crud_example.domain_models import (
    Project,
    ProjectData,
    ProjectUpdateCommand,
)

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
        project = cap.create(command)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None

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
    update_data: ProjectUpdateCommand,
    cap: BoundProjectWriteCapability = Depends(get_bound_project_write_capability),  # noqa: B008
) -> Project:
    """Update an existing project."""
    try:
        updated = cap.update(update_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    logger.info(f"Project updated: {updated.id}")
    return updated


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    cap: BoundProjectWriteCapability = Depends(get_bound_project_write_capability),  # noqa: B008
) -> None:
    """Delete a project."""
    project_id = cap.current.id
    cap.delete()
    logger.info(f"Project deleted: {project_id}")


@router.patch("/{project_id}/archive", response_model=Project)
async def archive_project(
    cap: BoundProjectWriteCapability = Depends(get_bound_project_write_capability),  # noqa: B008
) -> Project:
    """Archive a project."""
    archived = cap.archive()
    logger.info(f"Project archived: {archived.id}")
    return archived


@router.patch("/{project_id}/unarchive", response_model=Project)
async def unarchive_project(
    cap: BoundProjectWriteCapability = Depends(get_bound_project_write_capability),  # noqa: B008
) -> Project:
    """Unarchive a project."""
    unarchived = cap.unarchive()
    logger.info(f"Project unarchived: {unarchived.id}")
    return unarchived
