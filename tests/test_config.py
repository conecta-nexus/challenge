"""Unit tests for application configuration settings."""

import pytest

from src.core.config import Settings, settings


def test_default_settings():
    """Verify default configuration values match expected environment."""
    assert (
        settings.database_url
        == "postgresql+asyncpg://postgres:postgrespassword@postgres:5432/db_challenges"
    )
    assert settings.db_echo is False
    assert settings.app_env == "development"


def test_database_url_normalization_postgres():
    """Verify postgres:// URLs are normalized to postgresql+asyncpg://."""
    s = Settings(database_url="postgres://user:pass@localhost:5432/testdb")
    assert s.database_url == "postgresql+asyncpg://user:pass@localhost:5432/testdb"


def test_database_url_normalization_postgresql():
    """Verify postgresql:// URLs are normalized to postgresql+asyncpg://."""
    s = Settings(database_url="postgresql://user:pass@localhost:5432/testdb")
    assert s.database_url == "postgresql+asyncpg://user:pass@localhost:5432/testdb"


def test_database_url_already_asyncpg():
    """Verify postgresql+asyncpg:// URLs are preserved without alteration."""
    url = "postgresql+asyncpg://user:pass@remote-host:5432/custom_db"
    s = Settings(database_url=url)
    assert s.database_url == url


@pytest.mark.parametrize(
    ("raw_val", "expected"),
    [
        ("true", True),
        ("True", True),
        ("1", True),
        (True, True),
        ("false", False),
        ("False", False),
        ("0", False),
        (False, False),
    ],
)
def test_db_echo_boolean_parsing(raw_val, expected):
    """Verify DB_ECHO is correctly parsed into a boolean value."""
    s = Settings(db_echo=raw_val)
    assert s.db_echo is expected


def test_app_env_loading():
    """Verify APP_ENV is loaded and parsed correctly."""
    s_prod = Settings(app_env="production")
    assert s_prod.app_env == "production"

    s_test = Settings(app_env="testing")
    assert s_test.app_env == "testing"


def test_extra_fields_ignored():
    """Verify additional fields in environment are ignored without error."""
    s = Settings(unknown_setting="some_value")
    assert not hasattr(s, "unknown_setting")
