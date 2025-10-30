"""
Example property-based tests using Hypothesis.

This file demonstrates concrete examples of property-based testing patterns
for the project management CRUD application. These examples can be adapted
for actual implementation.

NOTE: This is an EXAMPLE file to illustrate the concepts. To implement
property-based testing, create a proper structure under tests/property_based/.
"""

import re
from typing import Any

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule
from sqlalchemy.exc import IntegrityError

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    OrganizationCreateCommand,
    OrganizationData,
    UserCreateCommand,
    UserData,
    UserRole,
    UserUpdateCommand,
    WorkflowCreateCommand,
    WorkflowData,
)

# NOTE: To run these tests, first install hypothesis:
# uv add --dev hypothesis

# Custom strategies for domain models
USERNAME_CHARS = st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-")


@st.composite
def usernames(draw: Any) -> str:
    """Generate valid usernames (3-50 chars, alphanumeric + underscore + dash)."""
    return draw(st.text(min_size=3, max_size=50, alphabet=USERNAME_CHARS))


@st.composite
def emails(draw: Any) -> str:
    """Generate valid email addresses."""
    local = draw(st.text(min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("Ll", "Nd"))))
    domain = draw(st.text(min_size=1, max_size=63, alphabet=st.characters(whitelist_categories=("Ll", "Nd"))))
    tld = draw(st.sampled_from(["com", "org", "net", "edu"]))
    return f"{local}@{domain}.{tld}"


@st.composite
def organization_names(draw: Any) -> str:
    """Generate valid organization names (1-255 chars)."""
    return draw(st.text(min_size=1, max_size=255))


@st.composite
def workflow_statuses(draw: Any) -> list[str]:
    """Generate valid workflow status lists."""
    # Valid pattern: ^[A-Z0-9_-]+$
    status_chars = st.characters(whitelist_categories=("Lu", "Nd"), whitelist_characters="_-")
    statuses = draw(
        st.lists(st.text(min_size=1, max_size=50, alphabet=status_chars), min_size=1, max_size=20, unique=True)
    )
    return statuses


# =============================================================================
# Example 1: Roundtrip Properties (Repository Layer)
# =============================================================================


class TestUserRepositoryProperties:
    """Example property-based tests for User repository."""

    @given(username=usernames(), email=emails())
    def test_user_username_roundtrip(self, test_repo: Repository, username: str, email: str) -> None:
        """Any valid username should survive create-retrieve roundtrip."""
        # Arrange
        org_data = OrganizationData(name="Test Org")
        org = test_repo.organizations.create(OrganizationCreateCommand(organization_data=org_data))

        user_data = UserData(username=username, email=email, full_name="Test User")

        # Act
        created = test_repo.users.create(
            UserCreateCommand(user_data=user_data, password="Pass123!", organization_id=org.id, role=UserRole.ADMIN)
        )
        retrieved = test_repo.users.get_by_id(created.id)

        # Assert
        assert retrieved is not None
        assert retrieved.username == username
        assert retrieved.email == email

    @given(username=usernames(), new_email=emails())
    def test_partial_update_preserves_other_fields(
        self, test_repo: Repository, username: str, new_email: str
    ) -> None:
        """Updating one field should not modify other fields."""
        # Arrange
        org_data = OrganizationData(name="Test Org")
        org = test_repo.organizations.create(OrganizationCreateCommand(organization_data=org_data))

        user_data = UserData(username=username, email="original@test.com", full_name="Original Name")
        user = test_repo.users.create(
            UserCreateCommand(user_data=user_data, password="Pass123!", organization_id=org.id, role=UserRole.ADMIN)
        )

        # Act
        test_repo.users.update(user.id, UserUpdateCommand(email=new_email))

        # Assert
        updated = test_repo.users.get_by_id(user.id)
        assert updated is not None
        assert updated.email == new_email
        assert updated.username == username  # Unchanged
        assert updated.full_name == "Original Name"  # Unchanged
        assert updated.role == UserRole.ADMIN  # Unchanged

    @given(username=usernames())
    def test_deleted_user_returns_none(self, test_repo: Repository, username: str) -> None:
        """Deleted user should return None on get_by_id."""
        # Arrange
        org_data = OrganizationData(name="Test Org")
        org = test_repo.organizations.create(OrganizationCreateCommand(organization_data=org_data))

        user_data = UserData(username=username, email=f"{username}@test.com", full_name="Test")
        user = test_repo.users.create(
            UserCreateCommand(user_data=user_data, password="Pass123!", organization_id=org.id, role=UserRole.ADMIN)
        )

        # Act
        test_repo.users.delete(user.id)

        # Assert
        retrieved = test_repo.users.get_by_id(user.id)
        assert retrieved is None

    @given(password=st.text(min_size=8, max_size=100))
    def test_password_never_equals_hash(self, test_repo: Repository, password: str) -> None:
        """Password hash should never equal the plaintext password."""
        # Arrange
        org_data = OrganizationData(name="Test Org")
        org = test_repo.organizations.create(OrganizationCreateCommand(organization_data=org_data))

        user_data = UserData(username="testuser", email="test@test.com", full_name="Test")

        # Act
        user = test_repo.users.create(
            UserCreateCommand(user_data=user_data, password=password, organization_id=org.id, role=UserRole.ADMIN)
        )

        # Get user with password hash
        auth_data = test_repo.users.get_by_username_with_password("testuser")

        # Assert
        assert auth_data is not None
        assert auth_data.password_hash != password
        assert len(auth_data.password_hash) > len(password)  # Hash is longer

    @given(
        username1=usernames(),
        username2=usernames(),
    )
    def test_creating_duplicate_usernames_fails(self, test_repo: Repository, username1: str, username2: str) -> None:
        """Creating users with duplicate usernames should fail."""
        # Only test when usernames are actually the same
        assume(username1.lower() == username2.lower())

        org_data = OrganizationData(name="Test Org")
        org = test_repo.organizations.create(OrganizationCreateCommand(organization_data=org_data))

        # First user succeeds
        user_data1 = UserData(username=username1, email="user1@test.com", full_name="User 1")
        test_repo.users.create(
            UserCreateCommand(user_data=user_data1, password="Pass123!", organization_id=org.id, role=UserRole.ADMIN)
        )

        # Second user with same username (different case) fails
        user_data2 = UserData(username=username2, email="user2@test.com", full_name="User 2")
        with pytest.raises(IntegrityError):
            test_repo.users.create(
                UserCreateCommand(
                    user_data=user_data2, password="Pass123!", organization_id=org.id, role=UserRole.ADMIN
                )
            )


# =============================================================================
# Example 2: Organization Properties
# =============================================================================


class TestOrganizationRepositoryProperties:
    """Example property-based tests for Organization repository."""

    @given(name=organization_names())
    def test_organization_name_roundtrip(self, test_repo: Repository, name: str) -> None:
        """Any valid organization name should survive create-retrieve roundtrip."""
        # Act
        org_data = OrganizationData(name=name)
        created = test_repo.organizations.create(OrganizationCreateCommand(organization_data=org_data))
        retrieved = test_repo.organizations.get_by_id(created.id)

        # Assert
        assert retrieved is not None
        assert retrieved.name == name

    @given(name1=organization_names(), name2=organization_names())
    def test_duplicate_organization_names_fail(self, test_repo: Repository, name1: str, name2: str) -> None:
        """Creating organizations with duplicate names should fail."""
        # Only test when names are actually the same
        assume(name1 == name2)

        org_data1 = OrganizationData(name=name1)
        test_repo.organizations.create(OrganizationCreateCommand(organization_data=org_data1))

        org_data2 = OrganizationData(name=name2)
        with pytest.raises(IntegrityError):
            test_repo.organizations.create(OrganizationCreateCommand(organization_data=org_data2))


# =============================================================================
# Example 3: Workflow Properties
# =============================================================================


class TestWorkflowRepositoryProperties:
    """Example property-based tests for Workflow repository."""

    @given(statuses=workflow_statuses())
    def test_workflow_statuses_are_unique(self, test_repo: Repository, statuses: list[str]) -> None:
        """Workflow statuses must be unique within a workflow."""
        # Act
        workflow_data = WorkflowData(name="Test Workflow", statuses=statuses)
        workflow = test_repo.workflows.create(WorkflowCreateCommand(workflow_data=workflow_data))

        # Assert
        assert len(workflow.statuses) == len(set(workflow.statuses))
        assert len(workflow.statuses) == len(statuses)

    @given(statuses=workflow_statuses())
    def test_workflow_statuses_match_pattern(self, test_repo: Repository, statuses: list[str]) -> None:
        """Workflow statuses must match pattern ^[A-Z0-9_-]+$."""
        # Act
        workflow_data = WorkflowData(name="Test Workflow", statuses=statuses)
        workflow = test_repo.workflows.create(WorkflowCreateCommand(workflow_data=workflow_data))

        # Assert
        for status in workflow.statuses:
            assert re.match(r"^[A-Z0-9_-]+$", status) is not None


# =============================================================================
# Example 4: Idempotency Properties
# =============================================================================


class TestIdempotencyProperties:
    """Example tests for idempotent operations."""

    def test_create_super_admin_idempotent(self, test_repo: Repository) -> None:
        """Creating super admin multiple times should not duplicate."""
        # First creation
        created1, user1 = test_repo.users.create_super_admin_if_needed("superadmin", "Pass123!")
        assert created1 is True
        assert user1 is not None

        # Second creation - should be no-op
        created2, user2 = test_repo.users.create_super_admin_if_needed("superadmin", "Pass123!")
        assert created2 is False
        assert user2 is None

        # Verify only one exists
        all_users = test_repo.users.get_all()
        super_admins = [u for u in all_users if u.role == UserRole.SUPER_ADMIN and u.username == "superadmin"]
        assert len(super_admins) == 1

    def test_create_default_workflow_idempotent(self, test_repo: Repository) -> None:
        """Creating default workflow multiple times should not duplicate."""
        # First call creates
        workflow1 = test_repo.workflows.create_default_workflow()

        # Second call returns existing
        workflow2 = test_repo.workflows.create_default_workflow()

        assert workflow1.id == workflow2.id

        # Verify only one default workflow exists
        all_workflows = test_repo.workflows.get_all()
        defaults = [w for w in all_workflows if w.is_default]
        assert len(defaults) == 1


# =============================================================================
# Example 5: Stateful Testing (State Machine)
# =============================================================================


class UserCRUDStateMachine(RuleBasedStateMachine):
    """
    Stateful testing for user CRUD operations.

    This state machine performs random sequences of create/update/delete
    operations and verifies the repository remains consistent.
    """

    def __init__(self) -> None:
        super().__init__()
        # NOTE: In actual implementation, you'd need a fixture-based approach
        # This is simplified for demonstration
        from tests.conftest import get_test_repository

        self.repo = get_test_repository()
        org_data = OrganizationData(name="Test Org")
        self.org = self.repo.organizations.create(OrganizationCreateCommand(organization_data=org_data))
        self.created_users: dict[str, str] = {}  # username -> id
        self.deleted_users: set[str] = set()

    @rule(username=usernames(), email=emails())
    def create_user(self, username: str, email: str) -> None:
        """Create a user."""
        # Skip if already exists or was deleted
        assume(username not in self.created_users)
        assume(username not in self.deleted_users)

        user_data = UserData(username=username, email=email, full_name=username)
        user = self.repo.users.create(
            UserCreateCommand(user_data=user_data, password="Pass123!", organization_id=self.org.id, role=UserRole.ADMIN)
        )

        self.created_users[username] = user.id

    @rule()
    @precondition(lambda self: len(self.created_users) > 0)
    def get_user(self) -> None:
        """Retrieve a user."""
        username = list(self.created_users.keys())[0]
        user_id = self.created_users[username]

        user = self.repo.users.get_by_id(user_id)

        # User should exist if not deleted
        assert user is not None
        assert user.username == username

    @rule()
    @precondition(lambda self: len(self.created_users) > 0)
    def update_user(self) -> None:
        """Update a user."""
        username = list(self.created_users.keys())[0]
        user_id = self.created_users[username]

        new_email = f"updated_{username}@test.com"
        self.repo.users.update(user_id, UserUpdateCommand(email=new_email))

        # Verify update
        updated = self.repo.users.get_by_id(user_id)
        assert updated is not None
        assert updated.email == new_email

    @rule()
    @precondition(lambda self: len(self.created_users) > 0)
    def delete_user(self) -> None:
        """Delete a user."""
        username = list(self.created_users.keys())[0]
        user_id = self.created_users[username]

        self.repo.users.delete(user_id)
        self.deleted_users.add(username)
        del self.created_users[username]

    @invariant()
    def check_consistency(self) -> None:
        """Verify repository is always consistent."""
        # All created users should be retrievable
        for username, user_id in self.created_users.items():
            user = self.repo.users.get_by_id(user_id)
            assert user is not None, f"Created user {username} should exist"
            assert user.username == username

        # All deleted users should not be retrievable
        for username in self.deleted_users:
            user = self.repo.users.get_by_username(username)
            assert user is None, f"Deleted user {username} should not exist"


# Convert to pytest test case
TestUserCRUDStateMachine = UserCRUDStateMachine.TestCase


# =============================================================================
# Example 6: API Layer Properties (through HTTP)
# =============================================================================
#
# NOTE: These would go in a separate file for API property tests
#
# from fastapi.testclient import TestClient
#
# class TestUserAPIProperties:
#     """Example property-based tests for User API."""
#
#     @given(username=usernames(), email=emails(), full_name=st.text(min_size=1, max_size=255))
#     def test_user_crud_roundtrip_via_api(
#         self, client: TestClient, super_admin_token: str,
#         username: str, email: str, full_name: str
#     ) -> None:
#         """User data should survive complete CRUD cycle through API."""
#         from tests.helpers import create_test_org, auth_headers
#
#         org_id = create_test_org(client, super_admin_token)
#
#         # Create
#         response = client.post(
#             "/api/users",
#             params={"organization_id": org_id, "role": "admin"},
#             json={"username": username, "email": email, "full_name": full_name},
#             headers=auth_headers(super_admin_token)
#         )
#         assert response.status_code == 201
#         user_id = response.json()["user"]["id"]
#
#         # Read
#         get_response = client.get(f"/api/users/{user_id}", headers=auth_headers(super_admin_token))
#         assert get_response.status_code == 200
#         user_data = get_response.json()
#         assert user_data["username"] == username
#         assert user_data["email"] == email
#         assert user_data["full_name"] == full_name
#
#         # Update
#         new_email = f"updated_{email}"
#         update_response = client.put(
#             f"/api/users/{user_id}",
#             json={"email": new_email},
#             headers=auth_headers(super_admin_token)
#         )
#         assert update_response.status_code == 200
#         assert update_response.json()["email"] == new_email
#
#         # Delete
#         delete_response = client.delete(f"/api/users/{user_id}", headers=auth_headers(super_admin_token))
#         assert delete_response.status_code == 204
#
#         # Verify deleted
#         final_get = client.get(f"/api/users/{user_id}", headers=auth_headers(super_admin_token))
#         assert final_get.status_code == 404
