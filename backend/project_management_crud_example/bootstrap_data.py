"""Bootstrap data utilities for development and testing.

This module provides utilities for bootstrapping the application with initial data,
including the Super Admin user and test data.

IMPORTANT: This is for EXAMPLE/DEVELOPMENT purposes only.
In production applications:
- Never use constant passwords
- Never auto-bootstrap on startup
- Use proper secrets management and secure initialization
"""

from project_management_crud_example.config import get_settings
from project_management_crud_example.dal.sqlite.database import Database
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.utils.password import PasswordHasher, TestPasswordHasher

# CONSTANT PASSWORD FOR EXAMPLE APPLICATION
# WARNING: This is a constant password for development/testing convenience only.
# This makes the example application easy to use and test, but should NEVER
# be done in production applications. In production, use secure password
# generation and proper secrets management.
SUPER_ADMIN_PASSWORD = "SuperAdmin123!"


def ensure_super_admin(db: Database) -> tuple[bool, str | None]:
    """Ensure Super Admin user exists, creating if needed.

    This function checks if a Super Admin exists and creates one with a constant
    password if not found. This is for EXAMPLE APPLICATION purposes only.

    Args:
        db: Database instance to use

    Returns:
        Tuple of (created: bool, user_id: str | None)
        - created: True if Super Admin was created, False if already exists
        - user_id: User ID if created, None if already exists

    Example:
        >>> db = Database("app.db")
        >>> db.create_tables()
        >>> created, user_id = ensure_super_admin(db)
        >>> if created:
        ...     print(f"Super Admin created: {user_id}")

    Note:
        Uses constant password SUPER_ADMIN_PASSWORD for development convenience.
        See module docstring for important security warnings.
    """
    settings = get_settings()

    with db.get_session() as session:
        # Use fast test hasher in testing mode, secure hasher in production
        password_hasher = TestPasswordHasher() if db.is_testing else PasswordHasher(is_secure=True)
        repo = Repository(session, password_hasher=password_hasher)

        created, user = repo.users.create_super_admin_if_needed(
            username=settings.BOOTSTRAP_ADMIN_USERNAME,
            email=settings.BOOTSTRAP_ADMIN_EMAIL,
            full_name=settings.BOOTSTRAP_ADMIN_FULL_NAME,
            password=SUPER_ADMIN_PASSWORD,
        )

        if created and user:
            return True, user.id
        return False, None


def ensure_default_workflows(db: Database) -> int:
    """Ensure all organizations have default workflows, creating if needed.

    This function checks all organizations and creates default workflows for any
    that don't have one. This is useful for migrations and ensuring consistency.

    Args:
        db: Database instance to use

    Returns:
        Number of default workflows created

    Example:
        >>> db = Database("app.db")
        >>> db.create_tables()
        >>> count = ensure_default_workflows(db)
        >>> print(f"Created {count} default workflows")

    Note:
        This is idempotent - it won't create duplicate default workflows.
    """
    with db.get_session() as session:
        # Use fast test hasher in testing mode (workflows don't need it, but repo requires it)
        password_hasher = TestPasswordHasher() if db.is_testing else PasswordHasher(is_secure=True)
        repo = Repository(session, password_hasher=password_hasher)

        # Get all organizations
        organizations = repo.organizations.get_all()

        created_count = 0
        for org in organizations:
            # Check if organization already has a default workflow
            existing_default = repo.workflows.get_default_workflow(org.id)
            if existing_default:
                continue

            # Create default workflow for this organization
            try:
                repo.workflows.create_default_workflow(org.id)
                created_count += 1
            except Exception as e:
                # Log but continue with other organizations
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Failed to create default workflow for organization {org.id}: {e}")

        return created_count
