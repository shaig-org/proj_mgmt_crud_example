"""Shared dependency injection functions for FastAPI.

This module provides shared dependency functions that can be used across
the application and routers without creating circular imports.
"""

import os
from typing import Iterator, Optional

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from project_management_crud_example.dal.sqlite.database import Database
from project_management_crud_example.dal.sqlite.repository import Repository, StubEntityRepository
from project_management_crud_example.domain_models import User, UserRole
from project_management_crud_example.exceptions import (
    AccountInactiveException,
    AuthenticationRequiredException,
    InsufficientPermissionsException,
    InvalidTokenError,
    InvalidTokenException,
    TokenExpiredError,
    TokenExpiredException,
)
from project_management_crud_example.utils.jwt import decode_access_token

# Global database instance
_db_instance: Database | None = None


def _get_db_path() -> str:
    """Get the appropriate database path based on environment.

    Returns:
        Database file path based on testing environment:
        - E2E_TESTING=true -> project_management_crud_example_e2e.db
        - TESTING=true -> stub_entities_test.db (for unit tests)
        - Otherwise -> project_management_crud_example.db (development)
    """
    if os.getenv("E2E_TESTING") == "true":
        return "project_management_crud_example_e2e.db"
    elif os.getenv("TESTING") == "true":
        return "stub_entities_test.db"
    return "project_management_crud_example.db"


def get_database(db_path: str | None = None) -> Database:
    """Get or create the database instance.

    Args:
        db_path: Optional override for database path. If not provided,
                uses environment-based detection.
    """
    global _db_instance
    if _db_instance is None:
        actual_path = db_path if db_path is not None else _get_db_path()
        _db_instance = Database(actual_path)
    return _db_instance


def get_db_session() -> Iterator[Session]:
    """Dependency to get database session."""
    db = get_database()
    with db.get_session() as session:
        yield session


def get_repository(session: Session = Depends(get_db_session)) -> Repository:  # noqa: B008
    """Dependency to get the main repository instance."""
    return Repository(session)


async def get_current_user(
    authorization: Optional[str] = Header(None),
    repo: Repository = Depends(get_repository),  # noqa: B008
) -> User:
    """Extract and validate user from Bearer token.

    Args:
        authorization: Authorization header value (format: "Bearer <token>")
        repo: Repository instance for database access

    Returns:
        User domain model with current role and is_active status

    Raises:
        AuthenticationRequiredException: No authorization header provided
        InvalidTokenException: Token is malformed or invalid
        TokenExpiredException: Token has expired
        AccountInactiveException: User account is inactive

    Note:
        - User role is fetched from database on every request
        - This ensures immediate effect of permission changes and user deactivation
    """
    # Check if authorization header is provided
    if not authorization:
        raise AuthenticationRequiredException()

    # Validate authorization header format
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise InvalidTokenException()

    token = parts[1]

    # Decode and validate token
    try:
        claims = decode_access_token(token)
    except TokenExpiredError:
        raise TokenExpiredException() from None
    except InvalidTokenError:
        raise InvalidTokenException() from None

    # Fetch user from database to get current role and is_active status
    user = repo.users.get_by_id(claims.user_id)
    if not user:
        raise InvalidTokenException()

    # Check if user is active
    if not user.is_active:
        raise AccountInactiveException()

    return user


async def get_super_admin_user(
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> User:
    """Verify that current user is a Super Admin.

    Args:
        current_user: Current authenticated user

    Returns:
        User if they are Super Admin

    Raises:
        InsufficientPermissionsException: User is not a Super Admin
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise InsufficientPermissionsException(detail="Super Admin access required")

    return current_user


async def get_admin_user(
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> User:
    """Verify that current user is an Admin (Super Admin or Organization Admin).

    Args:
        current_user: Current authenticated user

    Returns:
        User if they are Admin or Super Admin

    Raises:
        InsufficientPermissionsException: User is not an admin
    """
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        raise InsufficientPermissionsException(detail="Admin access required")

    return current_user


def get_stub_entity_repo(session: Session = Depends(get_db_session)) -> StubEntityRepository:  # noqa: B008
    """Dependency to get stub entity repository - template for creating real repository dependencies."""
    return StubEntityRepository(session)
