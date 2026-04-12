"""JWT token generation and validation utilities."""

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from pydantic import BaseModel

from project_management_crud_example.config import settings
from project_management_crud_example.exceptions import InvalidTokenError, TokenExpiredError


class TokenClaims(BaseModel):
    """Structured token claims extracted from JWT.

    Note: Role is NOT included in the token. Role must be fetched from the database
    on each request to ensure immediate effect of permission changes and user deactivation.
    """

    user_id: str
    organization_id: Optional[str]
    exp: int  # Expiration timestamp
    iat: int  # Issued at timestamp


def create_access_token(
    user_id: str,
    organization_id: Optional[str],
) -> str:
    """Generate a JWT access token with user claims.

    Args:
        user_id: ID of the user
        organization_id: User's organization ID (None for Super Admin)

    Returns:
        JWT token string

    The token includes:
    - user_id: User identifier
    - organization_id: Organization identifier (or None)
    - exp: Expiration timestamp (iat + configured expiration)
    - iat: Issued at timestamp

    Note: Role is NOT stored in the token. It must be fetched from the database
    to ensure permission changes take effect immediately.
    """
    now = datetime.now(timezone.utc)
    expiration = now + timedelta(seconds=settings.JWT_EXPIRATION_SECONDS)

    payload = {
        "user_id": user_id,
        "organization_id": organization_id,
        "exp": int(expiration.timestamp()),
        "iat": int(now.timestamp()),
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    return token


def decode_access_token(token: str) -> TokenClaims:
    """Validate and decode a JWT access token.

    Args:
        token: JWT token string

    Returns:
        TokenClaims with decoded user information (role must be fetched separately)

    Raises:
        TokenExpiredError: Token has expired
        InvalidTokenError: Token is invalid, malformed, or has invalid signature

    Clock skew tolerance is applied per configuration (default 5 minutes).
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            leeway=timedelta(seconds=settings.JWT_CLOCK_SKEW_SECONDS),
        )

        return TokenClaims(
            user_id=payload["user_id"],
            organization_id=payload.get("organization_id"),
            exp=payload["exp"],
            iat=payload["iat"],
        )

    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("Token has expired") from e
    except (jwt.InvalidTokenError, jwt.DecodeError, KeyError, ValueError) as e:
        raise InvalidTokenError("Invalid or malformed token") from e
