"""Password-change capability.

Narrow capability for the /auth/change-password endpoint. It lets the
authenticated user change their OWN password only. No cross-user writes.
"""

from project_management_crud_example.capabilities.errors import CapabilityPermissionError
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import PasswordChangeCommand, User
from project_management_crud_example.exceptions import InvalidCredentialsException
from project_management_crud_example.utils.activity_log_helpers import log_activity
from project_management_crud_example.utils.password import validate_password_strength


class PasswordChangeError(Exception):
    """Raised when password-change inputs are invalid (400-class)."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class PasswordChangeCapability:
    """Change the current user's own password. No other writes permitted."""

    def __init__(self, repo: Repository, current_user: User) -> None:
        self._repo = repo
        self._user = current_user

    @property
    def user(self) -> User:
        return self._user

    def change_own_password(self, current_password: str, new_password: str) -> None:
        """Verify current password, validate new password, persist, and log.

        Raises:
            InvalidCredentialsException: current password wrong or user missing
            PasswordChangeError: new password fails strength validation or
                persistence fails
            CapabilityPermissionError: never for change-own-password, but kept
                in the type surface for consistency with other capabilities
        """
        user_auth = self._repo.users.get_by_username_with_password(self._user.username)
        if user_auth is None:
            raise InvalidCredentialsException()

        if user_auth.id != self._user.id:
            raise CapabilityPermissionError("Can only change your own password")

        if not self._repo.password_hasher.verify_password(current_password, user_auth.password_hash):
            raise InvalidCredentialsException()

        is_valid, error_message = validate_password_strength(new_password)
        if not is_valid:
            raise PasswordChangeError(error_message or "Password does not meet strength requirements")

        if not self._repo.users.update_password(self._user.id, new_password):
            raise PasswordChangeError("Failed to update password")

        log_activity(
            repo=self._repo,
            command=PasswordChangeCommand(user_id=self._user.id),
            entity_id=self._user.id,
            actor_id=self._user.id,
            organization_id=self._user.organization_id or "",
        )
