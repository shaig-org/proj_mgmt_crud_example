"""SQLite database setup and connection management for the project management application.

This module provides database initialization, connection management, and session handling
for SQLite database operations in the DAL layer.
"""

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from .orm_data_models import Base


class Database:
    """Database connection and session management class."""

    def __init__(self, db_path: str, is_testing: bool = False) -> None:
        """Initialize database connection.

        Args:
            db_path: Path to database file or ':memory:' for in-memory database
            is_testing: Whether this is a test database (uses fast password hashing)
        """
        self.is_testing = is_testing

        # Convert db_path to SQLite URL
        if db_path == ":memory:":
            db_url = "sqlite:///:memory:"
        else:
            db_url = f"sqlite:///{db_path}"

        connect_args = {"check_same_thread": False}
        engine_args = {}

        if ":memory:" in db_url:
            # In-memory SQLite REQUIRES a single shared connection — each
            # connection would otherwise see its own empty :memory: DB.
            engine_args["poolclass"] = StaticPool
        elif is_testing:
            # File-based test DBs under E2E parallelism: NullPool gives each
            # request a fresh SQLite connection, side-stepping the "two
            # concurrent threads share one connection's transaction state"
            # races that StaticPool exhibits ("Organization not found" 100ms
            # after the org-create POST returned 200, etc).
            # WAL journal mode (set below) makes per-request connections
            # cheap and safe (concurrent readers + 1 writer at a time).
            engine_args["poolclass"] = NullPool

        self.engine = create_engine(db_url, connect_args=connect_args, **engine_args)

        # Enable WAL journal mode for file-based SQLite — allows concurrent
        # readers with one writer, which is what we want under E2E parallelism.
        # (Has no effect on :memory: DBs.) We do this with a one-shot PRAGMA
        # after engine creation rather than via connect_args because PRAGMA
        # journal_mode is per-database, not per-connection.
        if ":memory:" not in db_url:
            with self.engine.connect() as conn:
                conn.exec_driver_sql("PRAGMA journal_mode=WAL")
                conn.exec_driver_sql("PRAGMA busy_timeout=10000")
                conn.commit()
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def create_tables(self) -> None:
        """Create all tables defined in the models."""
        Base.metadata.create_all(bind=self.engine)

    def drop_tables(self) -> None:
        """Drop all tables - use with caution."""
        Base.metadata.drop_all(bind=self.engine)

    def dispose(self) -> None:
        """Dispose of the database engine and close all connections."""
        self.engine.dispose()

    @contextmanager
    def get_session(self) -> Iterator[Session]:
        """Get a database session with automatic closing."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
