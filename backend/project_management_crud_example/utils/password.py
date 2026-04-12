"""Password hashing and verification utilities."""

import hashlib
import re
import secrets
import string

import bcrypt


class PasswordHasher:
    """Bcrypt-based password hasher for production use.

    Args:
        is_secure: If True, uses 12 rounds (secure but slow ~300ms).
                   If False, uses 4 rounds (faster ~10ms for testing).
    """

    def __init__(self, is_secure: bool = True) -> None:
        self.rounds = 12 if is_secure else 4

    def hash_password(self, plain_password: str) -> str:
        """Hash a plain text password using bcrypt.

        Args:
            plain_password: The plain text password to hash

        Returns:
            The bcrypt password hash as a string
        """
        password_bytes = plain_password.encode("utf-8")
        salt = bcrypt.gensalt(rounds=self.rounds)
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode("utf-8")

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        """Verify a plain text password against a bcrypt hash.

        Args:
            plain_password: The plain text password to verify
            password_hash: The bcrypt hash to verify against

        Returns:
            True if the password matches the hash, False otherwise
        """
        password_bytes = plain_password.encode("utf-8")
        hash_bytes = password_hash.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hash_bytes)


class TestPasswordHasher:
    """Fast password hasher for testing using SHA256.

    This is NOT secure and should ONLY be used in tests.
    Uses SHA256 with a salt for speed (~0.001ms vs bcrypt's ~10-300ms).
    """

    def hash_password(self, plain_password: str) -> str:
        """Hash a password using SHA256 (fast but not secure).

        Format: salt$hash where both are hex-encoded.

        Args:
            plain_password: The plain text password to hash

        Returns:
            The SHA256 password hash as a string
        """
        # Generate a random salt
        salt = secrets.token_hex(16)
        # Hash password with salt
        salted = f"{salt}{plain_password}"
        hashed = hashlib.sha256(salted.encode("utf-8")).hexdigest()
        return f"{salt}${hashed}"

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        """Verify a password against a SHA256 hash.

        Args:
            plain_password: The plain text password to verify
            password_hash: The hash to verify against (format: salt$hash)

        Returns:
            True if the password matches the hash, False otherwise
        """
        try:
            salt, stored_hash = password_hash.split("$")
            salted = f"{salt}{plain_password}"
            computed_hash = hashlib.sha256(salted.encode("utf-8")).hexdigest()
            return computed_hash == stored_hash
        except ValueError:
            return False


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validate password strength against security requirements.

    Requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character

    Args:
        password: The password to validate

    Returns:
        Tuple of (is_valid, error_message)
        - (True, "") if password meets all requirements
        - (False, "error message") if password fails validation
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"

    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"

    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit"

    if not re.search(r"[!@#$%^&*()\-_=+\[\]{}|;:,.<>?]", password):
        return False, "Password must contain at least one special character"

    return True, ""


def generate_password() -> str:
    """Generate a secure random password.

    Generates a password with:
    - Minimum 12 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character

    Returns:
        A randomly generated secure password
    """
    # Define character sets
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special = "!@#$%^&*()-_=+[]{}|;:,.<>?"

    # Ensure at least one of each type
    password_chars = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(special),
    ]

    # Fill the rest with random characters from all sets
    all_chars = uppercase + lowercase + digits + special
    password_chars.extend(secrets.choice(all_chars) for _ in range(12))

    # Shuffle to avoid predictable patterns
    secrets.SystemRandom().shuffle(password_chars)

    return "".join(password_chars)
