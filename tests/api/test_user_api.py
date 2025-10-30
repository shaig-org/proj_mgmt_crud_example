"""Tests for user management API endpoints."""

import re

from fastapi.testclient import TestClient

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import ActionType
from tests.conftest import client, test_repo  # noqa: F401
from tests.fixtures.auth_fixtures import (  # noqa: F401
    org_admin_token,
    super_admin_token,
    write_user_token,
)
from tests.helpers import (
    auth_headers,
    create_admin_user,
    create_project_manager,
    create_read_user,
    create_test_org,
    create_test_project,
    create_write_user,
)


class TestCreateUser:
    """Tests for POST /api/users endpoint - REQ-USER-001, REQ-USER-002."""

    def test_create_user_as_super_admin(self, client: TestClient, super_admin_token: str) -> None:
        """Test Super Admin creating user in any organization."""
        # Create org first
        org_id = create_test_org(client, super_admin_token, "Target Org")

        # Create user
        response = client.post(
            "/api/users",
            params={"organization_id": org_id, "role": "admin"},
            json={"username": "newuser", "email": "new@example.com", "full_name": "New User"},
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["user"]["username"] == "newuser"
        assert data["user"]["email"] == "new@example.com"
        assert data["user"]["full_name"] == "New User"
        assert data["user"]["organization_id"] == org_id
        assert data["user"]["role"] == "admin"
        assert data["user"]["is_active"] is True
        assert "id" in data["user"]
        assert "created_at" in data["user"]

        # Verify generated password is returned
        assert "generated_password" in data
        password = data["generated_password"]
        assert len(password) >= 12
        # Verify password meets requirements
        assert re.search(r"[A-Z]", password) is not None  # Uppercase
        assert re.search(r"[a-z]", password) is not None  # Lowercase
        assert re.search(r"\d", password) is not None  # Digit
        assert re.search(r"[!@#$%^&*()\-_=+\[\]{}|;:,.<>?]", password) is not None  # Special char

        # Verify user can login with generated password
        login_response = client.post("/auth/login", json={"username": "newuser", "password": password})
        assert login_response.status_code == 200

    def test_create_user_as_org_admin_in_own_org(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test Org Admin creating user in their own organization."""
        token, org_id = org_admin_token

        response = client.post(
            "/api/users",
            params={"organization_id": org_id, "role": "write_access"},
            json={"username": "teamuser", "email": "team@example.com", "full_name": "Team User"},
            headers=auth_headers(token),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["user"]["username"] == "teamuser"
        assert data["user"]["organization_id"] == org_id
        assert data["user"]["role"] == "write_access"
        assert "generated_password" in data

    def test_create_user_as_org_admin_in_different_org_fails(
        self, client: TestClient, org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test Org Admin cannot create user in different organization."""
        token, org_id = org_admin_token

        # Create another org
        other_org_id = create_test_org(client, super_admin_token, "Other Org")

        response = client.post(
            "/api/users",
            params={"organization_id": other_org_id, "role": "admin"},
            json={"username": "baduser", "email": "bad@example.com", "full_name": "Bad User"},
            headers=auth_headers(token),
        )

        assert response.status_code == 403
        assert "own organization" in response.json()["detail"]

    def test_create_user_with_duplicate_username_fails(self, client: TestClient, super_admin_token: str) -> None:
        """Test creating user with duplicate username fails."""
        org_id = create_test_org(client, super_admin_token)

        # Create first user
        response1 = client.post(
            "/api/users",
            params={"organization_id": org_id, "role": "admin"},
            json={"username": "duplicate", "email": "email1@example.com", "full_name": "User 1"},
            headers=auth_headers(super_admin_token),
        )
        assert response1.status_code == 201

        # Attempt to create second user with same username
        response2 = client.post(
            "/api/users",
            params={"organization_id": org_id, "role": "admin"},
            json={"username": "duplicate", "email": "email2@example.com", "full_name": "User 2"},
            headers=auth_headers(super_admin_token),
        )
        assert response2.status_code == 400
        assert "Username already exists" in response2.json()["detail"]

    def test_create_user_with_invalid_role_fails(self, client: TestClient, super_admin_token: str) -> None:
        """Test creating user with invalid role fails validation."""
        org_id = create_test_org(client, super_admin_token)

        response = client.post(
            "/api/users",
            params={"organization_id": org_id, "role": "invalid_role"},
            json={"username": "user1", "email": "user1@example.com", "full_name": "User 1"},
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 422  # Validation error

    def test_create_user_with_super_admin_role_fails(self, client: TestClient, super_admin_token: str) -> None:
        """Test cannot assign super_admin role via API."""
        org_id = create_test_org(client, super_admin_token)

        response = client.post(
            "/api/users",
            params={"organization_id": org_id, "role": "super_admin"},
            json={"username": "badadmin", "email": "bad@example.com", "full_name": "Bad Admin"},
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 400
        assert "super_admin" in response.json()["detail"].lower()

    def test_create_user_in_nonexistent_org_fails(self, client: TestClient, super_admin_token: str) -> None:
        """Test creating user in non-existent organization fails."""
        response = client.post(
            "/api/users",
            params={"organization_id": "nonexistent-org-id", "role": "admin"},
            json={"username": "user1", "email": "user1@example.com", "full_name": "User 1"},
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 400
        assert "Organization not found" in response.json()["detail"]

    def test_create_user_without_auth_fails(self, client: TestClient, super_admin_token: str) -> None:
        """Test creating user without authentication fails."""
        org_id = create_test_org(client, super_admin_token)

        response = client.post(
            "/api/users",
            params={"organization_id": org_id, "role": "admin"},
            json={"username": "user1", "email": "user1@example.com", "full_name": "User 1"},
        )

        assert response.status_code == 401

    def test_create_user_as_regular_user_fails(self, client: TestClient, write_user_token: tuple[str, str]) -> None:
        """Test regular user cannot create users."""
        token, org_id = write_user_token

        response = client.post(
            "/api/users",
            params={"organization_id": org_id, "role": "read_access"},
            json={"username": "newuser", "email": "new@example.com", "full_name": "New User"},
            headers=auth_headers(token),
        )

        assert response.status_code == 403
        assert "Admin access required" in response.json()["detail"]


class TestGetUser:
    """Tests for GET /api/users/{id} endpoint - REQ-USER-007, REQ-USER-008."""

    def test_get_user_by_id_as_super_admin(self, client: TestClient, super_admin_token: str) -> None:
        """Test Super Admin can get any user."""
        # Create org and user
        org_id = create_test_org(client, super_admin_token)
        user_id, password = create_admin_user(client, super_admin_token, org_id)

        response = client.get(f"/api/users/{user_id}", headers=auth_headers(super_admin_token))

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        assert data["username"] == "admin"
        assert data["email"] == "admin@example.com"
        # Verify password is NOT exposed
        assert "password" not in data
        assert "password_hash" not in data

    def test_get_user_in_same_org(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test user can get another user in same organization."""
        token, org_id = org_admin_token

        # Create another user in same org using API
        create_response = client.post(
            "/api/users",
            params={"organization_id": org_id, "role": "write_access"},
            json={"username": "teammate", "email": "team@example.com", "full_name": "Team Mate"},
            headers=auth_headers(token),
        )
        created_user_id = create_response.json()["user"]["id"]

        # Get the user
        response = client.get(f"/api/users/{created_user_id}", headers=auth_headers(token))

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_user_id
        assert data["username"] == "teammate"

    def test_get_user_in_different_org_returns_404(
        self, client: TestClient, org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test user cannot access user from different organization (returns 404)."""
        token, org_id = org_admin_token

        # Create another org and user
        other_org_id = create_test_org(client, super_admin_token, "Other Org")
        other_user_id, _password = create_write_user(client, super_admin_token, other_org_id)

        response = client.get(f"/api/users/{other_user_id}", headers=auth_headers(token))

        # Should return 404 to avoid leaking cross-org information
        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    def test_get_nonexistent_user_returns_404(self, client: TestClient, super_admin_token: str) -> None:
        """Test getting non-existent user returns 404."""
        response = client.get("/api/users/nonexistent-id", headers=auth_headers(super_admin_token))

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    def test_get_user_without_auth_fails(self, client: TestClient, super_admin_token: str) -> None:
        """Test getting user without authentication fails."""
        # Create a user
        org_id = create_test_org(client, super_admin_token)
        user_id, _password = create_write_user(client, super_admin_token, org_id)

        response = client.get(f"/api/users/{user_id}")

        assert response.status_code == 401


class TestListUsers:
    """Tests for GET /api/users endpoint - REQ-USER-006."""

    def test_list_users_as_super_admin_sees_all(self, client: TestClient, super_admin_token: str) -> None:
        """Test Super Admin sees all users across all organizations."""
        # Create multiple orgs and users
        org1_id = create_test_org(client, super_admin_token, "Org 1")
        org2_id = create_test_org(client, super_admin_token, "Org 2")

        create_admin_user(client, super_admin_token, org1_id, username="user1")
        create_read_user(client, super_admin_token, org2_id, username="user2")

        response = client.get("/api/users", headers=auth_headers(super_admin_token))

        assert response.status_code == 200
        users = response.json()
        # Should include superadmin + user1 + user2 = 3
        assert len(users) >= 3
        usernames = {user["username"] for user in users}
        assert "user1" in usernames
        assert "user2" in usernames
        assert "superadmin" in usernames

    def test_list_users_as_org_admin_sees_only_own_org(
        self, client: TestClient, org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test Org Admin sees only users in their organization."""
        token, org_id = org_admin_token

        # Create user in same org
        create_write_user(client, super_admin_token, org_id, username="teammate")

        # Create user in different org
        other_org_id = create_test_org(client, super_admin_token, "Other Org")
        create_admin_user(client, super_admin_token, other_org_id, username="outsider")

        response = client.get("/api/users", headers=auth_headers(token))

        assert response.status_code == 200
        users = response.json()
        usernames = {user["username"] for user in users}
        # Should include orgadmin and teammate, but not outsider
        assert "orgadmin" in usernames
        assert "teammate" in usernames
        assert "outsider" not in usernames

    def test_list_users_with_role_filter(self, client: TestClient, super_admin_token: str) -> None:
        """Test filtering users by role."""
        org_id = create_test_org(client, super_admin_token)

        create_admin_user(client, super_admin_token, org_id, username="admin1")
        create_read_user(client, super_admin_token, org_id, username="reader1")

        response = client.get("/api/users", params={"role": "admin"}, headers=auth_headers(super_admin_token))

        assert response.status_code == 200
        users = response.json()
        # All returned users should be admins
        for user in users:
            assert user["role"] in ["admin", "super_admin"]

    def test_list_users_with_is_active_filter(self, client: TestClient, super_admin_token: str) -> None:
        """Test filtering users by active status."""
        org_id = create_test_org(client, super_admin_token)

        # Create active user with unique email
        create_admin_user(client, super_admin_token, org_id, username="active", email="active@example.com")

        # Create and deactivate user via API with unique email
        inactive_user_id, _password = create_admin_user(
            client, super_admin_token, org_id, username="inactive", email="inactive@example.com"
        )
        client.put(f"/api/users/{inactive_user_id}", json={"is_active": False}, headers=auth_headers(super_admin_token))

        # Filter for active users
        response = client.get("/api/users", params={"is_active": "true"}, headers=auth_headers(super_admin_token))

        assert response.status_code == 200
        users = response.json()
        usernames = {user["username"] for user in users}
        assert "active" in usernames
        assert "inactive" not in usernames

    def test_list_users_without_auth_fails(self, client: TestClient) -> None:
        """Test listing users without authentication fails."""
        response = client.get("/api/users")

        assert response.status_code == 401


class TestUpdateUser:
    """Tests for PUT /api/users/{id} endpoint - REQ-USER-003, REQ-USER-004."""

    def test_update_user_as_super_admin(self, client: TestClient, super_admin_token: str) -> None:
        """Test Super Admin can update any user."""
        org_id = create_test_org(client, super_admin_token)
        user_id, _password = create_write_user(client, super_admin_token, org_id)

        response = client.put(
            f"/api/users/{user_id}",
            json={"email": "new@example.com", "full_name": "New Name", "role": "project_manager"},
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "new@example.com"
        assert data["full_name"] == "New Name"
        assert data["role"] == "project_manager"
        # Verify unchanged fields
        assert data["username"] == "writer"
        assert data["organization_id"] == org_id

    def test_update_user_partial_fields(self, client: TestClient, super_admin_token: str) -> None:
        """Test updating only some user fields."""
        org_id = create_test_org(client, super_admin_token)
        user_id, _password = create_admin_user(client, super_admin_token, org_id)

        # Update only email
        response = client.put(
            f"/api/users/{user_id}",
            json={"email": "updated@example.com"},
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "updated@example.com"
        # Verify other fields unchanged
        assert data["full_name"] == "Admin User"
        assert data["role"] == "admin"

    def test_deactivate_user(self, client: TestClient, super_admin_token: str) -> None:
        """Test deactivating a user."""
        org_id = create_test_org(client, super_admin_token)
        user_id, password = create_admin_user(client, super_admin_token, org_id, username="deactivateme")

        # Deactivate
        response = client.put(
            f"/api/users/{user_id}",
            json={"is_active": False},
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 200
        assert response.json()["is_active"] is False

        # Verify user cannot login
        login_response = client.post("/auth/login", json={"username": "deactivateme", "password": password})
        assert login_response.status_code == 401

    def test_reactivate_user(self, client: TestClient, super_admin_token: str) -> None:
        """Test reactivating a user."""
        org_id = create_test_org(client, super_admin_token)
        user_id, password = create_admin_user(client, super_admin_token, org_id, username="reactivateme")

        # Deactivate first via API
        client.put(f"/api/users/{user_id}", json={"is_active": False}, headers=auth_headers(super_admin_token))

        # Reactivate via API
        response = client.put(
            f"/api/users/{user_id}",
            json={"is_active": True},
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 200
        assert response.json()["is_active"] is True

        # Verify user can login again
        login_response = client.post("/auth/login", json={"username": "reactivateme", "password": password})
        assert login_response.status_code == 200

    def test_update_user_as_org_admin_in_own_org(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test Org Admin can update users in their organization."""
        token, org_id = org_admin_token

        # Create user in same org via API
        create_response = client.post(
            "/api/users",
            params={"organization_id": org_id, "role": "write_access"},
            json={"username": "updateable", "email": "update@example.com", "full_name": "Updateable User"},
            headers=auth_headers(token),
        )
        user_id = create_response.json()["user"]["id"]

        # Update the user
        response = client.put(
            f"/api/users/{user_id}",
            json={"full_name": "Updated Name"},
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        assert response.json()["full_name"] == "Updated Name"

    def test_update_user_as_org_admin_in_different_org_fails(
        self, client: TestClient, org_admin_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test Org Admin cannot update users in different organization."""
        token, org_id = org_admin_token

        # Create user in different org
        other_org_id = create_test_org(client, super_admin_token, "Other Org")
        other_user_id, _password = create_admin_user(client, super_admin_token, other_org_id, username="other")

        response = client.put(
            f"/api/users/{other_user_id}",
            json={"full_name": "Hacked Name"},
            headers=auth_headers(token),
        )

        assert response.status_code == 403
        assert "own organization" in response.json()["detail"]

    def test_update_user_with_super_admin_role_fails(self, client: TestClient, super_admin_token: str) -> None:
        """Test cannot assign super_admin role via update."""
        org_id = create_test_org(client, super_admin_token)
        user_id, _password = create_admin_user(client, super_admin_token, org_id, username="user1")

        response = client.put(
            f"/api/users/{user_id}",
            json={"role": "super_admin"},
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 400
        assert "super_admin" in response.json()["detail"].lower()

    def test_update_nonexistent_user_returns_404(self, client: TestClient, super_admin_token: str) -> None:
        """Test updating non-existent user returns 404."""
        response = client.put(
            "/api/users/nonexistent-id",
            json={"full_name": "New Name"},
            headers=auth_headers(super_admin_token),
        )

        assert response.status_code == 404

    def test_update_user_as_regular_user_fails(
        self, client: TestClient, write_user_token: tuple[str, str], super_admin_token: str
    ) -> None:
        """Test regular user cannot update users."""
        token, org_id = write_user_token

        # Create another user with unique email
        user_id, _password = create_write_user(
            client, super_admin_token, org_id, username="writer2", email="writer2@example.com"
        )

        response = client.put(
            f"/api/users/{user_id}",
            json={"full_name": "Hacked"},
            headers=auth_headers(token),
        )

        assert response.status_code == 403

    def test_duplicate_email_within_organization_fails(self, client: TestClient, super_admin_token: str) -> None:
        """Test that duplicate emails are rejected within same organization.

        Regression test for bug discovered by property-based stateful testing.

        Bug Discovery:
        - Original test: tests/property_based/stateful/test_user_api.py::test_user_api_state_machine
        - Rule: attempt_duplicate_email_update
        - Issue: Email uniqueness constraint was missing from database schema (UserORM model)
        - Fix: Added composite unique index on (organization_id, email) in UserORM.__table_args__

        This test ensures the bug doesn't regress by testing the specific scenario:
        updating a user's email to match another user's email in the same organization.
        """
        org_id = create_test_org(client, super_admin_token)

        # Create first user with email "user1@example.com"
        create_admin_user(client, super_admin_token, org_id, username="user1", email="user1@example.com")

        # Create second user with different email
        user2_id, _ = create_admin_user(client, super_admin_token, org_id, username="user2", email="user2@example.com")

        # Attempt to update second user's email to duplicate first user's email
        response = client.put(
            f"/api/users/{user2_id}",
            json={"email": "user1@example.com"},
            headers=auth_headers(super_admin_token),
        )

        # Should fail with 400
        assert response.status_code == 400
        assert "email" in response.json()["detail"].lower()

        # Verify user2's email was not changed
        get_response = client.get(f"/api/users/{user2_id}", headers=auth_headers(super_admin_token))
        assert get_response.status_code == 200
        assert get_response.json()["email"] == "user2@example.com"


class TestDeleteUser:
    """Tests for DELETE /api/users/{id} endpoint - REQ-USER-005."""

    def test_delete_user_as_super_admin(self, client: TestClient, super_admin_token: str) -> None:
        """Test Super Admin can delete users."""
        org_id = create_test_org(client, super_admin_token)
        user_id, _password = create_write_user(client, super_admin_token, org_id)

        response = client.delete(f"/api/users/{user_id}", headers=auth_headers(super_admin_token))

        assert response.status_code == 204

        # Verify user is deleted
        get_response = client.get(f"/api/users/{user_id}", headers=auth_headers(super_admin_token))
        assert get_response.status_code == 404

    def test_delete_user_with_created_tickets_fails(self, client: TestClient, super_admin_token: str) -> None:
        """Test cannot delete user who has created tickets."""
        # Create org and user with PROJECT_MANAGER role to create projects
        org_id = create_test_org(client, super_admin_token)
        user_id, password = create_project_manager(client, super_admin_token, org_id)

        # Login as the user to create project and ticket via API
        login_response = client.post("/auth/login", json={"username": "projectmanager", "password": password})
        user_token = login_response.json()["access_token"]

        # Create project as the user
        project_id = create_test_project(client, user_token)

        # Create ticket via API as the user
        client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Test Ticket", "description": "Test", "priority": "MEDIUM"},
            headers=auth_headers(user_token),
        )

        # Attempt to delete user (should fail because they created a ticket)
        response = client.delete(f"/api/users/{user_id}", headers=auth_headers(super_admin_token))

        assert response.status_code == 400
        assert "ticket" in response.json()["detail"].lower()

    def test_delete_user_as_org_admin_fails(self, client: TestClient, org_admin_token: tuple[str, str]) -> None:
        """Test Org Admin cannot delete users (Super Admin only)."""
        token, org_id = org_admin_token

        # Create user via API
        create_response = client.post(
            "/api/users",
            params={"organization_id": org_id, "role": "write_access"},
            json={"username": "deleteme", "email": "delete@example.com", "full_name": "Delete Me"},
            headers=auth_headers(token),
        )
        user_id = create_response.json()["user"]["id"]

        # Attempt to delete
        response = client.delete(f"/api/users/{user_id}", headers=auth_headers(token))

        assert response.status_code == 403
        assert "Super Admin" in response.json()["detail"]

    def test_delete_nonexistent_user_returns_404(self, client: TestClient, super_admin_token: str) -> None:
        """Test deleting non-existent user returns 404."""
        response = client.delete("/api/users/nonexistent-id", headers=auth_headers(super_admin_token))

        assert response.status_code == 404

    def test_delete_user_without_auth_fails(self, client: TestClient, super_admin_token: str) -> None:
        """Test deleting user without authentication fails."""
        org_id = create_test_org(client, super_admin_token)
        user_id, _password = create_admin_user(client, super_admin_token, org_id, username="user1")

        response = client.delete(f"/api/users/{user_id}")

        assert response.status_code == 401


class TestUserActivityLogging:
    """Tests for user activity logging - REQ-ACTIVITY-003."""

    def test_create_user_logs_activity(self, client: TestClient, test_repo: Repository, super_admin_token: str) -> None:
        """Test that creating a user creates an activity log entry."""
        org_id = create_test_org(client, super_admin_token)

        # Create user
        user_id, _password = create_admin_user(client, super_admin_token, org_id, username="testuser")

        # Check activity log was created
        logs = test_repo.activity_logs.list(entity_type="user", entity_id=user_id)

        assert len(logs) == 1
        log = logs[0]
        assert log.entity_type == "user"
        assert log.entity_id == user_id
        assert log.action == ActionType.USER_CREATED
        assert log.organization_id == org_id

        # Verify command structure
        assert "command" in log.changes
        assert log.changes["command"]["user_data"]["username"] == "testuser"
        assert log.changes["command"]["organization_id"] == org_id
        # Verify password is redacted
        assert log.changes["command"]["password"] == "[REDACTED]"

    def test_update_user_logs_activity(self, client: TestClient, test_repo: Repository, super_admin_token: str) -> None:
        """Test that updating a user creates an activity log entry."""
        org_id = create_test_org(client, super_admin_token)
        user_id, _password = create_admin_user(client, super_admin_token, org_id, username="testuser")

        # Update user
        update_data = {"full_name": "Updated Name", "email": "updated@example.com"}
        response = client.put(
            f"/api/users/{user_id}",
            json=update_data,
            headers=auth_headers(super_admin_token),
        )
        assert response.status_code == 200

        # Check activity log for update
        logs = test_repo.activity_logs.list(entity_type="user", entity_id=user_id)

        # Should have 2 logs: create and update
        assert len(logs) == 2

        # Check update log (second one)
        update_log = logs[1]
        assert update_log.action == ActionType.USER_UPDATED
        assert "command" in update_log.changes
        assert update_log.changes["command"]["full_name"] == "Updated Name"
        assert update_log.changes["command"]["email"] == "updated@example.com"

    def test_delete_user_logs_activity(self, client: TestClient, test_repo: Repository, super_admin_token: str) -> None:
        """Test that deleting a user creates an activity log entry."""
        org_id = create_test_org(client, super_admin_token)
        user_id, _password = create_admin_user(client, super_admin_token, org_id, username="testuser")

        # Delete user
        response = client.delete(f"/api/users/{user_id}", headers=auth_headers(super_admin_token))
        assert response.status_code == 204

        # Check activity log - should persist even after deletion
        logs = test_repo.activity_logs.list(entity_type="user", entity_id=user_id)

        # Should have 2 logs: create and delete
        assert len(logs) == 2

        # Check delete log
        delete_log = logs[1]
        assert delete_log.action == ActionType.USER_DELETED
        assert "command" in delete_log.changes
        assert delete_log.changes["command"]["user_id"] == user_id
        assert "snapshot" in delete_log.changes
        assert delete_log.changes["snapshot"]["username"] == "testuser"

    def test_password_change_logs_activity(
        self, client: TestClient, test_repo: Repository, super_admin_token: str
    ) -> None:
        """Test that changing password creates an activity log entry with redacted passwords."""
        org_id = create_test_org(client, super_admin_token)
        user_id, password = create_admin_user(client, super_admin_token, org_id, username="testuser")

        # Login as the user
        login_response = client.post("/auth/login", json={"username": "testuser", "password": password})
        assert login_response.status_code == 200
        user_token = login_response.json()["access_token"]

        # Change password
        change_password_data = {"current_password": password, "new_password": "NewPassword123!"}
        response = client.post(
            "/auth/change-password",
            json=change_password_data,
            headers=auth_headers(user_token),
        )
        assert response.status_code == 200

        # Check activity log for password change
        logs = test_repo.activity_logs.list(entity_type="user", entity_id=user_id)

        # Should have at least 2 logs: create and password change
        password_change_logs = [log for log in logs if log.action == ActionType.USER_PASSWORD_CHANGED]
        assert len(password_change_logs) == 1

        password_log = password_change_logs[0]
        assert password_log.entity_type == "user"
        assert password_log.entity_id == user_id
        assert password_log.action == ActionType.USER_PASSWORD_CHANGED

        # Verify command structure - should NOT contain actual passwords
        assert "command" in password_log.changes
        assert password_log.changes["command"]["user_id"] == user_id
        # Verify no password fields are present (PasswordChangeCommand doesn't have them)
        assert "password" not in password_log.changes["command"]
        assert "current_password" not in password_log.changes["command"]
        assert "new_password" not in password_log.changes["command"]
