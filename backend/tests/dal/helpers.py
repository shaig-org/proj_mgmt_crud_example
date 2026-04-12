"""Helper functions for repository tests.

This module provides simple helper functions to create common test entities
via repository methods, reducing boilerplate in repository test files.
"""

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    ActionType,
    ActivityLog,
    ActivityLogCreateCommand,
    Epic,
    EpicCreateCommand,
    EpicData,
    Organization,
    OrganizationCreateCommand,
    OrganizationData,
    Project,
    ProjectCreateCommand,
    ProjectData,
    User,
    UserCreateCommand,
    UserData,
    UserRole,
)


def create_test_org_via_repo(test_repo: Repository, name: str = "Test Org") -> Organization:
    """Create test organization via repository.

    Note: Does NOT create default workflow automatically. Use create_test_org_with_workflow_via_repo
    if you need a default workflow for projects.

    Args:
        test_repo: Repository instance
        name: Organization name (default: "Test Org")

    Returns:
        Created Organization domain model
    """
    org_data = OrganizationData(name=name)
    return test_repo.organizations.create(OrganizationCreateCommand(organization_data=org_data))


def create_test_org_with_workflow_via_repo(test_repo: Repository, name: str = "Test Org") -> Organization:
    """Create test organization with default workflow via repository.

    This is a convenience helper for tests that need to create projects (which require workflows).

    Args:
        test_repo: Repository instance
        name: Organization name (default: "Test Org")

    Returns:
        Created Organization domain model (with default workflow created)
    """
    org_data = OrganizationData(name=name)
    org = test_repo.organizations.create(OrganizationCreateCommand(organization_data=org_data))

    # Create default workflow for the organization (required for projects)
    test_repo.workflows.create_default_workflow(org.id)

    return org


def create_test_project_via_repo(
    test_repo: Repository, org_id: str, name: str = "Test Project", description: str | None = None
) -> Project:
    """Create test project via repository.

    Args:
        test_repo: Repository instance
        org_id: Organization ID for the project
        name: Project name (default: "Test Project")
        description: Optional project description

    Returns:
        Created Project domain model
    """
    project_data = ProjectData(name=name, description=description)
    return test_repo.projects.create(ProjectCreateCommand(project_data=project_data, organization_id=org_id))


def create_test_user_via_repo(
    test_repo: Repository,
    org_id: str,
    username: str = "testuser",
    email: str | None = None,
    full_name: str | None = None,
    role: UserRole = UserRole.ADMIN,
    password: str = "password",
) -> User:
    """Create test user via repository.

    Args:
        test_repo: Repository instance
        org_id: Organization ID for the user
        username: Username (default: "testuser")
        email: Email (default: {username}@test.com)
        full_name: Full name (default: capitalized username)
        role: User role (default: ADMIN)
        password: Password (default: "password")

    Returns:
        Created User domain model
    """
    email = email or f"{username}@test.com"
    full_name = full_name or username.replace("_", " ").title()

    user_data = UserData(username=username, email=email, full_name=full_name)
    command = UserCreateCommand(user_data=user_data, password=password, organization_id=org_id, role=role)
    return test_repo.users.create(command)


def create_test_epic_via_repo(
    test_repo: Repository, org_id: str, name: str = "Test Epic", description: str | None = None
) -> Epic:
    """Create test epic via repository.

    Args:
        test_repo: Repository instance
        org_id: Organization ID for the epic
        name: Epic name (default: "Test Epic")
        description: Optional epic description

    Returns:
        Created Epic domain model
    """
    epic_data = EpicData(name=name, description=description)
    return test_repo.epics.create(EpicCreateCommand(epic_data=epic_data, organization_id=org_id))


def create_test_activity_log_via_repo(
    test_repo: Repository,
    entity_type: str = "ticket",
    entity_id: str = "test-entity-id",
    action: ActionType = ActionType.TICKET_CREATED,
    actor_id: str = "test-user-id",
    organization_id: str = "test-org-id",
    changes: dict | None = None,
    metadata: dict | None = None,
) -> ActivityLog:
    """Create test activity log via repository.

    Args:
        test_repo: Repository instance
        entity_type: Type of entity (default: "ticket")
        entity_id: Entity ID (default: "test-entity-id")
        action: Action type (default: TICKET_CREATED)
        actor_id: User who performed action (default: "test-user-id")
        organization_id: Organization ID (default: "test-org-id")
        changes: Changes dict (default: simple created dict)
        metadata: Optional metadata dict

    Returns:
        Created ActivityLog domain model
    """
    if changes is None:
        changes = {"created": {"name": "Test"}}

    command = ActivityLogCreateCommand(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
        organization_id=organization_id,
        changes=changes,
        metadata=metadata,
    )
    return test_repo.activity_logs.create(command)
