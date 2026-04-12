# Stateful Testing with Hypothesis: Comprehensive Guide

## Overview

Stateful testing uses **state machines** to test complex sequences of operations. Instead of testing one operation in isolation, it tests **hundreds of random operation sequences** to find bugs that only appear when operations interact in specific ways.

**Key Concept**: Maintain a "shadow state" (your model of what should be true) and verify the real system matches after every operation.

---

## Anatomy of a State Machine

```python
class MyStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        # 1. SETUP: Initialize real system and shadow state
        self.repo = get_test_repository()
        self.shadow_state = {}  # Your model of reality

    @rule(...)
    def operation(self, ...):
        # 2. PERFORM: Execute operation on real system
        result = self.repo.some_operation(...)
        # 3. UPDATE: Update shadow state to match
        self.shadow_state[...] = result

    @invariant()
    def check_something(self):
        # 4. VERIFY: Check real system matches shadow state
        assert real_system_state == self.shadow_state
```

**Hypothesis does this automatically:**
1. Creates instance
2. Randomly picks operations (rules) to execute
3. Runs invariants after each operation
4. Repeats 100s of times with different sequences
5. Shrinks failing sequences to minimal reproducible case

---

## Core Invariant Patterns

### Pattern 1: Shadow State Consistency

**Concept**: Maintain a Python data structure mirroring what should exist in the repository.

**When to use**: All CRUD operations.

```python
class UserStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.repo = get_test_repository()
        self.org = create_test_org_via_repo(self.repo)

        # Shadow state: track what SHOULD exist
        self.active_users: dict[str, tuple[str, UserData]] = {}  # username -> (id, data)
        self.deleted_users: set[str] = set()  # usernames of deleted users

    @rule(username=usernames(), email=emails())
    def create_user(self, username: str, email: str):
        assume(username not in self.active_users)
        assume(username not in self.deleted_users)

        user_data = UserData(username=username, email=email, full_name=username)
        user = self.repo.users.create(UserCreateCommand(
            user_data=user_data,
            password="Pass123!",
            organization_id=self.org.id,
            role=UserRole.ADMIN
        ))

        # Update shadow state
        self.active_users[username] = (user.id, user_data)

    @rule()
    @precondition(lambda self: len(self.active_users) > 0)
    def delete_user(self):
        username = list(self.active_users.keys())[0]
        user_id, _ = self.active_users[username]

        self.repo.users.delete(user_id)

        # Update shadow state
        del self.active_users[username]
        self.deleted_users.add(username)

    @invariant()
    def active_users_match(self):
        """Active users in shadow state should exist in repository."""
        for username, (user_id, user_data) in self.active_users.items():
            user = self.repo.users.get_by_id(user_id)
            assert user is not None, f"Active user {username} should exist"
            assert user.username == username
            assert user.email == user_data.email

    @invariant()
    def deleted_users_gone(self):
        """Deleted users should not be retrievable."""
        for username in self.deleted_users:
            user = self.repo.users.get_by_username(username)
            assert user is None, f"Deleted user {username} should not exist"
```

**What bugs this finds:**
- User deleted but still retrievable (soft delete bug)
- User created but get returns None (transaction bug)
- User update changes another user's data (ID collision)

---

### Pattern 2: Count Invariants

**Concept**: Track counts and verify they match reality.

**When to use**: Operations that add/remove entities, filtering.

```python
class ProjectStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.repo = get_test_repository()
        self.org, self.workflow = create_test_org_with_workflow_via_repo(self.repo)

        # Track counts
        self.total_created = 0
        self.total_deleted = 0
        self.archived_count = 0
        self.active_count = 0

    @rule(name=st.text(min_size=1, max_size=255))
    def create_project(self, name: str):
        project_data = ProjectData(name=name)
        project = self.repo.projects.create(ProjectCreateCommand(
            project_data=project_data,
            organization_id=self.org.id,
            workflow_id=self.workflow.id
        ))

        self.total_created += 1
        self.active_count += 1

    @rule()
    @precondition(lambda self: self.active_count > 0)
    def archive_project(self):
        # Get first active project
        all_projects = self.repo.projects.get_all(include_archived=False)
        if all_projects:
            project = all_projects[0]
            self.repo.projects.archive(project.id)
            self.active_count -= 1
            self.archived_count += 1

    @rule()
    @precondition(lambda self: self.archived_count > 0)
    def unarchive_project(self):
        # Get first archived project
        all_projects = self.repo.projects.get_all(include_archived=True)
        archived = [p for p in all_projects if p.is_archived]
        if archived:
            project = archived[0]
            self.repo.projects.unarchive(project.id)
            self.active_count += 1
            self.archived_count -= 1

    @rule()
    @precondition(lambda self: self.active_count > 0)
    def delete_project(self):
        all_projects = self.repo.projects.get_all(include_archived=False)
        if all_projects:
            project = all_projects[0]
            self.repo.projects.delete(project.id)
            self.active_count -= 1
            self.total_deleted += 1

    @invariant()
    def count_consistency(self):
        """Verify counts match repository state."""
        all_projects = self.repo.projects.get_all(include_archived=True)
        active_projects = self.repo.projects.get_all(include_archived=False)

        # Total - deleted = active + archived
        expected_total = self.total_created - self.total_deleted
        assert len(all_projects) == expected_total, \
            f"Expected {expected_total} total projects, got {len(all_projects)}"

        # Active count should match
        assert len(active_projects) == self.active_count, \
            f"Expected {self.active_count} active projects, got {len(active_projects)}"

        # Archived count should match
        archived_actual = [p for p in all_projects if p.is_archived]
        assert len(archived_actual) == self.archived_count, \
            f"Expected {self.archived_count} archived projects, got {len(archived_actual)}"

    @invariant()
    def active_projects_not_archived(self):
        """Active projects should never have is_archived=True."""
        active_projects = self.repo.projects.get_all(include_archived=False)
        for project in active_projects:
            assert project.is_archived is False, \
                f"Project {project.id} in active list but marked archived"
```

**What bugs this finds:**
- Archive doesn't update flag (still appears in active list)
- Delete doesn't actually delete (count mismatch)
- Unarchive creates duplicate (count increases by 2)

---

### Pattern 3: Relationship Invariants

**Concept**: Verify foreign key relationships remain valid.

**When to use**: Entities with relationships (tickets → projects, users → organizations).

```python
class TicketStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.repo = get_test_repository()
        self.org, self.workflow = create_test_org_with_workflow_via_repo(self.repo)

        # Track entities
        self.projects: dict[str, str] = {}  # name -> id
        self.users: dict[str, str] = {}  # username -> id
        self.tickets: dict[str, dict] = {}  # ticket_id -> {project_id, reporter_id, assignee_id}

    @rule(name=st.text(min_size=1, max_size=255))
    def create_project(self, name: str):
        assume(name not in self.projects)
        project_data = ProjectData(name=name)
        project = self.repo.projects.create(ProjectCreateCommand(
            project_data=project_data,
            organization_id=self.org.id,
            workflow_id=self.workflow.id
        ))
        self.projects[name] = project.id

    @rule(username=usernames())
    def create_user(self, username: str):
        assume(username not in self.users)
        user_data = UserData(username=username, email=f"{username}@test.com", full_name=username)
        user = self.repo.users.create(UserCreateCommand(
            user_data=user_data,
            password="Pass123!",
            organization_id=self.org.id,
            role=UserRole.ADMIN
        ))
        self.users[username] = user.id

    @rule(title=st.text(min_size=1, max_size=255))
    @precondition(lambda self: len(self.projects) > 0 and len(self.users) > 0)
    def create_ticket(self, title: str):
        project_id = list(self.projects.values())[0]
        reporter_id = list(self.users.values())[0]

        ticket_data = TicketData(
            title=title,
            status=self.workflow.statuses[0],
            priority=TicketPriority.MEDIUM
        )
        ticket = self.repo.tickets.create(TicketCreateCommand(
            ticket_data=ticket_data,
            project_id=project_id,
            reporter_id=reporter_id
        ))

        self.tickets[ticket.id] = {
            "project_id": project_id,
            "reporter_id": reporter_id,
            "assignee_id": None
        }

    @rule()
    @precondition(lambda self: len(self.tickets) > 0 and len(self.users) > 1)
    def assign_ticket(self):
        ticket_id = list(self.tickets.keys())[0]
        assignee_id = list(self.users.values())[1]  # Different user

        self.repo.tickets.update_assignee(ticket_id, assignee_id)
        self.tickets[ticket_id]["assignee_id"] = assignee_id

    @rule()
    @precondition(lambda self: len(self.projects) > 1 and len(self.tickets) > 0)
    def move_ticket_to_different_project(self):
        ticket_id = list(self.tickets.keys())[0]
        new_project_id = list(self.projects.values())[1]  # Different project

        self.repo.tickets.update_project(ticket_id, new_project_id)
        self.tickets[ticket_id]["project_id"] = new_project_id

    @invariant()
    def all_tickets_have_valid_project(self):
        """Every ticket must reference an existing project."""
        for ticket_id, shadow_data in self.tickets.items():
            ticket = self.repo.tickets.get_by_id(ticket_id)
            assert ticket is not None, f"Ticket {ticket_id} should exist"

            # Project must exist
            project = self.repo.projects.get_by_id(shadow_data["project_id"])
            assert project is not None, \
                f"Ticket {ticket_id} references non-existent project {shadow_data['project_id']}"
            assert ticket.project_id == shadow_data["project_id"]

    @invariant()
    def all_tickets_have_valid_reporter(self):
        """Every ticket must reference an existing reporter."""
        for ticket_id, shadow_data in self.tickets.items():
            ticket = self.repo.tickets.get_by_id(ticket_id)

            # Reporter must exist
            reporter = self.repo.users.get_by_id(shadow_data["reporter_id"])
            assert reporter is not None, \
                f"Ticket {ticket_id} references non-existent reporter {shadow_data['reporter_id']}"
            assert ticket.reporter_id == shadow_data["reporter_id"]

    @invariant()
    def assigned_tickets_have_valid_assignee(self):
        """Assigned tickets must reference an existing assignee."""
        for ticket_id, shadow_data in self.tickets.items():
            if shadow_data["assignee_id"] is not None:
                ticket = self.repo.tickets.get_by_id(ticket_id)

                # Assignee must exist
                assignee = self.repo.users.get_by_id(shadow_data["assignee_id"])
                assert assignee is not None, \
                    f"Ticket {ticket_id} references non-existent assignee {shadow_data['assignee_id']}"
                assert ticket.assignee_id == shadow_data["assignee_id"]
```

**What bugs this finds:**
- Deleting project doesn't cascade to tickets (orphaned tickets)
- Assigning ticket to deleted user succeeds
- Moving ticket to non-existent project succeeds
- Foreign key constraints not enforced

---

### Pattern 4: Business Rule Invariants

**Concept**: Verify domain-specific business rules always hold.

**When to use**: Complex business logic (workflows, permissions, calculations).

```python
class WorkflowStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.repo = get_test_repository()
        self.org = create_test_org_via_repo(self.repo)

        # Track workflows and their tickets
        self.workflows: dict[str, list[str]] = {}  # workflow_id -> [statuses]
        self.projects: dict[str, str] = {}  # project_id -> workflow_id
        self.tickets: dict[str, tuple[str, str]] = {}  # ticket_id -> (project_id, current_status)

    @rule(name=st.text(min_size=1, max_size=255), statuses=workflow_statuses())
    def create_workflow(self, name: str, statuses: list[str]):
        workflow_data = WorkflowData(name=name, statuses=statuses)
        workflow = self.repo.workflows.create(WorkflowCreateCommand(workflow_data=workflow_data))
        self.workflows[workflow.id] = statuses

    @rule(name=st.text(min_size=1, max_size=255))
    @precondition(lambda self: len(self.workflows) > 0)
    def create_project_with_workflow(self, name: str):
        workflow_id = list(self.workflows.keys())[0]
        project_data = ProjectData(name=name)
        project = self.repo.projects.create(ProjectCreateCommand(
            project_data=project_data,
            organization_id=self.org.id,
            workflow_id=workflow_id
        ))
        self.projects[project.id] = workflow_id

    @rule(title=st.text(min_size=1, max_size=255))
    @precondition(lambda self: len(self.projects) > 0)
    def create_ticket_in_project(self, title: str):
        project_id = list(self.projects.keys())[0]
        workflow_id = self.projects[project_id]
        valid_statuses = self.workflows[workflow_id]

        # Create user for reporter
        user_data = UserData(username=f"user_{title[:10]}", email=f"{title[:10]}@test.com", full_name="User")
        user = self.repo.users.create(UserCreateCommand(
            user_data=user_data,
            password="Pass123!",
            organization_id=self.org.id,
            role=UserRole.ADMIN
        ))

        # Create ticket with first valid status
        initial_status = valid_statuses[0]
        ticket_data = TicketData(title=title, status=initial_status, priority=TicketPriority.MEDIUM)
        ticket = self.repo.tickets.create(TicketCreateCommand(
            ticket_data=ticket_data,
            project_id=project_id,
            reporter_id=user.id
        ))

        self.tickets[ticket.id] = (project_id, initial_status)

    @rule()
    @precondition(lambda self: len(self.tickets) > 0)
    def change_ticket_status(self):
        ticket_id = list(self.tickets.keys())[0]
        project_id, current_status = self.tickets[ticket_id]
        workflow_id = self.projects[project_id]
        valid_statuses = self.workflows[workflow_id]

        # Pick a different valid status
        if len(valid_statuses) > 1:
            new_status = valid_statuses[1] if current_status == valid_statuses[0] else valid_statuses[0]
            self.repo.tickets.update_status(ticket_id, new_status)
            self.tickets[ticket_id] = (project_id, new_status)

    @invariant()
    def ticket_status_always_valid_for_workflow(self):
        """Every ticket's status must be valid for its project's workflow."""
        for ticket_id, (project_id, expected_status) in self.tickets.items():
            ticket = self.repo.tickets.get_by_id(ticket_id)
            assert ticket is not None

            # Get project's workflow
            project = self.repo.projects.get_by_id(project_id)
            workflow_id = project.workflow_id
            valid_statuses = self.workflows[workflow_id]

            # Ticket status must be in workflow's valid statuses
            assert ticket.status in valid_statuses, \
                f"Ticket {ticket_id} has status '{ticket.status}' not in workflow {workflow_id} " \
                f"(valid: {valid_statuses})"

    @invariant()
    def workflow_statuses_have_no_duplicates(self):
        """Workflow statuses must always be unique."""
        for workflow_id, statuses in self.workflows.items():
            workflow = self.repo.workflows.get_by_id(workflow_id)
            assert len(workflow.statuses) == len(set(workflow.statuses)), \
                f"Workflow {workflow_id} has duplicate statuses: {workflow.statuses}"

    @invariant()
    def workflow_statuses_match_pattern(self):
        """All workflow statuses must match ^[A-Z0-9_-]+$ pattern."""
        for workflow_id in self.workflows:
            workflow = self.repo.workflows.get_by_id(workflow_id)
            for status in workflow.statuses:
                assert re.match(r"^[A-Z0-9_-]+$", status), \
                    f"Workflow {workflow_id} has invalid status: '{status}'"
```

**What bugs this finds:**
- Ticket status changes to invalid status (not in workflow)
- Workflow allows duplicate statuses
- Ticket moved to project with incompatible workflow
- Status validation skipped in certain code paths

---

### Pattern 5: Aggregate Consistency

**Concept**: Verify computed values match their components.

**When to use**: Aggregates (epic ticket counts), derived data (full_name from first + last).

```python
class EpicStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.repo = get_test_repository()
        self.org, self.workflow = create_test_org_with_workflow_via_repo(self.repo)
        self.project = create_test_project_via_repo(self.repo, self.org.id, "Test Project", workflow_id=self.workflow.id)
        self.reporter = create_test_user_via_repo(self.repo, self.org.id)

        # Track epics and their tickets
        self.epics: dict[str, set[str]] = {}  # epic_id -> {ticket_ids}
        self.tickets: dict[str, str | None] = {}  # ticket_id -> epic_id (or None)

    @rule(name=st.text(min_size=1, max_size=255))
    def create_epic(self, name: str):
        epic_data = EpicData(name=name)
        epic = self.repo.epics.create(EpicCreateCommand(
            epic_data=epic_data,
            organization_id=self.org.id
        ))
        self.epics[epic.id] = set()

    @rule(title=st.text(min_size=1, max_size=255))
    def create_ticket(self, title: str):
        ticket_data = TicketData(
            title=title,
            status=self.workflow.statuses[0],
            priority=TicketPriority.MEDIUM
        )
        ticket = self.repo.tickets.create(TicketCreateCommand(
            ticket_data=ticket_data,
            project_id=self.project.id,
            reporter_id=self.reporter.id
        ))
        self.tickets[ticket.id] = None  # Not in any epic yet

    @rule()
    @precondition(lambda self: len(self.epics) > 0 and len(self.tickets) > 0)
    def add_ticket_to_epic(self):
        epic_id = list(self.epics.keys())[0]
        # Find ticket not in this epic
        available_tickets = [tid for tid, eid in self.tickets.items() if eid != epic_id]
        if available_tickets:
            ticket_id = available_tickets[0]

            # Remove from old epic if exists
            old_epic_id = self.tickets[ticket_id]
            if old_epic_id:
                self.epics[old_epic_id].discard(ticket_id)

            # Add to new epic
            self.repo.epics.add_ticket(epic_id, ticket_id)
            self.epics[epic_id].add(ticket_id)
            self.tickets[ticket_id] = epic_id

    @rule()
    @precondition(lambda self: any(len(tickets) > 0 for tickets in self.epics.values()))
    def remove_ticket_from_epic(self):
        # Find epic with tickets
        epic_with_tickets = [(eid, tickets) for eid, tickets in self.epics.items() if tickets]
        if epic_with_tickets:
            epic_id, tickets = epic_with_tickets[0]
            ticket_id = list(tickets)[0]

            self.repo.epics.remove_ticket(epic_id, ticket_id)
            self.epics[epic_id].discard(ticket_id)
            self.tickets[ticket_id] = None

    @invariant()
    def epic_ticket_counts_match(self):
        """Epic ticket counts must match actual ticket list."""
        for epic_id, shadow_tickets in self.epics.items():
            epic = self.repo.epics.get_by_id(epic_id)
            assert epic is not None

            # Count should match
            assert len(epic.ticket_ids) == len(shadow_tickets), \
                f"Epic {epic_id}: expected {len(shadow_tickets)} tickets, got {len(epic.ticket_ids)}"

            # Ticket IDs should match exactly
            assert set(epic.ticket_ids) == shadow_tickets, \
                f"Epic {epic_id}: ticket ID mismatch. Expected {shadow_tickets}, got {set(epic.ticket_ids)}"

    @invariant()
    def tickets_in_at_most_one_epic(self):
        """Each ticket should appear in at most one epic."""
        all_epic_tickets = {}  # ticket_id -> epic_id

        for epic_id, ticket_ids in self.epics.items():
            for ticket_id in ticket_ids:
                assert ticket_id not in all_epic_tickets, \
                    f"Ticket {ticket_id} appears in both epic {all_epic_tickets[ticket_id]} and {epic_id}"
                all_epic_tickets[ticket_id] = epic_id

    @invariant()
    def shadow_state_matches_reality(self):
        """Shadow state of ticket->epic mapping should match repository."""
        for ticket_id, shadow_epic_id in self.tickets.items():
            # Find which epic (if any) actually contains this ticket
            actual_epic_id = None
            for epic_id in self.epics:
                epic = self.repo.epics.get_by_id(epic_id)
                if ticket_id in epic.ticket_ids:
                    assert actual_epic_id is None, \
                        f"Ticket {ticket_id} found in multiple epics: {actual_epic_id} and {epic_id}"
                    actual_epic_id = epic_id

            assert actual_epic_id == shadow_epic_id, \
                f"Ticket {ticket_id}: shadow says epic {shadow_epic_id}, reality is {actual_epic_id}"
```

**What bugs this finds:**
- Epic ticket count doesn't update when ticket added/removed
- Ticket appears in multiple epics simultaneously
- Remove ticket doesn't actually remove it
- Add ticket doesn't update epic's ticket list

---

### Pattern 6: Temporal Consistency

**Concept**: Verify timestamps and time-based properties are correct.

**When to use**: Created/updated timestamps, audit logs, ordering.

```python
class TimestampStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.repo = get_test_repository()
        self.org = create_test_org_via_repo(self.repo)

        # Track creation and update times
        self.user_timestamps: dict[str, tuple[datetime, datetime]] = {}  # user_id -> (created_at, updated_at)
        self.operation_sequence: list[tuple[str, datetime]] = []  # (operation, timestamp)

    @rule(username=usernames())
    def create_user(self, username: str):
        before_create = datetime.now(timezone.utc)

        user_data = UserData(username=username, email=f"{username}@test.com", full_name=username)
        user = self.repo.users.create(UserCreateCommand(
            user_data=user_data,
            password="Pass123!",
            organization_id=self.org.id,
            role=UserRole.ADMIN
        ))

        after_create = datetime.now(timezone.utc)

        self.user_timestamps[user.id] = (user.created_at, user.updated_at)
        self.operation_sequence.append(("create", user.created_at))

        # Verify timestamp is reasonable
        assert before_create <= user.created_at <= after_create, \
            f"Created timestamp {user.created_at} not in range [{before_create}, {after_create}]"
        assert user.created_at == user.updated_at, \
            "On creation, created_at should equal updated_at"

    @rule()
    @precondition(lambda self: len(self.user_timestamps) > 0)
    def update_user(self):
        user_id = list(self.user_timestamps.keys())[0]
        original_created_at, original_updated_at = self.user_timestamps[user_id]

        # Small delay to ensure timestamp changes
        import time
        time.sleep(0.001)

        before_update = datetime.now(timezone.utc)
        self.repo.users.update(user_id, UserUpdateCommand(email="newemail@test.com"))
        after_update = datetime.now(timezone.utc)

        updated_user = self.repo.users.get_by_id(user_id)

        self.user_timestamps[user_id] = (updated_user.created_at, updated_user.updated_at)
        self.operation_sequence.append(("update", updated_user.updated_at))

        # Verify created_at didn't change
        assert updated_user.created_at == original_created_at, \
            "Update should not modify created_at"

        # Verify updated_at changed
        assert updated_user.updated_at > original_updated_at, \
            "Update should increase updated_at"
        assert before_update <= updated_user.updated_at <= after_update, \
            f"Updated timestamp {updated_user.updated_at} not in range [{before_update}, {after_update}]"

    @invariant()
    def created_before_updated(self):
        """For all users, created_at <= updated_at."""
        for user_id, (created_at, updated_at) in self.user_timestamps.items():
            user = self.repo.users.get_by_id(user_id)
            if user:
                assert user.created_at <= user.updated_at, \
                    f"User {user_id}: created_at {user.created_at} > updated_at {user.updated_at}"

    @invariant()
    def timestamps_are_utc(self):
        """All timestamps should be UTC."""
        for user_id in self.user_timestamps:
            user = self.repo.users.get_by_id(user_id)
            if user:
                assert user.created_at.tzinfo == timezone.utc, \
                    f"User {user_id}: created_at not UTC"
                assert user.updated_at.tzinfo == timezone.utc, \
                    f"User {user_id}: updated_at not UTC"

    @invariant()
    def timestamps_monotonic(self):
        """Operation timestamps should be roughly monotonic (allowing small variance)."""
        if len(self.operation_sequence) > 1:
            # Check most operations are in order (allow some out-of-order due to precision)
            for i in range(len(self.operation_sequence) - 1):
                op1, time1 = self.operation_sequence[i]
                op2, time2 = self.operation_sequence[i + 1]

                # Allow 1ms of wiggle room for timestamp precision
                time_diff = (time2 - time1).total_seconds()
                assert time_diff >= -0.001, \
                    f"Time went backwards: {op1} at {time1}, then {op2} at {time2}"
```

**What bugs this finds:**
- Timestamps not in UTC
- created_at changes on update
- updated_at doesn't change on update
- Timestamps in the future
- Timestamps monotonicity violations

---

### Pattern 7: Permission Invariants

**Concept**: Verify authorization rules always enforced.

**When to use**: Multi-user systems with role-based access.

```python
class PermissionStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.repo = get_test_repository()

        # Create organizations
        self.org1 = create_test_org_via_repo(self.repo, "Org 1")
        self.org2 = create_test_org_via_repo(self.repo, "Org 2")

        # Track users and their access
        self.users_by_org: dict[str, list[str]] = {
            self.org1.id: [],
            self.org2.id: []
        }
        self.projects_by_org: dict[str, list[str]] = {
            self.org1.id: [],
            self.org2.id: []
        }

    @rule(username=usernames(), org_num=st.sampled_from([1, 2]))
    def create_user_in_org(self, username: str, org_num: int):
        org_id = self.org1.id if org_num == 1 else self.org2.id

        user_data = UserData(username=username, email=f"{username}@test.com", full_name=username)
        user = self.repo.users.create(UserCreateCommand(
            user_data=user_data,
            password="Pass123!",
            organization_id=org_id,
            role=UserRole.ADMIN
        ))

        self.users_by_org[org_id].append(user.id)

    @rule(name=st.text(min_size=1, max_size=255), org_num=st.sampled_from([1, 2]))
    @precondition(lambda self: len(self.users_by_org[self.org1.id]) > 0 or len(self.users_by_org[self.org2.id]) > 0)
    def create_project_in_org(self, name: str, org_num: int):
        org_id = self.org1.id if org_num == 1 else self.org2.id

        # Create workflow for project
        workflow = self.repo.workflows.create_default_workflow()

        project_data = ProjectData(name=name)
        project = self.repo.projects.create(ProjectCreateCommand(
            project_data=project_data,
            organization_id=org_id,
            workflow_id=workflow.id
        ))

        self.projects_by_org[org_id].append(project.id)

    @invariant()
    def users_can_only_see_own_org_projects(self):
        """Users should only be able to access projects in their organization."""
        # For each org, verify users can see projects in that org
        for org_id, user_ids in self.users_by_org.items():
            if not user_ids:
                continue

            user_id = user_ids[0]
            user = self.repo.users.get_by_id(user_id)

            # Get all projects visible to this user (simulate API filtering)
            all_projects = self.repo.projects.get_all()
            visible_projects = [p for p in all_projects if p.organization_id == org_id]

            # User should see exactly their org's projects
            expected_project_ids = set(self.projects_by_org[org_id])
            visible_project_ids = set(p.id for p in visible_projects)

            assert visible_project_ids == expected_project_ids, \
                f"User {user_id} in org {org_id} sees wrong projects. " \
                f"Expected {expected_project_ids}, saw {visible_project_ids}"

    @invariant()
    def users_belong_to_one_org(self):
        """Each user should belong to exactly one organization."""
        all_user_ids = set()
        for org_id, user_ids in self.users_by_org.items():
            for user_id in user_ids:
                assert user_id not in all_user_ids, \
                    f"User {user_id} appears in multiple organizations"
                all_user_ids.add(user_id)

                # Verify user's org_id matches
                user = self.repo.users.get_by_id(user_id)
                assert user.organization_id == org_id, \
                    f"User {user_id} should be in org {org_id}, but is in {user.organization_id}"

    @invariant()
    def cross_org_access_forbidden(self):
        """Users in org1 should never see org2 projects."""
        if not (self.users_by_org[self.org1.id] and self.projects_by_org[self.org2.id]):
            return  # Not enough data to test

        # Get a user from org1
        org1_user_id = self.users_by_org[self.org1.id][0]
        org1_user = self.repo.users.get_by_id(org1_user_id)

        # Try to access org2 projects
        all_projects = self.repo.projects.get_all()
        org2_projects = [p for p in all_projects if p.organization_id == self.org2.id]

        # Simulate API access check (would normally be in API layer)
        for project in org2_projects:
            # In real system, API would return 404 or 403
            # Here we verify the data is separated
            assert project.organization_id != org1_user.organization_id, \
                f"Cross-org leak: User {org1_user_id} in {org1_user.organization_id} " \
                f"could access project {project.id} in {project.organization_id}"
```

**What bugs this finds:**
- Users can access other orgs' data
- Organization boundaries not enforced
- User assigned to multiple organizations
- Cross-org data leaks

---

## Advanced Techniques

### Technique 1: Multiple State Machines

**Concept**: Run multiple state machines testing different aspects simultaneously.

```python
# Test User CRUD
class UserStateMachine(RuleBasedStateMachine):
    ...

# Test Project lifecycle
class ProjectStateMachine(RuleBasedStateMachine):
    ...

# Test Ticket workflows
class TicketStateMachine(RuleBasedStateMachine):
    ...

# Hypothesis runs each independently
TestUserCRUD = UserStateMachine.TestCase
TestProjectLifecycle = ProjectStateMachine.TestCase
TestTicketWorkflow = TicketStateMachine.TestCase
```

### Technique 2: Bundles (For Complex Relationships)

**Concept**: Use bundles to track created entities and use them in subsequent operations.

```python
from hypothesis.stateful import Bundle, rule

class ComplexStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.repo = get_test_repository()
        self.org = create_test_org_via_repo(self.repo)

    # Bundle of created users
    users = Bundle("users")

    # Bundle of created projects
    projects = Bundle("projects")

    @rule(target=users, username=usernames())
    def create_user(self, username: str):
        """Create user and add to users bundle."""
        user_data = UserData(username=username, email=f"{username}@test.com", full_name=username)
        user = self.repo.users.create(UserCreateCommand(
            user_data=user_data,
            password="Pass123!",
            organization_id=self.org.id,
            role=UserRole.ADMIN
        ))
        return user.id  # Add to bundle

    @rule(target=projects, name=st.text(min_size=1, max_size=255))
    def create_project(self, name: str):
        """Create project and add to projects bundle."""
        workflow = self.repo.workflows.create_default_workflow()
        project_data = ProjectData(name=name)
        project = self.repo.projects.create(ProjectCreateCommand(
            project_data=project_data,
            organization_id=self.org.id,
            workflow_id=workflow.id
        ))
        return project.id  # Add to bundle

    @rule(project_id=projects, user_id=users, title=st.text(min_size=1, max_size=255))
    def create_ticket(self, project_id: str, user_id: str, title: str):
        """Create ticket using entities from bundles."""
        # Get workflow from project
        project = self.repo.projects.get_by_id(project_id)
        workflow = self.repo.workflows.get_by_id(project.workflow_id)

        ticket_data = TicketData(
            title=title,
            status=workflow.statuses[0],
            priority=TicketPriority.MEDIUM
        )
        ticket = self.repo.tickets.create(TicketCreateCommand(
            ticket_data=ticket_data,
            project_id=project_id,
            reporter_id=user_id
        ))

        # Verify ticket references valid project and user
        assert ticket.project_id == project_id
        assert ticket.reporter_id == user_id
```

**Benefits**:
- Hypothesis automatically manages entity references
- Tests realistic usage patterns (create user, then use in ticket)
- No manual tracking of created entities

---

### Technique 3: Shrinking Hints

**Concept**: Help Hypothesis shrink failing examples faster.

```python
@rule(username=usernames())
def create_user(self, username: str):
    # Tell Hypothesis this username is "interesting" for shrinking
    note(f"Creating user: {username}")

    user_data = UserData(username=username, email=f"{username}@test.com", full_name=username)
    user = self.repo.users.create(UserCreateCommand(
        user_data=user_data,
        password="Pass123!",
        organization_id=self.org.id,
        role=UserRole.ADMIN
    ))

    # Note the generated ID for debugging
    note(f"Generated ID: {user.id}")
```

---

## Running Stateful Tests

```bash
# Run single state machine
pytest tests/property_based/stateful/test_user_state_machine.py -v

# Run with more examples (longer sequences)
pytest tests/property_based/stateful/ --hypothesis-stateful-step-count=100

# Show operation sequences
pytest tests/property_based/stateful/ -v --hypothesis-verbosity=verbose

# Reproduce specific failure
pytest tests/property_based/stateful/test_user_state_machine.py -v --hypothesis-seed=12345
```

---

## Summary: When to Use Each Pattern

| Pattern | Use When | Example |
|---------|----------|---------|
| **Shadow State** | All CRUD operations | Track which users exist vs deleted |
| **Count Invariants** | Adding/removing entities | Total created - deleted = current count |
| **Relationship Invariants** | Foreign keys | All tickets reference existing projects |
| **Business Rules** | Domain logic | Ticket status must be in workflow |
| **Aggregate Consistency** | Computed values | Epic ticket count = actual tickets |
| **Temporal Consistency** | Timestamps | created_at <= updated_at, UTC timezone |
| **Permission Invariants** | Authorization | Users only see own org's data |

---

## Next Steps

1. **Start with Shadow State**: Implement User CRUD state machine
2. **Add Count Invariants**: Track totals for one entity
3. **Test Relationships**: Verify foreign keys (tickets → projects)
4. **Add Business Rules**: Test workflow status validation
5. **Full Integration**: Combine multiple patterns in one state machine

The key insight: **Stateful testing finds bugs that example-based tests miss** because it tests hundreds of random operation sequences, not just hand-picked scenarios.
