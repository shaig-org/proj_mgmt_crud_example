"""Capability layer: authorization-owning thin wrappers around the repository.

Route handlers depend on capability objects instead of directly on `Repository`.
Each capability encapsulates which sub-repo it uses, which user is acting, and
what 403-level authorization rules apply. Capabilities raise
`CapabilityPermissionError` on deny; the FastAPI exception handler converts that
to HTTP 403 with the standard `{"detail": ...}` envelope.

See docs/tasks/capability-di/plan.md for the design.
"""

from project_management_crud_example.capabilities.activity_logs_capability import ActivityLogReadCapability
from project_management_crud_example.capabilities.comments_capability import CommentCapability
from project_management_crud_example.capabilities.epics_capability import EpicReadCapability, EpicWriteCapability
from project_management_crud_example.capabilities.errors import CapabilityPermissionError
from project_management_crud_example.capabilities.organizations_capability import OrganizationCapability
from project_management_crud_example.capabilities.projects_capability import (
    ProjectReadCapability,
    ProjectWriteCapability,
)
from project_management_crud_example.capabilities.tickets_capability import (
    TicketReadCapability,
    TicketWriteCapability,
)
from project_management_crud_example.capabilities.users_capability import UserReadCapability, UserWriteCapability
from project_management_crud_example.capabilities.workflows_capability import (
    WorkflowReadCapability,
    WorkflowWriteCapability,
)

__all__ = [
    "ActivityLogReadCapability",
    "CapabilityPermissionError",
    "CommentCapability",
    "EpicReadCapability",
    "EpicWriteCapability",
    "OrganizationCapability",
    "ProjectReadCapability",
    "ProjectWriteCapability",
    "TicketReadCapability",
    "TicketWriteCapability",
    "UserReadCapability",
    "UserWriteCapability",
    "WorkflowReadCapability",
    "WorkflowWriteCapability",
]
