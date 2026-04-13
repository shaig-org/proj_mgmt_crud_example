"""User Management API endpoints (capability-based)."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from project_management_crud_example.capabilities import (
    OrgUserWriteCapability,
    SelfUserWriteCapability,
    UserReadCapability,
)
from project_management_crud_example.dependencies import (
    get_org_user_write_capability,
    get_self_user_write_capability,
    get_user_read_capability,
)
from project_management_crud_example.domain_models import (
    SelfUserUpdateCommand,
    User,
    UserCreateCommand,
    UserCreateResponse,
    UserData,
    UserDeleteCommand,
    UserRole,
    UserUpdateCommand,
)
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
    cap: OrgUserWriteCapability = Depends(get_org_user_write_capability),  # noqa: B008
) -> UserCreateResponse:
    """Create a new user with auto-generated password."""
    if role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign super_admin role via this endpoint",
        )

    cap.authorize_create(organization_id, role)

    # Verify organization exists
    organization = cap.repo.organizations.get_by_id(organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization not found",
        )

    generated_password = generate_password()
    command = UserCreateCommand(
        user_data=user_data,
        password=generated_password,
        organization_id=organization_id,
        role=role,
    )

    try:
        created_user = cap.repo.users.create(command)
    except IntegrityError as e:
        error_msg = str(e.orig) if hasattr(e, "orig") else str(e)
        if "username" in error_msg.lower() or "UNIQUE constraint failed: users.username" in error_msg:
            detail = "Username already exists"
        elif "email" in error_msg.lower():
            detail = "Email already exists in this organization"
        else:
            detail = "User creation failed due to constraint violation"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from None

    log_activity(
        repo=cap.repo,
        command=command,
        entity_id=created_user.id,
        actor_id=cap.user.id,
        organization_id=organization_id,
    )
    return UserCreateResponse(user=created_user, generated_password=generated_password)


@router.get("/{user_id}", response_model=User)
async def get_user(
    user_id: str,
    cap: UserReadCapability = Depends(get_user_read_capability),  # noqa: B008
) -> User:
    """Get user by ID."""
    user = cap.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("", response_model=List[User])
async def list_users(
    organization_id: Optional[str] = Query(None),  # noqa: B008
    role: Optional[UserRole] = Query(None),  # noqa: B008
    is_active: Optional[bool] = Query(None),  # noqa: B008
    cap: UserReadCapability = Depends(get_user_read_capability),  # noqa: B008
) -> List[User]:
    """List users."""
    return cap.list_users(organization_id=organization_id, role=role, is_active=is_active)


@router.put("/me", response_model=User)
async def update_own_profile(
    update_data: SelfUserUpdateCommand,
    cap: SelfUserWriteCapability = Depends(get_self_user_write_capability),  # noqa: B008
) -> User:
    """Update the authenticated user's own profile (email, full_name).

    Scope is baked into the capability: there is no path, via this endpoint,
    to reach any other user's record. Privileged fields (role, is_active) are
    not representable on `SelfUserUpdateCommand`.
    """
    existing_user = cap.repo.users.get_by_id(cap.user.id)
    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    try:
        updated_user = cap.update_profile(update_data)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists in this organization",
        ) from None

    if not updated_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    log_diff_debug(existing_user, updated_user, "user", "update_own_profile")
    log_activity(
        repo=cap.repo,
        command=update_data,
        entity_id=cap.user.id,
        actor_id=cap.user.id,
        organization_id=updated_user.organization_id or "",
    )
    return updated_user


@router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: str,
    update_data: UserUpdateCommand,
    cap: OrgUserWriteCapability = Depends(get_org_user_write_capability),  # noqa: B008
) -> User:
    """Update user details."""
    existing_user = cap.repo.users.get_by_id(user_id)
    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    cap.authorize_update(existing_user)

    if update_data.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign super_admin role via this endpoint",
        )

    try:
        updated_user = cap.update(user_id, update_data)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists in this organization",
        ) from None

    if not updated_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    log_diff_debug(existing_user, updated_user, "user", "update_user")
    log_activity(
        repo=cap.repo,
        command=update_data,
        entity_id=user_id,
        actor_id=cap.user.id,
        organization_id=updated_user.organization_id or "",
    )
    return updated_user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    cap: OrgUserWriteCapability = Depends(get_org_user_write_capability),  # noqa: B008
) -> None:
    """Delete a user (Super Admin only)."""
    cap.require_super_admin_for_delete()

    user = cap.repo.users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    try:
        success = cap.repo.users.delete(user_id)
    except IntegrityError as e:
        error_detail = str(e).split("\n")[0] if str(e) else "Cannot delete user: user has created data"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail) from None

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    log_diff_debug(user, None, "user", "delete_user")
    delete_cmd = UserDeleteCommand(user_id=user_id)
    log_activity(
        repo=cap.repo,
        command=delete_cmd,
        entity_id=user_id,
        actor_id=cap.user.id,
        organization_id=user.organization_id or "",
        snapshot=user.model_dump(mode="json", exclude_none=True),
    )
