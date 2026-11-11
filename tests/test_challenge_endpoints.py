"""Integration tests for challenge creation, ownership verification, and state locking (HU-06 / RB-06)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.challenge.main import app
from src.core.database import get_db
from src.core.security import AuthenticatedUser
from src.core.dependencies import get_current_user, require_role
from src.models.challenge import Challenge
from src.schemas.challenge import ChallengeResponse

client = TestClient(app)

COMPANY_ID_1 = uuid.uuid4()
COMPANY_ID_2 = uuid.uuid4()
STUDENT_ID = uuid.uuid4()


def create_sample_challenge(
    challenge_id: uuid.UUID | None = None,
    company_id: uuid.UUID = COMPANY_ID_1,
    status: str = "DRAFT",
    title: str = "Automated Inventory Tracking",
) -> Challenge:
    """Helper to instantiate mock Challenge ORM instance."""
    return Challenge(
        id=challenge_id or uuid.uuid4(),
        company_id=company_id,
        title=title,
        description="Develop an automated inventory tracking module with barcode scanning.",
        business_process="Warehouse Operations",
        status=status,
        difficulty_level="INTERMEDIATE",
        modality="HYBRID",
        min_semester=7,
        economic_sector="Logistics & Retail",
        required_skills=["Python", "FastAPI", "PostgreSQL"],
        knowledge_areas=["Software Engineering", "Logistics"],
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
    yield user
    app.dependency_overrides.pop(get_current_user, None)


# ------------------------------------------------------------------------------
# POST /api/v1/challenges Tests
# ------------------------------------------------------------------------------


def test_create_challenge_unauthorized(mock_db_session):
    """POST /api/v1/challenges without token yields 401 Unauthorized."""
    payload = {
        "title": "Inventory Tracking",
        "description": "Barcode system",
        "business_process": "Logistics",
        "difficulty_level": "INTERMEDIATE",
        "modality": "REMOTE",
        "min_semester": 7,
        "economic_sector": "Retail",
        "required_skills": ["Python"],
        "knowledge_areas": ["Databases"],
    }
    response = client.post("/api/v1/challenges", json=payload)
    assert response.status_code == 401


def test_create_challenge_forbidden_for_non_company(mock_db_session, auth_student):
    """POST /api/v1/challenges with STUDENT role yields 403 Forbidden."""
    payload = {
        "title": "Inventory Tracking",
        "description": "Barcode system",
        "business_process": "Logistics",
        "difficulty_level": "INTERMEDIATE",
        "modality": "REMOTE",
        "min_semester": 7,
        "economic_sector": "Retail",
        "required_skills": ["Python"],
        "knowledge_areas": ["Databases"],
    }
    response = client.post("/api/v1/challenges", json=payload)
    assert response.status_code == 403


def test_create_challenge_success_company(mock_db_session, auth_company_1):
    """POST /api/v1/challenges creates challenge for COMPANY with 201 Created."""
    created_sample = create_sample_challenge(company_id=COMPANY_ID_1, status="DRAFT")

    with patch(
        "src.services.challenge_service.ChallengeRepository.create",
        new=AsyncMock(return_value=created_sample),
    ) as mock_create:
        payload = {
            "title": "Automated Inventory Tracking",
            "description": "Develop an automated inventory tracking module with barcode scanning.",
            "business_process": "Warehouse Operations",
            "difficulty_level": "INTERMEDIATE",
            "modality": "HYBRID",
            "min_semester": 7,
            "economic_sector": "Logistics & Retail",
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
            "knowledge_areas": ["Software Engineering", "Logistics"],
        }
        response = client.post("/api/v1/challenges", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == str(created_sample.id)
        assert data["company_id"] == str(COMPANY_ID_1)
        assert data["status"] == "DRAFT"
        assert data["title"] == "Automated Inventory Tracking"
        mock_create.assert_called_once()


def test_create_challenge_validation_failure(mock_db_session, auth_company_1):
    """POST /api/v1/challenges fails with 422 if min_semester is below 6."""
    payload = {
        "title": "Invalid Semester Challenge",
        "description": "Description",
        "business_process": "Finance",
        "difficulty_level": "BEGINNER",
        "modality": "REMOTE",
        "min_semester": 4,  # Violates RB-02 (between 6 and 10)
        "economic_sector": "Fintech",
    }
    response = client.post("/api/v1/challenges", json=payload)
    assert response.status_code == 422


# ------------------------------------------------------------------------------
# GET /api/v1/challenges/{id} Tests
# ------------------------------------------------------------------------------


def test_get_challenge_unauthorized(mock_db_session):
    """GET /api/v1/challenges/{id} without token yields 401 Unauthorized."""
    test_id = uuid.uuid4()
    response = client.get(f"/api/v1/challenges/{test_id}")
    assert response.status_code == 401


def test_get_challenge_not_found(mock_db_session, auth_company_1):
    """GET /api/v1/challenges/{id} with non-existent UUID yields 404 Not Found."""
    test_id = uuid.uuid4()
    with patch(
        "src.services.challenge_service.ChallengeRepository.get_by_id",
        new=AsyncMock(return_value=None),
    ):
        response = client.get(f"/api/v1/challenges/{test_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Challenge not found"


def test_get_challenge_forbidden_for_different_company(mock_db_session, auth_company_2):
    """GET /api/v1/challenges/{id} owned by Company 1 requested by Company 2 yields 403 (RB-06)."""
    test_id = uuid.uuid4()
    sample = create_sample_challenge(challenge_id=test_id, company_id=COMPANY_ID_1)

    with patch(
        "src.services.challenge_service.ChallengeRepository.get_by_id",
        new=AsyncMock(return_value=sample),
    ):
        response = client.get(f"/api/v1/challenges/{test_id}")
        assert response.status_code == 403
        assert "ownership" in response.json()["detail"]


def test_get_challenge_success_for_owner(mock_db_session, auth_company_1):
    """GET /api/v1/challenges/{id} returns full details when requested by owning company."""
    test_id = uuid.uuid4()
    sample = create_sample_challenge(challenge_id=test_id, company_id=COMPANY_ID_1)

    with patch(
        "src.services.challenge_service.ChallengeRepository.get_by_id",
        new=AsyncMock(return_value=sample),
    ):
        response = client.get(f"/api/v1/challenges/{test_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_id)
        assert data["company_id"] == str(COMPANY_ID_1)


# ------------------------------------------------------------------------------
# PATCH /api/v1/challenges/{id} Tests
# ------------------------------------------------------------------------------


def test_patch_challenge_unauthorized(mock_db_session):
    """PATCH /api/v1/challenges/{id} without token yields 401 Unauthorized."""
    test_id = uuid.uuid4()
    response = client.patch(f"/api/v1/challenges/{test_id}", json={"title": "New Title"})
    assert response.status_code == 401


def test_patch_challenge_not_found(mock_db_session, auth_company_1):
    """PATCH /api/v1/challenges/{id} with non-existent UUID yields 404 Not Found."""
    test_id = uuid.uuid4()
    with patch(
        "src.services.challenge_service.ChallengeRepository.get_by_id",
        new=AsyncMock(return_value=None),
    ):
        response = client.patch(f"/api/v1/challenges/{test_id}", json={"title": "New Title"})
        assert response.status_code == 404
        assert response.json()["detail"] == "Challenge not found"


def test_patch_challenge_forbidden_for_different_company(mock_db_session, auth_company_2):
    """PATCH /api/v1/challenges/{id} owned by Company 1 edited by Company 2 yields 403 (RB-06)."""
    test_id = uuid.uuid4()
    sample = create_sample_challenge(challenge_id=test_id, company_id=COMPANY_ID_1, status="DRAFT")

    with patch(
        "src.services.challenge_service.ChallengeRepository.get_by_id",
        new=AsyncMock(return_value=sample),
    ):
        response = client.patch(f"/api/v1/challenges/{test_id}", json={"title": "Hacked Title"})
        assert response.status_code == 403
        assert "ownership" in response.json()["detail"]


def test_patch_challenge_success_when_draft(mock_db_session, auth_company_1):
    """PATCH /api/v1/challenges/{id} permits edits when challenge is in DRAFT status."""
    test_id = uuid.uuid4()
    sample = create_sample_challenge(challenge_id=test_id, company_id=COMPANY_ID_1, status="DRAFT")
    updated_sample = create_sample_challenge(
        challenge_id=test_id, company_id=COMPANY_ID_1, status="DRAFT", title="Updated Draft Title"
    )

    with patch(
        "src.services.challenge_service.ChallengeRepository.get_by_id",
        new=AsyncMock(return_value=sample),
    ), patch(
        "src.services.challenge_service.ChallengeRepository.update",
        new=AsyncMock(return_value=updated_sample),
    ) as mock_update:
        response = client.patch(
            f"/api/v1/challenges/{test_id}",
            json={"title": "Updated Draft Title", "min_semester": 8},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated Draft Title"
        mock_update.assert_called_once()


def test_patch_challenge_success_when_open(mock_db_session, auth_company_1):
    """PATCH /api/v1/challenges/{id} permits edits when challenge is in OPEN status."""
    test_id = uuid.uuid4()
    sample = create_sample_challenge(challenge_id=test_id, company_id=COMPANY_ID_1, status="OPEN")
    updated_sample = create_sample_challenge(
        challenge_id=test_id, company_id=COMPANY_ID_1, status="OPEN", title="Updated Open Title"
    )

    with patch(
        "src.services.challenge_service.ChallengeRepository.get_by_id",
        new=AsyncMock(return_value=sample),
    ), patch(
        "src.services.challenge_service.ChallengeRepository.update",
        new=AsyncMock(return_value=updated_sample),
    ) as mock_update:
        response = client.patch(
            f"/api/v1/challenges/{test_id}",
            json={"title": "Updated Open Title"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated Open Title"
        mock_update.assert_called_once()


@pytest.mark.parametrize("locked_status", ["IN_PROGRESS", "CLOSED", "CANCELLED"])
def test_patch_challenge_state_locking(mock_db_session, auth_company_1, locked_status):
    """PATCH /api/v1/challenges/{id} rejects edits with 422 if IN_PROGRESS, CLOSED, or CANCELLED (RB-06)."""
    test_id = uuid.uuid4()
    sample = create_sample_challenge(
        challenge_id=test_id, company_id=COMPANY_ID_1, status=locked_status
    )

    with patch(
        "src.services.challenge_service.ChallengeRepository.get_by_id",
        new=AsyncMock(return_value=sample),
    ):
        response = client.patch(
            f"/api/v1/challenges/{test_id}",
            json={"title": "Attempted Edit on Locked Status"},
        )
        assert response.status_code == 422
        assert "Cannot modify" in response.json()["detail"]
        assert locked_status in response.json()["detail"]
