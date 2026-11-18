"""Tests for public catalog list and detail endpoint behavior."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from src.challenge.main import app
from src.core.database import get_db
from src.models.attachment import ChallengeAttachment
from src.models.challenge import Challenge
from src.repositories.catalog_repository import CatalogRepository
from src.schemas.catalog import CatalogAttachmentResponse
from src.services.catalog_service import (
    CatalogChallengeNotFoundError,
    CatalogService,
)
from src.services.storage_service import StorageServiceError


client = TestClient(app)


def build_challenge(status: str = "OPEN") -> Challenge:
    """Build a challenge for catalog endpoint tests."""
    now = datetime.now(timezone.utc)
    return Challenge(
        id=uuid4(),
        company_id=uuid4(),
        title="Smart Inventory",
        description="Improve inventory forecasting accuracy.",
        business_process="Inventory Management",
        status=status,
        difficulty_level="INTERMEDIATE",
        modality="REMOTE",
        min_semester=7,
        economic_sector="Retail",
        required_skills=["Python"],
        knowledge_areas=["Data Science"],
        created_at=now,
        updated_at=now,
    )


def build_attachment(challenge_id) -> ChallengeAttachment:
    """Build attachment metadata without exposing its storage path publicly."""
    return ChallengeAttachment(
        id=uuid4(),
        challenge_id=challenge_id,
        file_name="requirements.pdf",
        file_size_bytes=2048,
        mime_type="application/pdf",
        storage_path=f"challenges/{challenge_id}/requirements.pdf",
        uploaded_by=uuid4(),
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_db_session():
    """Override the database dependency for endpoint tests."""
    session = AsyncMock()

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session
    app.dependency_overrides.pop(get_db, None)


def test_catalog_detail_returns_open_challenge(mock_db_session) -> None:
    """Return the complete public projection and signed attachment URL."""
    challenge = build_challenge()
    attachment_id = uuid4()
    detail = CatalogService.to_catalog_detail(challenge).model_copy(
        update={
            "attachments": [
                CatalogAttachmentResponse(
                    id=attachment_id,
                    file_name="requirements.pdf",
                    file_size_bytes=2048,
                    mime_type="application/pdf",
                    download_url="https://storage.test/signed",
                    created_at=datetime.now(timezone.utc),
                )
            ]
        }
    )

    with patch(
        "src.routers.catalog.CatalogService.get_catalog_detail",
        new=AsyncMock(return_value=detail),
    ):
        response = client.get(f"/api/v1/challenges/catalog/{challenge.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(challenge.id)
    assert payload["status"] == "OPEN"
    assert payload["attachments"][0]["id"] == str(attachment_id)
    assert payload["attachments"][0]["download_url"].startswith("https://")
    assert "storage_path" not in payload["attachments"][0]
    assert "uploaded_by" not in payload["attachments"][0]


@pytest.mark.parametrize("hidden_status", ["DRAFT", "CLOSED"])
def test_catalog_detail_hides_non_open_challenges(
    mock_db_session,
    hidden_status: str,
) -> None:
    """Return 404 for draft and closed challenges instead of leaking them."""
    challenge = build_challenge(hidden_status)

    with patch(
        "src.routers.catalog.CatalogService.get_catalog_detail",
        new=AsyncMock(
            side_effect=CatalogChallengeNotFoundError("Not publicly visible")
        ),
    ):
        response = client.get(f"/api/v1/challenges/catalog/{challenge.id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Open challenge not found"}


def test_catalog_detail_returns_503_when_storage_fails(mock_db_session) -> None:
    """Translate signed URL generation failures into a stable public response."""
    with patch(
        "src.routers.catalog.CatalogService.get_catalog_detail",
        new=AsyncMock(side_effect=StorageServiceError("MinIO unavailable")),
    ):
        response = client.get(f"/api/v1/challenges/catalog/{uuid4()}")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Attachment storage is temporarily unavailable"
    }


@pytest.mark.asyncio
async def test_catalog_service_builds_signed_read_only_attachments() -> None:
    """Generate signed URLs while excluding storage and uploader internals."""
    db = AsyncMock()
    challenge = build_challenge()
    attachment = build_attachment(challenge.id)
    storage = MagicMock()
    storage.generate_signed_url = AsyncMock(
        return_value="https://storage.test/signed-requirements"
    )

    with patch(
        "src.services.catalog_service.CatalogRepository.get_open_challenge",
        new=AsyncMock(return_value=challenge),
    ), patch(
        "src.services.catalog_service.CatalogRepository.list_public_attachments",
        new=AsyncMock(return_value=[attachment]),
    ):
        result = await CatalogService.get_catalog_detail(
            db,
            challenge.id,
            storage_service=storage,
        )

    assert result.status == "OPEN"
    assert len(result.attachments) == 1
    assert result.attachments[0].download_url.endswith("signed-requirements")
    assert "storage_path" not in result.attachments[0].model_dump()
    assert "uploaded_by" not in result.attachments[0].model_dump()
    storage.generate_signed_url.assert_awaited_once_with(attachment.storage_path)


@pytest.mark.asyncio
async def test_catalog_service_rejects_missing_or_hidden_challenge() -> None:
    """Stop before loading attachments when no OPEN challenge exists."""
    db = AsyncMock()
    challenge_id = uuid4()

    with patch(
        "src.services.catalog_service.CatalogRepository.get_open_challenge",
        new=AsyncMock(return_value=None),
    ), patch(
        "src.services.catalog_service.CatalogRepository.list_public_attachments",
        new=AsyncMock(),
    ) as list_attachments:
        with pytest.raises(CatalogChallengeNotFoundError):
            await CatalogService.get_catalog_detail(db, challenge_id)

    list_attachments.assert_not_awaited()


@pytest.mark.asyncio
async def test_repository_get_open_challenge_filters_status() -> None:
    """Build a detail query constrained by both ID and OPEN status."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    challenge_id = uuid4()

    challenge = await CatalogRepository.get_open_challenge(db, challenge_id)

    assert challenge is None
    statement = db.execute.await_args.args[0]
    compiled = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert str(challenge_id) in compiled
    assert "challenges.status = 'OPEN'" in compiled


@pytest.mark.asyncio
async def test_repository_lists_attachments_in_creation_order() -> None:
    """Load attachment metadata with deterministic oldest-first ordering."""
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute.return_value = result
    challenge_id = uuid4()

    attachments = await CatalogRepository.list_public_attachments(db, challenge_id)

    assert attachments == []
    statement = db.execute.await_args.args[0]
    compiled = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert str(challenge_id) in compiled
    assert "ORDER BY challenge_attachments.created_at ASC" in compiled
