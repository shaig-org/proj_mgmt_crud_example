"""Project operation rules for the system API state machine.

This mixin provides all property-based test rules for project-related API operations.
Each rule tests a specific API operation and verifies invariants are maintained.
"""

from typing import TYPE_CHECKING

from hypothesis.stateful import rule

from .bundles import Bundles

if TYPE_CHECKING:
    from tests.sdk.test_sdk import APITestSDK

    from .state_tracker import StateTracker


class ProjectRulesMixin:
    """Mixin providing project-related PBT rules.

    This mixin expects the parent class to have:
    - self.state: StateTracker instance for shadow state
    - self.sdk: APITestSDK instance with super admin auth
    - self.admin_sdk: APITestSDK instance with admin auth (projects require admin role)

    Bundle references use Bundles.projects from bundles.py.
    """

    # Type hints for mixin - these are provided by the parent class
    sdk: "APITestSDK"
    admin_sdk: "APITestSDK"
    state: "StateTracker"

    @rule(target=Bundles.projects)
    def create_project_via_api(self) -> str:
        """Create a new project via API and add to bundle."""
        import uuid

        project_name = f"Project {uuid.uuid4().hex[:8]}"

        # Create project via SDK (using admin SDK, not super admin)
        project = self.admin_sdk.projects.create(project_name).assert_ok()
        project_id = project.id

        # Track project
        self.state.created_project_ids.add(project_id)

        # Get workflow statuses for this project
        workflow_id = project.workflow_id
        if workflow_id:
            workflow_result = self.sdk.workflows.get(workflow_id)
            if workflow_result.ok and workflow_result.data is not None:
                workflow = workflow_result.data
                self.state.project_statuses[project_id] = workflow.statuses
            else:
                # Default statuses
                self.state.project_statuses[project_id] = ["TODO", "IN_PROGRESS", "DONE"]
        else:
            self.state.project_statuses[project_id] = ["TODO", "IN_PROGRESS", "DONE"]

        return project_id
