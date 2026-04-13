"""Shared helpers for capability unit tests.

Capability tests exercise the capability classes directly with an in-memory
repository and synthesized users. They do not use the FastAPI TestClient.
"""

from __future__ import annotations

from typing import Callable

import pytest

from project_management_crud_example.capabilities.errors import CapabilityPermissionError
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import Organization, User, UserRole
from tests.dal.helpers import create_test_org_via_repo, create_test_user_via_repo  # noqa: F401


def make_user(
    test_repo: Repository,
    org: Organization,
    role: UserRole,
    username: str | None = None,
) -> User:
    """Create a user in the given org with the specified role."""
    username = username or f"{role.name.lower()}_{org.id[:6]}"
    return create_test_user_via_repo(
        test_repo,
        org_id=org.id,
        username=username,
        role=role,
    )


def make_super_admin(test_repo: Repository, org: Organization | None = None) -> User:
    """Super admin may belong to any org (or none); for tests we attach one."""
    if org is None:
        org = create_test_org_via_repo(test_repo, name="SA Org")
    return create_test_user_via_repo(
        test_repo,
        org_id=org.id,
        username=f"super_{org.id[:6]}",
        role=UserRole.SUPER_ADMIN,
    )


def assert_denied(
    callable_: Callable[..., object],
    *args: object,
    **kwargs: object,
) -> CapabilityPermissionError:
    """Run a callable and assert it raised CapabilityPermissionError with non-empty detail."""
    with pytest.raises(CapabilityPermissionError) as exc_info:
        callable_(*args, **kwargs)
    assert exc_info.value.detail, "CapabilityPermissionError.detail must not be empty"
    return exc_info.value
