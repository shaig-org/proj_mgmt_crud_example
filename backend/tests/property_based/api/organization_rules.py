"""Organization operation rules for the system API state machine.

This mixin provides all property-based test rules for organization-related API operations.
Each rule tests a specific API operation and verifies invariants are maintained.
"""

from typing import TYPE_CHECKING

from hypothesis.stateful import rule

from .bundles import Bundles

if TYPE_CHECKING:
    from tests.sdk.test_sdk import APITestSDK

    from .state_tracker import StateTracker


class OrganizationRulesMixin:
    """Mixin providing organization-related PBT rules.

    This mixin expects the parent class to have:
    - self.state: StateTracker instance for shadow state
    - self.sdk: APITestSDK instance with super admin auth

    Bundle references use Bundles.organizations, Bundles.users from bundles.py.
    """

    # Type hints for mixin - these are provided by the parent class
    sdk: "APITestSDK"
    state: "StateTracker"

    @rule(target=Bundles.organizations)
    def create_additional_organization(self) -> str:
        """Create an additional organization for multi-org testing."""
        import uuid

        org_name = f"Test Org {uuid.uuid4().hex[:8]}"

        # Create organization via SDK
        org = self.sdk.organizations.create(org_name).assert_ok()
        org_id = org.id

        # Track the new organization
        self.state.created_org_ids.add(org_id)

        return org_id

    @rule(target=Bundles.users, org_id=Bundles.organizations)
    def create_user_in_specific_org(self, org_id: str) -> str:
        """Create a new user in a specific organization."""
        import uuid

        # Generate unique username and email
        username = f"apiuser{uuid.uuid4().hex[:10]}"
        email = f"{username}@example.com"
        full_name = f"API User {username}"

        # Create user in specified organization via SDK
        create_response = self.sdk.users.create(org_id, username, email, full_name, role="read_access").assert_ok()
        user_id = create_response.user.id
        user_obj = create_response.user

        # Track in shadow state using StateTracker methods
        self.state.track_user(user_id, user_obj.model_dump())
        self.state.track_user_email(org_id, email)

        # Invariant: organization_id matches what we sent
        assert user_obj.organization_id == org_id, f"User should be in org {org_id}"

        return user_id
