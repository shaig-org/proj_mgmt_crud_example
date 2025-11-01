"""High-level test SDK for API operations.

This module provides a type-safe, domain-focused SDK for testing API operations.
The SDK wraps low-level HTTP details (URLs, headers, JSON serialization) and provides
clean, expressive methods organized by entity type.

Usage:
    # Create SDK without auth (will crash if used)
    sdk = APITestSDK(client)

    # Create authenticated SDK
    admin_sdk = sdk.with_auth(admin_token)
    admin_sdk.users.deactivate(user_id)

    # Fixture usage
    @pytest.fixture
    def admin_sdk(client: TestClient, admin_token: str) -> APITestSDK:
        return APITestSDK(client).with_auth(admin_token)
"""

from fastapi.testclient import TestClient

from project_management_crud_example.domain_models import User, UserCreateResponse
from tests.sdk.api_result import APIResult


class AuthContext:
    """Authentication context for API requests.

    This small utility class encapsulates authentication token and provides
    methods for checking auth and constructing headers. It's passed to entity
    operation classes to avoid circular dependencies with the SDK.
    """

    def __init__(self, client: TestClient, auth_token: str | None) -> None:
        """Initialize auth context.

        Args:
            client: FastAPI TestClient
            auth_token: Optional authentication token
        """
        self.client = client
        self._token = auth_token

    def check_auth(self) -> str:
        """Check that auth token is set and return it.

        Returns:
            Authentication token

        Raises:
            RuntimeError: If no auth token is set
        """
        if self._token is None:
            raise RuntimeError(
                "No authentication token set. Use sdk.with_auth(token) to create an authenticated SDK instance."
            )
        return self._token

    def headers(self) -> dict[str, str]:
        """Get authorization headers for API requests.

        Returns:
            Dictionary with Authorization header

        Raises:
            RuntimeError: If no auth token is set (via check_auth)
        """
        return {"Authorization": f"Bearer {self.check_auth()}"}


class APITestSDK:
    """High-level test SDK for API operations.

    This SDK provides type-safe, domain-focused methods for testing API operations.
    It organizes operations by entity type (users, tickets, projects, etc.) and
    handles low-level HTTP details internally.

    Architecture:
        - APITestSDK: Top-level SDK coordinating entity operations
        - AuthContext: Small utility for auth token and headers
        - Entity operation classes: UserOperations, TicketOperations, etc.
        - Entity classes use AuthContext (no dependency on SDK)

    Authentication:
        The SDK uses an immutable authentication pattern. Create an unauthenticated
        SDK, then call with_auth() to get an authenticated instance. Attempting to
        call with_auth() on an already-authenticated SDK will raise an error.

    Usage:
        # Create unauthenticated SDK
        sdk = APITestSDK(client)

        # Create authenticated SDK
        admin_sdk = sdk.with_auth(admin_token)
        admin_sdk.users.deactivate(user_id)

        # ERROR: Can't double-authenticate
        admin_sdk.with_auth(pm_token)  # Raises RuntimeError

        # Create different authenticated instances for different users
        pm_sdk = sdk.with_auth(pm_token)
    """

    def __init__(self, client: TestClient, auth_token: str | None = None) -> None:
        """Initialize SDK.

        Args:
            client: FastAPI TestClient
            auth_token: Optional authentication token (internal use only)
        """
        self._client = client
        self._token = auth_token

        # Create auth context utility
        auth_ctx = AuthContext(client, auth_token)

        # Initialize entity operation namespaces, passing auth context
        self.users = UserOperations(auth_ctx)

    def with_auth(self, token: str) -> "APITestSDK":
        """Create a new SDK instance with authentication token.

        This method returns a NEW SDK instance with the token set. The original
        SDK instance is not modified.

        Args:
            token: Authentication token (JWT)

        Returns:
            New APITestSDK instance with authentication set

        Raises:
            RuntimeError: If this SDK instance already has authentication set

        Example:
            sdk = APITestSDK(client)
            admin_sdk = sdk.with_auth(admin_token)
            pm_sdk = sdk.with_auth(pm_token)  # Create from original sdk, not admin_sdk
        """
        if self._token is not None:
            raise RuntimeError(
                "SDK already has authentication token. "
                "To create a new authenticated SDK, use the original unauthenticated instance: "
                "sdk.with_auth(token), not authenticated_sdk.with_auth(token)"
            )

        return APITestSDK(self._client, token)


class UserOperations:
    """High-level user API operations.

    This class provides methods for all user-related API operations.
    All methods return APIResult[T] for type-safe response handling.

    The class uses AuthContext for authentication and headers, avoiding
    circular dependencies with the SDK.
    """

    def __init__(self, auth_ctx: AuthContext) -> None:
        """Initialize user operations.

        Args:
            auth_ctx: AuthContext providing client, auth checking, and headers
        """
        self._auth = auth_ctx

    def get(self, user_id: str) -> APIResult[User]:
        """Get user by ID.

        Args:
            user_id: User ID to retrieve

        Returns:
            APIResult containing User model on success (200) or error details

        Example:
            # Happy path
            user = sdk.users.get(user_id).assert_ok()

            # Validation testing
            result = sdk.users.get(deleted_user_id)
            assert result.status_code == 404
        """
        response = self._auth.client.get(f"/api/users/{user_id}", headers=self._auth.headers())

        # Parse data if success
        data = None
        if response.status_code == 200:
            data = User.model_validate(response.json())

        # Extract error if failure
        error = None
        if not (200 <= response.status_code < 300):
            error = response.json().get("detail", "Unknown error")

        return APIResult(status_code=response.status_code, raw_response=response, data=data, error=error)

    def create(
        self, organization_id: str, username: str, email: str, full_name: str, role: str = "read_access"
    ) -> APIResult[UserCreateResponse]:
        """Create a new user.

        Args:
            organization_id: Organization ID for the user
            username: Username
            email: Email address
            full_name: Full name
            role: User role (default: "read_access")

        Returns:
            APIResult containing UserCreateResponse on success (201) or error details

        Example:
            # Happy path
            result = sdk.users.create(org_id, "testuser", "test@example.com", "Test User")
            user_response = result.assert_ok()
            user_id = user_response.user.id
            password = user_response.generated_password
        """
        response = self._auth.client.post(
            f"/api/users?organization_id={organization_id}&role={role}",
            json={"username": username, "email": email, "full_name": full_name},
            headers=self._auth.headers(),
        )

        # Parse data if success
        data = None
        if response.status_code == 201:
            data = UserCreateResponse.model_validate(response.json())

        # Extract error if failure
        error = None
        if not (200 <= response.status_code < 300):
            error = response.json().get("detail", "Unknown error")

        return APIResult(status_code=response.status_code, raw_response=response, data=data, error=error)

    def update(self, user_id: str, **fields: str | bool) -> APIResult[User]:
        """Update user fields.

        Args:
            user_id: User ID to update
            **fields: Fields to update (full_name, email, role, is_active, etc.)

        Returns:
            APIResult containing updated User model on success (200) or error details

        Example:
            # Happy path
            user = sdk.users.update(user_id, full_name="New Name").assert_ok()
            assert user.full_name == "New Name"
        """
        response = self._auth.client.put(f"/api/users/{user_id}", json=fields, headers=self._auth.headers())

        # Parse data if success
        data = None
        if response.status_code == 200:
            data = User.model_validate(response.json())

        # Extract error if failure
        error = None
        if not (200 <= response.status_code < 300):
            error = response.json().get("detail", "Unknown error")

        return APIResult(status_code=response.status_code, raw_response=response, data=data, error=error)

    def deactivate(self, user_id: str) -> APIResult[User]:
        """Deactivate a user.

        Args:
            user_id: User ID to deactivate

        Returns:
            APIResult containing updated User model on success (200) or error details

        Example:
            # Happy path
            user = sdk.users.deactivate(user_id).assert_ok()
            assert user.is_active is False

            # Validation testing
            result = sdk.users.deactivate(deleted_user_id)
            assert result.status_code == 404
        """
        response = self._auth.client.put(
            f"/api/users/{user_id}", json={"is_active": False}, headers=self._auth.headers()
        )

        # Parse data if success
        data = None
        if response.status_code == 200:
            data = User.model_validate(response.json())

        # Extract error if failure
        error = None
        if not (200 <= response.status_code < 300):
            error = response.json().get("detail", "Unknown error")

        return APIResult(status_code=response.status_code, raw_response=response, data=data, error=error)

    def delete(self, user_id: str) -> APIResult[None]:
        """Delete a user.

        Args:
            user_id: User ID to delete

        Returns:
            APIResult with no data on success (204) or error details

        Example:
            # Happy path
            sdk.users.delete(user_id).assert_ok()

            # Validation testing
            result = sdk.users.delete(user_id)
            assert result.status_code == 404  # Already deleted
        """
        response = self._auth.client.delete(f"/api/users/{user_id}", headers=self._auth.headers())

        # No data for 204 response
        data = None

        # Extract error if failure
        error = None
        if not (200 <= response.status_code < 300):
            error = response.json().get("detail", "Unknown error")

        return APIResult(status_code=response.status_code, raw_response=response, data=data, error=error)
