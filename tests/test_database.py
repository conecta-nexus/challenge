"""Unit tests for database engine, session factory, and get_db dependency."""

import inspect
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from src.core.config import settings
from src.core.database import Base, async_engine, async_session_factory, get_db


def test_base_declarative():
    """Verify Base is a valid SQLAlchemy DeclarativeBase subclass."""
    assert issubclass(Base, DeclarativeBase)
    assert hasattr(Base, "metadata")


def test_async_engine_configuration():
    """Verify async_engine is properly configured for PostgreSQL + asyncpg."""
    assert isinstance(async_engine, AsyncEngine)
    assert async_engine.url.drivername == "postgresql+asyncpg"
    assert async_engine.echo == settings.db_echo

    # Verify connection pooling parameters
    pool = async_engine.pool
    assert pool.size() == 10
    assert getattr(pool, "_max_overflow", None) == 20
    assert getattr(pool, "_pre_ping", None) is True


def test_async_session_factory():
    """Verify async_session_factory configuration and created session type."""
    assert async_session_factory.class_ is AsyncSession
    assert async_session_factory.kw.get("expire_on_commit") is False

    # Instantiate a session to verify behavior
    session = async_session_factory()
    assert isinstance(session, AsyncSession)
    assert session.sync_session.expire_on_commit is False


def test_get_db_is_async_generator():
    """Verify get_db is an async generator function suitable for FastAPI Depends."""
    assert inspect.isasyncgenfunction(get_db)


@pytest.mark.asyncio
async def test_get_db_lifecycle():
    """Verify get_db yields an AsyncSession and exits context manager properly."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("src.core.database.async_session_factory", return_value=mock_session):
        gen = get_db()
        session = await anext(gen)
        assert session is mock_session
        mock_session.__aenter__.assert_awaited_once()

        try:
            await anext(gen)
        except StopAsyncIteration:
            pass

        mock_session.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_closes_session_on_exception():
    """Verify get_db cleans up session when an exception occurs in route handling."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = False

    with patch("src.core.database.async_session_factory", return_value=mock_session):
        gen = get_db()
        session = await anext(gen)
        assert session is mock_session

        with pytest.raises(RuntimeError, match="Handler failure"):
            await gen.athrow(RuntimeError("Handler failure"))

        mock_session.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_yields_real_async_session():
    """Verify get_db with unpatched factory yields a real AsyncSession instance."""
    gen = get_db()
    session = await anext(gen)
    try:
        assert isinstance(session, AsyncSession)
        assert session.sync_session.expire_on_commit is False
    finally:
        await gen.aclose()
