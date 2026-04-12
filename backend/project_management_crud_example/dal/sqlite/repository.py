"""Repository classes for data access operations.

This module provides a single Repository class that handles all database operations
for the project management application, following the Repository pattern to
separate business logic from data access logic.

The Repository class uses nested classes for organization (e.g., repo.users, repo.organizations).
This allows for clean organization while enabling cross-entity queries naturally.

The StubEntities nested class serves as a template/scaffolding for reference.
"""

import json
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from project_management_crud_example.domain_models import (
    ActionType,
    ActivityLog,
    ActivityLogCreateCommand,
    Comment,
    CommentCreateCommand,
    CommentUpdateCommand,
    Epic,
    EpicCreateCommand,
    EpicUpdateCommand,
    Organization,
    OrganizationCreateCommand,
    OrganizationUpdateCommand,
    Project,
    ProjectCreateCommand,
    ProjectUpdateCommand,
    StubEntity,
    StubEntityCreateCommand,
    StubEntityUpdateCommand,
    Ticket,
    TicketCreateCommand,
    TicketUpdateCommand,
    User,
    UserAuthData,
    UserCreateCommand,
    UserRole,
    UserUpdateCommand,
    Workflow,
    WorkflowCreateCommand,
    WorkflowUpdateCommand,
)
from project_management_crud_example.utils.password import PasswordHasher, TestPasswordHasher

from .converters import (
    orm_activity_log_to_domain_activity_log,
    orm_activity_logs_to_domain_activity_logs,
    orm_comment_to_domain_comment,
    orm_epic_to_domain_epic,
    orm_organization_to_domain_organization,
    orm_project_to_domain_project,
    orm_stub_entities_to_business_stub_entities,
    orm_stub_entity_to_business_stub_entity,
    orm_ticket_to_domain_ticket,
    orm_user_to_domain_user,
    orm_user_to_user_auth_data,
    orm_workflow_to_domain_workflow,
    orm_workflows_to_domain_workflows,
)
from .orm_data_models import (
    ActivityLogORM,
    CommentORM,
    EpicORM,
    EpicTicketORM,
    OrganizationORM,
    ProjectORM,
    StubEntityORM,
    TicketORM,
    UserORM,
    WorkflowORM,
)

logger = logging.getLogger(__name__)


class Repository:
    """Single repository for all data access operations.

    Organized using nested classes for clarity:
    - repo.organizations - organization operations
    - repo.users - user operations
    - repo.stub_entities - scaffolding/example operations

    Future: repo.projects, repo.tickets, etc.
    """

    def __init__(self, session: Session, password_hasher: Optional[PasswordHasher | TestPasswordHasher] = None) -> None:
        """Initialize the repository with a database session.

        Args:
            session: SQLAlchemy database session
            password_hasher: Password hasher to use. Defaults to PasswordHasher(is_secure=True).
                            Pass TestPasswordHasher() for fast testing.
        """
        self.session = session
        if password_hasher is None:
            password_hasher = PasswordHasher(is_secure=True)
        self.password_hasher = password_hasher

        self.organizations = self.Organizations(session)
        self.projects = self.Projects(session)
        self.epics = self.Epics(session)
        self.workflows = self.Workflows(session)
        self.tickets = self.Tickets(session)
        self.comments = self.Comments(session)
        self.users = self.Users(session, password_hasher)
        self.activity_logs = self.ActivityLogs(session)
        self.stub_entities = self.StubEntities(session)

    class Users:
        """User-related data access operations."""

        def __init__(self, session: Session, password_hasher: PasswordHasher | TestPasswordHasher) -> None:
            self.session = session
            self.password_hasher = password_hasher

        def create(self, user_create_command: UserCreateCommand) -> User:
            """Create a new user with provided password.

            Args:
                user_create_command: Command containing user data and plain text password

            Returns:
                Created User domain model (without password_hash)

            Note: Password is hashed before storage. Plain text password is never stored.
            """
            user_data = user_create_command.user_data
            logger.debug(f"Creating new user: {user_data.username}")

            # Hash the provided password
            password_hash = self.password_hasher.hash_password(user_create_command.password)

            orm_user = UserORM(
                username=user_data.username,
                email=user_data.email,
                full_name=user_data.full_name,
                password_hash=password_hash,
                organization_id=user_create_command.organization_id,
                role=user_create_command.role.value,
            )
            self.session.add(orm_user)
            self.session.commit()
            self.session.refresh(orm_user)
            logger.debug(f"User created with ID: {orm_user.id}")
            return orm_user_to_domain_user(orm_user)

        def get_by_id(self, user_id: str) -> Optional[User]:
            """Get a specific user by ID."""
            logger.debug(f"Retrieving user by ID: {user_id}")
            orm_user = self.session.query(UserORM).filter(UserORM.id == user_id).first()  # type: ignore[operator]
            if orm_user is None:
                logger.debug(f"User not found: {user_id}")
                return None
            logger.debug(f"User found: {user_id}")
            return orm_user_to_domain_user(orm_user)

        def get_by_username(self, username: str) -> Optional[User]:
            """Get a specific user by username (case-insensitive).

            Args:
                username: Username to search for (case-insensitive)

            Returns:
                User if found, None otherwise

            Note: Username lookup is case-insensitive to support login requirements.
            """
            logger.debug(f"Retrieving user by username: {username}")
            orm_user = (
                self.session.query(UserORM)
                .filter(func.lower(UserORM.username) == username.lower())  # type: ignore[operator]
                .first()
            )
            if orm_user is None:
                logger.debug(f"User not found: {username}")
                return None
            logger.debug(f"User found: {username}")
            return orm_user_to_domain_user(orm_user)

        def get_by_username_with_password(self, username: str) -> Optional[UserAuthData]:
            """Get user authentication data by username (case-insensitive).

            This method is for authentication purposes only. It returns a domain model
            which includes password_hash for verification.

            Args:
                username: Username to search for (case-insensitive)

            Returns:
                UserAuthData if found (includes password_hash), None otherwise

            Note: Returns a domain model (UserAuthData), never an ORM object.
            This maintains proper layering and prevents ORM leakage.
            """
            logger.debug(f"Retrieving user with password for authentication: {username}")
            orm_user = (
                self.session.query(UserORM)
                .filter(func.lower(UserORM.username) == username.lower())  # type: ignore[operator]
                .first()
            )
            if orm_user is None:
                return None

            return orm_user_to_user_auth_data(orm_user)

        def get_all(self) -> List[User]:
            """Get all users from the database, ordered by creation date."""
            orm_users = self.session.query(UserORM).order_by(UserORM.created_at).all()  # type: ignore[union-attr]
            return [orm_user_to_domain_user(orm_user) for orm_user in orm_users]

        def get_by_filters(
            self,
            organization_id: Optional[str] = None,
            role: Optional[UserRole] = None,
            is_active: Optional[bool] = None,
        ) -> List[User]:
            """Get users filtered by various criteria.

            Args:
                organization_id: Filter by organization ID
                role: Filter by user role
                is_active: Filter by active status

            Returns:
                List of users matching all provided filters, ordered by creation date
            """
            logger.debug(
                f"Retrieving users with filters: organization_id={organization_id}, role={role}, is_active={is_active}"
            )
            query = self.session.query(UserORM)

            if organization_id is not None:
                query = query.filter(UserORM.organization_id == organization_id)  # type: ignore[operator]
            if role is not None:
                query = query.filter(UserORM.role == role.value)  # type: ignore[operator]
            if is_active is not None:
                query = query.filter(UserORM.is_active == is_active)  # type: ignore[operator]

            orm_users = query.order_by(UserORM.created_at).all()  # type: ignore[union-attr]
            return [orm_user_to_domain_user(orm_user) for orm_user in orm_users]

        def update(self, user_id: str, update_command: UserUpdateCommand) -> Optional[User]:
            """Update an existing user.

            Args:
                user_id: ID of user to update
                update_command: Command containing fields to update

            Returns:
                Updated User if found, None otherwise

            Raises:
                IntegrityError: If updating to duplicate email within organization

            Note: username, organization_id, and password cannot be changed via this method.
            """
            logger.debug(f"Updating user: {user_id}")
            orm_user = self.session.query(UserORM).filter(UserORM.id == user_id).first()  # type: ignore[operator]

            if orm_user is None:
                logger.debug(f"User not found for update: {user_id}")
                return None

            # Update only provided fields
            if update_command.email is not None:
                orm_user.email = str(update_command.email)  # type: ignore[assignment]
            if update_command.full_name is not None:
                orm_user.full_name = update_command.full_name  # type: ignore[assignment]
            if update_command.role is not None:
                orm_user.role = update_command.role.value  # type: ignore[assignment]
            if update_command.is_active is not None:
                orm_user.is_active = update_command.is_active  # type: ignore[assignment]

            try:
                self.session.commit()
                self.session.refresh(orm_user)
                logger.debug(f"User updated: {user_id}")
                return orm_user_to_domain_user(orm_user)
            except IntegrityError as e:
                self.session.rollback()
                logger.warning(f"Failed to update user (likely duplicate email): {user_id}")
                raise e

        def delete(self, user_id: str) -> bool:
            """Delete a user by ID.

            Args:
                user_id: ID of user to delete

            Returns:
                True if user was deleted, False if user not found

            Raises:
                IntegrityError: If user has created data (tickets) - cannot delete

            Note: V1 prevents deletion if user has created tickets (reporter_id reference).
            """
            logger.debug(f"Deleting user: {user_id}")
            orm_user = self.session.query(UserORM).filter(UserORM.id == user_id).first()  # type: ignore[operator]
            if not orm_user:
                logger.debug(f"User not found for deletion: {user_id}")
                return False

            # Check if user has created tickets (reporter)
            from .orm_data_models import TicketORM

            reporter_tickets_count = (
                self.session.query(TicketORM)
                .filter(TicketORM.reporter_id == user_id)  # type: ignore[operator]
                .count()
            )

            if reporter_tickets_count > 0:
                logger.warning(f"Cannot delete user {user_id}: user has created {reporter_tickets_count} ticket(s)")
                # Create IntegrityError with proper message format
                error_msg = f"Cannot delete user: user has created {reporter_tickets_count} ticket(s)"
                # Create a base exception for the orig parameter
                orig_error = RuntimeError(error_msg)
                error = IntegrityError(statement=error_msg, params=None, orig=orig_error)
                # Set the args to make str(error) return our message
                error.args = (error_msg,)
                raise error

            self.session.delete(orm_user)
            self.session.commit()
            logger.debug(f"User deleted: {user_id}")
            return True

        def update_password(self, user_id: str, new_password: str) -> bool:
            """Update a user's password.

            Args:
                user_id: ID of user whose password to update
                new_password: New plain text password (will be hashed before storage)

            Returns:
                True if password was updated, False if user not found

            Note: Plain text password is never stored - it's hashed immediately.
            """
            logger.debug(f"Updating password for user: {user_id}")
            orm_user = self.session.query(UserORM).filter(UserORM.id == user_id).first()  # type: ignore[operator]

            if orm_user is None:
                logger.debug(f"User not found for password update: {user_id}")
                return False

            # Hash the new password
            password_hash = self.password_hasher.hash_password(new_password)
            orm_user.password_hash = password_hash  # type: ignore[assignment]

            self.session.commit()
            logger.debug(f"Password updated for user: {user_id}")
            return True

        def create_super_admin_if_needed(
            self, username: str, email: str, full_name: str, password: str
        ) -> tuple[bool, Optional[User]]:
            """Create Super Admin user if none exists.

            Args:
                username: Super Admin username
                email: Super Admin email
                full_name: Super Admin full name
                password: Plain text password (will be hashed)

            Returns:
                Tuple of (created: bool, user: User | None)
                - created: True if Super Admin was created, False if already exists
                - user: Created User if created, None if already exists

            Note: This function is idempotent - it will not create duplicate Super Admins.
            """
            from project_management_crud_example.domain_models import UserRole

            logger.debug("Checking if Super Admin exists")

            # Check if any Super Admin users exist
            all_users = self.get_all()
            existing_super_admins = [u for u in all_users if u.role == UserRole.SUPER_ADMIN]

            if existing_super_admins:
                logger.debug("Super Admin already exists, skipping creation")
                return False, None

            logger.info(f"Creating Super Admin: {username}")

            # Create Super Admin
            from project_management_crud_example.domain_models import UserData

            user_data = UserData(
                username=username,
                email=email,
                full_name=full_name,
            )

            command = UserCreateCommand(
                user_data=user_data,
                password=password,
                organization_id=None,  # Super Admin has no organization
                role=UserRole.SUPER_ADMIN,
            )

            user = self.create(command)
            logger.info(f"Super Admin created successfully: {user.id}")

            return True, user

    class Organizations:
        """Organization-related data access operations."""

        def __init__(self, session: Session) -> None:
            self.session = session

        def create(self, organization_create_command: OrganizationCreateCommand) -> Organization:
            """Create a new organization.

            Args:
                organization_create_command: Command containing organization data

            Returns:
                Created Organization domain model

            Raises:
                IntegrityError: If organization with same name already exists
            """
            org_data = organization_create_command.organization_data
            logger.debug(f"Creating new organization: {org_data.name}")

            orm_organization = OrganizationORM(
                name=org_data.name,
                description=org_data.description,
            )

            try:
                self.session.add(orm_organization)
                self.session.commit()
                self.session.refresh(orm_organization)
                logger.debug(f"Organization created with ID: {orm_organization.id}")
                return orm_organization_to_domain_organization(orm_organization)
            except IntegrityError as e:
                self.session.rollback()
                logger.warning(f"Failed to create organization (likely duplicate name): {org_data.name}")
                raise e

        def get_by_id(self, organization_id: str) -> Optional[Organization]:
            """Get a specific organization by ID."""
            logger.debug(f"Retrieving organization by ID: {organization_id}")
            orm_organization = (
                self.session.query(OrganizationORM)
                .filter(OrganizationORM.id == organization_id)  # type: ignore[operator]
                .first()
            )
            if orm_organization is None:
                logger.debug(f"Organization not found: {organization_id}")
                return None
            logger.debug(f"Organization found: {organization_id}")
            return orm_organization_to_domain_organization(orm_organization)

        def get_all(self) -> List[Organization]:
            """Get all organizations from the database, ordered by creation date."""
            orm_organizations = (
                self.session.query(OrganizationORM).order_by(OrganizationORM.created_at).all()  # type: ignore[union-attr]
            )
            return [orm_organization_to_domain_organization(org) for org in orm_organizations]

        def update(self, organization_id: str, update_command: OrganizationUpdateCommand) -> Optional[Organization]:
            """Update an existing organization.

            Args:
                organization_id: ID of organization to update
                update_command: Command containing fields to update

            Returns:
                Updated Organization if found, None otherwise

            Raises:
                IntegrityError: If updating to duplicate name
            """
            logger.debug(f"Updating organization: {organization_id}")
            orm_organization = (
                self.session.query(OrganizationORM)
                .filter(OrganizationORM.id == organization_id)  # type: ignore[operator]
                .first()
            )

            if orm_organization is None:
                logger.debug(f"Organization not found for update: {organization_id}")
                return None

            # Update only provided fields
            if update_command.name is not None:
                orm_organization.name = update_command.name  # type: ignore[assignment]
            if update_command.description is not None:
                orm_organization.description = update_command.description  # type: ignore[assignment]
            if update_command.is_active is not None:
                orm_organization.is_active = update_command.is_active  # type: ignore[assignment]

            try:
                self.session.commit()
                self.session.refresh(orm_organization)
                logger.debug(f"Organization updated: {organization_id}")
                return orm_organization_to_domain_organization(orm_organization)
            except IntegrityError as e:
                self.session.rollback()
                logger.warning(f"Failed to update organization (likely duplicate name): {organization_id}")
                raise e

        def delete(self, organization_id: str) -> bool:
            """Delete an organization by ID.

            Note: This is for testing/cleanup purposes. In production, use is_active flag instead.
            """
            logger.debug(f"Deleting organization: {organization_id}")
            orm_organization = (
                self.session.query(OrganizationORM)
                .filter(OrganizationORM.id == organization_id)  # type: ignore[operator]
                .first()
            )
            if not orm_organization:
                logger.debug(f"Organization not found for deletion: {organization_id}")
                return False

            self.session.delete(orm_organization)
            self.session.commit()
            logger.debug(f"Organization deleted: {organization_id}")
            return True

    class Projects:
        """Project-related data access operations."""

        def __init__(self, session: Session) -> None:
            self.session = session

        def create(self, project_create_command: ProjectCreateCommand) -> Project:
            """Create a new project.

            Args:
                project_create_command: Command containing project data and organization_id

            Returns:
                Created Project domain model

            Raises:
                ValueError: If specified workflow doesn't exist or is from different organization
            """
            project_data = project_create_command.project_data
            organization_id = project_create_command.organization_id
            logger.debug(f"Creating new project: {project_data.name} for organization: {organization_id}")

            # Determine workflow_id
            workflow_id = project_data.workflow_id
            if workflow_id:
                # Validate specified workflow exists and is in same organization
                workflow = (
                    self.session.query(WorkflowORM)
                    .filter(WorkflowORM.id == workflow_id)  # type: ignore[operator]
                    .first()
                )
                if not workflow:
                    raise ValueError(f"Workflow not found: {workflow_id}")
                if workflow.organization_id != organization_id:
                    raise ValueError(
                        f"Workflow {workflow_id} belongs to different organization {workflow.organization_id}"
                    )
            else:
                # Use organization's default workflow
                default_workflow = (
                    self.session.query(WorkflowORM)
                    .filter(WorkflowORM.organization_id == organization_id)  # type: ignore[operator]
                    .filter(WorkflowORM.is_default == True)  # type: ignore[operator]  # noqa: E712
                    .first()
                )
                if not default_workflow:
                    raise ValueError(f"No default workflow found for organization: {organization_id}")
                workflow_id = str(default_workflow.id)

            orm_project = ProjectORM(
                name=project_data.name,
                description=project_data.description,
                organization_id=organization_id,
                workflow_id=workflow_id,
            )

            self.session.add(orm_project)
            self.session.commit()
            self.session.refresh(orm_project)
            logger.debug(f"Project created with ID: {orm_project.id}, workflow: {workflow_id}")
            return orm_project_to_domain_project(orm_project)

        def get_by_id(self, project_id: str) -> Optional[Project]:
            """Get a specific project by ID."""
            logger.debug(f"Retrieving project by ID: {project_id}")
            orm_project = (
                self.session.query(ProjectORM).filter(ProjectORM.id == project_id).first()  # type: ignore[operator]
            )
            if orm_project is None:
                logger.debug(f"Project not found: {project_id}")
                return None
            logger.debug(f"Project found: {project_id}")
            return orm_project_to_domain_project(orm_project)

        def get_by_organization_id(self, organization_id: str) -> List[Project]:
            """Get all non-archived projects for a specific organization."""
            logger.debug(f"Retrieving projects for organization: {organization_id}")
            orm_projects = (
                self.session.query(ProjectORM)
                .filter(ProjectORM.organization_id == organization_id)  # type: ignore[operator]
                .filter(ProjectORM.is_archived == False)  # type: ignore[operator]  # noqa: E712
                .order_by(ProjectORM.created_at)  # type: ignore[union-attr]
                .all()
            )
            return [orm_project_to_domain_project(proj) for proj in orm_projects]

        def get_all(self) -> List[Project]:
            """Get all non-archived projects from the database, ordered by creation date."""
            orm_projects = (
                self.session.query(ProjectORM)
                .filter(ProjectORM.is_archived == False)  # type: ignore[operator]  # noqa: E712
                .order_by(ProjectORM.created_at)  # type: ignore[union-attr]
                .all()
            )
            return [orm_project_to_domain_project(proj) for proj in orm_projects]

        def get_by_filters(
            self,
            organization_id: Optional[str] = None,
            name: Optional[str] = None,
            is_active: Optional[bool] = None,
            include_archived: bool = False,
        ) -> List[Project]:
            """Get projects filtered by various criteria.

            Args:
                organization_id: Filter by organization ID (required for non-Super Admin users)
                name: Filter by name substring (case-insensitive)
                is_active: Filter by active status
                include_archived: Include archived projects in results (default: False)

            Returns:
                List of projects matching all provided filters, ordered by creation date
            """
            logger.debug(
                f"Retrieving projects with filters: organization_id={organization_id}, name={name}, "
                f"is_active={is_active}, include_archived={include_archived}"
            )
            query = self.session.query(ProjectORM)

            if organization_id is not None:
                query = query.filter(ProjectORM.organization_id == organization_id)  # type: ignore[operator]
            if name is not None:
                # Case-insensitive substring search
                query = query.filter(ProjectORM.name.ilike(f"%{name}%"))  # type: ignore[attr-defined]
            if is_active is not None:
                query = query.filter(ProjectORM.is_active == is_active)  # type: ignore[operator]

            # Exclude archived projects by default
            if not include_archived:
                query = query.filter(ProjectORM.is_archived == False)  # type: ignore[operator]  # noqa: E712

            orm_projects = query.order_by(ProjectORM.created_at).all()  # type: ignore[union-attr]
            return [orm_project_to_domain_project(proj) for proj in orm_projects]

        def update(self, project_id: str, update_command: ProjectUpdateCommand) -> Optional[Project]:
            """Update an existing project.

            Args:
                project_id: ID of project to update
                update_command: Command containing fields to update

            Returns:
                Updated Project if found, None otherwise

            Raises:
                ValueError: If specified workflow doesn't exist or is from different organization
            """
            logger.debug(f"Updating project: {project_id}")
            orm_project = (
                self.session.query(ProjectORM).filter(ProjectORM.id == project_id).first()  # type: ignore[operator]
            )

            if orm_project is None:
                logger.debug(f"Project not found for update: {project_id}")
                return None

            # Update only provided fields
            if update_command.name is not None:
                orm_project.name = update_command.name  # type: ignore[assignment]
            if update_command.description is not None:
                orm_project.description = update_command.description  # type: ignore[assignment]
            if update_command.workflow_id is not None:
                # Validate new workflow exists and is in same organization
                workflow = (
                    self.session.query(WorkflowORM)
                    .filter(WorkflowORM.id == update_command.workflow_id)  # type: ignore[operator]
                    .first()
                )
                if not workflow:
                    raise ValueError(f"Workflow not found: {update_command.workflow_id}")
                if workflow.organization_id != orm_project.organization_id:
                    raise ValueError(
                        f"Workflow {update_command.workflow_id} belongs to different organization "
                        f"{workflow.organization_id}"
                    )

                # Validate existing tickets have valid statuses for new workflow
                import json

                new_workflow_statuses = json.loads(workflow.statuses)

                # Check if any tickets in this project have statuses not in the new workflow
                from project_management_crud_example.dal.sqlite.orm_data_models import TicketORM

                tickets = (
                    self.session.query(TicketORM).filter(TicketORM.project_id == project_id).all()  # type: ignore[operator]
                )

                invalid_tickets = []
                for ticket in tickets:
                    if ticket.status not in new_workflow_statuses:
                        invalid_tickets.append(ticket.status)

                if invalid_tickets:
                    unique_statuses = sorted(set(invalid_tickets))
                    status_list = ", ".join(unique_statuses)
                    valid_statuses = ", ".join(new_workflow_statuses)
                    raise ValueError(
                        f"Cannot change workflow: {len(invalid_tickets)} ticket(s) have statuses "
                        f"({status_list}) that are not valid in the new workflow. "
                        f"Valid statuses in target workflow: {valid_statuses}. "
                        f"Please update ticket statuses first before changing the project's workflow."
                    )

                orm_project.workflow_id = update_command.workflow_id  # type: ignore[assignment]
            if update_command.is_active is not None:
                orm_project.is_active = update_command.is_active  # type: ignore[assignment]

            self.session.commit()
            self.session.refresh(orm_project)
            logger.debug(f"Project updated: {project_id}")
            return orm_project_to_domain_project(orm_project)

        def delete(self, project_id: str) -> bool:
            """Delete a project by ID.

            Note: This is for testing/cleanup purposes. In production, use archival instead.
            """
            logger.debug(f"Deleting project: {project_id}")
            orm_project = (
                self.session.query(ProjectORM).filter(ProjectORM.id == project_id).first()  # type: ignore[operator]
            )
            if not orm_project:
                logger.debug(f"Project not found for deletion: {project_id}")
                return False

            self.session.delete(orm_project)
            self.session.commit()
            logger.debug(f"Project deleted: {project_id}")
            return True

        def archive(self, project_id: str) -> Optional[Project]:
            """Archive a project (soft delete).

            Args:
                project_id: ID of project to archive

            Returns:
                Archived Project if found, None otherwise
            """
            from datetime import datetime, timezone

            logger.debug(f"Archiving project: {project_id}")
            orm_project = (
                self.session.query(ProjectORM).filter(ProjectORM.id == project_id).first()  # type: ignore[operator]
            )

            if orm_project is None:
                logger.debug(f"Project not found for archiving: {project_id}")
                return None

            # Set archive fields
            orm_project.is_archived = True  # type: ignore[assignment]
            orm_project.archived_at = datetime.now(timezone.utc)  # type: ignore[assignment]

            self.session.commit()
            self.session.refresh(orm_project)
            logger.debug(f"Project archived: {project_id}")
            return orm_project_to_domain_project(orm_project)

        def unarchive(self, project_id: str) -> Optional[Project]:
            """Unarchive a project (restore from archive).

            Args:
                project_id: ID of project to unarchive

            Returns:
                Unarchived Project if found, None otherwise
            """
            logger.debug(f"Unarchiving project: {project_id}")
            orm_project = (
                self.session.query(ProjectORM).filter(ProjectORM.id == project_id).first()  # type: ignore[operator]
            )

            if orm_project is None:
                logger.debug(f"Project not found for unarchiving: {project_id}")
                return None

            # Clear archive fields
            orm_project.is_archived = False  # type: ignore[assignment]
            orm_project.archived_at = None  # type: ignore[assignment]

            self.session.commit()
            self.session.refresh(orm_project)
            logger.debug(f"Project unarchived: {project_id}")
            return orm_project_to_domain_project(orm_project)

        def count_by_workflow_id(self, workflow_id: str) -> int:
            """Count projects using a specific workflow.

            Args:
                workflow_id: ID of workflow to check

            Returns:
                Number of projects using this workflow
            """
            logger.debug(f"Counting projects using workflow: {workflow_id}")
            count = (
                self.session.query(ProjectORM)
                .filter(ProjectORM.workflow_id == workflow_id)  # type: ignore[operator]
                .count()
            )
            logger.debug(f"Found {count} projects using workflow: {workflow_id}")
            return count

    class Epics:
        """Epic-related data access operations."""

        def __init__(self, session: Session) -> None:
            self.session = session

        def create(self, epic_create_command: EpicCreateCommand) -> Epic:
            """Create a new epic.

            Args:
                epic_create_command: Command containing epic data and organization_id

            Returns:
                Created Epic domain model
            """
            epic_data = epic_create_command.epic_data
            logger.debug(f"Creating new epic: {epic_data.name} for organization: {epic_create_command.organization_id}")

            orm_epic = EpicORM(
                name=epic_data.name,
                description=epic_data.description,
                organization_id=epic_create_command.organization_id,
            )

            self.session.add(orm_epic)
            self.session.commit()
            self.session.refresh(orm_epic)
            logger.debug(f"Epic created with ID: {orm_epic.id}")
            return orm_epic_to_domain_epic(orm_epic)

        def get_by_id(self, epic_id: str) -> Optional[Epic]:
            """Get a specific epic by ID."""
            logger.debug(f"Retrieving epic by ID: {epic_id}")
            orm_epic = (
                self.session.query(EpicORM).filter(EpicORM.id == epic_id).first()  # type: ignore[operator]
            )
            if orm_epic is None:
                logger.debug(f"Epic not found: {epic_id}")
                return None
            logger.debug(f"Epic found: {epic_id}")
            return orm_epic_to_domain_epic(orm_epic)

        def get_by_organization_id(self, organization_id: str) -> List[Epic]:
            """Get all epics for a specific organization."""
            logger.debug(f"Retrieving epics for organization: {organization_id}")
            orm_epics = (
                self.session.query(EpicORM)
                .filter(EpicORM.organization_id == organization_id)  # type: ignore[operator]
                .order_by(EpicORM.created_at)  # type: ignore[union-attr]
                .all()
            )
            return [orm_epic_to_domain_epic(epic) for epic in orm_epics]

        def get_all(self) -> List[Epic]:
            """Get all epics from the database, ordered by creation date."""
            orm_epics = (
                self.session.query(EpicORM).order_by(EpicORM.created_at).all()  # type: ignore[union-attr]
            )
            return [orm_epic_to_domain_epic(epic) for epic in orm_epics]

        def update(self, epic_id: str, update_command: EpicUpdateCommand) -> Optional[Epic]:
            """Update an existing epic.

            Args:
                epic_id: ID of epic to update
                update_command: Command containing fields to update

            Returns:
                Updated Epic if found, None otherwise
            """
            logger.debug(f"Updating epic: {epic_id}")
            orm_epic = (
                self.session.query(EpicORM).filter(EpicORM.id == epic_id).first()  # type: ignore[operator]
            )

            if orm_epic is None:
                logger.debug(f"Epic not found for update: {epic_id}")
                return None

            # Update only provided fields
            if update_command.name is not None:
                orm_epic.name = update_command.name  # type: ignore[assignment]
            if update_command.description is not None:
                orm_epic.description = update_command.description  # type: ignore[assignment]

            self.session.commit()
            self.session.refresh(orm_epic)
            logger.debug(f"Epic updated: {epic_id}")
            return orm_epic_to_domain_epic(orm_epic)

        def delete(self, epic_id: str) -> bool:
            """Delete an epic by ID.

            Note: This also deletes all epic-ticket associations for this epic.

            Args:
                epic_id: ID of epic to delete

            Returns:
                True if deleted, False if not found
            """
            logger.debug(f"Deleting epic: {epic_id}")
            orm_epic = (
                self.session.query(EpicORM).filter(EpicORM.id == epic_id).first()  # type: ignore[operator]
            )
            if not orm_epic:
                logger.debug(f"Epic not found for deletion: {epic_id}")
                return False

            # Delete epic-ticket associations first (CASCADE would handle this, but being explicit)
            self.session.query(EpicTicketORM).filter(
                EpicTicketORM.epic_id == epic_id  # type: ignore[operator]
            ).delete()

            self.session.delete(orm_epic)
            self.session.commit()
            logger.debug(f"Epic deleted: {epic_id}")
            return True

        def add_ticket_to_epic(self, epic_id: str, ticket_id: str) -> bool:
            """Add a ticket to an epic (idempotent).

            Args:
                epic_id: ID of epic
                ticket_id: ID of ticket to add

            Returns:
                True if association created or already exists, False if epic or ticket not found
            """
            logger.debug(f"Adding ticket {ticket_id} to epic {epic_id}")

            # Verify epic exists
            epic = self.session.query(EpicORM).filter(EpicORM.id == epic_id).first()  # type: ignore[operator]
            if not epic:
                logger.debug(f"Epic not found: {epic_id}")
                return False

            # Verify ticket exists
            ticket = self.session.query(TicketORM).filter(TicketORM.id == ticket_id).first()  # type: ignore[operator]
            if not ticket:
                logger.debug(f"Ticket not found: {ticket_id}")
                return False

            # Check if association already exists (idempotent)
            existing = (
                self.session.query(EpicTicketORM)
                .filter(
                    EpicTicketORM.epic_id == epic_id,  # type: ignore[operator]
                    EpicTicketORM.ticket_id == ticket_id,  # type: ignore[operator]
                )
                .first()
            )

            if existing:
                logger.debug(f"Ticket {ticket_id} already in epic {epic_id} (idempotent)")
                return True

            # Create association
            association = EpicTicketORM(epic_id=epic_id, ticket_id=ticket_id)
            self.session.add(association)
            self.session.commit()
            logger.debug(f"Ticket {ticket_id} added to epic {epic_id}")
            return True

        def remove_ticket_from_epic(self, epic_id: str, ticket_id: str) -> bool:
            """Remove a ticket from an epic (idempotent).

            Note: This only removes the association, not the ticket itself.

            Args:
                epic_id: ID of epic
                ticket_id: ID of ticket to remove

            Returns:
                True if association removed or didn't exist, False if epic or ticket not found
            """
            logger.debug(f"Removing ticket {ticket_id} from epic {epic_id}")

            # Verify epic exists
            epic = self.session.query(EpicORM).filter(EpicORM.id == epic_id).first()  # type: ignore[operator]
            if not epic:
                logger.debug(f"Epic not found: {epic_id}")
                return False

            # Verify ticket exists
            ticket = self.session.query(TicketORM).filter(TicketORM.id == ticket_id).first()  # type: ignore[operator]
            if not ticket:
                logger.debug(f"Ticket not found: {ticket_id}")
                return False

            # Delete association (idempotent - succeeds even if association doesn't exist)
            deleted_count = (
                self.session.query(EpicTicketORM)
                .filter(
                    EpicTicketORM.epic_id == epic_id,  # type: ignore[operator]
                    EpicTicketORM.ticket_id == ticket_id,  # type: ignore[operator]
                )
                .delete()
            )

            self.session.commit()

            if deleted_count > 0:
                logger.debug(f"Ticket {ticket_id} removed from epic {epic_id}")
            else:
                logger.debug(f"Ticket {ticket_id} was not in epic {epic_id} (idempotent)")

            return True

        def get_tickets_in_epic(self, epic_id: str) -> Optional[List[Ticket]]:
            """Get all tickets associated with an epic.

            Args:
                epic_id: ID of epic

            Returns:
                List of Ticket domain models if epic exists, None if epic not found
            """
            logger.debug(f"Getting tickets for epic: {epic_id}")

            # Verify epic exists
            epic = self.session.query(EpicORM).filter(EpicORM.id == epic_id).first()  # type: ignore[operator]
            if not epic:
                logger.debug(f"Epic not found: {epic_id}")
                return None

            # Query tickets via the association table
            orm_tickets = (
                self.session.query(TicketORM)
                .join(EpicTicketORM, TicketORM.id == EpicTicketORM.ticket_id)
                .filter(EpicTicketORM.epic_id == epic_id)  # type: ignore[operator]
                .order_by(TicketORM.created_at)  # type: ignore[union-attr]
                .all()
            )

            logger.debug(f"Found {len(orm_tickets)} tickets in epic {epic_id}")
            return [orm_ticket_to_domain_ticket(ticket) for ticket in orm_tickets]

    class Tickets:
        """Ticket-related data access operations."""

        def __init__(self, session: Session) -> None:
            self.session = session

        def create(self, ticket_create_command: TicketCreateCommand, reporter_id: str) -> Ticket:
            """Create a new ticket.

            Args:
                ticket_create_command: Command containing ticket data and project_id
                reporter_id: ID of the user creating this ticket (current user)

            Returns:
                Created Ticket domain model

            Raises:
                ValueError: If status is provided but not valid in project's workflow
            """
            ticket_data = ticket_create_command.ticket_data
            project_id = ticket_create_command.project_id
            logger.debug(f"Creating new ticket: {ticket_data.title} in project: {project_id}")

            # Get project to determine workflow
            project_orm = (
                self.session.query(ProjectORM)
                .filter(ProjectORM.id == project_id)  # type: ignore[operator]
                .first()
            )
            if not project_orm:
                raise ValueError(f"Project not found: {project_id}")

            # Get workflow to validate status
            workflow_orm = (
                self.session.query(WorkflowORM)
                .filter(WorkflowORM.id == project_orm.workflow_id)  # type: ignore[operator]
                .first()
            )
            if not workflow_orm:
                raise ValueError(f"Workflow not found: {project_orm.workflow_id}")

            # Parse workflow statuses from JSON
            import json

            workflow_statuses = json.loads(workflow_orm.statuses)

            # Determine status: use provided or default to first workflow status
            if ticket_data.status:
                status = ticket_data.status
                # Validate status is in workflow
                if status not in workflow_statuses:
                    valid_statuses = ", ".join(workflow_statuses)
                    raise ValueError(
                        f"Invalid status '{status}' for project's workflow. Valid statuses: {valid_statuses}"
                    )
            else:
                # Default to first status in workflow
                status = workflow_statuses[0]

            orm_ticket = TicketORM(
                title=ticket_data.title,
                description=ticket_data.description,
                status=status,
                priority=ticket_data.priority.value if ticket_data.priority else None,
                assignee_id=ticket_create_command.assignee_id,
                reporter_id=reporter_id,
                project_id=project_id,
            )

            self.session.add(orm_ticket)
            self.session.commit()
            self.session.refresh(orm_ticket)
            logger.debug(f"Ticket created with ID: {orm_ticket.id}, status: {status}")
            return orm_ticket_to_domain_ticket(orm_ticket)

        def get_by_id(self, ticket_id: str) -> Optional[Ticket]:
            """Get a specific ticket by ID."""
            logger.debug(f"Retrieving ticket by ID: {ticket_id}")
            orm_ticket = self.session.query(TicketORM).filter(TicketORM.id == ticket_id).first()  # type: ignore[operator]
            if orm_ticket is None:
                logger.debug(f"Ticket not found: {ticket_id}")
                return None
            logger.debug(f"Ticket found: {ticket_id}")
            return orm_ticket_to_domain_ticket(orm_ticket)

        def get_by_project_id(self, project_id: str) -> List[Ticket]:
            """Get all tickets for a specific project."""
            logger.debug(f"Retrieving tickets for project: {project_id}")
            orm_tickets = (
                self.session.query(TicketORM)
                .filter(TicketORM.project_id == project_id)  # type: ignore[operator]
                .order_by(TicketORM.created_at)  # type: ignore[union-attr]
                .all()
            )
            return [orm_ticket_to_domain_ticket(ticket) for ticket in orm_tickets]

        def get_all(self) -> List[Ticket]:
            """Get all tickets from the database, ordered by creation date."""
            orm_tickets = self.session.query(TicketORM).order_by(TicketORM.created_at).all()  # type: ignore[union-attr]
            return [orm_ticket_to_domain_ticket(ticket) for ticket in orm_tickets]

        def get_by_filters(
            self,
            project_id: Optional[str] = None,
            status: Optional[str] = None,
            assignee_id: Optional[str] = None,
        ) -> List[Ticket]:
            """Get tickets filtered by various criteria.

            Args:
                project_id: Filter by project ID
                status: Filter by ticket status string
                assignee_id: Filter by assignee user ID

            Returns:
                List of tickets matching all provided filters
            """
            logger.debug(
                f"Retrieving tickets with filters: project_id={project_id}, status={status}, assignee_id={assignee_id}"
            )
            query = self.session.query(TicketORM)

            if project_id is not None:
                query = query.filter(TicketORM.project_id == project_id)  # type: ignore[operator]
            if status is not None:
                query = query.filter(TicketORM.status == status)  # type: ignore[operator]
            if assignee_id is not None:
                query = query.filter(TicketORM.assignee_id == assignee_id)  # type: ignore[operator]

            orm_tickets = query.order_by(TicketORM.created_at).all()  # type: ignore[union-attr]
            return [orm_ticket_to_domain_ticket(ticket) for ticket in orm_tickets]

        def update(self, ticket_id: str, update_command: TicketUpdateCommand) -> Optional[Ticket]:
            """Update an existing ticket.

            Args:
                ticket_id: ID of ticket to update
                update_command: Command containing fields to update

            Returns:
                Updated Ticket if found, None otherwise
            """
            logger.debug(f"Updating ticket: {ticket_id}")
            orm_ticket = self.session.query(TicketORM).filter(TicketORM.id == ticket_id).first()  # type: ignore[operator]

            if orm_ticket is None:
                logger.debug(f"Ticket not found for update: {ticket_id}")
                return None

            # Update only provided fields
            if update_command.title is not None:
                orm_ticket.title = update_command.title  # type: ignore[assignment]
            if update_command.description is not None:
                orm_ticket.description = update_command.description  # type: ignore[assignment]
            if update_command.priority is not None:
                orm_ticket.priority = update_command.priority.value  # type: ignore[assignment]

            self.session.commit()
            self.session.refresh(orm_ticket)
            logger.debug(f"Ticket updated: {ticket_id}")
            return orm_ticket_to_domain_ticket(orm_ticket)

        def update_status(self, ticket_id: str, status: str) -> Optional[Ticket]:
            """Change ticket status.

            Args:
                ticket_id: ID of ticket to update
                status: New ticket status string

            Returns:
                Updated Ticket if found, None otherwise

            Raises:
                ValueError: If status is not valid in ticket's project's workflow
            """
            logger.debug(f"Updating ticket status: {ticket_id} to {status}")
            orm_ticket = self.session.query(TicketORM).filter(TicketORM.id == ticket_id).first()  # type: ignore[operator]

            if orm_ticket is None:
                logger.debug(f"Ticket not found for status update: {ticket_id}")
                return None

            # Get project's workflow to validate status
            project_orm = (
                self.session.query(ProjectORM)
                .filter(ProjectORM.id == orm_ticket.project_id)  # type: ignore[operator]
                .first()
            )
            if not project_orm:
                raise ValueError(f"Project not found: {orm_ticket.project_id}")

            workflow_orm = (
                self.session.query(WorkflowORM)
                .filter(WorkflowORM.id == project_orm.workflow_id)  # type: ignore[operator]
                .first()
            )
            if not workflow_orm:
                raise ValueError(f"Workflow not found: {project_orm.workflow_id}")

            # Parse workflow statuses from JSON
            import json

            workflow_statuses = json.loads(workflow_orm.statuses)

            # Validate status is in workflow
            if status not in workflow_statuses:
                valid_statuses = ", ".join(workflow_statuses)
                raise ValueError(f"Invalid status '{status}' for project's workflow. Valid statuses: {valid_statuses}")

            orm_ticket.status = status  # type: ignore[assignment]
            self.session.commit()
            self.session.refresh(orm_ticket)
            logger.debug(f"Ticket status updated: {ticket_id}")
            return orm_ticket_to_domain_ticket(orm_ticket)

        def update_project(self, ticket_id: str, project_id: str) -> Optional[Ticket]:
            """Move ticket to different project.

            Args:
                ticket_id: ID of ticket to move
                project_id: ID of target project

            Returns:
                Updated Ticket if found, None otherwise

            Raises:
                ValueError: If ticket's current status is not valid in target project's workflow
            """
            logger.debug(f"Moving ticket {ticket_id} to project {project_id}")
            orm_ticket = self.session.query(TicketORM).filter(TicketORM.id == ticket_id).first()  # type: ignore[operator]

            if orm_ticket is None:
                logger.debug(f"Ticket not found for project update: {ticket_id}")
                return None

            # Get target project's workflow to validate status compatibility
            target_project_orm = (
                self.session.query(ProjectORM)
                .filter(ProjectORM.id == project_id)  # type: ignore[operator]
                .first()
            )
            if not target_project_orm:
                raise ValueError(f"Target project not found: {project_id}")

            target_workflow_orm = (
                self.session.query(WorkflowORM)
                .filter(WorkflowORM.id == target_project_orm.workflow_id)  # type: ignore[operator]
                .first()
            )
            if not target_workflow_orm:
                raise ValueError(f"Workflow not found: {target_project_orm.workflow_id}")

            # Parse workflow statuses from JSON
            import json

            target_workflow_statuses = json.loads(target_workflow_orm.statuses)

            # Validate ticket's current status is in target workflow
            current_status = orm_ticket.status
            if current_status not in target_workflow_statuses:
                valid_statuses = ", ".join(target_workflow_statuses)
                raise ValueError(
                    f"Cannot move ticket: current status '{current_status}' is not valid in target project's workflow. "
                    f"Valid statuses in target workflow: {valid_statuses}. "
                    f"Please update ticket status first before moving."
                )

            orm_ticket.project_id = project_id  # type: ignore[assignment]
            self.session.commit()
            self.session.refresh(orm_ticket)
            logger.debug(f"Ticket moved to project: {project_id}")
            return orm_ticket_to_domain_ticket(orm_ticket)

        def update_assignee(self, ticket_id: str, assignee_id: Optional[str]) -> Optional[Ticket]:
            """Assign or unassign ticket to a user.

            Args:
                ticket_id: ID of ticket to update
                assignee_id: ID of user to assign (None to unassign)

            Returns:
                Updated Ticket if found, None otherwise
            """
            logger.debug(f"Updating ticket assignee: {ticket_id} to {assignee_id}")
            orm_ticket = self.session.query(TicketORM).filter(TicketORM.id == ticket_id).first()  # type: ignore[operator]

            if orm_ticket is None:
                logger.debug(f"Ticket not found for assignee update: {ticket_id}")
                return None

            orm_ticket.assignee_id = assignee_id  # type: ignore[assignment]
            self.session.commit()
            self.session.refresh(orm_ticket)
            logger.debug(f"Ticket assignee updated: {ticket_id}")
            return orm_ticket_to_domain_ticket(orm_ticket)

        def delete(self, ticket_id: str) -> bool:
            """Delete a ticket by ID.

            Note: This is for testing/cleanup purposes. In production, consider archival instead.
            """
            logger.debug(f"Deleting ticket: {ticket_id}")
            orm_ticket = self.session.query(TicketORM).filter(TicketORM.id == ticket_id).first()  # type: ignore[operator]
            if not orm_ticket:
                logger.debug(f"Ticket not found for deletion: {ticket_id}")
                return False

            self.session.delete(orm_ticket)
            self.session.commit()
            logger.debug(f"Ticket deleted: {ticket_id}")
            return True

    class ActivityLogs:
        """Activity log operations for audit trail."""

        def __init__(self, session: Session) -> None:
            self.session = session

        def create(self, command: ActivityLogCreateCommand) -> ActivityLog:
            """Create a new activity log entry.

            Args:
                command: Command containing activity log data

            Returns:
                Created ActivityLog domain model

            Note: Timestamp is auto-generated. Changes and metadata are serialized as JSON.
            """
            logger.debug(f"Creating activity log: {command.action} for {command.entity_type}:{command.entity_id}")

            orm_log = ActivityLogORM(
                entity_type=command.entity_type,
                entity_id=command.entity_id,
                action=command.action.value,
                actor_id=command.actor_id,
                organization_id=command.organization_id,
                changes=json.dumps(command.changes),
                extra_metadata=json.dumps(command.metadata) if command.metadata else None,
            )
            self.session.add(orm_log)
            self.session.commit()
            self.session.refresh(orm_log)
            logger.debug(f"Activity log created with ID: {orm_log.id}")
            return orm_activity_log_to_domain_activity_log(orm_log)

        def get_by_id(self, log_id: str) -> Optional[ActivityLog]:
            """Get a specific activity log by ID.

            Args:
                log_id: Activity log ID

            Returns:
                ActivityLog if found, None otherwise
            """
            logger.debug(f"Retrieving activity log by ID: {log_id}")
            orm_log = self.session.query(ActivityLogORM).filter(ActivityLogORM.id == log_id).first()  # type: ignore[operator]
            if orm_log is None:
                logger.debug(f"Activity log not found: {log_id}")
                return None
            logger.debug(f"Activity log found: {log_id}")
            return orm_activity_log_to_domain_activity_log(orm_log)

        def list(
            self,
            entity_type: Optional[str] = None,
            entity_id: Optional[str] = None,
            actor_id: Optional[str] = None,
            action: Optional[ActionType] = None,
            from_date: Optional[datetime] = None,
            to_date: Optional[datetime] = None,
            organization_id: Optional[str] = None,
            order: str = "asc",
        ) -> List[ActivityLog]:
            """List activity logs with optional filtering.

            Args:
                entity_type: Filter by entity type (e.g., "ticket", "project")
                entity_id: Filter by specific entity ID
                actor_id: Filter by user who performed action
                action: Filter by action type
                from_date: Filter logs after this timestamp (inclusive)
                to_date: Filter logs before this timestamp (inclusive)
                organization_id: Filter by organization
                order: "asc" for oldest first (default), "desc" for newest first

            Returns:
                List of ActivityLog entries matching filters, ordered by timestamp
            """
            logger.debug(f"Listing activity logs with filters: entity_type={entity_type}, entity_id={entity_id}")

            query = self.session.query(ActivityLogORM)

            # Apply filters
            if entity_type is not None:
                query = query.filter(ActivityLogORM.entity_type == entity_type)  # type: ignore[operator]
            if entity_id is not None:
                query = query.filter(ActivityLogORM.entity_id == entity_id)  # type: ignore[operator]
            if actor_id is not None:
                query = query.filter(ActivityLogORM.actor_id == actor_id)  # type: ignore[operator]
            if action is not None:
                query = query.filter(ActivityLogORM.action == action.value)  # type: ignore[operator]
            if from_date is not None:
                query = query.filter(ActivityLogORM.timestamp >= from_date)  # type: ignore[operator]
            if to_date is not None:
                query = query.filter(ActivityLogORM.timestamp <= to_date)  # type: ignore[operator]
            if organization_id is not None:
                query = query.filter(ActivityLogORM.organization_id == organization_id)  # type: ignore[operator]

            # Apply ordering
            if order == "desc":
                query = query.order_by(ActivityLogORM.timestamp.desc())  # type: ignore[union-attr]
            else:
                query = query.order_by(ActivityLogORM.timestamp.asc())  # type: ignore[union-attr]

            orm_logs = query.all()
            logger.debug(f"Found {len(orm_logs)} activity logs")
            return orm_activity_logs_to_domain_activity_logs(orm_logs)

    class Comments:
        """Comment-related data access operations."""

        def __init__(self, session: Session) -> None:
            self.session = session

        def create(self, comment_create_command: CommentCreateCommand, author_id: str) -> Comment:
            """Create a new comment.

            Args:
                comment_create_command: Command containing comment data and ticket_id
                author_id: ID of the user creating this comment (current user)

            Returns:
                Created Comment domain model
            """
            comment_data = comment_create_command.comment_data
            logger.debug(f"Creating new comment on ticket: {comment_create_command.ticket_id}")

            orm_comment = CommentORM(
                ticket_id=comment_create_command.ticket_id,
                author_id=author_id,
                content=comment_data.content,
            )

            self.session.add(orm_comment)
            self.session.commit()
            self.session.refresh(orm_comment)
            logger.debug(f"Comment created with ID: {orm_comment.id}")
            return orm_comment_to_domain_comment(orm_comment)

        def get_by_id(self, comment_id: str) -> Optional[Comment]:
            """Get a specific comment by ID."""
            logger.debug(f"Retrieving comment by ID: {comment_id}")
            orm_comment = self.session.query(CommentORM).filter(CommentORM.id == comment_id).first()  # type: ignore[operator]
            if orm_comment is None:
                logger.debug(f"Comment not found: {comment_id}")
                return None
            logger.debug(f"Comment found: {comment_id}")
            return orm_comment_to_domain_comment(orm_comment)

        def get_by_ticket_id(self, ticket_id: str) -> List[Comment]:
            """Get all comments for a specific ticket, ordered chronologically (oldest first).

            Args:
                ticket_id: ID of the ticket

            Returns:
                List of comments ordered by created_at (oldest first)
            """
            logger.debug(f"Retrieving comments for ticket: {ticket_id}")
            orm_comments = (
                self.session.query(CommentORM)
                .filter(CommentORM.ticket_id == ticket_id)  # type: ignore[operator]
                .order_by(CommentORM.created_at)  # type: ignore[union-attr]
                .all()
            )
            return [orm_comment_to_domain_comment(comment) for comment in orm_comments]

        def update(self, comment_id: str, update_command: CommentUpdateCommand) -> Optional[Comment]:
            """Update an existing comment's content.

            Args:
                comment_id: ID of comment to update
                update_command: Command containing new content

            Returns:
                Updated Comment if found, None otherwise
            """
            logger.debug(f"Updating comment: {comment_id}")
            orm_comment = self.session.query(CommentORM).filter(CommentORM.id == comment_id).first()  # type: ignore[operator]

            if orm_comment is None:
                logger.debug(f"Comment not found for update: {comment_id}")
                return None

            # Update content
            orm_comment.content = update_command.content  # type: ignore[assignment]

            self.session.commit()
            self.session.refresh(orm_comment)
            logger.debug(f"Comment updated: {comment_id}")
            return orm_comment_to_domain_comment(orm_comment)

        def delete(self, comment_id: str) -> bool:
            """Delete a comment.

            Args:
                comment_id: ID of comment to delete

            Returns:
                True if deleted, False if not found
            """
            logger.debug(f"Deleting comment: {comment_id}")
            orm_comment = self.session.query(CommentORM).filter(CommentORM.id == comment_id).first()  # type: ignore[operator]

            if orm_comment is None:
                logger.debug(f"Comment not found for deletion: {comment_id}")
                return False

            self.session.delete(orm_comment)
            self.session.commit()
            logger.debug(f"Comment deleted: {comment_id}")
            return True

    class StubEntities:
        """Stub entity operations - template/scaffolding for reference."""

        def __init__(self, session: Session) -> None:
            self.session = session

        def get_all(self) -> List[StubEntity]:
            """Get all stub entities from the database, ordered by creation date."""
            orm_stub_entities = self.session.query(StubEntityORM).order_by(StubEntityORM.created_at).all()  # type: ignore[union-attr]
            return orm_stub_entities_to_business_stub_entities(orm_stub_entities)

        def get_by_id(self, stub_entity_id: str) -> Optional[StubEntity]:
            """Get a specific stub entity by ID."""
            logger.debug(f"Retrieving stub entity by ID: {stub_entity_id}")
            orm_stub_entity = self.session.query(StubEntityORM).filter(StubEntityORM.id == stub_entity_id).first()  # type: ignore[operator]
            if orm_stub_entity is None:
                logger.debug(f"Stub entity not found: {stub_entity_id}")
                return None
            logger.debug(f"Stub entity found: {stub_entity_id}")
            return orm_stub_entity_to_business_stub_entity(orm_stub_entity)

        def _get_orm_by_id(self, stub_entity_id: str) -> Optional[StubEntityORM]:
            """Get a specific stub entity by ID as ORM object (for internal use)."""
            logger.debug(f"Retrieving ORM stub entity by ID: {stub_entity_id}")
            return self.session.query(StubEntityORM).filter(StubEntityORM.id == stub_entity_id).first()  # type: ignore[operator]

        def create(self, stub_entity_create_command: StubEntityCreateCommand) -> StubEntity:
            """Create a new stub entity."""
            stub_entity_data = stub_entity_create_command.stub_entity_data
            logger.debug(f"Creating new stub entity: {stub_entity_data.name}")

            orm_stub_entity = StubEntityORM(
                name=stub_entity_data.name,
                description=stub_entity_data.description,
            )
            self.session.add(orm_stub_entity)
            self.session.commit()
            self.session.refresh(orm_stub_entity)
            logger.debug(f"Stub entity created with ID: {orm_stub_entity.id}")
            return orm_stub_entity_to_business_stub_entity(orm_stub_entity)

        def update(self, stub_entity_id: str, stub_entity_data: StubEntityUpdateCommand) -> Optional[StubEntity]:
            """Update an existing stub entity."""
            logger.debug(f"Updating stub entity: {stub_entity_id}")
            stub_entity = self._get_orm_by_id(stub_entity_id)
            if not stub_entity:
                logger.debug(f"Stub entity not found for update: {stub_entity_id}")
                return None

            # Update only the fields that are provided and not None
            update_data = stub_entity_data.model_dump(exclude_unset=True, exclude_none=True)
            if update_data:  # Only proceed if there are fields to update
                for field, value in update_data.items():
                    self.session.query(StubEntityORM).filter(StubEntityORM.id == stub_entity_id).update({field: value})  # type: ignore[operator]

            self.session.commit()
            self.session.refresh(stub_entity)
            logger.debug(f"Stub entity updated: {stub_entity_id}")
            return orm_stub_entity_to_business_stub_entity(stub_entity)

        def delete(self, stub_entity_id: str) -> bool:
            """Delete a stub entity by ID."""
            logger.debug(f"Deleting stub entity: {stub_entity_id}")
            stub_entity = self._get_orm_by_id(stub_entity_id)
            if not stub_entity:
                logger.debug(f"Stub entity not found for deletion: {stub_entity_id}")
                return False

            self.session.delete(stub_entity)
            self.session.commit()
            logger.debug(f"Stub entity deleted: {stub_entity_id}")
            return True

    class Workflows:
        """Workflow-related data access operations."""

        def __init__(self, session: Session) -> None:
            self.session = session

        def create(self, workflow_create_command: WorkflowCreateCommand) -> Workflow:
            """Create a new workflow.

            Args:
                workflow_create_command: Command containing workflow data and organization_id

            Returns:
                Created Workflow domain model

            Raises:
                ValueError: If attempting to create a second default workflow for the organization
            """
            workflow_data = workflow_create_command.workflow_data
            organization_id = workflow_create_command.organization_id
            logger.debug(f"Creating new workflow: {workflow_data.name} for organization {organization_id}")

            # If this is a default workflow, ensure no other default exists for this org
            # Note: is_default is always False for workflows created through WorkflowCreateCommand
            # Default workflows are created automatically when organizations are created

            orm_workflow = WorkflowORM(
                name=workflow_data.name,
                description=workflow_data.description,
                statuses=json.dumps(workflow_data.statuses),  # Serialize list to JSON
                organization_id=organization_id,
                is_default=False,  # User-created workflows are never default
            )
            self.session.add(orm_workflow)
            self.session.commit()
            self.session.refresh(orm_workflow)
            logger.debug(f"Workflow created with ID: {orm_workflow.id}")
            return orm_workflow_to_domain_workflow(orm_workflow)

        def get_by_id(self, workflow_id: str) -> Optional[Workflow]:
            """Get a workflow by ID.

            Args:
                workflow_id: The workflow ID to retrieve

            Returns:
                Workflow if found, None otherwise
            """
            logger.debug(f"Retrieving workflow by ID: {workflow_id}")
            orm_workflow = self.session.query(WorkflowORM).filter(WorkflowORM.id == workflow_id).first()  # type: ignore[operator]
            if orm_workflow is None:
                logger.debug(f"Workflow not found: {workflow_id}")
                return None
            logger.debug(f"Workflow found: {workflow_id}")
            return orm_workflow_to_domain_workflow(orm_workflow)

        def _get_orm_by_id(self, workflow_id: str) -> Optional[WorkflowORM]:
            """Get a workflow by ID as ORM object (for internal use).

            Args:
                workflow_id: The workflow ID to retrieve

            Returns:
                WorkflowORM if found, None otherwise
            """
            logger.debug(f"Retrieving ORM workflow by ID: {workflow_id}")
            return self.session.query(WorkflowORM).filter(WorkflowORM.id == workflow_id).first()  # type: ignore[operator]

        def get_by_organization_id(self, organization_id: str) -> List[Workflow]:
            """Get all workflows for an organization.

            Args:
                organization_id: The organization ID

            Returns:
                List of workflows in the organization (including default)
            """
            logger.debug(f"Retrieving workflows for organization: {organization_id}")
            orm_workflows = (
                self.session.query(WorkflowORM)
                .filter(WorkflowORM.organization_id == organization_id)  # type: ignore[operator]
                .order_by(WorkflowORM.created_at.desc())  # type: ignore[union-attr]
                .all()
            )
            return orm_workflows_to_domain_workflows(orm_workflows)

        def get_all(self) -> List[Workflow]:
            """Get all workflows (for Super Admin).

            Returns:
                List of all workflows across all organizations
            """
            logger.debug("Retrieving all workflows")
            orm_workflows = self.session.query(WorkflowORM).order_by(WorkflowORM.created_at.desc()).all()  # type: ignore[union-attr]
            return orm_workflows_to_domain_workflows(orm_workflows)

        def get_default_workflow(self, organization_id: str) -> Optional[Workflow]:
            """Get the default workflow for an organization.

            Args:
                organization_id: The organization ID

            Returns:
                Default workflow if exists, None otherwise
            """
            logger.debug(f"Retrieving default workflow for organization: {organization_id}")
            orm_workflow = (
                self.session.query(WorkflowORM)
                .filter(WorkflowORM.organization_id == organization_id, WorkflowORM.is_default == True)  # type: ignore[operator]  # noqa: E712
                .first()
            )
            if orm_workflow is None:
                logger.debug(f"No default workflow found for organization: {organization_id}")
                return None
            return orm_workflow_to_domain_workflow(orm_workflow)

        def create_default_workflow(self, organization_id: str) -> Workflow:
            """Create default workflow for an organization.

            This is used during organization creation to set up the default TODO/IN_PROGRESS/DONE workflow.

            Args:
                organization_id: The organization ID

            Returns:
                Created default workflow

            Raises:
                IntegrityError: If default workflow already exists for this organization
            """
            logger.debug(f"Creating default workflow for organization: {organization_id}")

            # Check if default workflow already exists
            existing_default = self.get_default_workflow(organization_id)
            if existing_default:
                raise ValueError(f"Default workflow already exists for organization {organization_id}")

            orm_workflow = WorkflowORM(
                name="Default Workflow",
                description="Standard workflow with TODO, IN_PROGRESS, and DONE statuses",
                statuses=json.dumps(["TODO", "IN_PROGRESS", "DONE"]),
                organization_id=organization_id,
                is_default=True,
            )
            self.session.add(orm_workflow)
            self.session.commit()
            self.session.refresh(orm_workflow)
            logger.debug(f"Default workflow created with ID: {orm_workflow.id}")
            return orm_workflow_to_domain_workflow(orm_workflow)

        def update(self, workflow_id: str, update_command: WorkflowUpdateCommand) -> Optional[Workflow]:
            """Update an existing workflow.

            Args:
                workflow_id: ID of workflow to update
                update_command: Update command with fields to change

            Returns:
                Updated workflow if found, None otherwise

            Note: is_default cannot be changed through update
            """
            logger.debug(f"Updating workflow: {workflow_id}")
            workflow = self._get_orm_by_id(workflow_id)
            if not workflow:
                logger.debug(f"Workflow not found for update: {workflow_id}")
                return None

            # Update only the fields that are provided and not None
            update_data = update_command.model_dump(exclude_unset=True, exclude_none=True)
            if update_data:
                # Special handling for statuses (needs JSON serialization)
                if "statuses" in update_data:
                    update_data["statuses"] = json.dumps(update_data["statuses"])

                for field, value in update_data.items():
                    setattr(workflow, field, value)

            self.session.commit()
            self.session.refresh(workflow)
            logger.debug(f"Workflow updated: {workflow_id}")
            return orm_workflow_to_domain_workflow(workflow)

        def delete(self, workflow_id: str) -> bool:
            """Delete a workflow.

            Args:
                workflow_id: ID of workflow to delete

            Returns:
                True if deleted, False if not found

            Note: Caller should verify workflow is not in use before calling this
            """
            logger.debug(f"Deleting workflow: {workflow_id}")
            workflow = self._get_orm_by_id(workflow_id)
            if not workflow:
                logger.debug(f"Workflow not found for deletion: {workflow_id}")
                return False

            self.session.delete(workflow)
            self.session.commit()
            logger.debug(f"Workflow deleted: {workflow_id}")
            return True

        def check_status_usage(self, workflow_id: str, statuses_to_check: List[str]) -> List[str]:
            """Check which of the given statuses are currently used by tickets in projects using this workflow.

            Args:
                workflow_id: ID of workflow being updated
                statuses_to_check: List of status strings to check for usage

            Returns:
                List of statuses that are currently in use by tickets
            """
            logger.debug(f"Checking status usage for workflow {workflow_id}: {statuses_to_check}")

            # Find all projects using this workflow
            from project_management_crud_example.dal.sqlite.orm_data_models import ProjectORM, TicketORM

            projects = self.session.query(ProjectORM).filter(ProjectORM.workflow_id == workflow_id).all()  # type: ignore[operator]

            if not projects:
                logger.debug(f"No projects use workflow {workflow_id}")
                return []

            project_ids = [str(p.id) for p in projects]

            # Check which statuses are used by tickets in these projects
            used_statuses = set()
            for status_to_check in statuses_to_check:
                # Query tickets in these projects with this status
                ticket_count = (
                    self.session.query(TicketORM)
                    .filter(TicketORM.project_id.in_(project_ids))  # type: ignore[operator, attr-defined]
                    .filter(TicketORM.status == status_to_check)  # type: ignore[operator]
                    .count()
                )
                if ticket_count > 0:
                    logger.debug(f"Status '{status_to_check}' is used by {ticket_count} tickets")
                    used_statuses.add(status_to_check)

            result = list(used_statuses)
            logger.debug(f"Statuses in use: {result}")
            return result


# Legacy classes kept for backward compatibility with existing tests
# TODO: Remove once all tests are migrated to use Repository class


class StubEntityRepository:
    """Legacy wrapper for backward compatibility with existing tests."""

    def __init__(self, session: Session) -> None:
        self._repo = Repository(session).stub_entities

    def get_all_stub_entities(self) -> List[StubEntity]:
        return self._repo.get_all()

    def get_stub_entity_by_id(self, stub_entity_id: str) -> Optional[StubEntity]:
        return self._repo.get_by_id(stub_entity_id)

    def create_stub_entity(self, command: StubEntityCreateCommand) -> StubEntity:
        return self._repo.create(command)

    def update_stub_entity(self, stub_entity_id: str, update_data: StubEntityUpdateCommand) -> Optional[StubEntity]:
        return self._repo.update(stub_entity_id, update_data)

    def delete_stub_entity(self, stub_entity_id: str) -> bool:
        return self._repo.delete(stub_entity_id)


class UserRepository:
    """Legacy wrapper for backward compatibility with existing tests."""

    def __init__(self, session: Session) -> None:
        self._repo = Repository(session).users

    def create_user(self, command: UserCreateCommand) -> User:
        return self._repo.create(command)

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        return self._repo.get_by_id(user_id)

    def get_user_by_username(self, username: str) -> Optional[User]:
        return self._repo.get_by_username(username)

    def get_all_users(self) -> List[User]:
        return self._repo.get_all()

    def delete_user(self, user_id: str) -> bool:
        return self._repo.delete(user_id)
