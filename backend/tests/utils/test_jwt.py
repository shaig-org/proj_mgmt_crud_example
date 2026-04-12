"""Tests for JWT token generation and validation."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from project_management_crud_example.config import settings
from project_management_crud_example.exceptions import InvalidTokenError, TokenExpiredError
from project_management_crud_example.utils.jwt import TokenClaims, create_access_token, decode_access_token


class TestCreateAccessToken:
    """Tests for JWT token generation."""

    def test_create_token_includes_all_claims(self) -> None:
        """Test that generated token includes all required claims."""
        token = create_access_token(
            user_id="user-123",
            organization_id="org-456",
        )

        # Decode without validation to inspect claims
        payload = jwt.decode(token, options={"verify_signature": False})

        assert "user_id" in payload
        assert "organization_id" in payload
        assert "exp" in payload
        assert "iat" in payload
        # Role is NOT in token - fetched from DB on each request
        assert "role" not in payload

    def test_create_token_for_regular_user(self) -> None:
        """Test creating token for user with organization."""
        token = create_access_token(
            user_id="user-123",
            organization_id="org-456",
        )

        payload = jwt.decode(token, options={"verify_signature": False})

        assert payload["user_id"] == "user-123"
        assert payload["organization_id"] == "org-456"

    def test_create_token_for_super_admin(self) -> None:
        """Test creating token for Super Admin without organization."""
        token = create_access_token(
            user_id="admin-123",
            organization_id=None,
        )

        payload = jwt.decode(token, options={"verify_signature": False})

        assert payload["user_id"] == "admin-123"
        assert payload["organization_id"] is None

    def test_create_token_sets_expiration(self) -> None:
        """Test that token expiration is set correctly."""
        before = datetime.now(timezone.utc).replace(microsecond=0)  # Truncate to seconds
        token = create_access_token(
            user_id="user-123",
            organization_id="org-456",
        )
        after = datetime.now(timezone.utc).replace(microsecond=0)  # Truncate to seconds

        payload = jwt.decode(token, options={"verify_signature": False})
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat_time = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)

        # Expiration should be JWT_EXPIRATION_SECONDS after issued time
        expected_lifetime = timedelta(seconds=settings.JWT_EXPIRATION_SECONDS)
        actual_lifetime = exp_time - iat_time

        assert actual_lifetime == expected_lifetime
        assert before <= iat_time <= after

    def test_create_token_is_signed(self) -> None:
        """Test that token is properly signed and can be verified."""
        token = create_access_token(
            user_id="user-123",
            organization_id="org-456",
        )

        # Should decode successfully with correct key
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        assert payload["user_id"] == "user-123"

        # Should fail with wrong key
        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(
                token,
                "wrong-secret-key",
                algorithms=[settings.JWT_ALGORITHM],
            )

    def test_multiple_tokens_can_be_created(self) -> None:
        """Test that multiple tokens can be generated and are valid."""
        token1 = create_access_token(
            user_id="user-123",
            organization_id="org-456",
        )

        token2 = create_access_token(
            user_id="user-123",
            organization_id="org-456",
        )

        # Both tokens should be valid
        assert token1  # Not empty
        assert token2  # Not empty

        # Both should decode successfully
        claims1 = decode_access_token(token1)
        claims2 = decode_access_token(token2)

        assert claims1.user_id == "user-123"
        assert claims2.user_id == "user-123"


class TestDecodeAccessToken:
    """Tests for JWT token validation and decoding."""

    def test_decode_valid_token_succeeds(self) -> None:
        """Test that valid token is decoded successfully."""
        token = create_access_token(
            user_id="user-123",
            organization_id="org-456",
        )

        claims = decode_access_token(token)

        assert isinstance(claims, TokenClaims)
        assert claims.user_id == "user-123"

    def test_decode_token_returns_correct_claims(self) -> None:
        """Test that all claims are extracted correctly."""
        token = create_access_token(
            user_id="user-123",
            organization_id="org-456",
        )

        claims = decode_access_token(token)

        assert claims.user_id == "user-123"
        assert claims.organization_id == "org-456"
        assert claims.exp > 0
        assert claims.iat > 0
        assert claims.exp > claims.iat
        # Role is NOT in claims - must be fetched from DB
        assert not hasattr(claims, "role")

    def test_decode_expired_token_raises_error(self) -> None:
        """Test that expired token raises TokenExpiredError."""
        # Manually create an expired token
        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=2)  # Expired 2 hours ago (beyond clock skew)

        payload = {
            "user_id": "user-123",
            "organization_id": "org-456",
            "exp": int(past.timestamp()),
            "iat": int((past - timedelta(hours=1)).timestamp()),
        }

        expired_token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

        with pytest.raises(TokenExpiredError) as exc_info:
            decode_access_token(expired_token)

        assert "expired" in str(exc_info.value).lower()

    def test_decode_invalid_signature_raises_error(self) -> None:
        """Test that token with wrong signature raises InvalidTokenError."""
        token = create_access_token(
            user_id="user-123",
            organization_id="org-456",
        )

        # Manually create token with wrong signature
        payload = jwt.decode(token, options={"verify_signature": False})
        bad_token = jwt.encode(payload, "wrong-secret", algorithm=settings.JWT_ALGORITHM)

        with pytest.raises(InvalidTokenError):
            decode_access_token(bad_token)

    def test_decode_malformed_token_raises_error(self) -> None:
        """Test that malformed token raises InvalidTokenError."""
        malformed_tokens = [
            "not-a-token",
            "invalid.token.format",
            "",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid",  # Invalid payload
        ]

        for bad_token in malformed_tokens:
            with pytest.raises(InvalidTokenError):
                decode_access_token(bad_token)

    def test_decode_token_with_clock_skew(self) -> None:
        """Test that recently expired token within skew tolerance is accepted."""
        # Manually create token that expired recently (within clock skew)
        now = datetime.now(timezone.utc)
        recent_past = now - timedelta(seconds=10)  # Expired 10 seconds ago (within 5min skew)

        payload = {
            "user_id": "user-123",
            "organization_id": "org-456",
            "exp": int(recent_past.timestamp()),
            "iat": int((recent_past - timedelta(hours=1)).timestamp()),
        }

        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        # Should still be valid within clock skew tolerance (5 minutes default)
        claims = decode_access_token(token)
        assert claims.user_id == "user-123"

    def test_decode_token_with_null_organization(self) -> None:
        """Test that Super Admin token with null organization is handled."""
        token = create_access_token(
            user_id="admin-123",
            organization_id=None,
        )

        claims = decode_access_token(token)

        assert claims.user_id == "admin-123"
        assert claims.organization_id is None
