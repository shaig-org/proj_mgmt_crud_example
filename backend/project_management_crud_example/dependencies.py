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
from project_management_crud_example.utils.password import PasswordHasher, TestPasswordHasher

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
        # Mark the Database as testing under E2E so bootstrap_data uses the
        # fast password hasher (SHA256, ~0.001ms vs bcrypt's ~300ms). Combined
        # with TestPasswordHasher in get_repository(), this removes the
        # bcrypt bottleneck under high E2E parallelism.
        is_testing = os.getenv("E2E_TESTING") == "true" or os.getenv("TESTING") == "true"
        _db_instance = Database(actual_path, is_testing=is_testing)
    return _db_instance


def get_db_session() -> Iterator[Session]:
    """Dependency to get database session."""
    db = get_database()
    with db.get_session() as session:
        yield session


# Module-level so we hash-once-decide-once instead of re-checking the env per request.
# Production: secure 12-round bcrypt. E2E: SHA256 (~0.001ms vs ~300ms) — see
# utils/password.py TestPasswordHasher for why this is safe in test contexts only.
_PASSWORD_HASHER: PasswordHasher | TestPasswordHasher = (
    TestPasswordHasher() if os.getenv("E2E_TESTING") == "true" else PasswordHasher(is_secure=True)
)


def get_repository(session: Session = Depends(get_db_session)) -> Repository:  # noqa: B008
    """Dependency to get the main repository instance."""
    return Repository(session, password_hasher=_PASSWORD_HASHER)


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


# ---------------------------------------------------------------------------
# Capability factories
#
# These are the only new places allowed to reference `get_repository` outside
# the documented exception list (see docs/tasks/capability-di/plan.md). Every
# route handler should depend on a capability rather than on Repository
# directly.
# ---------------------------------------------------------------------------


from project_management_crud_example.capabilities import (  # noqa: E402
    ActivityLogReadCapability,
    CommentReadCapability,
    EpicReadCapability,
    GlobalOrganizationWriteCapability,
    OrganizationReadCapability,
    OrgCommentModerationCapability,
    OrgEpicWriteCapability,
    OrgProjectWriteCapability,
    OrgTicketWriteCapability,
    OrgUserWriteCapability,
    OrgWorkflowWriteCapability,
    OwnCommentWriteCapability,
    PasswordChangeCapability,
    ProjectReadCapability,
    SelfUserWriteCapability,
    TicketReadCapability,
    UserReadCapability,
    WorkflowReadCapability,
)


def get_password_change_capability(
    repo: Repository = Depends(get_repository),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> PasswordChangeCapability:
    return PasswordChangeCapability(repo, user)


def get_project_read_capability(
    repo: Repository = Depends(get_repository),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> ProjectReadCapability:
    return ProjectReadCapability(repo, user)


def get_org_project_write_capability(
    repo: Repository = Depends(get_repository),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> OrgProjectWriteCapability:
    return OrgProjectWriteCapability(repo, user)


def get_user_read_capability(
    repo: Repository = Depends(get_repository),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> UserReadCapability:
    return UserReadCapability(repo, user)


def get_self_user_write_capability(
    repo: Repository = Depends(get_repository),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> SelfUserWriteCapability:
    """Self-only user writes. No authorization gate needed — scope is baked in."""
    return SelfUserWriteCapability(repo, user)


def get_org_user_write_capability(
    repo: Repository = Depends(get_repository),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> OrgUserWriteCapability:
    """Org-scoped user writes. Admin gate enforced at the factory so non-admins
    cannot even construct the capability; they get 403 before the handler runs."""
    from project_management_crud_example.capabilities.errors import CapabilityPermissionError
    from project_management_crud_example.domain_models import UserRole

    if user.role not in {UserRole.SUPER_ADMIN, UserRole.ADMIN}:
        raise CapabilityPermissionError("Admin access required")
    return OrgUserWriteCapability(repo, user)


def get_organization_read_capability(
    repo: Repository = Depends(get_repository),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> OrganizationReadCapability:
    return OrganizationReadCapability(repo, user)


def get_global_organization_write_capability(
    repo: Repository = Depends(get_repository),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> GlobalOrganizationWriteCapability:
    """Super-admin-only global writes on organizations. Role enforced at the
    factory so non-super-admins cannot construct it; they 403 before handler."""
    from project_management_crud_example.capabilities.errors import CapabilityPermissionError
    from project_management_crud_example.domain_models import UserRole

    if user.role != UserRole.SUPER_ADMIN:
        raise CapabilityPermissionError("Super Admin access required")
    return GlobalOrganizationWriteCapability(repo, user)


def get_epic_read_capability(
    repo: Repository = Depends(get_repository),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> EpicReadCapability:
    return EpicReadCapability(repo, user)


def get_org_epic_write_capability(
    repo: Repository = Depends(get_repository),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> OrgEpicWriteCapability:
    return OrgEpicWriteCapability(repo, user)


def get_workflow_read_capability(
    repo: Repository = Depends(get_repository),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> WorkflowReadCapability:
    return WorkflowReadCapability(repo, user)


def get_org_workflow_write_capability(
    repo: Repository = Depends(get_repository),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> OrgWorkflowWriteCapability:
    return OrgWorkflowWriteCapability(repo, user)


def get_ticket_read_capability(
    repo: Repository = Depends(get_repository),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> TicketReadCapability:
    return TicketReadCapability(repo, user)


def get_org_ticket_write_capability(
    repo: Repository = Depends(get_repository),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> OrgTicketWriteCapability:
    return OrgTicketWriteCapability(repo, user)


def get_comment_read_capability(
    repo: Repository = Depends(get_repository),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> CommentReadCapability:
    return CommentReadCapability(repo, user)


def get_own_comment_write_capability(
    repo: Repository = Depends(get_repository),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> OwnCommentWriteCapability:
    """Self-authored comment writes. Scope is baked in — author_id = caller.id."""
    return OwnCommentWriteCapability(repo, user)


def get_org_comment_moderation_capability(
    repo: Repository = Depends(get_repository),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> OrgCommentModerationCapability:
    """Admin-only moderation. Admin role enforced at the factory so non-admins
    cannot construct it; they 403 before the handler runs."""
    from project_management_crud_example.capabilities.errors import CapabilityPermissionError
    from project_management_crud_example.domain_models import UserRole

    if user.role not in {UserRole.SUPER_ADMIN, UserRole.ADMIN}:
        raise CapabilityPermissionError("Admin access required")
    return OrgCommentModerationCapability(repo, user)


def get_activity_log_read_capability(
    repo: Repository = Depends(get_repository),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> ActivityLogReadCapability:
    return ActivityLogReadCapability(repo, user)
