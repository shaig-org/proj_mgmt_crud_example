"""Authentication API endpoints.

This module provides authentication endpoints including login.
"""

import logging

from fastapi import APIRouter, Depends

from project_management_crud_example.capabilities import PasswordChangeCapability
from project_management_crud_example.config import settings
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.dependencies import get_password_change_capability, get_repository
from project_management_crud_example.domain_models import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
)
from project_management_crud_example.exceptions import AccountInactiveException, InvalidCredentialsException
from project_management_crud_example.utils.jwt import create_access_token

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
    cap: PasswordChangeCapability = Depends(get_password_change_capability),  # noqa: B008
) -> dict:
    """Change the authenticated user's own password via the capability."""
    logger.debug(f"Password change request for user: {cap.user.id}")
    cap.change_own_password(request.current_password, request.new_password)
    logger.info(f"Password changed successfully for user: {cap.user.id}")
    return {"message": "Password changed successfully"}
