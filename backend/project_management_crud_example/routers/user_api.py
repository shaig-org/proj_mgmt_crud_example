"""User Management API endpoints.

This module provides user CRUD endpoints with role-based permissions.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.dependencies import (
    get_admin_user,
    get_current_user,
    get_repository,
    get_super_admin_user,
)
from project_management_crud_example.domain_models import (
    User,
    UserCreateResponse,
    UserData,
    UserDeleteCommand,
    UserRole,
    UserUpdateCommand,
)
from project_management_crud_example.exceptions import InsufficientPermissionsException
from project_management_crud_example.utils.activity_log_helpers import log_activity
from project_management_crud_example.utils.debug_helpers import log_diff_debug
from project_management_crud_example.utils.password import generate_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post("", response_model=UserCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserData,
    organization_id: str,
    role: UserRole,
    repo: Repository = Depends(get_repository),  # noqa: B008
    admin: User = Depends(get_admin_user),  # noqa: B008
) -> UserCreateResponse:
    """Create a new user with auto-generated password.

    Permission rules:
    - Super Admin: Can create users in any organization
    - Organization Admin: Can only create users in their own organization
    - Cannot assign super_admin role via this endpoint (system-level only)

    Args:
        user_data: User data (username, email, full_name)
        organization_id: Organization to assign user to
        role: User role (admin, project_manager, write_access, read_access)
        repo: Repository instance for database access
        admin: Current admin user (validates admin permission)

    Returns:
        UserCreateResponse with user details and generated_password

    Raises:
        HTTP 403: Non-Super Admin trying to create user in different organization
        HTTP 400: Invalid role, duplicate username/email, or non-existent organization
    """
    logger.info(
        f"Creating user: {user_data.username} in organization {organization_id} "
        f"with role {role.value} (by user {admin.id})"
    )

    # Prevent assigning super_admin role via API
    if role == UserRole.SUPER_ADMIN:
        logger.warning(f"Attempted to create super_admin via API by user {admin.id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign super_admin role via this endpoint",
        )

    # Permission check: Org Admin can only create users in their own organization
    if admin.role != UserRole.SUPER_ADMIN:
        if admin.organization_id != organization_id:
            logger.warning(f"Org Admin {admin.id} attempted to create user in different organization {organization_id}")
            raise InsufficientPermissionsException(detail="Can only create users in your own organization")

    # Verify organization exists
    organization = repo.organizations.get_by_id(organization_id)
    if not organization:
        logger.warning(f"Attempted to create user in non-existent organization: {organization_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization not found",
        )

    # Generate secure password
    generated_password = generate_password()

    # Create user
    from project_management_crud_example.domain_models import UserCreateCommand

    command = UserCreateCommand(
        user_data=user_data,
        password=generated_password,
        organization_id=organization_id,
        role=role,
    )

    try:
        created_user = repo.users.create(command)
        logger.info(f"User created: {created_user.id} (username: {user_data.username})")

        # Log activity - command-based
        log_activity(
            repo=repo,
            command=command,
            entity_id=created_user.id,
            actor_id=admin.id,
            organization_id=organization_id,
        )

        return UserCreateResponse(
            user=created_user,
            generated_password=generated_password,
        )
    except IntegrityError as e:
        logger.warning(f"Failed to create user - integrity error: {user_data.username}")
        error_msg = str(e.orig) if hasattr(e, "orig") else str(e)

        if "username" in error_msg.lower() or "UNIQUE constraint failed: users.username" in error_msg:
            detail = "Username already exists"
        elif "email" in error_msg.lower():
            detail = "Email already exists in this organization"
        else:
            detail = "User creation failed due to constraint violation"

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from None


@router.get("/{user_id}", response_model=User)
async def get_user(
    user_id: str,
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> User:
    """Get user by ID.

    Permission rules:
    - Super Admin: Can access any user
    - Other users: Can only access users in their organization

    Args:
        user_id: ID of user to retrieve
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        User if found and user has permission

    Raises:
        HTTP 404: User not found or not in same organization
    """
    logger.debug(f"Getting user: {user_id} (by user {current_user.id})")

    user = repo.users.get_by_id(user_id)

    if not user:
        logger.debug(f"User not found: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Permission check: Super Admin can access any, others only their own org
    if current_user.role != UserRole.SUPER_ADMIN:
        if user.organization_id != current_user.organization_id:
            logger.warning(f"User {current_user.id} attempted to access user {user_id} from different organization")
            # Return 404 to avoid leaking cross-organization user existence
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

    return user


@router.get("", response_model=List[User])
async def list_users(
    organization_id: Optional[str] = Query(None, description="Filter by organization ID (Super Admin only)"),  # noqa: B008
    role: Optional[UserRole] = Query(None, description="Filter by user role"),  # noqa: B008
    is_active: Optional[bool] = Query(None, description="Filter by active status"),  # noqa: B008
    repo: Repository = Depends(get_repository),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> List[User]:
    """List users based on permissions and filters.

    Permission rules:
    - Super Admin: Can see all users, can filter by organization_id
    - Other users: Can only see users in their organization, organization_id filter ignored

    Args:
        organization_id: Filter by organization (Super Admin only)
        role: Filter by user role
        is_active: Filter by active status
        repo: Repository instance for database access
        current_user: Current authenticated user

    Returns:
        List of users matching filters and permission scope
    """
    logger.debug(f"Listing users (by user {current_user.id})")

    # Override organization_id filter for non-Super Admins
    if current_user.role != UserRole.SUPER_ADMIN:
        # Regular users can only see users in their own organization
        organization_id = current_user.organization_id
        logger.debug(f"Non-Super Admin, restricting to organization: {organization_id}")

    # Get filtered users
    users = repo.users.get_by_filters(
        organization_id=organization_id,
        role=role,
        is_active=is_active,
    )

    logger.debug(f"Retrieved {len(users)} users")
    return users


@router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: str,
    update_data: UserUpdateCommand,
    repo: Repository = Depends(get_repository),  # noqa: B008
    admin: User = Depends(get_admin_user),  # noqa: B008
) -> User:
    """Update user details.

    Permission rules:
    - Super Admin: Can update any user
    - Organization Admin: Can only update users in their organization

    Note: username, organization_id, and password cannot be changed via this endpoint.

    Args:
        user_id: ID of user to update
        update_data: Fields to update (email, full_name, role, is_active)
        repo: Repository instance for database access
        admin: Current admin user (validates admin permission)

    Returns:
        Updated User

    Raises:
        HTTP 403: Non-Super Admin trying to update user in different organization
        HTTP 404: User not found
        HTTP 400: Validation error (e.g., duplicate email)
    """
    logger.info(f"Updating user: {user_id} (by user {admin.id})")

    # Check if user exists
    existing_user = repo.users.get_by_id(user_id)
    if not existing_user:
        logger.debug(f"User not found for update: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Permission check: Org Admin can only update users in their org
    if admin.role != UserRole.SUPER_ADMIN:
        if existing_user.organization_id != admin.organization_id:
            logger.warning(f"Org Admin {admin.id} attempted to update user {user_id} from different organization")
            raise InsufficientPermissionsException(detail="Can only update users in your own organization")

    # Prevent assigning super_admin role via API
    if update_data.role == UserRole.SUPER_ADMIN:
        logger.warning(f"Attempted to assign super_admin role via API by user {admin.id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign super_admin role via this endpoint",
        )

    # Capture old state for debug logging
    old_user = existing_user

    try:
        updated_user = repo.users.update(user_id, update_data)

        if not updated_user:
            # Should not happen as we checked existence above
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Debug logging: show what changed
        log_diff_debug(old_user, updated_user, "user", "update_user")

        # Log activity - command-based
        log_activity(
            repo=repo,
            command=update_data,
            entity_id=user_id,
            actor_id=admin.id,
            organization_id=updated_user.organization_id or "",  # Handle None for super admin
        )

        logger.info(f"User updated: {user_id}")
        return updated_user
    except IntegrityError:
        logger.warning(f"Failed to update user - integrity error: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists in this organization",
        ) from None


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    repo: Repository = Depends(get_repository),  # noqa: B008
    super_admin: User = Depends(get_super_admin_user),  # noqa: B008
) -> None:
    """Delete a user (Super Admin only).

    Only Super Admins can delete users. Users who have created data (tickets)
    cannot be deleted to maintain data integrity.

    Args:
        user_id: ID of user to delete
        repo: Repository instance for database access
        super_admin: Current Super Admin user

    Raises:
        HTTP 403: User is not Super Admin
        HTTP 404: User not found
        HTTP 400: User has created data and cannot be deleted
    """
    logger.info(f"Deleting user: {user_id} (by Super Admin {super_admin.id})")

    # Get user before deletion for snapshot
    user = repo.users.get_by_id(user_id)
    if not user:
        logger.debug(f"User not found for deletion: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    try:
        success = repo.users.delete(user_id)

        if not success:
            # Should not happen as we checked existence above
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Debug logging: show what was deleted
        log_diff_debug(user, None, "user", "delete_user")

        # Log activity - command-based with snapshot
        delete_cmd = UserDeleteCommand(user_id=user_id)
        log_activity(
            repo=repo,
            command=delete_cmd,
            entity_id=user_id,
            actor_id=super_admin.id,
            organization_id=user.organization_id or "",  # Handle None for super admin
            snapshot=user.model_dump(mode="json", exclude_none=True),
        )

        logger.info(f"User deleted: {user_id}")
    except IntegrityError as e:
        logger.warning(f"Cannot delete user {user_id}: has created data")
        # Extract a meaningful error message from the IntegrityError
        error_detail = str(e).split("\n")[0] if str(e) else "Cannot delete user: user has created data"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail,
        ) from None
