"""Custom exceptions for the application."""

from typing import Any, Dict, Optional

from fastapi import HTTPException, status


class TokenExpiredError(Exception):
    """Raised when a JWT token has expired."""

    pass


class InvalidTokenError(Exception):
    """Raised when a JWT token is invalid or malformed."""

    pass


# HTTP Exceptions with structured error responses


class AuthHTTPException(HTTPException):
    """Base class for authentication HTTP exceptions with error codes."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str,
        headers: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code


class InvalidCredentialsException(AuthHTTPException):
    """Raised when login credentials are invalid."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            error_code="INVALID_CREDENTIALS",
        )


class AccountInactiveException(AuthHTTPException):
    """Raised when user account is inactive."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account inactive",
            error_code="ACCOUNT_INACTIVE",
        )


class AuthenticationRequiredException(AuthHTTPException):
    """Raised when no authentication token is provided."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            error_code="AUTHENTICATION_REQUIRED",
            headers={"WWW-Authenticate": "Bearer"},
        )


class TokenExpiredException(AuthHTTPException):
    """Raised when token has expired (HTTP version)."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            error_code="TOKEN_EXPIRED",
            headers={"WWW-Authenticate": "Bearer"},
        )


class InvalidTokenException(AuthHTTPException):
    """Raised when token is invalid (HTTP version)."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            error_code="INVALID_TOKEN",
            headers={"WWW-Authenticate": "Bearer"},
        )


class InsufficientPermissionsException(AuthHTTPException):
    """Raised when user lacks required permissions for an action."""

    def __init__(self, detail: str = "Insufficient permissions") -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code="INSUFFICIENT_PERMISSIONS",
        )
