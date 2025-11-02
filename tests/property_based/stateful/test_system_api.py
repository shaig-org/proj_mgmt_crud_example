"""Unified stateful property-based tests for the entire system API.

This combines all entity operations (Users, Projects, Tickets) into a single
comprehensive state machine that tests the system as a whole, including
cross-entity interactions and workflows.

The state machine is organized using mixins for better maintainability:
- State tracking: StateTracker (state_tracker.py)
- User rules: UserRulesMixin (user_rules.py)
- Bundles: Central registry (bundles.py) - see thread-safety note there
"""

from fastapi.testclient import TestClient
from hypothesis.stateful import RuleBasedStateMachine, run_state_machine_as_test

from tests.conftest import client  # noqa: F401
from tests.fixtures.auth_fixtures import super_admin_token  # noqa: F401
from tests.helpers import create_admin_user, create_test_org
from tests.sdk.test_sdk import APITestSDK

# Import new modular components
from .bundles import Bundles
from .organization_rules import OrganizationRulesMixin
from .project_rules import ProjectRulesMixin
from .state_tracker import StateTracker
from .ticket_rules import TicketRulesMixin
from .user_rules import UserRulesMixin
from .validation_rules import ValidationRulesMixin


class SystemAPIStateMachine(
    UserRulesMixin,  # All user operation rules
    OrganizationRulesMixin,  # Multi-organization testing rules
    ProjectRulesMixin,  # Project operation rules
    TicketRulesMixin,  # All ticket operation rules
    ValidationRulesMixin,  # Validation testing rules (invalid operations)
    RuleBasedStateMachine,
):
    """Comprehensive stateful property-based tests for the entire system API.

    This state machine uses a mixin architecture to compose rules from multiple
    focused modules, testing the system as a whole including cross-entity
    interactions and workflows.

    Architecture:
    - Bundles: Central registry (bundles.py) - see thread-safety note there
    - State tracking: StateTracker (state_tracker.py) - manages shadow state
    - User rules: UserRulesMixin (user_rules.py) - 7 user operations
    - Organization rules: OrganizationRulesMixin (organization_rules.py) - multi-org testing
    - Project rules: ProjectRulesMixin (project_rules.py) - project operations
    - Ticket rules: TicketRulesMixin (ticket_rules.py) - 9 ticket operations
    - Validation rules: ValidationRulesMixin (validation_rules.py) - error testing

    Invariants Tested:
    - CRUD operations: Created entities are retrievable, updates persist
    - Deletion: Deleted entities return 404, not in lists
    - Data consistency: Retrieved data matches shadow state
    - Immutability: Fields like username, organization_id never change
    - Multi-org isolation: Users/data isolated per organization
    - Cross-entity: Tickets assigned to users in same organization
    - Workflow: Status transitions follow project workflow rules
    - Validation: Invalid operations fail with correct error codes

    This comprehensive test suite verifies the entire API maintains consistency
    across all entity types and operations.
    """

    # Bundle references from central registry
    # See bundles.py for thread-safety limitations
    users = Bundles.users
    organizations = Bundles.organizations
    projects = Bundles.projects
    tickets = Bundles.tickets

    def __init__(self, client: TestClient, super_admin_token: str) -> None:
        import uuid

        super().__init__()

        # Create initial organization for this test run (each Hypothesis example gets its own)
        org_name = f"Test Org {uuid.uuid4().hex[:8]}"
        organization_id = create_test_org(client, super_admin_token, name=org_name)

        # Create admin user in the organization (super admin can't create projects)
        admin_username = f"admin{uuid.uuid4().hex[:8]}"
        admin_user_id, admin_password = create_admin_user(
            client, super_admin_token, organization_id, username=admin_username
        )

        # Login as admin to get token
        login_response = client.post("/auth/login", json={"username": admin_username, "password": admin_password})
        admin_token = login_response.json()["access_token"]

        # Create SDK instances for different auth contexts
        base_sdk = APITestSDK(client)
        self.sdk = base_sdk.with_auth(super_admin_token)  # Super admin SDK for most operations
        self.admin_sdk = base_sdk.with_auth(admin_token)  # Admin SDK for projects

        # Initialize state tracker (manages all shadow state)
        # All rules access state via self.state
        self.state = StateTracker(organization_id, admin_user_id)


# Test function that pytest will discover
def test_system_api_state_machine(client: TestClient, super_admin_token: str) -> None:
    """Run the unified System API state machine test."""
    # Run state machine - each Hypothesis example creates its own org/admin in __init__
    run_state_machine_as_test(lambda: SystemAPIStateMachine(client, super_admin_token))


def test_system_api_state_machine(client: TestClient, super_admin_token: str) -> None:
    """Run the unified System API state machine test."""
    run_state_machine_as_test(lambda: SystemAPIStateMachine(client, super_admin_token))
