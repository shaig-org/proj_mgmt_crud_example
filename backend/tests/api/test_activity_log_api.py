"""Tests for activity log API endpoints."""

from datetime import datetime, timedelta
from urllib.parse import quote

from fastapi.testclient import TestClient

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import ActionType
from tests.conftest import client, test_repo  # noqa: F401
from tests.fixtures.auth_fixtures import (  # noqa: F401
    org_admin_token,
    project_manager_token,
    read_user_token,
    super_admin_token,
    write_user_token,
)
from tests.helpers import (
    auth_headers,
    create_admin_user,
    create_test_epic,
    create_test_org,
    create_test_project,
)


class TestListActivityLogs:
    """Tests for GET /api/activity-logs endpoint."""

    def test_list_activity_logs_as_super_admin(
        self, client: TestClient, test_repo: Repository, super_admin_token: str
    ) -> None:
        """Test that Super Admin can list all activity logs."""
        # Create two organizations with activities
        org1_id = create_test_org(client, super_admin_token, "Org 1")
        org2_id = create_test_org(client, super_admin_token, "Org 2")

        # Create admin in org1 and create a project
        admin1_id, password1 = create_admin_user(client, super_admin_token, org1_id, username="admin1")
        login_response1 = client.post("/auth/login", json={"username": "admin1", "password": password1})
        admin1_token = login_response1.json()["access_token"]
        create_test_project(client, admin1_token, "Project 1")

        # Create admin in org2 and create a project
        admin2_id, password2 = create_admin_user(client, super_admin_token, org2_id, username="admin2")
        login_response2 = client.post("/auth/login", json={"username": "admin2", "password": password2})
        admin2_token = login_response2.json()["access_token"]
        create_test_project(client, admin2_token, "Project 2")

        # Super Admin lists all logs (should see both organizations)
        response = client.get("/api/activity-logs", headers=auth_headers(super_admin_token))

        assert response.status_code == 200
        logs = response.json()

        # Should have multiple logs from both orgs (org creation, user creation, project creation)
        assert len(logs) > 0

        # Verify logs from both organizations are present
        org_ids = {log["organization_id"] for log in logs}
        assert org1_id in org_ids
        assert org2_id in org_ids

    def test_list_activity_logs_as_admin_filtered_to_org(
        self, client: TestClient, test_repo: Repository, super_admin_token: str
    ) -> None:
        """Test that Admin can only see logs from their organization."""
        # Create two organizations
        org1_id = create_test_org(client, super_admin_token, "Org 1")
        org2_id = create_test_org(client, super_admin_token, "Org 2")

        # Create admin in org1
        admin1_id, password1 = create_admin_user(client, super_admin_token, org1_id, username="admin1")
        login_response1 = client.post("/auth/login", json={"username": "admin1", "password": password1})
        admin1_token = login_response1.json()["access_token"]

        # Create project in org1
        create_test_project(client, admin1_token, "Project 1")

        # Create admin in org2 and create project
        admin2_id, password2 = create_admin_user(client, super_admin_token, org2_id, username="admin2")
        login_response2 = client.post("/auth/login", json={"username": "admin2", "password": password2})
        admin2_token = login_response2.json()["access_token"]
        create_test_project(client, admin2_token, "Project 2")

        # Admin1 lists logs - should only see org1 logs
        response = client.get("/api/activity-logs", headers=auth_headers(admin1_token))

        assert response.status_code == 200
        logs = response.json()

        # All logs should be from org1
        for log in logs:
            assert log["organization_id"] == org1_id

        # Verify no logs from org2
        org_ids = {log["organization_id"] for log in logs}
        assert org2_id not in org_ids

    def test_list_activity_logs_with_entity_type_filter(
        self, client: TestClient, test_repo: Repository, super_admin_token: str
    ) -> None:
        """Test filtering activity logs by entity type."""
        org_id = create_test_org(client, super_admin_token, "Test Org")
        admin_id, password = create_admin_user(client, super_admin_token, org_id, username="admin")

        # Login as admin
        login_response = client.post("/auth/login", json={"username": "admin", "password": password})
        admin_token = login_response.json()["access_token"]

        # Create project and epic (different entity types)
        create_test_project(client, admin_token, "Test Project")
        create_test_epic(client, admin_token, "Test Epic")

        # Filter by entity_type="project"
        response = client.get("/api/activity-logs?entity_type=project", headers=auth_headers(admin_token))

        assert response.status_code == 200
        logs = response.json()

        # All logs should be for projects
        for log in logs:
            assert log["entity_type"] == "project"

    def test_list_activity_logs_with_action_filter(
        self, client: TestClient, test_repo: Repository, super_admin_token: str
    ) -> None:
        """Test filtering activity logs by action type."""
        org_id = create_test_org(client, super_admin_token, "Test Org")
        admin_id, password = create_admin_user(client, super_admin_token, org_id, username="admin")

        # Login as admin
        login_response = client.post("/auth/login", json={"username": "admin", "password": password})
        admin_token = login_response.json()["access_token"]

        # Create and update a project
        project_id = create_test_project(client, admin_token, "Test Project")
        client.put(
            f"/api/projects/{project_id}",
            json={"name": "Updated Project"},
            headers=auth_headers(admin_token),
        )

        # Filter by action="project_created"
        response = client.get(
            f"/api/activity-logs?action={ActionType.PROJECT_CREATED.value}",
            headers=auth_headers(admin_token),
        )

        assert response.status_code == 200
        logs = response.json()

        # All logs should be PROJECT_CREATED actions
        for log in logs:
            assert log["action"] == ActionType.PROJECT_CREATED.value

    def test_list_activity_logs_with_date_range_filter(
        self, client: TestClient, test_repo: Repository, super_admin_token: str
    ) -> None:
        """Test filtering activity logs by date range."""
        org_id = create_test_org(client, super_admin_token, "Test Org")
        admin_id, password = create_admin_user(client, super_admin_token, org_id, username="admin")

        # Login as admin
        login_response = client.post("/auth/login", json={"username": "admin", "password": password})
        admin_token = login_response.json()["access_token"]

        # Record current time
        from datetime import UTC

        before_create = datetime.now(UTC)

        # Create project
        create_test_project(client, admin_token, "Test Project")

        after_create = datetime.now(UTC) + timedelta(seconds=1)

        # Query with date range that includes the creation
        response = client.get(
            f"/api/activity-logs?from_date={quote(before_create.isoformat())}&to_date={quote(after_create.isoformat())}",
            headers=auth_headers(admin_token),
        )

        assert response.status_code == 200
        logs = response.json()

        # Should have at least the project creation log
        assert len(logs) > 0

        # All timestamps should be within range
        from datetime import UTC as datetime_UTC

        for log in logs:
            log_timestamp = log["timestamp"]
            # Parse ISO format, ensure timezone aware
            if log_timestamp.endswith("Z"):
                log_time = datetime.fromisoformat(log_timestamp.replace("Z", "+00:00"))
            elif "+" in log_timestamp or log_timestamp.count("-") > 2:
                # Has timezone info
                log_time = datetime.fromisoformat(log_timestamp)
            else:
                # No timezone, assume UTC
                log_time = datetime.fromisoformat(log_timestamp).replace(tzinfo=datetime_UTC)
            assert before_create <= log_time <= after_create

    def test_list_activity_logs_with_order_desc(
        self, client: TestClient, test_repo: Repository, super_admin_token: str
    ) -> None:
        """Test listing activity logs in descending order (newest first)."""
        org_id = create_test_org(client, super_admin_token, "Test Org")
        admin_id, password = create_admin_user(client, super_admin_token, org_id, username="admin")

        # Login as admin
        login_response = client.post("/auth/login", json={"username": "admin", "password": password})
        admin_token = login_response.json()["access_token"]

        # Create two projects
        create_test_project(client, admin_token, "Project 1")
        create_test_project(client, admin_token, "Project 2")

        # Get logs in descending order (default)
        response = client.get("/api/activity-logs?order=desc", headers=auth_headers(admin_token))

        assert response.status_code == 200
        logs = response.json()

        # Verify timestamps are in descending order
        for i in range(len(logs) - 1):
            current_time = datetime.fromisoformat(logs[i]["timestamp"].replace("Z", "+00:00"))
            next_time = datetime.fromisoformat(logs[i + 1]["timestamp"].replace("Z", "+00:00"))
            assert current_time >= next_time

    def test_list_activity_logs_with_order_asc(
        self, client: TestClient, test_repo: Repository, super_admin_token: str
    ) -> None:
        """Test listing activity logs in ascending order (oldest first)."""
        org_id = create_test_org(client, super_admin_token, "Test Org")
        admin_id, password = create_admin_user(client, super_admin_token, org_id, username="admin")

        # Login as admin
        login_response = client.post("/auth/login", json={"username": "admin", "password": password})
        admin_token = login_response.json()["access_token"]

        # Create two projects
        create_test_project(client, admin_token, "Project 1")
        create_test_project(client, admin_token, "Project 2")

        # Get logs in ascending order
        response = client.get("/api/activity-logs?order=asc", headers=auth_headers(admin_token))

        assert response.status_code == 200
        logs = response.json()

        # Verify timestamps are in ascending order
        for i in range(len(logs) - 1):
            current_time = datetime.fromisoformat(logs[i]["timestamp"].replace("Z", "+00:00"))
            next_time = datetime.fromisoformat(logs[i + 1]["timestamp"].replace("Z", "+00:00"))
            assert current_time <= next_time


class TestGetActivityLog:
    """Tests for GET /api/activity-logs/{log_id} endpoint."""

    def test_get_activity_log_by_id_as_super_admin(
        self, client: TestClient, test_repo: Repository, super_admin_token: str
    ) -> None:
        """Test that Super Admin can get any activity log by ID."""
        # Create organization and project
        org_id = create_test_org(client, super_admin_token, "Test Org")
        admin_id, password = create_admin_user(client, super_admin_token, org_id, username="admin")

        # Login as admin
        login_response = client.post("/auth/login", json={"username": "admin", "password": password})
        admin_token = login_response.json()["access_token"]

        # Create project and get its activity log
        project_id = create_test_project(client, admin_token, "Test Project")
        logs = test_repo.activity_logs.list(entity_type="project", entity_id=project_id)
        log_id = logs[0].id

        # Super Admin gets log by ID
        response = client.get(f"/api/activity-logs/{log_id}", headers=auth_headers(super_admin_token))

        assert response.status_code == 200
        log = response.json()
        assert log["id"] == log_id
        assert log["entity_type"] == "project"
        assert log["entity_id"] == project_id

    def test_get_activity_log_by_id_as_admin_same_org(
        self, client: TestClient, test_repo: Repository, super_admin_token: str
    ) -> None:
        """Test that Admin can get activity log from their organization."""
        # Create organization
        org_id = create_test_org(client, super_admin_token, "Test Org")
        admin_id, password = create_admin_user(client, super_admin_token, org_id, username="admin")

        # Login as admin
        login_response = client.post("/auth/login", json={"username": "admin", "password": password})
        admin_token = login_response.json()["access_token"]

        # Create project
        project_id = create_test_project(client, admin_token, "Test Project")
        logs = test_repo.activity_logs.list(entity_type="project", entity_id=project_id)
        log_id = logs[0].id

        # Admin gets log by ID from their org
        response = client.get(f"/api/activity-logs/{log_id}", headers=auth_headers(admin_token))

        assert response.status_code == 200
        log = response.json()
        assert log["id"] == log_id
        assert log["organization_id"] == org_id

    def test_get_activity_log_by_id_as_admin_different_org_fails(
        self, client: TestClient, test_repo: Repository, super_admin_token: str
    ) -> None:
        """Test that Admin cannot get activity log from different organization."""
        # Create two organizations
        org1_id = create_test_org(client, super_admin_token, "Org 1")
        org2_id = create_test_org(client, super_admin_token, "Org 2")

        # Create admin in org1
        admin1_id, password1 = create_admin_user(client, super_admin_token, org1_id, username="admin1")
        login_response1 = client.post("/auth/login", json={"username": "admin1", "password": password1})
        admin1_token = login_response1.json()["access_token"]

        # Create admin in org2 and create project
        admin2_id, password2 = create_admin_user(client, super_admin_token, org2_id, username="admin2")
        login_response2 = client.post("/auth/login", json={"username": "admin2", "password": password2})
        admin2_token = login_response2.json()["access_token"]
        project_id = create_test_project(client, admin2_token, "Project in Org 2")

        # Get activity log from org2
        logs = test_repo.activity_logs.list(entity_type="project", entity_id=project_id)
        log_id = logs[0].id

        # Admin1 (from org1) tries to get log from org2 - should fail
        response = client.get(f"/api/activity-logs/{log_id}", headers=auth_headers(admin1_token))

        assert response.status_code == 404
        assert response.json()["detail"] == "Activity log not found"

    def test_get_activity_log_not_found(
        self, client: TestClient, test_repo: Repository, super_admin_token: str
    ) -> None:
        """Test getting non-existent activity log returns 404."""
        response = client.get("/api/activity-logs/non-existent-id", headers=auth_headers(super_admin_token))

        assert response.status_code == 404
        assert response.json()["detail"] == "Activity log not found"


class TestActivityLogPermissions:
    """Tests for activity log permission controls."""

    def test_read_user_can_access_activity_logs(
        self, client: TestClient, test_repo: Repository, read_user_token: tuple[str, str]
    ) -> None:
        """Test that read-only users can access activity logs."""
        token, org_id = read_user_token

        # List activity logs - should succeed
        response = client.get("/api/activity-logs", headers=auth_headers(token))

        assert response.status_code == 200
        logs = response.json()

        # All logs should be from user's organization
        for log in logs:
            assert log["organization_id"] == org_id

    def test_activity_logs_are_read_only(self, client: TestClient, super_admin_token: str) -> None:
        """Test that activity logs cannot be modified or deleted."""
        # Try to create activity log directly (should not have endpoint)
        response = client.post("/api/activity-logs", json={}, headers=auth_headers(super_admin_token))
        assert response.status_code == 405  # Method Not Allowed

        # Try to update activity log (should not have endpoint)
        response = client.put("/api/activity-logs/some-id", json={}, headers=auth_headers(super_admin_token))
        assert response.status_code == 405  # Method Not Allowed

        # Try to delete activity log (should not have endpoint)
        response = client.delete("/api/activity-logs/some-id", headers=auth_headers(super_admin_token))
        assert response.status_code == 405  # Method Not Allowed
