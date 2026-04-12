"""Test data fixtures for creating organizations, projects, and tickets.

This module provides centralized fixtures for creating test data entities
used across multiple test files.
"""

import pytest

from project_management_crud_example.dal.sqlite.repository import Repository
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import create_test_org_with_workflow_via_repo


@pytest.fixture
def organization(test_repo: Repository) -> str:
    """Create a test organization with default workflow.

    Returns:
        Organization ID
    """
    org = create_test_org_with_workflow_via_repo(test_repo, name="Test Organization")
    return org.id


@pytest.fixture
def second_organization(test_repo: Repository) -> str:
    """Create a second test organization for cross-org testing with default workflow.

    Returns:
        Organization ID
    """
    org = create_test_org_with_workflow_via_repo(test_repo, name="Second Organization")
    return org.id
