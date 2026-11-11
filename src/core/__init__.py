"""Core application configuration and infrastructure module."""

from src.core.config import settings
from src.core.database import Base, async_engine, async_session_factory, get_db
from src.core.dependencies import (
    get_current_user,
    get_optional_user,
    require_role,
    require_roles,
    require_scope,
    require_scopes,
)
from src.core.security import (
    AuthenticatedUser,
    InvalidTokenError,
    SecurityError,
    TokenExpiredError,
    UserInactiveError,
    decode_token,
    get_token_user,
    load_public_key,
)

__all__ = [
    "AuthenticatedUser",
    "Base",
    "InvalidTokenError",
    "SecurityError",
    "TokenExpiredError",
    "UserInactiveError",
    "async_engine",
    "async_session_factory",
    "decode_token",
    "get_current_user",
    "get_db",
    "get_optional_user",
    "get_token_user",
    "load_public_key",
    "require_role",
    "require_roles",
    "require_scope",
    "require_scopes",
    "settings",
]
