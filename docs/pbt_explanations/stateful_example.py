"""
Concrete examples of stateful testing with multiple invariant patterns.

This file demonstrates practical stateful testing for the project management
system with detailed comments explaining each invariant pattern.

NOTE: To run these tests, first install hypothesis:
    uv add --dev hypothesis

Then run:
    pytest tests/stateful_example.py -v

IMPORTANT: These examples use `from tests.conftest import get_test_repository`
which is a helper function. In actual implementation, you'd use pytest fixtures.
"""

from hypothesis import note
from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    invariant,
    precondition,
    rule,
)
from hypothesis.strategies import SearchStrategy, sampled_from, text

from project_management_crud_example.domain_models import (
    EpicCreateCommand,
    EpicData,
    OrganizationCreateCommand,
    OrganizationData,
    ProjectCreateCommand,
    ProjectData,
    TicketCreateCommand,
    TicketData,
    TicketPriority,
    UserCreateCommand,
    UserData,
    UserRole,
    UserUpdateCommand,
)

# Custom strategies
USERNAME_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"


def usernames() -> SearchStrategy[str]:
    """Generate valid usernames."""
    return text(min_size=3, max_size=20, alphabet=USERNAME_CHARS)


def names() -> SearchStrategy[str]:
    """Generate general names."""
    return text(
        min_size=1,
        max_size=50,
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ",
    )


# =============================================================================
# Example 1: User CRUD with Shadow State Pattern
# =============================================================================


class UserCRUDStateMachine(RuleBasedStateMachine):
    """
    Tests User CRUD operations with shadow state tracking.

    Invariants tested:
    1. Active users in shadow state exist in repository
    2. Deleted users are not retrievable
    3. User counts match expectations
    4. All users have valid IDs and required fields
    """

    def __init__(self):
        super().__init__()
        # Get test repository (in real tests, this comes from fixture)
        from tests.conftest import get_test_repository

        self.repo = get_test_repository()

        # Create organization for users
        org_data = OrganizationData(name="Test Org")
        self.org = self.repo.organizations.create(
            OrganizationCreateCommand(organization_data=org_data)
        )

        # PATTERN 1: Shadow State - track what SHOULD exist
        self.active_users: dict[
            str, tuple[str, UserData]
        ] = {}  # username -> (id, original_data)
        self.deleted_usernames: set[str] = set()

        # PATTERN 2: Count Invariants - track totals
        self.total_created = 0
        self.total_deleted = 0
        self.total_updates = 0

    @rule(username=usernames())
    def create_user(self, username: str):
        """Create a new user."""
        # Skip if username already used
        if username in self.active_users or username in self.deleted_usernames:
            return

        note(f"Creating user: {username}")

        user_data = UserData(
            username=username,
            email=f"{username}@test.com",
            full_name=f"User {username}",
        )

        user = self.repo.users.create(
            UserCreateCommand(
                user_data=user_data,
                password="Pass123!",
                organization_id=self.org.id,
                role=UserRole.ADMIN,
            )
        )

        # Update shadow state
        self.active_users[username] = (user.id, user_data)
        self.total_created += 1

        note(f"Created user ID: {user.id}")

    @rule()
    @precondition(lambda self: len(self.active_users) > 0)
    def update_user_email(self):
        """Update a user's email."""
        username = list(self.active_users.keys())[0]
        user_id, original_data = self.active_users[username]

        note(f"Updating user: {username}")

        new_email = f"updated_{username}@test.com"
        self.repo.users.update(user_id, UserUpdateCommand(email=new_email))

        # Update shadow state
        updated_data = UserData(
            username=username, email=new_email, full_name=original_data.full_name
        )
        self.active_users[username] = (user_id, updated_data)
        self.total_updates += 1

    @rule()
    @precondition(lambda self: len(self.active_users) > 0)
    def delete_user(self):
        """Delete a user."""
        username = list(self.active_users.keys())[0]
        user_id, _ = self.active_users[username]

        note(f"Deleting user: {username}")

        self.repo.users.delete(user_id)

        # Update shadow state
        del self.active_users[username]
        self.deleted_usernames.add(username)
        self.total_deleted += 1

    @rule()
    @precondition(lambda self: len(self.active_users) > 0)
    def get_user_by_id(self):
        """Retrieve a user by ID."""
        username = list(self.active_users.keys())[0]
        user_id, _ = self.active_users[username]

        note(f"Getting user: {username}")

        user = self.repo.users.get_by_id(user_id)
        assert user is not None, f"Active user {username} should be retrievable"
        assert user.username == username

    # =========================================================================
    # INVARIANTS - Checked after EVERY operation
    # =========================================================================

    @invariant()
    def active_users_exist(self):
        """PATTERN 1: Shadow State - All active users should exist in repository."""
        for username, (user_id, user_data) in self.active_users.items():
            user = self.repo.users.get_by_id(user_id)
            assert user is not None, (
                f"Active user '{username}' (ID: {user_id}) should exist but returned None"
            )
            assert user.username == username, (
                f"Username mismatch: expected '{username}', got '{user.username}'"
            )
            assert user.email == user_data.email, (
                f"Email mismatch for user '{username}'"
            )

    @invariant()
    def deleted_users_gone(self):
        """PATTERN 1: Shadow State - Deleted users should not be retrievable."""
        for username in self.deleted_usernames:
            user = self.repo.users.get_by_username(username)
            assert user is None, (
                f"Deleted user '{username}' should return None but was found"
            )

    @invariant()
    def user_count_matches(self):
        """PATTERN 2: Count Invariants - Total created - deleted should equal active users."""
        expected_active = self.total_created - self.total_deleted
        actual_active = len(self.active_users)

        assert actual_active == expected_active, (
            f"User count mismatch: expected {expected_active} active users "
            f"(created: {self.total_created}, deleted: {self.total_deleted}), "
            f"but shadow state has {actual_active}"
        )

        # Also verify repository count
        all_users_in_org = [
            u for u in self.repo.users.get_all() if u.organization_id == self.org.id
        ]
        repo_count = len(all_users_in_org)
        assert repo_count == expected_active, (
            f"Repository has {repo_count} users but should have {expected_active} "
            f"(created: {self.total_created}, deleted: {self.total_deleted})"
        )

    @invariant()
    def all_users_have_valid_ids(self):
        """All users should have non-empty IDs."""
        for username, (user_id, _) in self.active_users.items():
            assert user_id, f"User '{username}' has empty ID"
            assert isinstance(user_id, str), (
                f"User '{username}' ID is not a string: {type(user_id)}"
            )
            assert len(user_id) > 0, f"User '{username}' has zero-length ID"


# Convert to pytest test case
TestUserCRUD = UserCRUDStateMachine.TestCase


# =============================================================================
# Example 2: Project State Machine with Archive/Unarchive
# =============================================================================


class ProjectLifecycleStateMachine(RuleBasedStateMachine):
    """
    Tests Project lifecycle with archive/unarchive operations.

    Invariants tested:
    1. Count invariants (total = active + archived)
    2. Archive flag consistency
    3. Active projects never have is_archived=True
    """

    def __init__(self):
        super().__init__()
        from tests.conftest import get_test_repository

        self.repo = get_test_repository()

        # Setup
        org_data = OrganizationData(name="Test Org")
        self.org = self.repo.organizations.create(
            OrganizationCreateCommand(organization_data=org_data)
        )
        self.workflow = self.repo.workflows.create_default_workflow()

        # PATTERN 2: Count Invariants
        self.total_created = 0
        self.total_deleted = 0
        self.active_count = 0
        self.archived_count = 0

        # Track projects by state
        self.active_projects: dict[str, str] = {}  # name -> id
        self.archived_projects: dict[str, str] = {}  # name -> id

    @rule(name=names())
    def create_project(self, name: str):
        """Create a new project."""
        # Skip if name already used
        if name in self.active_projects or name in self.archived_projects:
            return

        note(f"Creating project: {name}")

        project_data = ProjectData(name=name, description=f"Description for {name}")
        project = self.repo.projects.create(
            ProjectCreateCommand(
                project_data=project_data,
                organization_id=self.org.id,
                workflow_id=self.workflow.id,
            )
        )

        self.active_projects[name] = project.id
        self.total_created += 1
        self.active_count += 1

    @rule()
    @precondition(lambda self: len(self.active_projects) > 0)
    def archive_project(self):
        """Archive an active project."""
        name = list(self.active_projects.keys())[0]
        project_id = self.active_projects[name]

        note(f"Archiving project: {name}")

        self.repo.projects.archive(project_id)

        # Move from active to archived
        del self.active_projects[name]
        self.archived_projects[name] = project_id
        self.active_count -= 1
        self.archived_count += 1

    @rule()
    @precondition(lambda self: len(self.archived_projects) > 0)
    def unarchive_project(self):
        """Unarchive an archived project."""
        name = list(self.archived_projects.keys())[0]
        project_id = self.archived_projects[name]

        note(f"Unarchiving project: {name}")

        self.repo.projects.unarchive(project_id)

        # Move from archived to active
        del self.archived_projects[name]
        self.active_projects[name] = project_id
        self.active_count += 1
        self.archived_count -= 1

    @rule()
    @precondition(lambda self: len(self.active_projects) > 0)
    def delete_project(self):
        """Delete an active project."""
        name = list(self.active_projects.keys())[0]
        project_id = self.active_projects[name]

        note(f"Deleting project: {name}")

        self.repo.projects.delete(project_id)

        del self.active_projects[name]
        self.active_count -= 1
        self.total_deleted += 1

    @invariant()
    def count_consistency(self):
        """PATTERN 2: Count Invariants - Verify all counts match."""
        # Total - deleted = active + archived
        expected_total = self.total_created - self.total_deleted
        expected_sum = self.active_count + self.archived_count

        assert expected_sum == expected_total, (
            f"Count mismatch: active ({self.active_count}) + archived ({self.archived_count}) "
            f"= {expected_sum}, but should equal created ({self.total_created}) - "
            f"deleted ({self.total_deleted}) = {expected_total}"
        )

        # Verify repository matches
        all_projects = self.repo.projects.get_all(include_archived=True)
        all_in_org = [p for p in all_projects if p.organization_id == self.org.id]

        assert len(all_in_org) == expected_total, (
            f"Repository has {len(all_in_org)} projects but should have {expected_total}"
        )

    @invariant()
    def archived_flag_consistency(self):
        """PATTERN 3: Archive flag matches actual state."""
        # All active projects should have is_archived=False
        for name, project_id in self.active_projects.items():
            project = self.repo.projects.get_by_id(project_id)
            assert project is not None, f"Active project '{name}' not found"
            assert project.is_archived is False, (
                f"Active project '{name}' has is_archived=True"
            )

        # All archived projects should have is_archived=True
        for name, project_id in self.archived_projects.items():
            project = self.repo.projects.get_by_id(project_id)
            assert project is not None, f"Archived project '{name}' not found"
            assert project.is_archived is True, (
                f"Archived project '{name}' has is_archived=False"
            )

    @invariant()
    def active_list_excludes_archived(self):
        """PATTERN 3: get_all(include_archived=False) should not return archived projects."""
        active_list = self.repo.projects.get_all(include_archived=False)
        active_list_in_org = [
            p for p in active_list if p.organization_id == self.org.id
        ]

        # Count should match
        assert len(active_list_in_org) == self.active_count, (
            f"Active list has {len(active_list_in_org)} projects but should have {self.active_count}"
        )

        # None should be archived
        for project in active_list_in_org:
            assert project.is_archived is False, (
                f"Active list contains archived project {project.id}"
            )


TestProjectLifecycle = ProjectLifecycleStateMachine.TestCase


# =============================================================================
# Example 3: Epic-Ticket Relationships with Bundles
# =============================================================================


class EpicTicketStateMachine(RuleBasedStateMachine):
    """
    Tests Epic-Ticket relationships using Bundles.

    Invariants tested:
    1. Epic ticket counts match actual tickets
    2. Tickets appear in at most one epic
    3. Relationship invariants (all ticket IDs reference real tickets)
    """

    def __init__(self):
        super().__init__()
        from tests.conftest import get_test_repository

        self.repo = get_test_repository()

        # Setup
        org_data = OrganizationData(name="Test Org")
        self.org = self.repo.organizations.create(
            OrganizationCreateCommand(organization_data=org_data)
        )
        self.workflow = self.repo.workflows.create_default_workflow()

        project_data = ProjectData(name="Test Project")
        self.project = self.repo.projects.create(
            ProjectCreateCommand(
                project_data=project_data,
                organization_id=self.org.id,
                workflow_id=self.workflow.id,
            )
        )

        user_data = UserData(
            username="reporter", email="reporter@test.com", full_name="Reporter"
        )
        self.reporter = self.repo.users.create(
            UserCreateCommand(
                user_data=user_data,
                password="Pass123!",
                organization_id=self.org.id,
                role=UserRole.ADMIN,
            )
        )

        # PATTERN 5: Aggregate Consistency - track epic-ticket relationships
        self.epic_tickets: dict[str, set[str]] = {}  # epic_id -> {ticket_ids}
        self.ticket_epic: dict[str, str | None] = {}  # ticket_id -> epic_id (or None)

    # Use Bundles to manage created entities
    epics = Bundle("epics")
    tickets = Bundle("tickets")

    @rule(target=epics, name=names())
    def create_epic(self, name: str):
        """Create an epic and add to epics bundle."""
        note(f"Creating epic: {name}")

        epic_data = EpicData(name=name, description=f"Epic: {name}")
        epic = self.repo.epics.create(
            EpicCreateCommand(epic_data=epic_data, organization_id=self.org.id)
        )

        # Initialize tracking
        self.epic_tickets[epic.id] = set()

        return epic.id  # Add to bundle

    @rule(target=tickets, title=names())
    def create_ticket(self, title: str):
        """Create a ticket and add to tickets bundle."""
        note(f"Creating ticket: {title}")

        ticket_data = TicketData(
            title=title,
            status=self.workflow.statuses[0],
            priority=TicketPriority.MEDIUM,
        )

        ticket = self.repo.tickets.create(
            TicketCreateCommand(
                ticket_data=ticket_data,
                project_id=self.project.id,
                reporter_id=self.reporter.id,
            )
        )

        # Initialize tracking
        self.ticket_epic[ticket.id] = None  # Not in any epic yet

        return ticket.id  # Add to bundle

    @rule(epic_id=epics, ticket_id=tickets)
    def add_ticket_to_epic(self, epic_id: str, ticket_id: str):
        """Add a ticket to an epic."""
        # Skip if ticket already in this epic
        if self.ticket_epic.get(ticket_id) == epic_id:
            return

        note(f"Adding ticket {ticket_id} to epic {epic_id}")

        # Remove from old epic if exists
        old_epic_id = self.ticket_epic.get(ticket_id)
        if old_epic_id and old_epic_id in self.epic_tickets:
            self.epic_tickets[old_epic_id].discard(ticket_id)

        # Add to new epic
        self.repo.epics.add_ticket(epic_id, ticket_id)

        # Update tracking
        if epic_id not in self.epic_tickets:
            self.epic_tickets[epic_id] = set()
        self.epic_tickets[epic_id].add(ticket_id)
        self.ticket_epic[ticket_id] = epic_id

    @rule(epic_id=epics, ticket_id=tickets)
    @precondition(
        lambda self: any(len(tickets) > 0 for tickets in self.epic_tickets.values())
    )
    def remove_ticket_from_epic(self, epic_id: str, ticket_id: str):
        """Remove a ticket from an epic."""
        # Skip if ticket not in this epic
        if self.ticket_epic.get(ticket_id) != epic_id:
            return

        # Skip if epic has no tickets
        if epic_id not in self.epic_tickets or not self.epic_tickets[epic_id]:
            return

        note(f"Removing ticket {ticket_id} from epic {epic_id}")

        self.repo.epics.remove_ticket(epic_id, ticket_id)

        # Update tracking
        self.epic_tickets[epic_id].discard(ticket_id)
        self.ticket_epic[ticket_id] = None

    @invariant()
    def epic_ticket_counts_match(self):
        """PATTERN 5: Epic ticket counts must match actual relationships."""
        for epic_id, shadow_tickets in self.epic_tickets.items():
            epic = self.repo.epics.get_by_id(epic_id)
            if epic is None:
                continue

            # Count should match
            assert len(epic.ticket_ids) == len(shadow_tickets), (
                f"Epic {epic_id}: expected {len(shadow_tickets)} tickets, "
                f"got {len(epic.ticket_ids)}"
            )

            # IDs should match exactly
            assert set(epic.ticket_ids) == shadow_tickets, (
                f"Epic {epic_id}: ticket ID mismatch. "
                f"Expected {shadow_tickets}, got {set(epic.ticket_ids)}"
            )

    @invariant()
    def tickets_in_at_most_one_epic(self):
        """Each ticket should appear in at most one epic."""
        all_epic_tickets: dict[str, str] = {}  # ticket_id -> epic_id

        for epic_id, ticket_ids in self.epic_tickets.items():
            for ticket_id in ticket_ids:
                assert ticket_id not in all_epic_tickets, (
                    f"Ticket {ticket_id} appears in both epic "
                    f"{all_epic_tickets[ticket_id]} and {epic_id}"
                )
                all_epic_tickets[ticket_id] = epic_id

    @invariant()
    def epic_tickets_reference_real_tickets(self):
        """PATTERN 3: All ticket IDs in epics must reference existing tickets."""
        for epic_id in self.epic_tickets:
            epic = self.repo.epics.get_by_id(epic_id)
            if epic is None:
                continue

            for ticket_id in epic.ticket_ids:
                ticket = self.repo.tickets.get_by_id(ticket_id)
                assert ticket is not None, (
                    f"Epic {epic_id} references non-existent ticket {ticket_id}"
                )


TestEpicTicketRelationships = EpicTicketStateMachine.TestCase


# =============================================================================
# Example 4: Multi-Organization Permission Boundaries
# =============================================================================


class OrganizationBoundariesStateMachine(RuleBasedStateMachine):
    """
    Tests organization boundaries and permission invariants.

    Invariants tested:
    1. Users only see projects in their organization
    2. Each user belongs to exactly one organization
    3. Cross-org data access is impossible
    """

    def __init__(self):
        super().__init__()
        from tests.conftest import get_test_repository

        self.repo = get_test_repository()

        # Create two separate organizations
        org1_data = OrganizationData(name="Organization 1")
        self.org1 = self.repo.organizations.create(
            OrganizationCreateCommand(organization_data=org1_data)
        )

        org2_data = OrganizationData(name="Organization 2")
        self.org2 = self.repo.organizations.create(
            OrganizationCreateCommand(organization_data=org2_data)
        )

        # Create workflows
        self.workflow1 = self.repo.workflows.create_default_workflow()

        # PATTERN 7: Permission Invariants - track by organization
        self.users_by_org: dict[str, list[str]] = {self.org1.id: [], self.org2.id: []}

        self.projects_by_org: dict[str, list[str]] = {
            self.org1.id: [],
            self.org2.id: [],
        }

    @rule(username=usernames(), org_num=sampled_from([1, 2]))
    def create_user_in_org(self, username: str, org_num: int):
        """Create a user in a specific organization."""
        org_id = self.org1.id if org_num == 1 else self.org2.id

        # Skip if username already exists
        if any(
            username in self.repo.users.get_by_username(username)
            for _ in [1]
            if self.repo.users.get_by_username(username)
        ):
            return

        note(f"Creating user {username} in org {org_num}")

        user_data = UserData(
            username=username, email=f"{username}@test.com", full_name=username
        )
        user = self.repo.users.create(
            UserCreateCommand(
                user_data=user_data,
                password="Pass123!",
                organization_id=org_id,
                role=UserRole.ADMIN,
            )
        )

        self.users_by_org[org_id].append(user.id)

    @rule(name=names(), org_num=sampled_from([1, 2]))
    def create_project_in_org(self, name: str, org_num: int):
        """Create a project in a specific organization."""
        org_id = self.org1.id if org_num == 1 else self.org2.id

        note(f"Creating project {name} in org {org_num}")

        project_data = ProjectData(name=name)
        project = self.repo.projects.create(
            ProjectCreateCommand(
                project_data=project_data,
                organization_id=org_id,
                workflow_id=self.workflow1.id,
            )
        )

        self.projects_by_org[org_id].append(project.id)

    @invariant()
    def users_belong_to_one_org(self):
        """PATTERN 7: Each user belongs to exactly one organization."""
        all_user_ids: set[str] = set()

        for org_id, user_ids in self.users_by_org.items():
            for user_id in user_ids:
                # No duplicates across orgs
                assert user_id not in all_user_ids, (
                    f"User {user_id} appears in multiple organizations"
                )
                all_user_ids.add(user_id)

                # Verify user's org_id matches
                user = self.repo.users.get_by_id(user_id)
                assert user is not None, f"User {user_id} should exist"
                assert user.organization_id == org_id, (
                    f"User {user_id} tracked in org {org_id} but "
                    f"database says {user.organization_id}"
                )

    @invariant()
    def projects_belong_to_correct_org(self):
        """PATTERN 7: Each project belongs to correct organization."""
        for org_id, project_ids in self.projects_by_org.items():
            for project_id in project_ids:
                project = self.repo.projects.get_by_id(project_id)
                assert project is not None, f"Project {project_id} should exist"
                assert project.organization_id == org_id, (
                    f"Project {project_id} tracked in org {org_id} but "
                    f"database says {project.organization_id}"
                )

    @invariant()
    def no_cross_org_data_visibility(self):
        """PATTERN 7: Projects from one org should not be visible to users in another org."""
        # Get all projects for each org
        all_projects = self.repo.projects.get_all()

        org1_projects = [p for p in all_projects if p.organization_id == self.org1.id]
        org2_projects = [p for p in all_projects if p.organization_id == self.org2.id]

        # Verify separation
        org1_project_ids = set(p.id for p in org1_projects)
        org2_project_ids = set(p.id for p in org2_projects)

        # No overlap
        overlap = org1_project_ids & org2_project_ids
        assert len(overlap) == 0, f"Projects appear in both orgs: {overlap}"


TestOrganizationBoundaries = OrganizationBoundariesStateMachine.TestCase
