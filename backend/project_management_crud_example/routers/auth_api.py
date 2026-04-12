"""Authentication API endpoints.

This module provides authentication endpoints including login.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from project_management_crud_example.config import settings
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.dependencies import get_current_user, get_repository
from project_management_crud_example.domain_models import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    PasswordChangeCommand,
    User,
)
from project_management_crud_example.exceptions import AccountInactiveException, InvalidCredentialsException
from project_management_crud_example.utils.activity_log_helpers import log_activity
from project_management_crud_example.utils.jwt import create_access_token
from project_management_crud_example.utils.password import validate_password_strength

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    repo: Repository = Depends(get_repository),  # noqa: B008
) -> LoginResponse:
    """Authenticate user and issue JWT token.

    Args:
        request: Login credentials (username and password)
        repo: Repository instance for database access

    Returns:
        LoginResponse with JWT token and user information

    Raises:
        InvalidCredentialsException: Username not found or password incorrect
        AccountInactiveException: User account is inactive

    Note:
        - Username lookup is case-insensitive
        - Password verification is case-sensitive
        - Error messages do not reveal username existence
    """
    logger.debug(f"Login attempt for username: {request.username}")

    # Fetch user authentication data (domain model with password hash)
    user_auth = repo.users.get_by_username_with_password(request.username)

    # Check if user exists
    if not user_auth:
        logger.debug(f"User not found: {request.username}")
        raise InvalidCredentialsException()

    # Check if user is active
    if not user_auth.is_active:
        logger.debug(f"User inactive: {request.username}")
        raise AccountInactiveException()

    # Verify password
    if not repo.password_hasher.verify_password(request.password, user_auth.password_hash):
        logger.debug(f"Invalid password for user: {request.username}")
        raise InvalidCredentialsException()

    # Generate JWT token (role is NOT included - fetched from DB on each request)
    access_token = create_access_token(
        user_id=user_auth.id,
        organization_id=user_auth.organization_id,
    )

    logger.info(f"User logged in successfully: {request.username} (ID: {user_auth.id})")

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_SECONDS,
        user_id=user_auth.id,
        organization_id=user_auth.organization_id,
        role=user_auth.role,
    )


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
    repo: Repository = Depends(get_repository),  # noqa: B008
) -> dict:
    """Change the authenticated user's password.

    Args:
        request: Password change request with current and new passwords
        current_user: Current authenticated user from bearer token
        repo: Repository instance for database access

    Returns:
        Success message

    Raises:
        InvalidCredentialsException: Current password is incorrect
        HTTPException 400: New password does not meet strength requirements

    Note:
        - User can only change their own password
        - Current password must be correct
        - New password must meet strength requirements (8+ chars, upper, lower, digit, special)
        - Existing tokens remain valid after password change (stateless tokens)
    """
    logger.debug(f"Password change request for user: {current_user.id}")

    # Fetch user with password hash for verification
    user_auth = repo.users.get_by_username_with_password(current_user.username)

    if not user_auth:
        logger.error(f"User not found during password change: {current_user.id}")
        raise InvalidCredentialsException()

    # Verify current password
    if not repo.password_hasher.verify_password(request.current_password, user_auth.password_hash):
        logger.debug(f"Invalid current password for user: {current_user.id}")
        raise InvalidCredentialsException()

    # Validate new password strength
    is_valid, error_message = validate_password_strength(request.new_password)
    if not is_valid:
        logger.debug(f"Weak password rejected for user {current_user.id}: {error_message}")
        raise HTTPException(status_code=400, detail=error_message)

    # Update password
    success = repo.users.update_password(current_user.id, request.new_password)

    if not success:
        logger.error(f"Failed to update password for user: {current_user.id}")
        raise HTTPException(status_code=500, detail="Failed to update password")

    # Log activity - password change (no actual passwords logged)
    password_change_cmd = PasswordChangeCommand(user_id=current_user.id)
    log_activity(
        repo=repo,
        command=password_change_cmd,
        entity_id=current_user.id,
        actor_id=current_user.id,  # User changing their own password
        organization_id=current_user.organization_id or "",  # Handle None for super admin
    )

    logger.info(f"Password changed successfully for user: {current_user.id}")
    return {"message": "Password changed successfully"}
