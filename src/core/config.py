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

    # JWT Cryptographic & OAuth2 Specifications (ADR-002)
    jwt_public_key_path: str = "certs/jwt_public.pem"
    jwt_public_key: str | None = None
    jwt_algorithm: str = "RS256"
    jwt_issuer: str = "https://auth.conectanexus.ufps.edu.co"
    jwt_audiences: list[str] = [
        "conecta-nexus-gateway",
        "conecta-nexus-services",
    ]

    storage_endpoint: str = "localhost:9000"
    storage_access_key: str = "conectaadmin"
    storage_secret_key: str = "change-this-storage-secret"
    storage_bucket: str = "challenge-attachments"
    storage_secure: bool = False
    storage_region: str = "us-east-1"
    storage_pool_max_size: int = 20
    storage_part_size_bytes: int = 10 * 1024 * 1024
    storage_auto_create_bucket: bool = True

    @field_validator("database_url", mode="after")
    @classmethod
    def assemble_db_connection(cls, v: str) -> str:
        """Ensure database URL uses postgresql+asyncpg driver."""
        if v.startswith("postgresql+asyncpg://"):
            return v
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("storage_endpoint", mode="after")
    @classmethod
    def validate_storage_endpoint(cls, value: str) -> str:
        """Require the host:port format expected by the MinIO SDK."""
        endpoint = value.strip().rstrip("/")
        if endpoint.startswith(("http://", "https://")):
            raise ValueError(
                "STORAGE_ENDPOINT must use host:port format without a URL scheme"
            )
        if not endpoint:
            raise ValueError("STORAGE_ENDPOINT cannot be empty")
        return endpoint

    @field_validator("storage_pool_max_size")
    @classmethod
    def validate_storage_pool_size(cls, value: int) -> int:
        if value < 1:
            raise ValueError("STORAGE_POOL_MAX_SIZE must be greater than zero")
        return value

    @field_validator("storage_part_size_bytes")
    @classmethod
    def validate_storage_part_size(cls, value: int) -> int:
        minimum_part_size = 5 * 1024 * 1024
        if value < minimum_part_size:
            raise ValueError("STORAGE_PART_SIZE_BYTES must be at least 5 MiB")
        return value


settings = Settings()
