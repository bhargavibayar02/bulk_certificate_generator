"""
Application Configuration.

Uses Pydantic Settings to manage configuration from environment variables
with sensible defaults for local development.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Info
    APP_NAME: str = "Bulk Certificate Generator"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database Configuration
    # Defaults to local SQLite, can easily be changed to PostgreSQL via env var:
    # DATABASE_URL="postgresql://user:password@localhost/dbname"
    DATABASE_URL: str = "sqlite:///./bulk_certificates.db"

    # Certificate Storage Directory
    # Relative to project root or specified via environment variable
    CERTIFICATES_DIR: Path = Path("generated_certificates")

    # Business Rules & Constraints
    MAX_RECIPIENTS_PER_JOB: int = 500
    MAX_LOGOS_PER_JOB: int = 10
    MAX_LOGO_FILE_SIZE_BYTES: int = 2 * 1024 * 1024  # 2MB
    ALLOWED_LOGO_EXTENSIONS: tuple[str, ...] = (".png", ".jpg", ".jpeg")

    # Pydantic Settings Config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


# Global settings instance
settings = Settings()
