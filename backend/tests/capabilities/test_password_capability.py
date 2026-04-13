"""Unit tests for PasswordChangeCapability."""

from __future__ import annotations

import pytest

from project_management_crud_example.capabilities.password_capability import (
    PasswordChangeCapability,
    PasswordChangeError,
)
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import User, UserRole
from project_management_crud_example.exceptions import InvalidCredentialsException
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import create_test_org_via_repo, create_test_user_via_repo


def _seed_user(test_repo: Repository, password: str = "OldPass123!") -> User:
    org = create_test_org_via_repo(test_repo, name="Org")
    return create_test_user_via_repo(
        test_repo,
        org_id=org.id,
        username="alice",
        role=UserRole.WRITE_ACCESS,
        password=password,
    )


def test_change_own_password_succeeds_with_valid_inputs(test_repo: Repository) -> None:
    user = _seed_user(test_repo, password="OldPass123!")
    cap = PasswordChangeCapability(test_repo, user)
    cap.change_own_password("OldPass123!", "NewPass456!")

    refreshed = test_repo.users.get_by_username_with_password("alice")
    assert refreshed is not None
    assert test_repo.password_hasher.verify_password("NewPass456!", refreshed.password_hash)


def test_change_own_password_rejects_wrong_current_password(test_repo: Repository) -> None:
    user = _seed_user(test_repo, password="OldPass123!")
    cap = PasswordChangeCapability(test_repo, user)
    with pytest.raises(InvalidCredentialsException):
        cap.change_own_password("WrongPass!", "NewPass456!")


def test_change_own_password_rejects_weak_new_password(test_repo: Repository) -> None:
    user = _seed_user(test_repo, password="OldPass123!")
    cap = PasswordChangeCapability(test_repo, user)
    with pytest.raises(PasswordChangeError) as exc:
        cap.change_own_password("OldPass123!", "weak")
    assert exc.value.detail
