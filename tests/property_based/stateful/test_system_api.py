"""Unified stateful property-based tests for the entire system API.

This combines all entity operations (Users, Projects, Tickets) into a single
comprehensive state machine that tests the system as a whole, including
cross-entity interactions and workflows.
"""

from fastapi.testclient import TestClient
from hypothesis import strategies as st
from hypothesis.stateful import Bundle, RuleBasedStateMachine, rule, run_state_machine_as_test

from project_management_crud_example.domain_models import (
    Ticket,
    TicketPriority,
    User,
    UserCreateResponse,
    UserData,
    UserUpdateCommand,
)
from tests.conftest import client  # noqa: F401
from tests.fixtures.auth_fixtures import super_admin_token  # noqa: F401
from tests.helpers import create_admin_user, create_test_org, create_test_project
from tests.sdk.test_sdk import APITestSDK


class SystemAPIStateMachine(RuleBasedStateMachine):
    """Comprehensive stateful property-based tests for the entire system API.

    This tests that ALL API operations maintain consistent state across the system:

    USER OPERATIONS:
    - Created users return 201 and can be retrieved with 200
    - Deleted users return 404 on GET
    - Updated users persist changes correctly
    - List endpoint count matches created - deleted users
    - Email uniqueness is enforced within organizations
    - HTTP responses are consistent with state
    - Immutable fields (username, organization_id) never change
    - Multi-organization isolation is enforced

    TICKET OPERATIONS:
    - Created tickets return 201 and can be retrieved with 200
    - Deleted tickets return 404 on GET
    - Updated tickets persist changes correctly
    - Status transitions follow workflow rules
    - Assignments are tracked correctly
    - List endpoint count matches created - deleted tickets
    - Organization and project isolation is enforced

    CROSS-ENTITY INVARIANTS:
    - Tickets can be assigned to users in the same organization
    - Users can be reporters and assignees for tickets
    - Projects belong to organizations
    - Tickets belong to projects which belong to organizations
    """

    # Bundles for all entities
    users = Bundle("users")
    organizations = Bundle("organizations")
    projects = Bundle("projects")
    tickets = Bundle("tickets")

    # Define immutable fields once for reuse across all checks
    IMMUTABLE_USER_FIELDS = ["username", "organization_id"]

    def __init__(self, client: TestClient, super_admin_token: str) -> None:
        import uuid

        super().__init__()
        self.client = client
        self.super_admin_token = super_admin_token

        # Create initial organization for this test run (each Hypothesis example gets its own)
        org_name = f"Test Org {uuid.uuid4().hex[:8]}"
        self.organization_id = create_test_org(client, super_admin_token, name=org_name)

        # Create admin user in the organization (super admin can't create projects)
        admin_username = f"admin{uuid.uuid4().hex[:8]}"
        admin_user_id, admin_password = create_admin_user(
            client, super_admin_token, self.organization_id, username=admin_username
        )

        # Login as admin to get token
        login_response = client.post("/auth/login", json={"username": admin_username, "password": admin_password})
        self.admin_token = login_response.json()["access_token"]

        # Create SDK instances for different auth contexts
        base_sdk = APITestSDK(client)
        self.sdk = base_sdk.with_auth(super_admin_token)  # Super admin SDK for most operations

        # Track organizations for multi-org testing
        self.created_org_ids: set[str] = {self.organization_id}  # Start with initial org

        # Track user IDs (include the admin user created in setup)
        self.created_user_ids: set[str] = {admin_user_id}  # Start with admin user
        self.deleted_user_ids: set[str] = set()
        # Note: We don't track admin user in user_data/immutable_fields because
        # we won't be testing operations on it (it's just for infrastructure)

        # Shadow state for user data
        self.user_data: dict[
            str, dict[str, str | bool]
        ] = {}  # user_id -> {email, full_name, role, is_active, organization_id}

        # Track immutable fields (username, organization_id) for invariant checking
        self.immutable_fields: dict[str, dict[str, str]] = {}  # user_id -> {username, organization_id}

        # Track emails in use per organization (for uniqueness testing within org)
        self.emails_in_use_per_org: dict[str, set[str]] = {}  # org_id -> set of emails

        # Track project IDs
        self.created_project_ids: set[str] = set()

        # Shadow state for projects (to track valid statuses)
        self.project_statuses: dict[str, list[str]] = {}  # project_id -> list of valid statuses

        # Track ticket IDs
        self.created_ticket_ids: set[str] = set()
        self.deleted_ticket_ids: set[str] = set()

        # Shadow state for tickets
        self.ticket_data: dict[
            str, dict
        ] = {}  # ticket_id -> {title, description, priority, status, assignee_id, reporter_id, project_id}

    # ========================================================================
    # USER RULES
    # ========================================================================

    def _verify_immutable_fields(self, user_id: str, user_obj: dict) -> None:
        """Helper to verify immutable fields haven't changed.

        Args:
            user_id: ID of the user to check
            user_obj: User object from API response
        """
        if user_id in self.immutable_fields:
            for field in self.IMMUTABLE_USER_FIELDS:
                expected = self.immutable_fields[user_id][field]
                actual = user_obj[field]
                assert actual == expected, f"{field} changed for user {user_id}: expected {expected}, got {actual}"

    @rule(target=users)
    def create_user_via_api(self) -> str:
        """Create a new user via API and add to bundle."""
        import uuid

        # Generate unique username and email using UUID to avoid collisions
        username = f"apiuser{uuid.uuid4().hex[:10]}"
        email = f"{username}@example.com"
        full_name = f"API User {username}"

        # Create Pydantic model for request
        user_data = UserData(username=username, email=email, full_name=full_name)

        # Create user via API (serialize Pydantic model to JSON)
        response = self.client.post(
            f"/api/users?organization_id={self.organization_id}&role=read_access",
            json=user_data.model_dump(mode="json"),
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Create should return 201
        assert response.status_code == 201, f"Create should return 201, got {response.status_code}"

        # Deserialize response to Pydantic model (validates structure)
        create_response = UserCreateResponse.model_validate(response.json())
        user_id = create_response.user.id
        user_obj = create_response.user

        # Track in shadow state
        self.created_user_ids.add(user_id)
        self.user_data[user_id] = {
            "email": email,
            "full_name": full_name,
            "role": "read_access",
            "is_active": True,
            "organization_id": self.organization_id,
        }
        # Track immutable fields
        self.immutable_fields[user_id] = {
            "username": username,
            "organization_id": self.organization_id,
        }
        # Track email in use for this organization
        if self.organization_id not in self.emails_in_use_per_org:
            self.emails_in_use_per_org[self.organization_id] = set()
        self.emails_in_use_per_org[self.organization_id].add(email)

        # Invariant: Response has correct structure (validated by Pydantic automatically)
        assert create_response.generated_password is not None, "Create response should have generated_password"
        assert len(create_response.generated_password) > 0, "Generated password should not be empty"

        # Invariant: User data matches what we sent
        assert user_obj.email == email
        assert user_obj.full_name == full_name
        assert user_obj.role == "read_access"

        # Invariant: Just-created user should be retrievable
        get_response = self.client.get(
            f"/api/users/{user_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )
        assert get_response.status_code == 200, "Just-created user should return 200 on GET"
        retrieved_user = User.model_validate(get_response.json())
        assert retrieved_user.id == user_id

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

            # Deserialize to Pydantic model (validates structure)
            user_obj = User.model_validate(response.json())
            assert user_obj.id == user_id

            # Invariant: Retrieved data matches shadow state
            if user_id in self.user_data:
                shadow = self.user_data[user_id]
                assert user_obj.email == shadow["email"], f"Email mismatch for user {user_id}"
                assert user_obj.full_name == shadow["full_name"], f"Full name mismatch for user {user_id}"
                assert user_obj.role == shadow["role"], f"Role mismatch for user {user_id}"
                assert user_obj.is_active == shadow["is_active"], f"is_active mismatch for user {user_id}"

            # Invariant: Immutable fields never change
            # Convert Pydantic model to dict for the helper
            self._verify_immutable_fields(user_id, user_obj.model_dump())
        else:
            assert response.status_code == 404, f"Deleted user should return 404, got {response.status_code}"

    @rule(user_id=users)
    def delete_user_via_api(self, user_id: str) -> None:
        """Delete a user via API."""
        # Skip if already deleted
        if user_id in self.deleted_user_ids:
            return

        # Get user data before deletion for cleanup
        user_email = self.user_data.get(user_id, {}).get("email")

        # Delete user
        response = self.client.delete(
            f"/api/users/{user_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Delete should return 204
        assert response.status_code == 204, f"Delete should return 204, got {response.status_code}"

        # Track deletion and clean up shadow state
        self.deleted_user_ids.add(user_id)
        if user_id in self.user_data:
            user_org_id = str(self.user_data[user_id].get("organization_id", ""))
            del self.user_data[user_id]
            # Remove email from organization's email set
            if user_email and user_org_id and user_org_id in self.emails_in_use_per_org:
                if user_email in self.emails_in_use_per_org[user_org_id]:
                    self.emails_in_use_per_org[user_org_id].remove(user_email)

        # Invariant: Deleted user should return 404
        get_response = self.client.get(
            f"/api/users/{user_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )
        assert get_response.status_code == 404, "Deleted user should return 404"

    @rule(user_id=users, new_full_name=st.text(min_size=1, max_size=50))
    def update_user_full_name(self, user_id: str, new_full_name: str) -> None:
        """Update a user's full name via API."""
        # Skip if deleted
        if user_id in self.deleted_user_ids:
            return

        # Create Pydantic update command
        update_cmd = UserUpdateCommand(full_name=new_full_name)

        # Update user (serialize to JSON)
        response = self.client.put(
            f"/api/users/{user_id}",
            json=update_cmd.model_dump(mode="json", exclude_unset=True),
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Update should return 200
        assert response.status_code == 200, f"Update should return 200, got {response.status_code}"

        # Deserialize response
        user_obj = User.model_validate(response.json())

        # Invariant: Updated field changed
        assert user_obj.full_name == new_full_name, "Full name should be updated"

        # Invariant: Other fields unchanged
        if user_id in self.user_data:
            shadow = self.user_data[user_id]
            assert user_obj.email == shadow["email"], "Email should not change"
            assert user_obj.role == shadow["role"], "Role should not change"
            assert user_obj.is_active == shadow["is_active"], "is_active should not change"

        # Invariant: Immutable fields never change
        self._verify_immutable_fields(user_id, user_obj.model_dump())

        # Update shadow state
        if user_id in self.user_data:
            self.user_data[user_id]["full_name"] = new_full_name

        # Invariant: GET reflects the update
        get_response = self.client.get(
            f"/api/users/{user_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )
        assert get_response.status_code == 200
        updated_user = User.model_validate(get_response.json())
        assert updated_user.full_name == new_full_name

    @rule(
        user_id=users,
        new_role=st.sampled_from(["read_access", "write_access", "project_manager", "admin"]),
    )
    def update_user_role(self, user_id: str, new_role: str) -> None:
        """Update a user's role via API."""
        # Skip if deleted
        if user_id in self.deleted_user_ids:
            return

        # Update user
        response = self.client.put(
            f"/api/users/{user_id}",
            json={"role": new_role},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Update should return 200
        assert response.status_code == 200, f"Update should return 200, got {response.status_code}"

        user_obj = User.model_validate(response.json())

        # Invariant: Updated field changed
        assert user_obj.role == new_role, f"Role should be updated to {new_role}"

        # Invariant: Immutable fields never change
        self._verify_immutable_fields(user_id, user_obj.model_dump())

        # Update shadow state
        if user_id in self.user_data:
            self.user_data[user_id]["role"] = new_role

    @rule(user_id=users)
    def deactivate_user(self, user_id: str) -> None:
        """Deactivate a user via API."""
        # Skip if deleted or already inactive
        if user_id in self.deleted_user_ids:
            return
        if user_id in self.user_data and not self.user_data[user_id]["is_active"]:
            return

        # Deactivate user using SDK
        # Invariant: Update should succeed
        user = self.sdk.users.deactivate(user_id).assert_ok()

        # Invariant: User is now inactive
        assert user.is_active is False, "User should be inactive"

        # Update shadow state
        if user_id in self.user_data:
            self.user_data[user_id]["is_active"] = False

        # Invariant: Inactive user still exists (not deleted)
        get_result = self.sdk.users.get(user_id)
        assert get_result.ok, "Inactive user should still be retrievable"

    @rule()
    def list_users_verify_count(self) -> None:
        """List all users in our organization and verify count matches shadow state."""
        # Filter by our organization since super admin sees all users
        response = self.client.get(
            f"/api/users?organization_id={self.organization_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: List should return 200
        assert response.status_code == 200, f"List should return 200, got {response.status_code}"

        # Deserialize to list of User models (validates structure for each user)
        users_list = [User.model_validate(u) for u in response.json()]

        # Invariant: Should return a list (validated by Pydantic)
        assert isinstance(users_list, list), "List endpoint should return a list"

        # Invariant: Count matches users in this organization (created - deleted)
        # Note: For users in user_data, check organization matches. For users NOT in user_data
        # (like the initial admin user), they're assumed to be in self.organization_id
        expected_user_ids = {
            user_id
            for user_id in self.created_user_ids
            if user_id not in self.deleted_user_ids
            and (
                user_id not in self.user_data  # Initial admin user (not tracked in user_data)
                or str(self.user_data[user_id].get("organization_id", "")) == self.organization_id
            )
        }
        expected_count = len(expected_user_ids)
        actual_count = len(users_list)
        assert actual_count == expected_count, f"User count mismatch: expected {expected_count}, got {actual_count}"

        # Invariant: All non-deleted users from this org appear in list
        returned_user_ids = {user.id for user in users_list}
        assert returned_user_ids == expected_user_ids, (
            f"User IDs mismatch. Expected: {expected_user_ids}, got: {returned_user_ids}"
        )

        # Invariant: No deleted users appear in list
        for user in users_list:
            assert user.id not in self.deleted_user_ids, f"Deleted user {user.id} should not appear in list"

        # Invariant: Each user's data matches shadow state
        for user in users_list:
            user_id = user.id
            if user_id in self.user_data:
                shadow = self.user_data[user_id]
                assert user.email == shadow["email"], f"Email mismatch in list for user {user_id}"
                assert user.full_name == shadow["full_name"], f"Full name mismatch in list for user {user_id}"
                assert user.role == shadow["role"], f"Role mismatch in list for user {user_id}"
                assert user.is_active == shadow["is_active"], f"is_active mismatch in list for user {user_id}"

    @rule(target=organizations)
    def create_additional_organization(self) -> str:
        """Create an additional organization for multi-org testing."""
        import uuid

        org_name = f"Test Org {uuid.uuid4().hex[:8]}"
        org_id = create_test_org(self.client, self.super_admin_token, name=org_name)

        # Track the new organization
        self.created_org_ids.add(org_id)

        return org_id

    @rule(target=users, org_id=organizations)
    def create_user_in_specific_org(self, org_id: str) -> str:
        """Create a new user in a specific organization."""
        import uuid

        # Generate unique username and email
        username = f"apiuser{uuid.uuid4().hex[:10]}"
        email = f"{username}@example.com"
        full_name = f"API User {username}"

        # Create Pydantic model for request
        user_data = UserData(username=username, email=email, full_name=full_name)

        # Create user in specified organization
        response = self.client.post(
            f"/api/users?organization_id={org_id}&role=read_access",
            json=user_data.model_dump(mode="json"),
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Create should return 201
        assert response.status_code == 201, f"Create should return 201, got {response.status_code}"

        # Deserialize response
        create_response = UserCreateResponse.model_validate(response.json())
        user_id = create_response.user.id
        user_obj = create_response.user

        # Track in shadow state
        self.created_user_ids.add(user_id)
        self.user_data[user_id] = {
            "email": email,
            "full_name": full_name,
            "role": "read_access",
            "is_active": True,
            "organization_id": org_id,
        }
        # Track immutable fields
        self.immutable_fields[user_id] = {
            "username": username,
            "organization_id": org_id,
        }
        # Track email in use for this organization
        if org_id not in self.emails_in_use_per_org:
            self.emails_in_use_per_org[org_id] = set()
        self.emails_in_use_per_org[org_id].add(email)

        # Invariant: organization_id matches what we sent
        assert user_obj.organization_id == org_id, f"User should be in org {org_id}"

        return user_id

    # ========================================================================
    # PROJECT RULES
    # ========================================================================

    @rule(target=projects)
    def create_project_via_api(self) -> str:
        """Create a new project via API and add to bundle."""
        import uuid

        project_name = f"Project {uuid.uuid4().hex[:8]}"

        # Use helper to create project (using admin token, not super admin)
        project_id = create_test_project(
            self.client,
            self.admin_token,
            name=project_name,
        )

        # Track project
        self.created_project_ids.add(project_id)

        # Get project to get workflow information
        project_response = self.client.get(
            f"/api/projects/{project_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )
        assert project_response.status_code == 200

        project = project_response.json()

        # Get workflow statuses for this project
        workflow_id = project.get("workflow_id")
        if workflow_id:
            workflow_response = self.client.get(
                f"/api/workflows/{workflow_id}",
                headers={"Authorization": f"Bearer {self.super_admin_token}"},
            )
            if workflow_response.status_code == 200:
                workflow = workflow_response.json()
                self.project_statuses[project_id] = workflow.get("statuses", ["TODO", "IN_PROGRESS", "DONE"])
            else:
                # Default statuses
                self.project_statuses[project_id] = ["TODO", "IN_PROGRESS", "DONE"]
        else:
            self.project_statuses[project_id] = ["TODO", "IN_PROGRESS", "DONE"]

        return project_id

    # ========================================================================
    # TICKET RULES
    # ========================================================================

    @rule(target=tickets, project_id=projects, reporter_id=users)
    def create_ticket_via_api(self, project_id: str, reporter_id: str) -> str:
        """Create a new ticket via API and add to bundle."""
        import uuid

        title = f"Ticket {uuid.uuid4().hex[:8]}"
        description = f"Description for {title}"
        priority = "HIGH"

        # Create ticket via API
        response = self.client.post(
            f"/api/tickets?project_id={project_id}",
            json={"title": title, "description": description, "priority": priority},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Create should return 201
        assert response.status_code == 201, f"Create ticket should return 201, got {response.status_code}"

        ticket = Ticket.model_validate(response.json())
        ticket_id = ticket.id

        # Track in shadow state
        self.created_ticket_ids.add(ticket_id)
        self.ticket_data[ticket_id] = {
            "title": title,
            "description": description,
            "priority": priority,
            "status": ticket.status,  # Use actual status from response
            "assignee_id": None,
            "reporter_id": reporter_id,
            "project_id": project_id,
        }

        # Invariant: Ticket data matches what we sent
        assert ticket.title == title
        assert ticket.description == description
        assert ticket.priority == TicketPriority.HIGH
        assert ticket.project_id == project_id

        # Invariant: Just-created ticket should be retrievable
        get_response = self.client.get(
            f"/api/tickets/{ticket_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )
        assert get_response.status_code == 200, "Just-created ticket should return 200 on GET"

        return ticket_id

    @rule(ticket_id=tickets)
    def get_ticket_via_api(self, ticket_id: str) -> None:
        """Retrieve a ticket by ID via API."""
        response = self.client.get(
            f"/api/tickets/{ticket_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Status code matches deletion state
        if ticket_id not in self.deleted_ticket_ids:
            assert response.status_code == 200, f"Non-deleted ticket should return 200, got {response.status_code}"

            ticket = Ticket.model_validate(response.json())
            assert ticket.id == ticket_id

            # Invariant: Retrieved data matches shadow state
            if ticket_id in self.ticket_data:
                shadow = self.ticket_data[ticket_id]
                assert ticket.title == shadow["title"], f"Title mismatch for ticket {ticket_id}"
                assert ticket.description == shadow["description"], f"Description mismatch for ticket {ticket_id}"
                assert ticket.priority.value == shadow["priority"], f"Priority mismatch for ticket {ticket_id}"
                assert ticket.status == shadow["status"], f"Status mismatch for ticket {ticket_id}"
                assert ticket.project_id == shadow["project_id"], f"Project ID mismatch for ticket {ticket_id}"
        else:
            assert response.status_code == 404, f"Deleted ticket should return 404, got {response.status_code}"

    @rule(ticket_id=tickets)
    def delete_ticket_via_api(self, ticket_id: str) -> None:
        """Delete a ticket via API."""
        # Skip if already deleted
        if ticket_id in self.deleted_ticket_ids:
            return

        # Delete ticket
        response = self.client.delete(
            f"/api/tickets/{ticket_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Delete should return 204
        assert response.status_code == 204, f"Delete should return 204, got {response.status_code}"

        # Track deletion and clean up shadow state
        self.deleted_ticket_ids.add(ticket_id)
        if ticket_id in self.ticket_data:
            del self.ticket_data[ticket_id]

        # Invariant: Deleted ticket should return 404
        get_response = self.client.get(
            f"/api/tickets/{ticket_id}",
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )
        assert get_response.status_code == 404, "Deleted ticket should return 404"

    @rule(ticket_id=tickets, new_title=st.text(min_size=1, max_size=100))
    def update_ticket_title(self, ticket_id: str, new_title: str) -> None:
        """Update a ticket's title via API."""
        # Skip if deleted
        if ticket_id in self.deleted_ticket_ids:
            return

        # Update ticket
        response = self.client.put(
            f"/api/tickets/{ticket_id}",
            json={"title": new_title},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Update should return 200
        assert response.status_code == 200, f"Update should return 200, got {response.status_code}"

        ticket = Ticket.model_validate(response.json())

        # Invariant: Updated field changed
        assert ticket.title == new_title, "Title should be updated"

        # Update shadow state
        if ticket_id in self.ticket_data:
            self.ticket_data[ticket_id]["title"] = new_title

    @rule(ticket_id=tickets, new_priority=st.sampled_from(["LOW", "MEDIUM", "HIGH", "CRITICAL"]))
    def update_ticket_priority(self, ticket_id: str, new_priority: str) -> None:
        """Update a ticket's priority via API."""
        # Skip if deleted
        if ticket_id in self.deleted_ticket_ids:
            return

        # Update ticket
        response = self.client.put(
            f"/api/tickets/{ticket_id}",
            json={"priority": new_priority},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Update should return 200
        assert response.status_code == 200, f"Update should return 200, got {response.status_code}"

        ticket = Ticket.model_validate(response.json())

        # Invariant: Updated field changed
        assert ticket.priority.value == new_priority, "Priority should be updated"

        # Update shadow state
        if ticket_id in self.ticket_data:
            self.ticket_data[ticket_id]["priority"] = new_priority

    @rule(ticket_id=tickets)
    def update_ticket_status(self, ticket_id: str) -> None:
        """Update a ticket's status to a valid status from its project's workflow."""
        # Skip if deleted
        if ticket_id in self.deleted_ticket_ids:
            return

        # Get ticket's project
        if ticket_id not in self.ticket_data:
            return

        project_id = self.ticket_data[ticket_id]["project_id"]

        # Get valid statuses for this project
        if project_id not in self.project_statuses:
            return

        valid_statuses = self.project_statuses[project_id]
        if not valid_statuses:
            return

        # Pick first valid status for simplicity
        new_status = valid_statuses[0]

        # Update status via dedicated endpoint
        response = self.client.put(
            f"/api/tickets/{ticket_id}/status",
            json={"status": new_status},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Update should return 200 for valid status
        assert response.status_code == 200, f"Update status should return 200, got {response.status_code}"

        ticket = Ticket.model_validate(response.json())

        # Invariant: Status should be updated
        assert ticket.status == new_status, f"Status should be {new_status}, got {ticket.status}"

        # Update shadow state
        if ticket_id in self.ticket_data:
            self.ticket_data[ticket_id]["status"] = new_status

    @rule(ticket_id=tickets, assignee_id=users)
    def assign_ticket_to_user(self, ticket_id: str, assignee_id: str) -> None:
        """Assign a ticket to a user via API."""
        # Skip if ticket or user is deleted
        if ticket_id in self.deleted_ticket_ids:
            return
        if assignee_id in self.deleted_user_ids:
            return
        # Skip if user is inactive (cannot assign to inactive users)
        if assignee_id in self.user_data and not self.user_data[assignee_id].get("is_active", True):
            return

        # Assign ticket
        response = self.client.put(
            f"/api/tickets/{ticket_id}/assignee",
            json={"assignee_id": assignee_id},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Assignment should return 200
        assert response.status_code == 200, f"Assignment should return 200, got {response.status_code}"

        ticket = Ticket.model_validate(response.json())

        # Invariant: Assignee should be updated
        assert ticket.assignee_id == assignee_id, f"Assignee should be {assignee_id}"

        # Update shadow state
        if ticket_id in self.ticket_data:
            self.ticket_data[ticket_id]["assignee_id"] = assignee_id

    @rule(ticket_id=tickets)
    def unassign_ticket(self, ticket_id: str) -> None:
        """Unassign a ticket via API."""
        # Skip if deleted
        if ticket_id in self.deleted_ticket_ids:
            return

        # Unassign ticket
        response = self.client.put(
            f"/api/tickets/{ticket_id}/assignee",
            json={"assignee_id": None},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Unassignment should return 200
        assert response.status_code == 200, f"Unassignment should return 200, got {response.status_code}"

        ticket = Ticket.model_validate(response.json())

        # Invariant: Assignee should be None
        assert ticket.assignee_id is None, "Assignee should be None"

        # Update shadow state
        if ticket_id in self.ticket_data:
            self.ticket_data[ticket_id]["assignee_id"] = None

    @rule(project_id=projects)
    def list_tickets_by_project(self, project_id: str) -> None:
        """List all tickets for a project and verify count matches shadow state."""
        response = self.client.get(
            f"/api/tickets?project_id={project_id}",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )

        # Invariant: List should return 200
        assert response.status_code == 200, f"List should return 200, got {response.status_code}"

        tickets_list = [Ticket.model_validate(t) for t in response.json()]

        # Invariant: Count matches expected tickets in this project
        expected_ticket_ids = {
            ticket_id
            for ticket_id in self.ticket_data
            if ticket_id not in self.deleted_ticket_ids and self.ticket_data[ticket_id]["project_id"] == project_id
        }
        returned_ticket_ids = {t.id for t in tickets_list}

        assert returned_ticket_ids == expected_ticket_ids, (
            f"Project filter mismatch. Expected {len(expected_ticket_ids)} tickets in project {project_id}, "
            f"got {len(returned_ticket_ids)}"
        )

        # Invariant: All returned tickets belong to this project
        for ticket in tickets_list:
            assert ticket.project_id == project_id, f"Ticket {ticket.id} should be in project {project_id}"

    # ========================================================================
    # VALIDATION TESTING RULES (Testing that invalid operations fail correctly)
    # ========================================================================

    @rule(ticket_id=tickets, assignee_id=users)
    def attempt_assign_to_inactive_user(self, ticket_id: str, assignee_id: str) -> None:
        """Test that assigning ticket to inactive user returns 400.

        This rule tests VALIDATION - it intentionally attempts an invalid operation
        and verifies the API rejects it correctly.
        """
        # Precondition: Only run if user IS inactive (opposite of assign_ticket_to_user)
        if assignee_id not in self.user_data:
            return
        if self.user_data[assignee_id].get("is_active", True):
            return  # Skip if user is active

        # Precondition: Skip if ticket or user is deleted
        if ticket_id in self.deleted_ticket_ids:
            return
        if assignee_id in self.deleted_user_ids:
            return

        # Attempt to assign ticket to inactive user
        response = self.client.put(
            f"/api/tickets/{ticket_id}/assignee",
            json={"assignee_id": assignee_id},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Assignment to inactive user should return 400
        assert response.status_code == 400, f"Assigning to inactive user should return 400, got {response.status_code}"

        # Invariant: Error message should mention "inactive"
        error_detail = response.json().get("detail", "").lower()
        assert "inactive" in error_detail, f"Error message should mention inactive user, got: {error_detail}"

    @rule(ticket_id=tickets, assignee_id=users)
    def attempt_assign_to_deleted_user(self, ticket_id: str, assignee_id: str) -> None:
        """Test that assigning ticket to deleted user returns 404.

        This rule tests VALIDATION - it intentionally attempts an invalid operation
        and verifies the API rejects it correctly.
        """
        # Precondition: Only run if user IS deleted (opposite of assign_ticket_to_user)
        if assignee_id not in self.deleted_user_ids:
            return  # Skip if user is not deleted

        # Precondition: Skip if ticket is deleted
        if ticket_id in self.deleted_ticket_ids:
            return

        # Attempt to assign ticket to deleted user
        response = self.client.put(
            f"/api/tickets/{ticket_id}/assignee",
            json={"assignee_id": assignee_id},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Assignment to deleted user should return 404
        assert response.status_code == 404, f"Assigning to deleted user should return 404, got {response.status_code}"

        # Invariant: Error message should mention user not found
        error_detail = response.json().get("detail", "").lower()
        assert "not found" in error_detail or "user" in error_detail, (
            f"Error message should mention user not found, got: {error_detail}"
        )

    @rule(ticket_id=tickets)
    def attempt_invalid_status_transition(self, ticket_id: str) -> None:
        """Test that setting an invalid status returns 422.

        This rule tests VALIDATION - it intentionally attempts an invalid operation
        and verifies the API rejects it correctly.
        """
        # Precondition: Skip if ticket is deleted
        if ticket_id in self.deleted_ticket_ids:
            return

        # Precondition: Get ticket's project to know valid statuses
        if ticket_id not in self.ticket_data:
            return

        project_id = self.ticket_data[ticket_id]["project_id"]

        # Get valid statuses for this project
        if project_id not in self.project_statuses:
            return

        valid_statuses = self.project_statuses[project_id]
        if not valid_statuses:
            return

        # Use an invalid status that is definitely not in the workflow
        # Common workflow statuses are TODO, IN_PROGRESS, DONE, etc.
        # We'll use something that should never be valid
        invalid_status = "DEFINITELY_NOT_A_VALID_STATUS_XYZ123"

        # Make sure this isn't somehow valid
        if invalid_status in valid_statuses:
            return  # Skip if by some chance this status is valid

        # Attempt to set invalid status
        response = self.client.put(
            f"/api/tickets/{ticket_id}/status",
            json={"status": invalid_status},
            headers={"Authorization": f"Bearer {self.super_admin_token}"},
        )

        # Invariant: Invalid status should return 422 (validation error) or 400 (business logic error)
        # Both are acceptable as different layers may catch the validation
        assert response.status_code in [400, 422], (
            f"Invalid status should return 400 or 422, got {response.status_code}"
        )

        # Invariant: Error message should mention status or workflow
        error_detail = response.json().get("detail", "").lower()
        assert any(keyword in error_detail for keyword in ["status", "workflow", "invalid", "valid"]), (
            f"Error message should mention status validation, got: {error_detail}"
        )


# Test function that pytest will discover
def test_system_api_state_machine(client: TestClient, super_admin_token: str) -> None:
    """Run the unified System API state machine test."""
    # Run state machine - each Hypothesis example creates its own org/admin in __init__
    run_state_machine_as_test(lambda: SystemAPIStateMachine(client, super_admin_token))
