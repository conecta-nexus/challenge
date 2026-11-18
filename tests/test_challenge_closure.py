"""Integration tests for voluntary challenge closure and company challenge portfolio (HU-08)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.challenge.main import app
from src.core.database import get_db
from src.core.dependencies import get_current_user, require_role
from src.core.security import AuthenticatedUser
from src.models.challenge import Challenge

client = TestClient(app)

COMPANY_ID_1 = uuid.uuid4()
COMPANY_ID_2 = uuid.uuid4()
STUDENT_ID = uuid.uuid4()


def create_sample_challenge(
    challenge_id: uuid.UUID | None = None,
    company_id: uuid.UUID = COMPANY_ID_1,
    status: str = "DRAFT",
    title: str = "Predictive Maintenance Engine",
    closure_reason: str | None = None,
) -> Challenge:
    """Helper to instantiate mock Challenge ORM instance."""
    return Challenge(
        id=challenge_id or uuid.uuid4(),
        company_id=company_id,
        title=title,
        description="Develop predictive maintenance IoT pipeline for industrial pumps.",
        business_process="Plant Maintenance",
        status=status,
        difficulty_level="ADVANCED",
        modality="REMOTE",
        min_semester=8,
        economic_sector="Manufacturing",
        required_skills=["Python", "TimescaleDB", "MQTT"],
        knowledge_areas=["IoT", "Industrial Engineering"],
        closure_reason=closure_reason,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_db_session():
    """Override get_db FastAPI dependency with AsyncMock."""
    mock_session = AsyncMock()

    async def _get_db_override():
        yield mock_session

    app.dependency_overrides[get_db] = _get_db_override
    yield mock_session
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def auth_company_1():
    """Authenticate client as Company 1."""
    user = AuthenticatedUser(
        id=COMPANY_ID_1,
        email="company1@acme.com",
        role="COMPANY",
        scopes=["challenge:write", "challenge:read"],
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_role("COMPANY")] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_role("COMPANY"), None)


@pytest.fixture
def auth_company_2():
    """Authenticate client as Company 2."""
    user = AuthenticatedUser(
        id=COMPANY_ID_2,
        email="company2@globex.com",
        role="COMPANY",
        scopes=["challenge:write", "challenge:read"],
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_role("COMPANY")] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_role("COMPANY"), None)


@pytest.fixture
def auth_student():
    """Authenticate client as Student."""
    user = AuthenticatedUser(
        id=STUDENT_ID,
        email="student@ufps.edu.co",
        role="STUDENT",
        scopes=["challenge:read"],
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_role("COMPANY")] = None
    yield user
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_role("COMPANY"), None)


# ------------------------------------------------------------------------------
# POST /api/v1/challenges/{id}/close Tests
# ------------------------------------------------------------------------------


def test_close_challenge_unauthorized(mock_db_session):
    """POST /api/v1/challenges/{id}/close without token yields 401 Unauthorized."""
    test_id = uuid.uuid4()
    response = client.post(
        f"/api/v1/challenges/{test_id}/close",
        json={"closure_reason": "Project completed successfully."},
    )
    assert response.status_code == 401


def test_close_challenge_not_found(mock_db_session, auth_company_1):
    """POST /api/v1/challenges/{id}/close with non-existent UUID yields 404 Not Found."""
    test_id = uuid.uuid4()
    with patch(
        "src.services.challenge_service.ChallengeRepository.get_by_id",
        new=AsyncMock(return_value=None),
    ):
        response = client.post(
            f"/api/v1/challenges/{test_id}/close",
            json={"closure_reason": "The challenge was fulfilled by an internal team."},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Challenge not found"


def test_close_challenge_forbidden_for_non_owner(mock_db_session, auth_company_2):
    """POST /api/v1/challenges/{id}/close owned by Company 1 yields 403 when called by Company 2 (RB-06)."""
    test_id = uuid.uuid4()
    sample = create_sample_challenge(challenge_id=test_id, company_id=COMPANY_ID_1, status="OPEN")

    with patch(
        "src.services.challenge_service.ChallengeRepository.get_by_id",
        new=AsyncMock(return_value=sample),
    ):
        response = client.post(
            f"/api/v1/challenges/{test_id}/close",
            json={"closure_reason": "Attempting unauthorized closure of another company challenge."},
        )
        assert response.status_code == 403
        assert "ownership" in response.json()["detail"]


@pytest.mark.parametrize(
    "invalid_reason",
    [
        "",
        "Short",
        "Less than 15",
        "   padded   ",  # stripped is 6 chars
    ],
)
def test_close_challenge_rejects_insufficient_justification(
    mock_db_session, auth_company_1, invalid_reason
):
    """POST /api/v1/challenges/{id}/close rejects reasons shorter than 15 characters with 422."""
    test_id = uuid.uuid4()
    response = client.post(
        f"/api/v1/challenges/{test_id}/close",
        json={"closure_reason": invalid_reason},
    )
    assert response.status_code == 422


def test_close_challenge_already_closed(mock_db_session, auth_company_1):
    """POST /api/v1/challenges/{id}/close on an already CLOSED challenge yields 422."""
    test_id = uuid.uuid4()
    sample = create_sample_challenge(
        challenge_id=test_id,
        company_id=COMPANY_ID_1,
        status="CLOSED",
        closure_reason="Previously closed with adequate justification.",
    )

    with patch(
        "src.services.challenge_service.ChallengeRepository.get_by_id",
        new=AsyncMock(return_value=sample),
    ):
        response = client.post(
            f"/api/v1/challenges/{test_id}/close",
            json={"closure_reason": "Attempting to close an already closed challenge."},
        )
        assert response.status_code == 422
        assert "already closed" in response.json()["detail"]


def test_close_challenge_success(mock_db_session, auth_company_1):
    """POST /api/v1/challenges/{id}/close successfully transitions to CLOSED and stores audit reason."""
    test_id = uuid.uuid4()
    sample = create_sample_challenge(challenge_id=test_id, company_id=COMPANY_ID_1, status="OPEN")
    reason = "The internal objective was successfully achieved and candidates evaluated."
    closed_sample = create_sample_challenge(
        challenge_id=test_id,
        company_id=COMPANY_ID_1,
        status="CLOSED",
        closure_reason=reason,
    )

    with patch(
        "src.services.challenge_service.ChallengeRepository.get_by_id",
        new=AsyncMock(return_value=sample),
    ), patch(
        "src.services.challenge_service.ChallengeRepository.close_challenge",
        new=AsyncMock(return_value=closed_sample),
    ) as mock_close:
        response = client.post(
            f"/api/v1/challenges/{test_id}/close",
            json={"closure_reason": reason},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_id)
        assert data["status"] == "CLOSED"
        assert data["closure_reason"] == reason
        mock_close.assert_called_once()


# ------------------------------------------------------------------------------
# POST /api/v1/challenges/{id}/publish Tests
# ------------------------------------------------------------------------------


def test_publish_challenge_unauthorized(mock_db_session):
    """POST /api/v1/challenges/{id}/publish without token yields 401 Unauthorized."""
    test_id = uuid.uuid4()
    response = client.post(f"/api/v1/challenges/{test_id}/publish")
    assert response.status_code == 401


def test_publish_challenge_not_found(mock_db_session, auth_company_1):
    """POST /api/v1/challenges/{id}/publish with non-existent UUID yields 404 Not Found."""
    test_id = uuid.uuid4()
    with patch(
        "src.services.challenge_service.ChallengeRepository.get_by_id",
        new=AsyncMock(return_value=None),
    ):
        response = client.post(f"/api/v1/challenges/{test_id}/publish")
        assert response.status_code == 404


def test_publish_challenge_forbidden_for_non_owner(mock_db_session, auth_company_2):
    """POST /api/v1/challenges/{id}/publish owned by Company 1 yields 403 when called by Company 2."""
    test_id = uuid.uuid4()
    sample = create_sample_challenge(challenge_id=test_id, company_id=COMPANY_ID_1, status="DRAFT")

    with patch(
        "src.services.challenge_service.ChallengeRepository.get_by_id",
        new=AsyncMock(return_value=sample),
    ):
        response = client.post(f"/api/v1/challenges/{test_id}/publish")
        assert response.status_code == 403
        assert "ownership" in response.json()["detail"]


@pytest.mark.parametrize("non_draft_status", ["OPEN", "IN_PROGRESS", "CLOSED", "CANCELLED"])
def test_publish_challenge_non_draft_rejected(mock_db_session, auth_company_1, non_draft_status):
    """POST /api/v1/challenges/{id}/publish yields 422 if challenge is not in DRAFT status."""
    test_id = uuid.uuid4()
    sample = create_sample_challenge(
        challenge_id=test_id, company_id=COMPANY_ID_1, status=non_draft_status
    )

    with patch(
        "src.services.challenge_service.ChallengeRepository.get_by_id",
        new=AsyncMock(return_value=sample),
    ):
        response = client.post(f"/api/v1/challenges/{test_id}/publish")
        assert response.status_code == 422
        assert "Only DRAFT challenges can be published" in response.json()["detail"]


def test_publish_challenge_success(mock_db_session, auth_company_1):
    """POST /api/v1/challenges/{id}/publish transitions DRAFT to OPEN successfully."""
    test_id = uuid.uuid4()
    sample = create_sample_challenge(challenge_id=test_id, company_id=COMPANY_ID_1, status="DRAFT")
    published_sample = create_sample_challenge(
        challenge_id=test_id, company_id=COMPANY_ID_1, status="OPEN"
    )

    with patch(
        "src.services.challenge_service.ChallengeRepository.get_by_id",
        new=AsyncMock(return_value=sample),
    ), patch(
        "src.services.challenge_service.ChallengeRepository.publish_challenge",
        new=AsyncMock(return_value=published_sample),
    ) as mock_publish:
        response = client.post(f"/api/v1/challenges/{test_id}/publish")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_id)
        assert data["status"] == "OPEN"
        mock_publish.assert_called_once()


# ------------------------------------------------------------------------------
# GET /api/v1/challenges/company/me Tests (Portfolio & Summary)
# ------------------------------------------------------------------------------


def test_company_portfolio_unauthorized(mock_db_session):
    """GET /api/v1/challenges/company/me without token yields 401 Unauthorized."""
    response = client.get("/api/v1/challenges/company/me")
    assert response.status_code == 401


def test_company_portfolio_forbidden_for_student(mock_db_session, auth_student):
    """GET /api/v1/challenges/company/me yields 403 for non-company roles."""
    response = client.get("/api/v1/challenges/company/me")
    assert response.status_code == 403


def test_company_portfolio_success_with_summary(mock_db_session, auth_company_1):
    """GET /api/v1/challenges/company/me returns owned challenges with status breakdown metrics."""
    c1 = create_sample_challenge(company_id=COMPANY_ID_1, status="DRAFT", title="Draft 1")
    c2 = create_sample_challenge(company_id=COMPANY_ID_1, status="OPEN", title="Open 1")
    c3 = create_sample_challenge(company_id=COMPANY_ID_1, status="CLOSED", title="Closed 1")

    mock_status_counts = {"DRAFT": 1, "OPEN": 1, "CLOSED": 1}

    with patch(
        "src.services.challenge_service.ChallengeRepository.get_company_portfolio",
        new=AsyncMock(return_value=([c1, c2, c3], 3, mock_status_counts)),
    ):
        response = client.get("/api/v1/challenges/company/me?page=1&limit=10")
        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 3
        assert data["page"] == 1
        assert data["limit"] == 10
        assert len(data["items"]) == 3

        # Verify summary metrics
        summary = data["summary"]
        assert summary["total"] == 3
        assert summary["draft"] == 1
        assert summary["open"] == 1
        assert summary["closed"] == 1
        assert summary["in_progress"] == 0
        assert summary["cancelled"] == 0


def test_company_portfolio_data_isolation(mock_db_session, auth_company_2):
    """GET /api/v1/challenges/company/me guarantees strict multi-tenant isolation per company."""
    c_company_2 = create_sample_challenge(
        company_id=COMPANY_ID_2, status="OPEN", title="Globex Special Challenge"
    )

    mock_status_counts = {"OPEN": 1}

    with patch(
        "src.services.challenge_service.ChallengeRepository.get_company_portfolio",
        new=AsyncMock(return_value=([c_company_2], 1, mock_status_counts)),
    ) as mock_get_portfolio:
        response = client.get("/api/v1/challenges/company/me")
        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["company_id"] == str(COMPANY_ID_2)

        # Confirm repository was queried specifically with Company 2's ID
        mock_get_portfolio.assert_called_once()
        _, kwargs = mock_get_portfolio.call_args
        assert kwargs["company_id"] == COMPANY_ID_2
