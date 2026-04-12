"""Project API endpoints.

This module provides project CRUD endpoints with role-based permissions and organization scoping.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.dependencies import get_current_user, get_repository
from project_management_crud_example.domain_models import (
    Project,
    ProjectArchiveCommand,
    ProjectCreateCommand,
    ProjectData,
    ProjectDeleteCommand,
    ProjectUnarchiveCommand,
    ProjectUpdateCommand,
    User,
    UserRole,
)
from project_management_crud_example.utils.activity_log_helpers import log_activity
from project_management_crud_example.utils.debug_helpers import log_diff_debug

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectData,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Project:
    """Create a new project within the user's organization.

    Permission rules:
    - Super Admin: Can create projects in any organization (must specify org in future)
    - Admin/Project Manager: Can create projects in their own organization
    - Other roles: Cannot create projects

    Args:
        project_data: Project data (name, description)
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        Created Project with id and timestamps

    Raises:
        HTTP 403: User does not have permission to create projects
        HTTP 400: Invalid data or organization not found
    """
    # Permission check: Only Admin, Project Manager, and Super Admin can create projects
    allowed_roles = {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.PROJECT_MANAGER}
    if current_user.role not in allowed_roles:
        logger.warning(f"User {current_user.id} ({current_user.role}) attempted to create project without permission")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create projects",
        )

    # For now, projects are created in the user's organization
    # TODO: In future, Super Admin might specify organization_id
    if not current_user.organization_id:
        logger.error(f"User {current_user.id} has no organization_id (Super Admin needs org support)")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create project: user has no organization",
        )

    logger.info(
        f"Creating project: {project_data.name} in org {current_user.organization_id} (by user {current_user.id})"
    )

    command = ProjectCreateCommand(
        project_data=project_data,
        organization_id=current_user.organization_id,
    )

    try:
        project = repo.projects.create(command)
        logger.info(f"Project created: {project.id}")

        # Log activity - command-based
        log_activity(
            repo=repo,
            command=command,
            entity_id=project.id,
            actor_id=current_user.id,
            organization_id=project.organization_id,
        )

        return project
    except ValueError as e:
        # Handle workflow validation errors
        logger.warning(f"Failed to create project: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None


@router.get("/{project_id}", response_model=Project)
async def get_project(
    project_id: str,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Project:
    """Get project by ID.

    Permission rules:
    - Super Admin: Can access any project
    - Other users: Can only access projects in their organization

    Args:
        project_id: ID of project to retrieve
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        Project if found and user has permission

    Raises:
        HTTP 403: User attempting to access project in different organization
        HTTP 404: Project not found
    """
    logger.debug(f"Getting project: {project_id} (by user {current_user.id})")

    project = repo.projects.get_by_id(project_id)

    if not project:
        logger.debug(f"Project not found: {project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Permission check: Super Admin can access any, others only their own org
    if current_user.role != UserRole.SUPER_ADMIN:
        if project.organization_id != current_user.organization_id:
            logger.warning(f"User {current_user.id} attempted to access project {project_id} from different org")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: project belongs to different organization",
            )

    return project


@router.get("", response_model=List[Project])
async def list_projects(
    name: Optional[str] = None,
    is_active: Optional[bool] = None,
    include_archived: bool = False,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> List[Project]:
    """List all projects accessible to the current user with optional filtering.

    Permission rules:
    - Super Admin: Can see all projects across all organizations
    - Other users: Can only see projects in their organization

    Query parameters:
    - name: Filter by name substring (case-insensitive)
    - is_active: Filter by active status (true/false)
    - include_archived: Include archived projects (default: false)

    Args:
        name: Optional name filter (substring search, case-insensitive)
        is_active: Optional filter for active/inactive projects
        include_archived: Include archived projects in results (default: False)
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        List of projects the user has permission to access, filtered by query parameters
    """
    logger.debug(
        f"Listing projects (by user {current_user.id}, role {current_user.role}, name={name}, "
        f"is_active={is_active}, include_archived={include_archived})"
    )

    # Determine organization filter based on user role
    organization_filter = None if current_user.role == UserRole.SUPER_ADMIN else current_user.organization_id

    # For non-Super Admin users with no organization, return empty list
    if current_user.role != UserRole.SUPER_ADMIN and not current_user.organization_id:
        logger.warning(f"User {current_user.id} has no organization_id")
        return []

    # Use filtering method with all criteria
    projects = repo.projects.get_by_filters(
        organization_id=organization_filter,
        name=name,
        is_active=is_active,
        include_archived=include_archived,
    )

    logger.debug(f"Retrieved {len(projects)} projects matching filters")
    return projects


@router.put("/{project_id}", response_model=Project)
async def update_project(
    project_id: str,
    update_data: ProjectUpdateCommand,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Project:
    """Update an existing project.

    Permission rules:
    - Super Admin: Can update any project
    - Admin/Project Manager: Can update projects in their organization
    - Other roles: Cannot update projects

    Args:
        project_id: ID of project to update
        update_data: Fields to update
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        Updated project

    Raises:
        HTTP 403: User does not have permission to update this project
        HTTP 404: Project not found
        HTTP 400: Invalid update data
    """
    logger.debug(f"Updating project: {project_id} (by user {current_user.id})")

    # Permission check: Only Admin, Project Manager, and Super Admin can update
    allowed_roles = {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.PROJECT_MANAGER}
    if current_user.role not in allowed_roles:
        logger.warning(f"User {current_user.id} ({current_user.role}) attempted to update project without permission")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update projects",
        )

    # Verify project exists
    project = repo.projects.get_by_id(project_id)
    if not project:
        logger.debug(f"Project not found: {project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Permission check: Non-Super-Admin can only update their own org's projects
    if current_user.role != UserRole.SUPER_ADMIN:
        if project.organization_id != current_user.organization_id:
            logger.warning(f"User {current_user.id} attempted to update project {project_id} from different org")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: project belongs to different organization",
            )

    # Capture old state for debug logging
    old_project = project

    try:
        updated_project = repo.projects.update(project_id, update_data)
        if not updated_project:
            # Should not happen since we verified existence, but defensive check
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )

        # Debug logging: show what changed
        log_diff_debug(old_project, updated_project, "project", "update_project")

        # Log activity - command-based
        log_activity(
            repo=repo,
            command=update_data,
            entity_id=project_id,
            actor_id=current_user.id,
            organization_id=updated_project.organization_id,
        )

        logger.info(f"Project updated: {project_id}")
        return updated_project
    except ValueError as e:
        # Handle workflow validation errors
        logger.warning(f"Failed to update project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> None:
    """Delete a project.

    Permission rules:
    - Super Admin: Can delete any project
    - Admin: Can delete projects in their organization
    - Other roles: Cannot delete projects

    Args:
        project_id: ID of project to delete
        repo: Repository instance for database access
        current_user: Current authenticated user

    Raises:
        HTTP 403: User does not have permission to delete this project
        HTTP 404: Project not found
    """
    logger.debug(f"Deleting project: {project_id} (by user {current_user.id})")

    # Permission check: Only Admin and Super Admin can delete
    allowed_roles = {UserRole.SUPER_ADMIN, UserRole.ADMIN}
    if current_user.role not in allowed_roles:
        logger.warning(f"User {current_user.id} ({current_user.role}) attempted to delete project without permission")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete projects",
        )

    # Verify project exists and capture snapshot
    project = repo.projects.get_by_id(project_id)
    if not project:
        logger.debug(f"Project not found: {project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Permission check: Non-Super-Admin can only delete their own org's projects
    if current_user.role != UserRole.SUPER_ADMIN:
        if project.organization_id != current_user.organization_id:
            logger.warning(f"User {current_user.id} attempted to delete project {project_id} from different org")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: project belongs to different organization",
            )

    success = repo.projects.delete(project_id)
    if not success:
        # Should not happen since we verified existence, but defensive check
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Debug logging: show what was deleted
    log_diff_debug(project, None, "project", "delete_project")

    # Log activity - command-based with snapshot
    delete_cmd = ProjectDeleteCommand(project_id=project_id)
    log_activity(
        repo=repo,
        command=delete_cmd,
        entity_id=project_id,
        actor_id=current_user.id,
        organization_id=project.organization_id,
        snapshot=project.model_dump(mode="json", exclude_none=True),
    )

    logger.info(f"Project deleted: {project_id}")


@router.patch("/{project_id}/archive", response_model=Project)
async def archive_project(
    project_id: str,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Project:
    """Archive a project (soft delete).

    Permission rules:
    - Super Admin: Can archive any project
    - Admin/Project Manager: Can archive projects in their organization
    - Other roles: Cannot archive projects

    Args:
        project_id: ID of project to archive
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        Archived project

    Raises:
        HTTP 403: User does not have permission to archive this project
        HTTP 404: Project not found
    """
    logger.debug(f"Archiving project: {project_id} (by user {current_user.id})")

    # Permission check: Admin, PM, and Super Admin can archive
    allowed_roles = {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.PROJECT_MANAGER}
    if current_user.role not in allowed_roles:
        logger.warning(f"User {current_user.id} ({current_user.role}) attempted to archive project without permission")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to archive projects",
        )

    # Verify project exists
    project = repo.projects.get_by_id(project_id)
    if not project:
        logger.debug(f"Project not found: {project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Permission check: Non-Super-Admin can only archive their own org's projects
    if current_user.role != UserRole.SUPER_ADMIN:
        if project.organization_id != current_user.organization_id:
            logger.warning(f"User {current_user.id} attempted to archive project {project_id} from different org")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: project belongs to different organization",
            )

    archived_project = repo.projects.archive(project_id)
    if not archived_project:
        # Should not happen since we verified existence, but defensive check
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Log activity - command-based
    archive_cmd = ProjectArchiveCommand(project_id=project_id)
    log_activity(
        repo=repo,
        command=archive_cmd,
        entity_id=project_id,
        actor_id=current_user.id,
        organization_id=archived_project.organization_id,
    )

    logger.info(f"Project archived: {project_id}")
    return archived_project


@router.patch("/{project_id}/unarchive", response_model=Project)
async def unarchive_project(
    project_id: str,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Project:
    """Unarchive a project (restore from archive).

    Permission rules:
    - Super Admin: Can unarchive any project
    - Admin: Can unarchive projects in their organization
    - Other roles: Cannot unarchive projects

    Args:
        project_id: ID of project to unarchive
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        Unarchived project

    Raises:
        HTTP 403: User does not have permission to unarchive this project
        HTTP 404: Project not found
    """
    logger.debug(f"Unarchiving project: {project_id} (by user {current_user.id})")

    # Permission check: Only Admin and Super Admin can unarchive
    allowed_roles = {UserRole.SUPER_ADMIN, UserRole.ADMIN}
    if current_user.role not in allowed_roles:
        logger.warning(
            f"User {current_user.id} ({current_user.role}) attempted to unarchive project without permission"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to unarchive projects",
        )

    # Verify project exists
    project = repo.projects.get_by_id(project_id)
    if not project:
        logger.debug(f"Project not found: {project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Permission check: Non-Super-Admin can only unarchive their own org's projects
    if current_user.role != UserRole.SUPER_ADMIN:
        if project.organization_id != current_user.organization_id:
            logger.warning(f"User {current_user.id} attempted to unarchive project {project_id} from different org")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: project belongs to different organization",
            )

    unarchived_project = repo.projects.unarchive(project_id)
    if not unarchived_project:
        # Should not happen since we verified existence, but defensive check
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Log activity - command-based
    unarchive_cmd = ProjectUnarchiveCommand(project_id=project_id)
    log_activity(
        repo=repo,
        command=unarchive_cmd,
        entity_id=project_id,
        actor_id=current_user.id,
        organization_id=unarchived_project.organization_id,
    )

    logger.info(f"Project unarchived: {project_id}")
    return unarchived_project
