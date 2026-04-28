"""FastAPI application for project management backend service.

This module sets up the main FastAPI application with database initialization,
CORS middleware, dependency injection, and core endpoints.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from project_management_crud_example.capabilities import (
    CapabilityNotFoundError,
    CapabilityPermissionError,
    PasswordChangeError,
)
from project_management_crud_example.dependencies import get_database
from project_management_crud_example.exceptions import AuthHTTPException
from project_management_crud_example.middleware.e2e_tracing import E2eTracingMiddleware
from project_management_crud_example.routers import (
    activity_log_api,
    auth_api,
    comment_api,
    e2e_api,
    epic_api,
    health,
    organization_api,
    project_api,
    stub_entity_api,
    ticket_api,
    user_api,
    workflow_api,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifespan events."""
    # Wipe the E2E DB on startup so the bootstrap admin gets re-seeded with
    # the fast TestPasswordHasher (otherwise a stale bcrypt-hashed admin from
    # a prior non-E2E run would fail to verify against SHA256). Production
    # paths untouched.
    if os.getenv("E2E_TESTING") == "true":
        from project_management_crud_example.dependencies import _get_db_path
        e2e_db_path = _get_db_path()
        if os.path.exists(e2e_db_path):
            logger.info(f"E2E mode: removing stale DB at {e2e_db_path}")
            os.remove(e2e_db_path)

    # Initialize database on startup
    logger.info("Initializing database")
    db = get_database()
    db.create_tables()

    # Auto-bootstrap Super Admin for development/testing convenience
    # NOTE: This is for EXAMPLE APPLICATIONS only. In production:
    # - Never auto-bootstrap with constant passwords
    # - Use proper initialization and secrets management
    from project_management_crud_example.bootstrap_data import ensure_default_workflows, ensure_super_admin

    created, user_id = ensure_super_admin(db)
    if created:
        logger.info(f"Super Admin auto-bootstrapped (user_id={user_id})")
        logger.warning(
            "Using constant password for development. (This is for example apps only - never use in production!)"
        )
    else:
        logger.info("Super Admin already exists")

    # Ensure all organizations have default workflows
    # This is a migration for existing organizations and a safety check for consistency
    workflow_count = ensure_default_workflows(db)
    if workflow_count > 0:
        logger.info(f"Created {workflow_count} default workflow(s) for existing organizations")
    else:
        logger.info("All organizations have default workflows")

    # Bootstrap rich demo data if BOOTSTRAP_DEMO_DATA environment variable is set
    if os.getenv("BOOTSTRAP_DEMO_DATA") == "true":
        logger.info("BOOTSTRAP_DEMO_DATA=true detected - creating rich demo data...")
        from project_management_crud_example.bootstrap_rich_data import bootstrap_rich_data

        try:
            bootstrap_rich_data()
            logger.info("Rich demo data bootstrapped successfully")
        except Exception as e:
            logger.error(f"Failed to bootstrap demo data: {e}")
            # Don't crash the app, just log the error

    yield
    # Cleanup resources on shutdown if needed
    pass


app = FastAPI(
    title="Project Management API",
    description="Backend service with stub entity template/scaffolding built with FastAPI and SQLite",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,  # type: ignore[arg-type]  # FastAPI middleware typing issue
    allow_origins=["*"],  # For development only, restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(E2eTracingMiddleware)

# Include routers
app.include_router(auth_api.router)
app.include_router(user_api.router)
app.include_router(organization_api.router)
app.include_router(project_api.router)
app.include_router(epic_api.router)
app.include_router(workflow_api.router)
app.include_router(ticket_api.router)
app.include_router(comment_api.router)
app.include_router(activity_log_api.router)
app.include_router(stub_entity_api.router)
app.include_router(e2e_api.router)  # E2E testing utilities (only available when E2E_TESTING=true)
app.include_router(health.router)


# Exception Handlers
def _make_json_serializable(obj: object) -> object:
    """Convert objects to JSON-serializable format."""
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    elif isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_make_json_serializable(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        # For any other type (like ValueError, Exception, etc.), convert to string
        return str(obj)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle validation errors with detailed error information."""
    logger.warning(f"Validation error on {request.method} {request.url}: {exc.errors()}")

    # Convert the errors to a JSON-serializable format
    errors = []
    for error in exc.errors():
        # Ensure all values are JSON serializable
        json_error = _make_json_serializable(error)
        errors.append(json_error)

    return JSONResponse(
        status_code=422,
        content={"detail": errors},
    )


@app.exception_handler(CapabilityPermissionError)
async def capability_permission_handler(request: Request, exc: CapabilityPermissionError) -> JSONResponse:
    """Map CapabilityPermissionError to HTTP 403 with standard envelope."""
    logger.warning(f"Capability permission denied on {request.method} {request.url}: {exc.detail}")
    return JSONResponse(status_code=403, content={"detail": exc.detail})


@app.exception_handler(CapabilityNotFoundError)
async def capability_not_found_handler(request: Request, exc: CapabilityNotFoundError) -> JSONResponse:
    """Map CapabilityNotFoundError to HTTP 404 with standard envelope."""
    logger.info(f"Capability target not found on {request.method} {request.url}: {exc.detail}")
    return JSONResponse(status_code=404, content={"detail": exc.detail})


@app.exception_handler(PasswordChangeError)
async def password_change_error_handler(request: Request, exc: PasswordChangeError) -> JSONResponse:
    """Map PasswordChangeError (invalid new password, persistence failure) to HTTP 400."""
    logger.warning(f"Password change rejected on {request.method} {request.url}: {exc.detail}")
    return JSONResponse(status_code=400, content={"detail": exc.detail})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions with consistent error format.

    For AuthHTTPException instances, includes error_code in the response.
    """
    logger.warning(f"HTTP error on {request.method} {request.url}: {exc.status_code} - {exc.detail}")

    content = {"detail": exc.detail}
    # Include error_code if present (for AuthHTTPException)
    if isinstance(exc, AuthHTTPException):
        content["error_code"] = exc.error_code

    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # pragma: no cover
    """Handle unexpected exceptions with generic error response."""
    logger.error(f"Unexpected error on {request.method} {request.url}: {type(exc).__name__}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
