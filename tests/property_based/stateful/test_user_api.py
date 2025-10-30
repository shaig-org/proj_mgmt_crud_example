"""Stateful property-based tests for User API endpoints."""

from fastapi.testclient import TestClient
from hypothesis.stateful import Bundle, RuleBasedStateMachine, rule, run_state_machine_as_test

from tests.conftest import client  # noqa: F401
from tests.fixtures.auth_fixtures import super_admin_token  # noqa: F401
from tests.helpers import create_test_org


class UserAPIStateMachine(RuleBasedStateMachine):
    """Minimal state machine testing User API endpoints.

    This tests that API operations maintain consistent state:
    - Created users return 201 and can be retrieved with 200
    - Deleted users return 404 on GET
    - HTTP responses are consistent with state
    """

    users = Bundle("users")

    def __init__(self, client: TestClient, super_admin_token: str) -> None:
        import uuid

        super().__init__()
        self.client = client
        self.super_admin_token = super_admin_token
        # Create organization for all users with unique name
        org_name = f"Test Org {uuid.uuid4().hex[:8]}"
        org_id = create_test_org(client, super_admin_token, name=org_name)
        self.organization_id = org_id
        self.created_user_ids: set[str] = set()
        self.deleted_user_ids: set[str] = set()

    @rule(target=users)
    def create_user_via_api(self) -> str:
        """Create a new user via API and add to bundle."""
        import uuid

        # Generate unique username using UUID to avoid collisions
        username = f"apiuser{uuid.uuid4().hex[:10]}"

        # Create user via API
        response = self.client.post(
            f"/api/users?organization_id={self.organization_id}&role=read_access",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "full_name": f"API User {username}",
            },
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Create should return 201
        assert response.status_code == 201, f"Create should return 201, got {response.status_code}"

        response_data = response.json()
        user_id = response_data["user"]["id"]
        self.created_user_ids.add(user_id)

        # Invariant: Just-created user should be retrievable
        get_response = self.client.get(
            f"/api/users/{user_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )
        assert get_response.status_code == 200, "Just-created user should return 200 on GET"
        assert get_response.json()["id"] == user_id

        return user_id

    @rule(user_id=users)
    def get_user_via_api(self, user_id: str) -> None:
        """Retrieve a user by ID via API."""
        response = self.client.get(
            f"/api/users/{user_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Status code matches deletion state
        if user_id not in self.deleted_user_ids:
            assert response.status_code == 200, f"Non-deleted user should return 200, got {response.status_code}"
            assert response.json()["id"] == user_id
        else:
            assert response.status_code == 404, f"Deleted user should return 404, got {response.status_code}"

    @rule(user_id=users)
    def delete_user_via_api(self, user_id: str) -> None:
        """Delete a user via API."""
        # Skip if already deleted
        if user_id in self.deleted_user_ids:
            return

        # Delete user
        response = self.client.delete(
            f"/api/users/{user_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Delete should return 204
        assert response.status_code == 204, f"Delete should return 204, got {response.status_code}"

        # Track deletion
        self.deleted_user_ids.add(user_id)

        # Invariant: Deleted user should return 404
        get_response = self.client.get(
            f"/api/users/{user_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )
        assert get_response.status_code == 404, "Deleted user should return 404"


# Test function that pytest will discover
def test_user_api_state_machine(client: TestClient, super_admin_token: str) -> None:
    """Run the User API state machine test."""
    # Run state machine with test client and auth token
    run_state_machine_as_test(lambda: UserAPIStateMachine(client, super_admin_token))
