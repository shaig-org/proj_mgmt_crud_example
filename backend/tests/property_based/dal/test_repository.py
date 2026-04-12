"""Unified stateful property-based tests for the repository layer.

This tests the repository layer directly via Repository methods, without HTTP/API overhead.
It uses a mixin architecture to compose rules from multiple focused modules.

Location: tests/property_based/dal/ - DAL-level (repository) tests
Counterpart: tests/property_based/api/ - API-level (system) tests

Architecture:
- Bundles: Central registry (bundles.py)
- State tracking: StateTracker (state_tracker.py) - manages shadow state
- User rules: UserRulesMixin (user_rules.py) - 6 user repository operations

Invariants Tested:
- CRUD operations: Created entities are retrievable, updates persist
- Deletion: Deleted entities return None, not retrievable
- Data consistency: Retrieved data matches shadow state
- Immutability: Fields like username, organization_id never change
- Query methods: get_by_username, etc. return correct results

This comprehensive test suite verifies the repository layer maintains consistency
across all operations.
"""

from hypothesis.stateful import RuleBasedStateMachine, run_state_machine_as_test

from project_management_crud_example.dal.sqlite.repository import Repository
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import create_test_org_via_repo

from .bundles import Bundles
from .state_tracker import StateTracker
from .user_rules import UserRulesMixin


class RepositoryStateMachine(
    UserRulesMixin,  # All user repository operation rules
    RuleBasedStateMachine,
):
    """Comprehensive stateful property-based tests for the repository layer.

    This state machine composes rule mixins to test the repository as a whole.

    Organization:
    - State tracking: StateTracker (state_tracker.py)
    - Bundles: Central registry (bundles.py)
    - User rules: UserRulesMixin (user_rules.py)
    - TODO: Add organization, project, ticket rules as needed

    Currently focused on User repository operations. Can be extended with
    additional mixins for other entities (Organizations, Projects, Tickets).
    """

    # Bundle references from central registry
    users = Bundles.users
    organizations = Bundles.organizations
    projects = Bundles.projects
    tickets = Bundles.tickets

    def __init__(self, repo: Repository) -> None:
        import uuid

        super().__init__()

        self.repo = repo

        # Create initial organization for this test run
        org_name = f"Test Org {uuid.uuid4().hex[:8]}"
        org = create_test_org_via_repo(repo, name=org_name)

        # Initialize state tracker (manages all shadow state)
        # All rules access state via self.state
        self.state = StateTracker(org.id)


# Test function that pytest will discover
def test_repository_state_machine(test_repo: Repository) -> None:
    """Run the repository state machine test.

    This tests the entire repository layer as a unified system, verifying
    that all operations maintain consistent state.
    """
    run_state_machine_as_test(lambda: RepositoryStateMachine(test_repo))
