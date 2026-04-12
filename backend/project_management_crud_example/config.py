"""Application configuration settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    JWT Configuration:
    - JWT_SECRET_KEY: Secret key for signing tokens (REQUIRED, set via environment)
    - JWT_ALGORITHM: Algorithm for JWT signing (default: HS256)
    - JWT_EXPIRATION_SECONDS: Token lifetime in seconds (default: 3600 = 1 hour)
    - JWT_CLOCK_SKEW_SECONDS: Clock skew tolerance in seconds (default: 300 = 5 minutes)

    Password Hashing Configuration:
    - BCRYPT_ROUNDS: Number of bcrypt rounds for password hashing (default: 12)
      Lower values = faster but less secure (use 4 for testing, 12+ for production)

    Bootstrap Configuration:
    - BOOTSTRAP_ADMIN_USERNAME: Initial Super Admin username (default: admin)
    - BOOTSTRAP_ADMIN_EMAIL: Initial Super Admin email (default: admin@example.com)
    - BOOTSTRAP_ADMIN_FULL_NAME: Initial Super Admin full name (default: System Administrator)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # JWT Configuration
    JWT_SECRET_KEY: str  # Must be set via environment variable
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_SECONDS: int = 3600  # 1 hour
    JWT_CLOCK_SKEW_SECONDS: int = 300  # 5 minutes

    # Password Hashing Configuration
    BCRYPT_ROUNDS: int = 12  # 12 rounds = ~300ms (secure), 4 rounds = ~1-10ms (fast for testing)

    # Bootstrap Configuration (optional)
    BOOTSTRAP_ADMIN_USERNAME: str = "admin"
    BOOTSTRAP_ADMIN_EMAIL: str = "admin@example.com"
    BOOTSTRAP_ADMIN_FULL_NAME: str = "System Administrator"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    This function loads settings from environment variables and caches the result.
    Using a function allows the type checker to understand the initialization pattern.
    """
    return Settings()  # type: ignore[call-arg]


# Global settings instance for convenience
settings = get_settings()
