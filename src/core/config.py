"""Application configuration module using pydantic-settings."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str = (
        "postgresql+asyncpg://postgres:postgrespassword@postgres:5432/db_challenges"
    )
    db_echo: bool = False
    app_env: str = "development"

    @field_validator("database_url", mode="after")
    @classmethod
    def assemble_db_connection(cls, v: str) -> str:
        """Ensure database URL uses postgresql+asyncpg driver.

        Normalizes postgres:// and postgresql:// schemes to postgresql+asyncpg://.
        Leaves already compatible asyncpg schemes unmodified.
        """
        if v.startswith("postgresql+asyncpg://"):
            return v
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v


settings = Settings()
