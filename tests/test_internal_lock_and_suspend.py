"""Integration tests for internal challenge locking (RB-04) and admin suspension (HU-14)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.challenge.main import app
from src.core.database import get_db
from src.core.dependencies import get_current_user, require_role, require_scope
from src.core.security import AuthenticatedUser
from src.models.challenge import Challenge

client = TestClient(app)


def _sample_challenge(status_value: str = "OPEN") -> Challenge:
    return Challenge(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        title="Supply Chain Optimizer",
        description="Build an optimization engine for regional logistics.",
        business_process="Supply Chain",
        status=status_value,
        difficulty_level="INTERMEDIATE",
        modality="HYBRID",
        min_semester=6,
        economic_sector="Logistics",
        required_skills=["Python", "OR-Tools"],
        knowledge_areas=["Operations Research"],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_db():
    session = AsyncMock()

    async def _override():
        yield session

    app.dependency_overrides[get_db] = _override
    yield session
    app.dependency_overrides.pop(get_db, None)


def test_internal_lock_transitions_open_challenge_to_in_progress(mock_db):
    challenge = _sample_challenge("OPEN")
    caller = AuthenticatedUser(
        id=uuid.uuid4(),
        email="internal.application@conectanexus.ufps.edu.co",
        role="ADMIN",
        scopes=["internal:service"],
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: caller
    try:
        with (
            patch(
                "src.repositories.challenge_repository.ChallengeRepository.get_by_id",
                new=AsyncMock(return_value=challenge),
            ),
            patch(
                "src.repositories.challenge_repository.ChallengeRepository.lock_challenge_in_progress",
                new=AsyncMock(side_effect=lambda db, db_obj: setattr(db_obj, "status", "IN_PROGRESS") or db_obj),
            ),
        ):
            response = client.post(f"/api/v1/challenges/internal/{challenge.id}/lock")
        assert response.status_code == 200
        assert response.json()["status"] == "IN_PROGRESS"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_internal_lock_rejects_non_open_challenge_with_409(mock_db):
    challenge = _sample_challenge("IN_PROGRESS")
    caller = AuthenticatedUser(
        id=challenge.company_id,
        email="owner@acme.co",
        role="COMPANY",
        scopes=["challenge:write_own"],
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: caller
    try:
        with patch(
            "src.repositories.challenge_repository.ChallengeRepository.get_by_id",
            new=AsyncMock(return_value=challenge),
        ):
            response = client.post(f"/api/v1/challenges/internal/{challenge.id}/lock")
        assert response.status_code == 409
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_internal_lock_rejects_unrelated_student_with_403(mock_db):
    challenge = _sample_challenge("OPEN")
    caller = AuthenticatedUser(
        id=uuid.uuid4(),
        email="student@ufps.edu.co",
        role="STUDENT",
        scopes=["challenge:read"],
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: caller
    try:
        with patch(
            "src.repositories.challenge_repository.ChallengeRepository.get_by_id",
            new=AsyncMock(return_value=challenge),
        ):
            response = client.post(f"/api/v1/challenges/internal/{challenge.id}/lock")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_admin_suspend_transitions_challenge_to_cancelled(mock_db):
    challenge = _sample_challenge("OPEN")
    admin = AuthenticatedUser(
        id=uuid.uuid4(),
        email="admin@conectanexus.ufps.edu.co",
        role="ADMIN",
        scopes=["challenge:moderate", "audit:read"],
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        with (
            patch(
                "src.repositories.challenge_repository.ChallengeRepository.get_by_id",
                new=AsyncMock(return_value=challenge),
            ),
            patch(
                "src.repositories.challenge_repository.ChallengeRepository.suspend_challenge",
                new=AsyncMock(side_effect=lambda db, db_obj, **_: setattr(db_obj, "status", "CANCELLED") or db_obj),
            ),
        ):
            response = client.post(
                f"/api/v1/challenges/{challenge.id}/suspend",
                json={"justification": "Violates institutional academic integrity policy."},
            )
        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_suspend_rejects_non_admin_with_403(mock_db):
    company = AuthenticatedUser(
        id=uuid.uuid4(),
        email="company@acme.co",
        role="COMPANY",
        scopes=["challenge:write_own"],
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: company
    try:
        response = client.post(
            f"/api/v1/challenges/{uuid.uuid4()}/suspend",
            json={"justification": "Violates institutional academic integrity policy."},
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
