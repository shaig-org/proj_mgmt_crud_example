"""E2E testing utility endpoints.

These endpoints are ONLY available when E2E_TESTING environment variable is set to "true".
They provide utilities for test cleanup and verification during end-to-end testing.

SECURITY: These endpoints can delete all data and should NEVER be enabled in production.
"""

import os

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.dependencies import get_repository

router = APIRouter(
    prefix="/e2e",
    tags=["e2e-testing"],
)


class E2EClearResponse(BaseModel):
    """Response model for clear operations."""

    cleared: bool
    message: str


class E2EStatsResponse(BaseModel):
    """Response model for database statistics."""

    total_users: int
    total_organizations: int
    total_projects: int
    total_epics: int
    total_tickets: int
    total_workflows: int


def _check_e2e_mode() -> None:
    """Verify that E2E testing mode is enabled.

    Raises:
        HTTPException: 403 if E2E_TESTING environment variable is not set to "true"
    """
    if os.getenv("E2E_TESTING") != "true":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="E2E endpoints are only available when E2E_TESTING=true environment variable is set",
        )


@router.delete("/clear-all", response_model=E2EClearResponse)
async def clear_all_e2e_data(repo: Repository = Depends(get_repository)) -> E2EClearResponse:  # noqa: B008
    """Clear ALL data from the E2E test database.

    This endpoint deletes all records from all tables in the correct order to handle
    foreign key constraints. It's used for global cleanup after E2E test runs.

    Security:
        Only available when E2E_TESTING environment variable is set to "true"

    Returns:
        Confirmation that data was cleared

    Raises:
        HTTPException: 403 if not in E2E testing mode
    """
    _check_e2e_mode()

    # Delete in order to respect foreign key constraints
    # Order: child tables first, parent tables last

    # 1. Delete tickets (has FK to epic, project)
    tickets = repo.tickets.get_all()
    for ticket in tickets:
        repo.tickets.delete(ticket.id)

    # 2. Delete epics (has FK to project)
    epics = repo.epics.get_all()
    for epic in epics:
        repo.epics.delete(epic.id)

    # 3. Delete projects (has FK to organization)
    projects = repo.projects.get_all()
    for project in projects:
        repo.projects.delete(project.id)

    # 4. Delete workflows (has FK to organization)
    workflows = repo.workflows.get_all()
    for workflow in workflows:
        repo.workflows.delete(workflow.id)

    # 5. Delete users (has FK to organization)
    users = repo.users.get_all()
    for user in users:
        # Skip super admin to avoid breaking bootstrap
        if user.username == "admin":
            continue
        repo.users.delete(user.id)

    # 6. Delete organizations (parent table)
    organizations = repo.organizations.get_all()
    for org in organizations:
        repo.organizations.delete(org.id)

    return E2EClearResponse(
        cleared=True,
        message="All E2E test data cleared successfully",
    )


@router.get("/stats", response_model=E2EStatsResponse)
async def get_e2e_stats(repo: Repository = Depends(get_repository)) -> E2EStatsResponse:  # noqa: B008
    """Get statistics about current database content.

    Useful for verifying cleanup and debugging test issues.

    Security:
        Only available when E2E_TESTING environment variable is set to "true"

    Returns:
        Count of records in each main table

    Raises:
        HTTPException: 403 if not in E2E testing mode
    """
    _check_e2e_mode()

    return E2EStatsResponse(
        total_users=len(repo.users.get_all()),
        total_organizations=len(repo.organizations.get_all()),
        total_projects=len(repo.projects.get_all()),
        total_epics=len(repo.epics.get_all()),
        total_tickets=len(repo.tickets.get_all()),
        total_workflows=len(repo.workflows.get_all()),
    )
