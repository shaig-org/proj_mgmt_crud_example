"""API result wrapper for type-safe test responses."""

from dataclasses import dataclass
from typing import Generic, TypeVar

from httpx import Response

T = TypeVar("T")


@dataclass
class APIResult(Generic[T]):
    """Wrapper for API response with optional parsed data.

    This class provides a type-safe wrapper around HTTP responses that includes
    both the raw response and parsed domain model data.

    Attributes:
        status_code: HTTP status code
        raw_response: Raw TestClient Response object
        data: Parsed Pydantic model (None if error or not applicable)
        error: Error message from response detail (None if success)

    Example:
        # Happy path - assert success and get data
        user = result.assert_ok()

        # Validation testing - check specific error
        assert result.status_code == 400
        assert "inactive" in result.error.lower()

        # Flexible checking
        if result.ok:
            user = result.data
        else:
            print(f"Failed: {result.error}")
    """

    status_code: int
    raw_response: Response
    data: T | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        """True if status code is 2xx (success)."""
        return 200 <= self.status_code < 300

    def assert_ok(self) -> T:
        """Assert success and return data, or raise AssertionError.

        Returns:
            Parsed data (Pydantic model)

        Raises:
            AssertionError: If status code is not 2xx

        Example:
            user = sdk.users.get(user_id).assert_ok()
        """
        if not self.ok:
            raise AssertionError(f"Expected 2xx status, got {self.status_code}: {self.error}")
        assert self.data is not None, "Success response should have data"
        return self.data

    def assert_status(self, expected_status: int) -> "APIResult[T]":
        """Assert specific status code.

        Args:
            expected_status: Expected HTTP status code

        Returns:
            Self for chaining

        Raises:
            AssertionError: If status code doesn't match

        Example:
            sdk.users.delete(user_id).assert_status(404)
        """
        if self.status_code != expected_status:
            raise AssertionError(f"Expected status {expected_status}, got {self.status_code}: {self.error}")
        return self

    def assert_error_contains(self, text: str) -> "APIResult[T]":
        """Assert error message contains specific text (case-insensitive).

        Args:
            text: Text to search for in error message

        Returns:
            Self for chaining

        Raises:
            AssertionError: If error doesn't contain text

        Example:
            sdk.tickets.assign(ticket_id, inactive_user).assert_error_contains("inactive")
        """
        if self.error is None:
            raise AssertionError("Expected error message, but response was successful")
        if text.lower() not in self.error.lower():
            raise AssertionError(f"Expected error to contain '{text}', got: {self.error}")
        return self
