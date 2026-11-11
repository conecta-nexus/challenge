"""FastAPI security dependencies for authentication and role-based authorization (ADR-002).

Provides dependencies for extracting and verifying RS256 Bearer JWT tokens,
enforcing RBAC roles (COMPANY, STUDENT, ADMIN), and verifying OAuth2 scopes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.database import get_db
from src.core.security import (
    AuthenticatedUser,
    InvalidTokenError,
    TokenExpiredError,
    UserInactiveError,
    get_token_user,
)

http_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="Bearer",
    description="Stateless RS256 JWT access token issued by auth microservice.",
)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)],
) -> AuthenticatedUser:
    """FastAPI dependency extracting and verifying the authenticated user from the Bearer token.

    Args:
        credentials: The HTTP authorization credentials containing the Bearer token.

    Returns:
        AuthenticatedUser: The validated authenticated user claims.

    Raises:
        HTTPException(401): If no token is provided, or the token is invalid/expired.
        HTTPException(403): If the user account is flagged as inactive.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        return get_token_user(token)
    except TokenExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token", error_description="The token has expired"'},
        ) from exc
    except UserInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        ) from exc
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {exc}",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from exc


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)],
) -> AuthenticatedUser | None:
    """FastAPI dependency for endpoints that allow anonymous access but identify users if authenticated.

    Args:
        credentials: The HTTP authorization credentials, if provided.

    Returns:
        AuthenticatedUser | None: The user if valid token supplied, else None.
    """
    if credentials is None or not credentials.credentials:
        return None

    try:
        return get_token_user(credentials.credentials)
    except (InvalidTokenError, TokenExpiredError, UserInactiveError):
        return None


def require_role(role: str) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    """Dependency factory enforcing that the authenticated user possesses a specific role.

    Args:
        role: The role required (e.g. 'COMPANY', 'STUDENT', 'ADMIN').

    Returns:
        FastAPI dependency function that validates user role.
    """
    expected_role = role.strip().upper()

    def role_dependency(
        user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        if not user.has_role(expected_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires '{expected_role}' role.",
            )
        return user

    return role_dependency


def require_roles(*roles: str) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    """Dependency factory enforcing that the user possesses at least one of the specified roles.

    Args:
        roles: Allowed roles.

    Returns:
        FastAPI dependency function.
    """
    expected_roles = [r.strip().upper() for r in roles]

    def roles_dependency(
        user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        if not user.has_any_role(*expected_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires one of the following roles: {expected_roles}.",
            )
        return user

    return roles_dependency


def require_scope(scope: str) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    """Dependency factory enforcing that the user token contains a specific OAuth2 scope.

    Args:
        scope: The required scope string (e.g. 'challenge:create').

    Returns:
        FastAPI dependency function.
    """
    expected_scope = scope.strip()

    def scope_dependency(
        user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        if not user.has_scope(expected_scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required OAuth2 scope: '{expected_scope}'.",
            )
        return user

    return scope_dependency


def require_scopes(*scopes: str) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    """Dependency factory enforcing that the user token contains all specified OAuth2 scopes.

    Args:
        scopes: All scopes that must be present.

    Returns:
        FastAPI dependency function.
    """
    expected_scopes = [s.strip() for s in scopes]

    def scopes_dependency(
        user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        if not user.has_all_scopes(*expected_scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required OAuth2 scopes. Required all of: {expected_scopes}.",
            )
        return user

    return scopes_dependency


__all__ = [
    "get_current_user",
    "get_db",
    "get_optional_user",
    "require_role",
    "require_roles",
    "require_scope",
    "require_scopes",
]
