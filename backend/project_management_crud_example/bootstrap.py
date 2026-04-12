"""CLI script for bootstrapping the application with initial data.

This script initializes the database and creates the Super Admin user if needed.
It uses a constant password for development/testing convenience.

See bootstrap_data.py for the actual bootstrap logic and important security warnings.
"""

import sys

from project_management_crud_example.bootstrap_data import SUPER_ADMIN_PASSWORD, ensure_super_admin
from project_management_crud_example.dal.sqlite.database import Database


def main() -> None:
    """CLI entry point for bootstrapping the system."""
    from project_management_crud_example.config import get_settings

    current_settings = get_settings()

    print("Bootstrapping system...")
    print()

    # Create database and initialize tables
    db = Database("stub_entities.db")
    db.create_tables()

    # Bootstrap Super Admin
    created, user_id = ensure_super_admin(db)

    if created:
        print("✓ Super Admin created successfully!")
        print()
        print("=" * 60)
        print("SUPER ADMIN CREDENTIALS")
        print("=" * 60)
        print(f"Username: {current_settings.BOOTSTRAP_ADMIN_USERNAME}")
        print(f"Email:    {current_settings.BOOTSTRAP_ADMIN_EMAIL}")
        print(f"Password: {SUPER_ADMIN_PASSWORD}")
        print("=" * 60)
        print()
        print("⚠️  NOTE: This is a constant password for development/testing.")
        print("    In production, use secure password management.")
        print()
    else:
        print("✓ Super Admin already exists, skipping creation")
        print()

    db.dispose()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBootstrap cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Bootstrap failed: {e}")
        sys.exit(1)
