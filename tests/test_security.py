"""Unit and integration test suite for RS256 JWT security and RBAC dependencies (ADR-002)."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI, status
from fastapi.testclient import TestClient

from src.core.config import settings
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
    TokenExpiredError,
    UserInactiveError,
    decode_token,
    get_token_user,
    load_public_key,
)


@pytest.fixture(scope="session")
def rsa_keypair() -> tuple[str, str]:
    """Generate an ephemeral 2048-bit RSA keypair for cryptographic test isolation."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


@pytest.fixture
def generate_token(rsa_keypair: tuple[str, str]):
    """Helper fixture to mint RS256 JWT tokens with custom claims."""
    private_pem, _ = rsa_keypair

    def _create(
        user_id: uuid.UUID | str | None = None,
        role: str = "COMPANY",
        email: str = "test@company.com",
        scopes: str | list[str] = "challenge:create challenge:read_own",
        is_active: bool = True,
        token_type: str = "access",
        issuer: str = settings.jwt_issuer,
        audience: str | list[str] | None = None,
        expires_delta: timedelta = timedelta(minutes=15),
        key: str = private_pem,
    ) -> str:
        uid = str(user_id or uuid.uuid4())
        aud = audience or list(settings.jwt_audiences)
        now = datetime.now(timezone.utc)
        exp = now + expires_delta

        scope_val = " ".join(scopes) if isinstance(scopes, list) else scopes

        payload: dict[str, Any] = {
            "iss": issuer,
            "aud": aud,
            "sub": uid,
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "type": token_type,
            "email": email,
            "role": role,
            "is_active": is_active,
            "scope": scope_val,
        }
        return jwt.encode(payload, key, algorithm="RS256")

    return _create


# ==============================================================================
# 1. Public Key Loading Tests
# ==============================================================================


def test_load_public_key_from_default_file():
    """Verify that public key loads cleanly from the default project path."""
    key = load_public_key()
    assert "-----BEGIN PUBLIC KEY-----" in key
    assert "-----END PUBLIC KEY-----" in key


def test_load_public_key_custom_override(rsa_keypair: tuple[str, str]):
    """Verify custom key string override works."""
    _, public_pem = rsa_keypair
    key = load_public_key(custom_key=public_pem)
    assert key == public_pem.strip()


def test_load_public_key_file_not_found(monkeypatch):
    """Verify error handling when key file does not exist."""
    monkeypatch.setattr(settings, "jwt_public_key_path", "nonexistent/key.pem")
    monkeypatch.setattr(settings, "jwt_public_key", None)
    with pytest.raises(InvalidTokenError, match="not found"):
        load_public_key()


def test_load_public_key_empty_file(tmp_path, monkeypatch):
    """Verify error handling when key file is empty."""
    empty_key = tmp_path / "empty.pem"
    empty_key.write_text("")
    monkeypatch.setattr(settings, "jwt_public_key_path", str(empty_key))
    monkeypatch.setattr(settings, "jwt_public_key", None)
    with pytest.raises(InvalidTokenError, match="empty"):
        load_public_key()


# ==============================================================================
# 2. Token Decoding & Claims Verification Tests
# ==============================================================================


def test_decode_valid_token_success(rsa_keypair: tuple[str, str], generate_token):
    """Verify valid token decodes with all standard claims."""
    _, public_pem = rsa_keypair
    user_id = uuid.uuid4()
    token = generate_token(user_id=user_id, role="COMPANY", email="hr@startup.co")

    payload = decode_token(token, public_key=public_pem)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "COMPANY"
    assert payload["email"] == "hr@startup.co"
    assert payload["type"] == "access"
    assert payload["is_active"] is True


def test_decode_token_with_single_string_audience(rsa_keypair: tuple[str, str], generate_token):
    """Verify audience validation succeeds when aud claim is a single valid string."""
    _, public_pem = rsa_keypair
    token = generate_token(audience="conecta-nexus-services")
    payload = decode_token(token, public_key=public_pem)
    assert payload["aud"] == "conecta-nexus-services"


def test_decode_token_expired_raises(rsa_keypair: tuple[str, str], generate_token):
    """Verify expired token raises TokenExpiredError."""
    _, public_pem = rsa_keypair
    token = generate_token(expires_delta=timedelta(seconds=-10))

    with pytest.raises(TokenExpiredError, match="expired"):
        decode_token(token, public_key=public_pem)


def test_decode_token_expired_with_verify_exp_false(rsa_keypair: tuple[str, str], generate_token):
    """Verify verify_exp=False allows reading expired claims."""
    _, public_pem = rsa_keypair
    token = generate_token(expires_delta=timedelta(seconds=-10))
    payload = decode_token(token, public_key=public_pem, verify_exp=False)
    assert payload is not None


def test_decode_token_tampered_signature_raises(rsa_keypair: tuple[str, str], generate_token):
    """Verify altered token string raises InvalidTokenError."""
    _, public_pem = rsa_keypair
    token = generate_token()
    parts = token.split(".")
    tampered_sig = parts[2][:-4] + "AAAA"
    tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"

    with pytest.raises(InvalidTokenError, match="decoding failed"):
        decode_token(tampered_token, public_key=public_pem)


def test_decode_token_wrong_key_raises(generate_token):
    """Verify signature verification fails with an alien public key."""
    alien_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    alien_public = alien_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    token = generate_token()  # Signed with rsa_keypair
    with pytest.raises(InvalidTokenError):
        decode_token(token, public_key=alien_public)


def test_decode_token_invalid_issuer_raises(rsa_keypair: tuple[str, str], generate_token):
    """Verify token signed with rogue issuer is rejected."""
    _, public_pem = rsa_keypair
    token = generate_token(issuer="https://evil-auth.com")
    with pytest.raises(InvalidTokenError, match="decoding failed"):
        decode_token(token, public_key=public_pem)


def test_decode_token_invalid_audience_raises(rsa_keypair: tuple[str, str], generate_token):
    """Verify token with unintended audience is rejected."""
    _, public_pem = rsa_keypair
    token = generate_token(audience=["unrelated-microservice"])
    with pytest.raises(InvalidTokenError, match="Invalid token audience"):
        decode_token(token, public_key=public_pem)


def test_decode_token_refresh_type_rejected(rsa_keypair: tuple[str, str], generate_token):
    """Verify refresh tokens cannot be used as access tokens."""
    _, public_pem = rsa_keypair
    token = generate_token(token_type="refresh")
    with pytest.raises(InvalidTokenError, match="expected 'access'"):
        decode_token(token, public_key=public_pem)


def test_decode_token_inactive_user_raises(rsa_keypair: tuple[str, str], generate_token):
    """Verify inactive users are rejected."""
    _, public_pem = rsa_keypair
    token = generate_token(is_active=False)
    with pytest.raises(UserInactiveError, match="inactive"):
        decode_token(token, public_key=public_pem)


def test_decode_token_empty_string_raises():
    """Verify empty token input raises InvalidTokenError."""
    with pytest.raises(InvalidTokenError, match="non-empty string"):
        decode_token("")


# ==============================================================================
# 3. AuthenticatedUser Model & Methods Tests
# ==============================================================================


def test_authenticated_user_methods():
    """Verify role and scope helper methods on AuthenticatedUser."""
    user_id = uuid.uuid4()
    user = AuthenticatedUser(
        id=user_id,
        email="developer@ufps.edu.co",
        role="COMPANY",
        scopes=["challenge:create", "challenge:read_own", "challenge:write_own"],
        is_active=True,
    )

    # Role checks
    assert user.has_role("COMPANY")
    assert user.has_role("company")
    assert not user.has_role("STUDENT")
    assert user.has_any_role("STUDENT", "COMPANY")
    assert not user.has_any_role("STUDENT", "ADMIN")

    # Scope checks
    assert user.has_scope("challenge:create")
    assert not user.has_scope("challenge:delete_all")
    assert user.has_any_scope("challenge:create", "admin:all")
    assert not user.has_any_scope("admin:all", "other:scope")
    assert user.has_all_scopes("challenge:create", "challenge:read_own")
    assert not user.has_all_scopes("challenge:create", "challenge:delete_all")


def test_get_token_user_success(rsa_keypair: tuple[str, str], generate_token):
    """Verify get_token_user builds a valid AuthenticatedUser instance."""
    _, public_pem = rsa_keypair
    expected_id = uuid.uuid4()
    token = generate_token(
        user_id=expected_id,
        role="STUDENT",
        email="student@ufps.edu.co",
        scopes="challenge:read application:create",
    )

    user = get_token_user(token, public_key=public_pem)
    assert user.id == expected_id
    assert user.role == "STUDENT"
    assert user.email == "student@ufps.edu.co"
    assert user.scopes == ["challenge:read", "application:create"]
    assert user.is_active is True


def test_get_token_user_invalid_sub_uuid(rsa_keypair: tuple[str, str], generate_token):
    """Verify non-UUID sub claim raises InvalidTokenError."""
    _, public_pem = rsa_keypair
    token = generate_token(user_id="not-a-valid-uuid")

    with pytest.raises(InvalidTokenError, match="Invalid user ID"):
        get_token_user(token, public_key=public_pem)


# ==============================================================================
# 4. FastAPI Security Dependencies Tests (get_current_user, RBAC, Scopes)
# ==============================================================================


@pytest.fixture
def test_app(rsa_keypair: tuple[str, str]) -> FastAPI:
    """Create a minimal FastAPI test application testing all security dependencies."""
    _, public_pem = rsa_keypair
    app = FastAPI(title="Security Dependency Test App")

    # Patch load_public_key in app context
    from src.core import security

    security.settings.jwt_public_key = public_pem

    @app.get("/me")
    async def me_endpoint(user: AuthenticatedUser = Depends(get_current_user)):
        return {"id": str(user.id), "role": user.role, "email": user.email}

    @app.get("/optional")
    async def optional_endpoint(user: AuthenticatedUser | None = Depends(get_optional_user)):
        if user is None:
            return {"authenticated": False}
        return {"authenticated": True, "id": str(user.id)}

    @app.post("/company-only")
    async def company_only(user: AuthenticatedUser = Depends(require_role("COMPANY"))):
        return {"status": "ok", "role": user.role}

    @app.get("/multi-role")
    async def multi_role(user: AuthenticatedUser = Depends(require_roles("COMPANY", "ADMIN"))):
        return {"status": "ok", "role": user.role}

    @app.post("/create-challenge")
    async def create_challenge(user: AuthenticatedUser = Depends(require_scope("challenge:create"))):
        return {"status": "created", "by": str(user.id)}

    @app.post("/multi-scope")
    async def multi_scope(
        user: AuthenticatedUser = Depends(require_scopes("challenge:create", "challenge:read_own")),
    ):
        return {"status": "authorized"}

    return app


def test_get_current_user_missing_header(test_app: FastAPI):
    """Missing Authorization header returns 401."""
    client = TestClient(test_app)
    response = client.get("/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "WWW-Authenticate" in response.headers
    assert "credentials were not provided" in response.json()["detail"]


def test_get_current_user_invalid_bearer(test_app: FastAPI):
    """Malformed token string returns 401."""
    client = TestClient(test_app)
    response = client.get("/me", headers={"Authorization": "Bearer invalid.token.value"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Could not validate credentials" in response.json()["detail"]


def test_get_current_user_expired_token(test_app: FastAPI, generate_token):
    """Expired Bearer token returns 401."""
    client = TestClient(test_app)
    token = generate_token(expires_delta=timedelta(seconds=-10))
    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Token has expired."


def test_get_current_user_inactive_user(test_app: FastAPI, generate_token):
    """Token for deactivated user returns 403."""
    client = TestClient(test_app)
    token = generate_token(is_active=False)
    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "deactivated" in response.json()["detail"]


def test_get_current_user_valid(test_app: FastAPI, generate_token):
    """Valid Bearer token returns 200 with user payload."""
    client = TestClient(test_app)
    uid = uuid.uuid4()
    token = generate_token(user_id=uid, role="COMPANY", email="ceo@startup.co")
    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == str(uid)
    assert response.json()["role"] == "COMPANY"


def test_get_optional_user(test_app: FastAPI, generate_token):
    """Verify optional authentication for public/hybrid routes."""
    client = TestClient(test_app)

    # Anonymous call
    resp_anon = client.get("/optional")
    assert resp_anon.status_code == status.HTTP_200_OK
    assert resp_anon.json() == {"authenticated": False}

    # Authenticated call
    uid = uuid.uuid4()
    token = generate_token(user_id=uid)
    resp_auth = client.get("/optional", headers={"Authorization": f"Bearer {token}"})
    assert resp_auth.status_code == status.HTTP_200_OK
    assert resp_auth.json() == {"authenticated": True, "id": str(uid)}


def test_require_role_rbac_enforcement(test_app: FastAPI, generate_token):
    """Verify require_role allows authorized role and blocks others with 403."""
    client = TestClient(test_app)

    # Company user succeeds
    company_token = generate_token(role="COMPANY")
    resp_company = client.post("/company-only", headers={"Authorization": f"Bearer {company_token}"})
    assert resp_company.status_code == status.HTTP_200_OK

    # Student user is rejected with 403
    student_token = generate_token(role="STUDENT")
    resp_student = client.post("/company-only", headers={"Authorization": f"Bearer {student_token}"})
    assert resp_student.status_code == status.HTTP_403_FORBIDDEN
    assert "'COMPANY'" in resp_student.json()["detail"]


def test_require_roles_multi_role_enforcement(test_app: FastAPI, generate_token):
    """Verify require_roles allows any matching role in whitelist."""
    client = TestClient(test_app)

    company_token = generate_token(role="COMPANY")
    assert client.get("/multi-role", headers={"Authorization": f"Bearer {company_token}"}).status_code == 200

    admin_token = generate_token(role="ADMIN")
    assert client.get("/multi-role", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 200

    student_token = generate_token(role="STUDENT")
    assert client.get("/multi-role", headers={"Authorization": f"Bearer {student_token}"}).status_code == 403


def test_require_scope_enforcement(test_app: FastAPI, generate_token):
    """Verify require_scope checks specific OAuth2 permission."""
    client = TestClient(test_app)

    # Token with required scope
    token_with_scope = generate_token(scopes="challenge:create challenge:read_own")
    resp_ok = client.post("/create-challenge", headers={"Authorization": f"Bearer {token_with_scope}"})
    assert resp_ok.status_code == status.HTTP_200_OK

    # Token without required scope
    token_without_scope = generate_token(scopes="challenge:read_own")
    resp_forbidden = client.post("/create-challenge", headers={"Authorization": f"Bearer {token_without_scope}"})
    assert resp_forbidden.status_code == status.HTTP_403_FORBIDDEN
    assert "Missing required OAuth2 scope: 'challenge:create'" in resp_forbidden.json()["detail"]


def test_require_scopes_all_enforcement(test_app: FastAPI, generate_token):
    """Verify require_scopes requires all listed scopes."""
    client = TestClient(test_app)

    # All scopes present
    token_all = generate_token(scopes=["challenge:create", "challenge:read_own"])
    assert client.post("/multi-scope", headers={"Authorization": f"Bearer {token_all}"}).status_code == 200

    # Partial scopes present
    token_partial = generate_token(scopes=["challenge:create"])
    resp = client.post("/multi-scope", headers={"Authorization": f"Bearer {token_partial}"})
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert "Missing required OAuth2 scopes" in resp.json()["detail"]
