"""Comprehensive API tests for Comment endpoints.

Tests verify complete CRUD functionality, role-based permissions, organization scoping,
author-only editing, and admin/author deletion rules for comments.
"""

import pytest
from fastapi.testclient import TestClient

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import ActionType
from tests.conftest import client, test_repo  # noqa: F401
from tests.fixtures.auth_fixtures import super_admin_token  # noqa: F401
from tests.fixtures.data_fixtures import organization, second_organization  # noqa: F401
from tests.helpers import auth_headers, create_write_user

# Local fixtures for comment tests - create multiple users in the SAME organization
# Note: These fixtures are prefixed with 'shared_org_' to avoid shadowing global fixtures
# Comment tests need all users in the same org to test cross-user scenarios.


@pytest.fixture
def shared_org_admin_token(client: TestClient, organization: str, super_admin_token: str) -> tuple[str, str]:
    """Create Admin user in shared organization and return token and org_id."""
    from tests.helpers import create_admin_user

    _, password = create_admin_user(client, super_admin_token, organization)
    response = client.post("/auth/login", json={"username": "admin", "password": password})
    return response.json()["access_token"], organization


@pytest.fixture
def shared_org_pm_token(client: TestClient, organization: str, super_admin_token: str) -> tuple[str, str]:
    """Create Project Manager user in shared organization."""
    from tests.helpers import create_project_manager

    _, password = create_project_manager(client, super_admin_token, organization)
    response = client.post("/auth/login", json={"username": "projectmanager", "password": password})
    return response.json()["access_token"], organization


@pytest.fixture
def shared_org_write_token(client: TestClient, organization: str, super_admin_token: str) -> tuple[str, str]:
    """Create Write Access user in shared organization."""
    _, password = create_write_user(client, super_admin_token, organization)
    response = client.post("/auth/login", json={"username": "writer", "password": password})
    return response.json()["access_token"], organization


@pytest.fixture
def shared_org_read_token(client: TestClient, organization: str, super_admin_token: str) -> tuple[str, str]:
    """Create Read Access user in shared organization."""
    from tests.helpers import create_read_user

    _, password = create_read_user(client, super_admin_token, organization)
    response = client.post("/auth/login", json={"username": "reader", "password": password})
    return response.json()["access_token"], organization


class TestCreateComment:
    """Test POST /api/tickets/{ticket_id}/comments endpoint."""

    def test_create_comment_as_write_user(
        self, client: TestClient, shared_org_admin_token: tuple[str, str], shared_org_write_token: tuple[str, str]
    ) -> None:
        """Test that Write user can create comments."""
        admin_token, org_id = shared_org_admin_token
        write_token, _ = shared_org_write_token
        admin_headers = auth_headers(admin_token)
        write_headers = auth_headers(write_token)

        # Admin creates project
        project_response = client.post("/api/projects", json={"name": "Test Project"}, headers=admin_headers)
        project_id = project_response.json()["id"]

        # Write user creates ticket
        ticket_response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Test Ticket"},
            headers=write_headers,
        )
        ticket_id = ticket_response.json()["id"]

        # Write user creates comment
        response = client.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"content": "This is a test comment"},
            headers=write_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "This is a test comment"
        assert data["ticket_id"] == ticket_id
        assert "author_id" in data
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_comment_as_admin(self, client: TestClient, shared_org_admin_token: tuple[str, str]) -> None:
        """Test that Admin can create comments."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket
        project_response = client.post("/api/projects", json={"name": "Test Project"}, headers=headers)
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Test Ticket"},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        # Create comment
        response = client.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"content": "Admin comment"},
            headers=headers,
        )

        assert response.status_code == 201
        assert response.json()["content"] == "Admin comment"

    def test_create_comment_as_project_manager(
        self, client: TestClient, shared_org_admin_token: tuple[str, str], shared_org_pm_token: tuple[str, str]
    ) -> None:
        """Test that Project Manager can create comments."""
        admin_token, org_id = shared_org_admin_token
        pm_token, _ = shared_org_pm_token
        admin_headers = auth_headers(admin_token)
        pm_headers = auth_headers(pm_token)

        # Admin creates project and ticket
        project_response = client.post("/api/projects", json={"name": "Test Project"}, headers=admin_headers)
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Test Ticket"},
            headers=admin_headers,
        )
        ticket_id = ticket_response.json()["id"]

        # PM creates comment
        response = client.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"content": "PM comment"},
            headers=pm_headers,
        )

        assert response.status_code == 201
        assert response.json()["content"] == "PM comment"

    def test_create_comment_as_read_user_fails(
        self,
        client: TestClient,
        shared_org_admin_token: tuple[str, str],
        shared_org_write_token: tuple[str, str],
        shared_org_read_token: tuple[str, str],
    ) -> None:
        """Test that Read user cannot create comments."""
        admin_token, org_id = shared_org_admin_token
        write_token, _ = shared_org_write_token
        read_token, _ = shared_org_read_token
        admin_headers = auth_headers(admin_token)
        write_headers = auth_headers(write_token)
        read_headers = auth_headers(read_token)

        # Admin creates project, Write user creates ticket
        project_response = client.post("/api/projects", json={"name": "Test Project"}, headers=admin_headers)
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Test Ticket"},
            headers=write_headers,
        )
        ticket_id = ticket_response.json()["id"]

        # Read user attempts to create comment
        response = client.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"content": "Should fail"},
            headers=read_headers,
        )

        assert response.status_code == 403
        assert "read-only users cannot create comments" in response.json()["detail"]

    def test_create_comment_on_nonexistent_ticket(
        self, client: TestClient, shared_org_write_token: tuple[str, str]
    ) -> None:
        """Test creating comment on non-existent ticket returns 404."""
        token, org_id = shared_org_write_token
        headers = auth_headers(token)

        response = client.post(
            "/api/tickets/non-existent-ticket-id/comments",
            json={"content": "Test comment"},
            headers=headers,
        )

        assert response.status_code == 404
        assert "Ticket not found" in response.json()["detail"]

    def test_create_comment_without_authentication(self, client: TestClient) -> None:
        """Test creating comment without authentication fails."""
        response = client.post(
            "/api/tickets/some-ticket-id/comments",
            json={"content": "Test comment"},
        )

        assert response.status_code == 401

    def test_create_comment_with_empty_content_fails(
        self, client: TestClient, shared_org_admin_token: tuple[str, str]
    ) -> None:
        """Test creating comment with empty content returns 422."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket
        project_response = client.post("/api/projects", json={"name": "Test Project"}, headers=headers)
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Test Ticket"},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        # Attempt to create comment with empty content
        response = client.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"content": ""},
            headers=headers,
        )

        assert response.status_code == 422

    def test_create_comment_cross_organization_access_denied(
        self,
        client: TestClient,
        shared_org_write_token: tuple[str, str],
        second_organization: str,
        super_admin_token: str,
    ) -> None:
        """Test that user cannot comment on tickets from different organization."""
        write_token, org1_id = shared_org_write_token
        write_headers = auth_headers(write_token)

        # Create admin user in second organization
        from tests.helpers import create_admin_user

        _, org2_admin_password = create_admin_user(client, super_admin_token, second_organization, username="org2admin")
        org2_admin_login = client.post("/auth/login", json={"username": "org2admin", "password": org2_admin_password})
        org2_admin_token = org2_admin_login.json()["access_token"]
        org2_admin_headers = auth_headers(org2_admin_token)

        # Org2 admin creates project and ticket in second organization
        project_response = client.post(
            "/api/projects",
            json={"name": "Org2 Project"},
            headers=org2_admin_headers,
        )
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Org2 Ticket"},
            headers=org2_admin_headers,
        )
        ticket_id = ticket_response.json()["id"]

        # User from org1 attempts to comment on org2 ticket
        response = client.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"content": "Cross-org comment attempt"},
            headers=write_headers,
        )

        assert response.status_code == 403
        assert "different organization" in response.json()["detail"]

    def test_create_comment_activity_logged(
        self, client: TestClient, test_repo: Repository, shared_org_admin_token: tuple[str, str]
    ) -> None:
        """Test that comment creation is logged in activity log."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket
        project_response = client.post("/api/projects", json={"name": "Test Project"}, headers=headers)
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Test Ticket"},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        # Create comment
        response = client.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"content": "Test comment for activity log"},
            headers=headers,
        )

        assert response.status_code == 201
        comment_id = response.json()["id"]

        # Check activity log
        logs = test_repo.activity_logs.list(entity_type="comment", entity_id=comment_id)
        assert len(logs) == 1
        assert logs[0].action == ActionType.COMMENT_CREATED
        assert logs[0].entity_id == comment_id


class TestGetComment:
    """Test GET /api/comments/{comment_id} endpoint."""

    def test_get_comment_by_id(self, client: TestClient, shared_org_admin_token: tuple[str, str]) -> None:
        """Test retrieving a comment by ID."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project, ticket, and comment
        project_response = client.post("/api/projects", json={"name": "Test Project"}, headers=headers)
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Test Ticket"},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        comment_response = client.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"content": "Test comment"},
            headers=headers,
        )
        comment_id = comment_response.json()["id"]

        # Get comment by ID
        response = client.get(f"/api/comments/{comment_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == comment_id
        assert data["content"] == "Test comment"
        assert data["ticket_id"] == ticket_id

    def test_get_comment_not_found(self, client: TestClient, shared_org_admin_token: tuple[str, str]) -> None:
        """Test getting non-existent comment returns 404."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        response = client.get("/api/comments/non-existent-id", headers=headers)

        assert response.status_code == 404
        assert "Comment not found" in response.json()["detail"]

    def test_get_comment_without_authentication(self, client: TestClient) -> None:
        """Test getting comment without authentication fails."""
        response = client.get("/api/comments/some-id")

        assert response.status_code == 401

    def test_get_comment_cross_organization_access_denied(
        self,
        client: TestClient,
        shared_org_write_token: tuple[str, str],
        second_organization: str,
        super_admin_token: str,
    ) -> None:
        """Test that user cannot get comments from different organization."""
        write_token, org1_id = shared_org_write_token
        write_headers = auth_headers(write_token)

        # Create admin user in second organization
        from tests.helpers import create_admin_user

        _, org2_admin_password = create_admin_user(client, super_admin_token, second_organization, username="org2admin")
        org2_admin_login = client.post("/auth/login", json={"username": "org2admin", "password": org2_admin_password})
        org2_admin_token = org2_admin_login.json()["access_token"]
        org2_admin_headers = auth_headers(org2_admin_token)

        # Org2 admin creates project, ticket, and comment in second organization
        project_response = client.post(
            "/api/projects",
            json={"name": "Org2 Project"},
            headers=org2_admin_headers,
        )
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Org2 Ticket"},
            headers=org2_admin_headers,
        )
        ticket_id = ticket_response.json()["id"]

        comment_response = client.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"content": "Org2 comment"},
            headers=org2_admin_headers,
        )
        comment_id = comment_response.json()["id"]

        # User from org1 attempts to get org2 comment
        response = client.get(f"/api/comments/{comment_id}", headers=write_headers)

        assert response.status_code == 403
        assert "different organization" in response.json()["detail"]


class TestListTicketComments:
    """Test GET /api/tickets/{ticket_id}/comments endpoint."""

    def test_list_ticket_comments(self, client: TestClient, shared_org_admin_token: tuple[str, str]) -> None:
        """Test listing all comments for a ticket."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket
        project_response = client.post("/api/projects", json={"name": "Test Project"}, headers=headers)
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Test Ticket"},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        # Create multiple comments
        comment1 = client.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"content": "First comment"},
            headers=headers,
        ).json()
        comment2 = client.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"content": "Second comment"},
            headers=headers,
        ).json()
        comment3 = client.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"content": "Third comment"},
            headers=headers,
        ).json()

        # List comments
        response = client.get(f"/api/tickets/{ticket_id}/comments", headers=headers)

        assert response.status_code == 200
        comments = response.json()
        assert len(comments) == 3
        # Verify chronological order (oldest first)
        assert comments[0]["id"] == comment1["id"]
        assert comments[1]["id"] == comment2["id"]
        assert comments[2]["id"] == comment3["id"]

    def test_list_comments_for_ticket_with_no_comments(
        self, client: TestClient, shared_org_admin_token: tuple[str, str]
    ) -> None:
        """Test listing comments for ticket with no comments returns empty list."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project and ticket
        project_response = client.post("/api/projects", json={"name": "Test Project"}, headers=headers)
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Test Ticket"},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        # List comments
        response = client.get(f"/api/tickets/{ticket_id}/comments", headers=headers)

        assert response.status_code == 200
        assert response.json() == []

    def test_list_comments_for_nonexistent_ticket(
        self, client: TestClient, shared_org_write_token: tuple[str, str]
    ) -> None:
        """Test listing comments for non-existent ticket returns 404."""
        token, org_id = shared_org_write_token
        headers = auth_headers(token)

        response = client.get("/api/tickets/non-existent-id/comments", headers=headers)

        assert response.status_code == 404
        assert "Ticket not found" in response.json()["detail"]

    def test_list_comments_without_authentication(self, client: TestClient) -> None:
        """Test listing comments without authentication fails."""
        response = client.get("/api/tickets/some-id/comments")

        assert response.status_code == 401


class TestUpdateComment:
    """Test PUT /api/comments/{comment_id} endpoint."""

    def test_update_comment_as_author(self, client: TestClient, shared_org_admin_token: tuple[str, str]) -> None:
        """Test that comment author can update their own comment."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project, ticket, and comment
        project_response = client.post("/api/projects", json={"name": "Test Project"}, headers=headers)
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Test Ticket"},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        comment_response = client.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"content": "Original content"},
            headers=headers,
        )
        comment_id = comment_response.json()["id"]

        # Update comment
        response = client.put(
            f"/api/comments/{comment_id}",
            json={"content": "Updated content"},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == comment_id
        assert data["content"] == "Updated content"

    def test_update_comment_as_non_author_fails(
        self,
        client: TestClient,
        shared_org_write_token: tuple[str, str],
        shared_org_admin_token: tuple[str, str],
    ) -> None:
        """Test that non-author (even admin) cannot update comment."""
        write_token, org_id = shared_org_write_token
        admin_token, _ = shared_org_admin_token
        write_headers = auth_headers(write_token)
        admin_headers = auth_headers(admin_token)

        # Admin creates project, Write user creates ticket and comment
        project_response = client.post("/api/projects", json={"name": "Test Project"}, headers=admin_headers)
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Test Ticket"},
            headers=write_headers,
        )
        ticket_id = ticket_response.json()["id"]

        comment_response = client.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"content": "Original content"},
            headers=write_headers,
        )
        comment_id = comment_response.json()["id"]

        # Admin attempts to update write user's comment
        response = client.put(
            f"/api/comments/{comment_id}",
            json={"content": "Admin trying to edit"},
            headers=admin_headers,
        )

        assert response.status_code == 403
        assert "only comment author can update" in response.json()["detail"]

    def test_update_comment_not_found(self, client: TestClient, shared_org_admin_token: tuple[str, str]) -> None:
        """Test updating non-existent comment returns 404."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        response = client.put(
            "/api/comments/non-existent-id",
            json={"content": "Updated content"},
            headers=headers,
        )

        assert response.status_code == 404
        assert "Comment not found" in response.json()["detail"]

    def test_update_comment_without_authentication(self, client: TestClient) -> None:
        """Test updating comment without authentication fails."""
        response = client.put(
            "/api/comments/some-id",
            json={"content": "Updated content"},
        )

        assert response.status_code == 401

    def test_update_comment_activity_logged(
        self, client: TestClient, test_repo: Repository, shared_org_admin_token: tuple[str, str]
    ) -> None:
        """Test that comment update is logged in activity log."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project, ticket, and comment
        project_response = client.post("/api/projects", json={"name": "Test Project"}, headers=headers)
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Test Ticket"},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        comment_response = client.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"content": "Original"},
            headers=headers,
        )
        comment_id = comment_response.json()["id"]

        # Update comment
        response = client.put(
            f"/api/comments/{comment_id}",
            json={"content": "Updated"},
            headers=headers,
        )

        assert response.status_code == 200

        # Check activity log
        logs = test_repo.activity_logs.list(entity_type="comment", entity_id=comment_id)
        update_logs = [log for log in logs if log.action == ActionType.COMMENT_UPDATED]
        assert len(update_logs) == 1
        assert update_logs[0].entity_id == comment_id


class TestDeleteComment:
    """Test DELETE /api/comments/{comment_id} endpoint."""

    def test_delete_comment_as_author(self, client: TestClient, shared_org_admin_token: tuple[str, str]) -> None:
        """Test that comment author can delete their own comment."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project, ticket, and comment
        project_response = client.post("/api/projects", json={"name": "Test Project"}, headers=headers)
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Test Ticket"},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        comment_response = client.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"content": "To be deleted"},
            headers=headers,
        )
        comment_id = comment_response.json()["id"]

        # Delete comment
        response = client.delete(f"/api/comments/{comment_id}", headers=headers)

        assert response.status_code == 204

        # Verify deletion
        get_response = client.get(f"/api/comments/{comment_id}", headers=headers)
        assert get_response.status_code == 404

    def test_delete_comment_as_admin(
        self,
        client: TestClient,
        shared_org_write_token: tuple[str, str],
        shared_org_admin_token: tuple[str, str],
    ) -> None:
        """Test that admin can delete any comment in their organization."""
        write_token, org_id = shared_org_write_token
        admin_token, _ = shared_org_admin_token
        write_headers = auth_headers(write_token)
        admin_headers = auth_headers(admin_token)

        # Admin creates project, Write user creates ticket and comment
        project_response = client.post("/api/projects", json={"name": "Test Project"}, headers=admin_headers)
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Test Ticket"},
            headers=write_headers,
        )
        ticket_id = ticket_response.json()["id"]

        comment_response = client.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"content": "To be deleted by admin"},
            headers=write_headers,
        )
        comment_id = comment_response.json()["id"]

        # Admin deletes comment
        response = client.delete(f"/api/comments/{comment_id}", headers=admin_headers)

        assert response.status_code == 204

        # Verify deletion
        get_response = client.get(f"/api/comments/{comment_id}", headers=admin_headers)
        assert get_response.status_code == 404

    def test_delete_comment_as_non_author_non_admin_fails(
        self,
        client: TestClient,
        shared_org_write_token: tuple[str, str],
        shared_org_pm_token: tuple[str, str],
    ) -> None:
        """Test that non-author/non-admin cannot delete comment."""
        write_token, org_id = shared_org_write_token
        pm_token, _ = shared_org_pm_token
        write_headers = auth_headers(write_token)
        pm_headers = auth_headers(pm_token)

        # PM creates project, Write user creates ticket and comment
        project_response = client.post("/api/projects", json={"name": "Test Project"}, headers=pm_headers)
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Test Ticket"},
            headers=write_headers,
        )
        ticket_id = ticket_response.json()["id"]

        comment_response = client.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"content": "Cannot be deleted by PM"},
            headers=write_headers,
        )
        comment_id = comment_response.json()["id"]

        # PM attempts to delete
        response = client.delete(f"/api/comments/{comment_id}", headers=pm_headers)

        assert response.status_code == 403
        assert "only comment author or admins can delete" in response.json()["detail"]

    def test_delete_comment_not_found(self, client: TestClient, shared_org_admin_token: tuple[str, str]) -> None:
        """Test deleting non-existent comment returns 404."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        response = client.delete("/api/comments/non-existent-id", headers=headers)

        assert response.status_code == 404
        assert "Comment not found" in response.json()["detail"]

    def test_delete_comment_without_authentication(self, client: TestClient) -> None:
        """Test deleting comment without authentication fails."""
        response = client.delete("/api/comments/some-id")

        assert response.status_code == 401

    def test_delete_comment_activity_logged(
        self, client: TestClient, test_repo: Repository, shared_org_admin_token: tuple[str, str]
    ) -> None:
        """Test that comment deletion is logged in activity log."""
        token, org_id = shared_org_admin_token
        headers = auth_headers(token)

        # Create project, ticket, and comment
        project_response = client.post("/api/projects", json={"name": "Test Project"}, headers=headers)
        project_id = project_response.json()["id"]

        ticket_response = client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": "Test Ticket"},
            headers=headers,
        )
        ticket_id = ticket_response.json()["id"]

        comment_response = client.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"content": "To be deleted"},
            headers=headers,
        )
        comment_id = comment_response.json()["id"]

        # Delete comment
        response = client.delete(f"/api/comments/{comment_id}", headers=headers)

        assert response.status_code == 204

        # Check activity log
        logs = test_repo.activity_logs.list(entity_type="comment", entity_id=comment_id)
        delete_logs = [log for log in logs if log.action == ActionType.COMMENT_DELETED]
        assert len(delete_logs) == 1
        assert delete_logs[0].entity_id == comment_id
