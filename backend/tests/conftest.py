"""Pytest configuration and shared fixtures."""

import os

# CRITICAL: Set test environment variables BEFORE any project imports
# These must be set before the config module is loaded
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only-not-for-production")
os.environ.setdefault("BCRYPT_ROUNDS", "4")  # Minimal bcrypt hashing for fast tests (4 is minimum, 12 default = ~300ms)

import tempfile
from pathlib import Path
from typing import Generator

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from project_management_crud_example.app import app
from project_management_crud_example.dal.sqlite.database import Database
from project_management_crud_example.dal.sqlite.repository import Repository, StubEntityRepository, UserRepository
from project_management_crud_example.dependencies import get_db_session, get_repository
from project_management_crud_example.utils.password import TestPasswordHasher


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command line options."""
    parser.addoption(
        "--db-mode",
        action="store",
        default="disk",
        choices=["memory", "disk"],
        help="Database mode: 'memory' for in-memory SQLite, 'disk' for file-based (default: disk)",
    )


@pytest.fixture
def db_path(request: pytest.FixtureRequest) -> Generator[str, None, None]:
    """Provide database path based on --db-mode parameter.

    - In 'disk' mode (default): Creates a temporary file for each test
    - In 'memory' mode: Returns ':memory:' for in-memory database

    Each test gets its own isolated database.
    """
    db_mode = request.config.getoption("--db-mode")

    if db_mode == "memory":
        yield ":memory:"
    else:
        # Create a temporary directory and file for this test
        with tempfile.TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / f"test_{request.node.name}.db"
            yield str(db_file)
            # Cleanup happens automatically when temp_dir context exits


@pytest.fixture
def test_db(db_path: str) -> Generator[Database, None, None]:
    """Create a fresh database for each test.

    This fixture ensures each test gets a completely isolated database
    that is automatically cleaned up after the test completes.
    Uses disk-based SQLite by default (respects --db-mode parameter).
    """
    db = Database(db_path, is_testing=True)
    db.create_tables()
    yield db
    db.drop_tables()
    db.dispose()


@pytest.fixture
def test_session(test_db: Database) -> Generator[Session, None, None]:
    """Get a database session for testing.

    This fixture provides a database session that is automatically
    committed and closed after each test.
    """
    with test_db.get_session() as session:
        yield session


@pytest.fixture
def test_repo(test_session: Session) -> Repository:
    """Get the main repository for testing.

    This fixture provides a Repository instance connected to the test database session.
    Uses TestPasswordHasher for fast password hashing in tests.
    Access nested operations via repo.users, repo.organizations, etc.
    """
    return Repository(test_session, password_hasher=TestPasswordHasher())


@pytest.fixture
def test_stub_entity_repo(test_session: Session) -> StubEntityRepository:
    """Get a stub entity repository for testing.

    LEGACY: For backward compatibility with existing tests.
    New tests should use test_repo fixture instead.
    """
    return StubEntityRepository(test_session)


@pytest.fixture
def test_user_repo(test_session: Session) -> UserRepository:
    """Get a user repository for testing.

    LEGACY: For backward compatibility with existing tests.
    New tests should use test_repo fixture instead.
    """
    return UserRepository(test_session)


@pytest.fixture
def client(test_db: Database) -> Generator[TestClient, None, None]:
    """Standardized FastAPI TestClient fixture for all API tests.

    - Ensures every test gets a fresh, isolated database (disk-based by default).
    - Overrides the get_db_session and get_repository dependencies to use test database with fast password hashing.
    - Cleans up dependency overrides after each test to prevent leakage.
    - All API tests MUST use this fixture for client access.
    """

    def override_get_db_session() -> Generator[Session, None, None]:
        with test_db.get_session() as session:
            yield session

    def override_get_repository(session: Session = Depends(override_get_db_session)) -> Repository:  # noqa: B008
        return Repository(session, password_hasher=TestPasswordHasher())

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_repository] = override_get_repository

    with TestClient(app) as test_client:
        yield test_client

    # Reset dependency overrides to prevent test interference
    app.dependency_overrides = {}
