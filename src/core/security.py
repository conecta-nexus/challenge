"""Stateless RS256 JWT security and claims verification module (ADR-002).

Implements cryptographic signature validation, OAuth2 claims parsing, and
role-based scope verification for the challenge microservice without database
lookups to the auth microservice.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError as PyJWTError

from src.core.config import settings

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Base exception for security-related errors."""


class TokenExpiredError(SecurityError):
    """Raised when the JWT token signature is expired."""


class InvalidTokenError(SecurityError):
    """Raised when the JWT token is malformed, has invalid signature, or invalid claims."""


class UserInactiveError(SecurityError):
    """Raised when the user account in token claims is flagged as inactive."""


@dataclass(frozen=True)
class AuthenticatedUser:
    """Immutable representation of an authenticated entity extracted from RS256 JWT claims."""

    id: uuid.UUID
    email: str
    role: str
    scopes: list[str] = field(default_factory=list)
    is_active: bool = True
    payload: dict[str, Any] = field(default_factory=dict, repr=False)

    def has_role(self, role: str) -> bool:
        """Check if the user has the specified role (case-insensitive)."""
        return self.role.upper() == role.strip().upper()

    def has_any_role(self, *roles: str) -> bool:
        """Check if the user has any of the specified roles."""
        normalized = {r.strip().upper() for r in roles}
        return self.role.upper() in normalized

    def has_scope(self, scope: str) -> bool:
        """Check if the user token grants the specified OAuth2 scope."""
        return scope.strip() in self.scopes

    def has_any_scope(self, *scopes: str) -> bool:
        """Check if the user token grants at least one of the specified scopes."""
        target_scopes = {s.strip() for s in scopes}
        return any(scope in target_scopes for scope in self.scopes)

    def has_all_scopes(self, *scopes: str) -> bool:
        """Check if the user token grants all of the specified scopes."""
        target_scopes = {s.strip() for s in scopes}
        return target_scopes.issubset(set(self.scopes))


def load_public_key(custom_key: str | None = None) -> str:
    """Retrieve and validate the RSA public key PEM from settings, env, or disk.

    Args:
        custom_key: Optional explicit PEM string for testing or overrides.

    Returns:
        Clean RSA public key PEM string.

    Raises:
        InvalidTokenError: If the key cannot be found or loaded.
    """
    if custom_key and custom_key.strip():
        return custom_key.strip()

    if settings.jwt_public_key and settings.jwt_public_key.strip():
        return settings.jwt_public_key.strip()

    key_path = Path(settings.jwt_public_key_path)
    if not key_path.is_absolute():
        # Try relative to current working directory and relative to project root
        candidates = [
            Path.cwd() / key_path,
            Path(__file__).resolve().parent.parent.parent / key_path,
        ]
        resolved_path = next((p for p in candidates if p.exists() and p.is_file()), None)
    else:
        resolved_path = key_path if key_path.exists() and key_path.is_file() else None

    if not resolved_path:
        raise InvalidTokenError(
            f"RSA public key file not found at '{settings.jwt_public_key_path}'."
        )

    try:
        content = resolved_path.read_text(encoding="utf-8").strip()
        if not content:
            raise InvalidTokenError(f"RSA public key file at '{resolved_path}' is empty.")
        return content
    except OSError as exc:
        raise InvalidTokenError(
            f"Failed to read RSA public key from '{resolved_path}': {exc}"
        ) from exc


def decode_token(
    token: str,
    public_key: str | None = None,
    verify_exp: bool = True,
) -> dict[str, Any]:
    """Decode and cryptographically verify an RS256 JWT access token.

    Validates signature, expiration, issuer, audience, token type, and active status.

    Args:
        token: Raw JWT Bearer token string.
        public_key: Optional explicit RSA public key PEM string.
        verify_exp: Whether to verify token expiration.

    Returns:
        Decoded payload dictionary.

    Raises:
        TokenExpiredError: If the token has expired.
        UserInactiveError: If claims indicate user is deactivated.
        InvalidTokenError: If signature, claims, or format is invalid.
    """
    if not token or not isinstance(token, str):
        raise InvalidTokenError("Token string must be a non-empty string.")

    pem_key = load_public_key(custom_key=public_key)

    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            pem_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            options={
                "verify_signature": True,
                "verify_exp": verify_exp,
                "verify_iss": True,
                "verify_aud": False,  # Custom multi-audience matching below
                "require": ["exp", "sub", "role"],
            },
        )
    except ExpiredSignatureError as exc:
        raise TokenExpiredError("JWT token has expired.") from exc
    except PyJWTError as exc:
        raise InvalidTokenError(f"JWT token decoding failed: {exc}") from exc

    # Validate Audience (supports string or list of audiences)
    token_aud = payload.get("aud")
    expected_audiences = set(settings.jwt_audiences)
    if isinstance(token_aud, str):
        aud_valid = token_aud in expected_audiences
    elif isinstance(token_aud, (list, tuple)):
        aud_valid = any(aud in expected_audiences for aud in token_aud)
    else:
        aud_valid = False

    if not aud_valid:
        raise InvalidTokenError(
            f"Invalid token audience '{token_aud}'. Expected one of {list(expected_audiences)}."
        )

    # Validate Token Type (only access tokens are accepted for API operations)
    token_type = payload.get("type", "access")
    if token_type != "access":
        raise InvalidTokenError(
            f"Invalid token type: expected 'access', got '{token_type}'."
        )

    # Validate User Active Status
    if payload.get("is_active") is False:
        raise UserInactiveError("User account is inactive.")

    return payload


def get_token_user(
    token: str,
    public_key: str | None = None,
    verify_exp: bool = True,
) -> AuthenticatedUser:
    """Decode token and construct an AuthenticatedUser instance.

    Args:
        token: Raw JWT Bearer token string.
        public_key: Optional explicit RSA public key PEM string.
        verify_exp: Whether to verify token expiration.

    Returns:
        AuthenticatedUser with claims.

    Raises:
        TokenExpiredError: If token is expired.
        UserInactiveError: If user is inactive.
        InvalidTokenError: If token structure or UUID is invalid.
    """
    payload = decode_token(token, public_key=public_key, verify_exp=verify_exp)

    raw_sub = payload.get("sub")
    try:
        user_uuid = uuid.UUID(str(raw_sub))
    except (ValueError, TypeError) as exc:
        raise InvalidTokenError(f"Invalid user ID ('sub') claim in token: '{raw_sub}'.") from exc

    role = str(payload.get("role", "")).strip().upper()
    email = str(payload.get("email", "")).strip()
    is_active = bool(payload.get("is_active", True))

    raw_scope = payload.get("scope", "")
    if isinstance(raw_scope, str):
        scopes = [s for s in raw_scope.split() if s]
    elif isinstance(raw_scope, (list, tuple)):
        scopes = [str(s) for s in raw_scope if s]
    else:
        scopes = []

    return AuthenticatedUser(
        id=user_uuid,
        email=email,
        role=role,
        scopes=scopes,
        is_active=is_active,
        payload=payload,
    )
