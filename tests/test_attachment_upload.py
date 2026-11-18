"""Endpoint and workflow tests for HU-07 attachment management."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.challenge.main import app
from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.core.security import AuthenticatedUser
from src.repositories.attachment_repository import AttachmentRepository
from src.repositories.challenge_repository import ChallengeRepository
from src.routers.attachments import get_attachment_service
from src.services.attachment_service import AttachmentService
from src.services.storage_service import StorageServiceError

CHALLENGE_ID = uuid4()
OWNER_ID = uuid4()
OTHER_ID = uuid4()
ATTACHMENT_ID = uuid4()
ENDPOINT = f"/api/v1/challenges/{CHALLENGE_ID}/attachments"
PDF_CONTENT = b"%PDF-1.7\ntechnical attachment"


class FakeStorage:
    def __init__(self) -> None:
        self.upload_file = AsyncMock(side_effect=self._upload)
        self.generate_signed_url = AsyncMock(return_value="https://storage.example/file?signature=temp")
        self.delete_file = AsyncMock(return_value=True)

    @staticmethod
    async def _upload(file_obj, destination_path, content_type):
        assert file_obj.read()  # The file was rewound after chunked validation.
        assert content_type in {"application/pdf", "image/png", "image/jpeg", "image/webp"}
        return destination_path


def sample_attachment():
    return SimpleNamespace(
        id=ATTACHMENT_ID,
        challenge_id=CHALLENGE_ID,
        file_name="spec.pdf",
        file_size_bytes=len(PDF_CONTENT),
        mime_type="application/pdf",
        storage_path=f"challenges/{CHALLENGE_ID}/attachments/{ATTACHMENT_ID}",
        uploaded_by=OWNER_ID,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def environment(monkeypatch):
    db = AsyncMock()
    storage = FakeStorage()
    challenge = SimpleNamespace(id=CHALLENGE_ID, company_id=OWNER_ID, status="OPEN")

    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=OWNER_ID,
        email="owner@example.com",
        role="COMPANY",
    )
    app.dependency_overrides[get_attachment_service] = lambda: AttachmentService(storage)
    mock_challenge = AsyncMock(return_value=challenge)
    monkeypatch.setattr(ChallengeRepository, "get_by_id", mock_challenge)
    mock_create = AsyncMock(side_effect=lambda db, attachment: saved_attachment(attachment))
    monkeypatch.setattr(AttachmentRepository, "create", mock_create)

    yield SimpleNamespace(db=db, storage=storage, challenge=challenge, create=mock_create)
    app.dependency_overrides.clear()


def saved_attachment(attachment):
    attachment.created_at = datetime.now(timezone.utc)
    return attachment


def upload(content: bytes = PDF_CONTENT, name: str = "spec.pdf", mime: str = "application/pdf"):
    return TestClient(app).post(ENDPOINT, files={"file": (name, content, mime)})


def test_valid_upload_returns_201_and_metadata(environment):
    response = upload()
    assert response.status_code == 201, response.text
    assert response.json()["file_name"] == "spec.pdf"
    assert response.json()["file_size_bytes"] == len(PDF_CONTENT)
    assert "storage_path" not in response.json()
    environment.storage.upload_file.assert_awaited_once()
    environment.create.assert_awaited_once()


def test_valid_exact_10_mib_boundary(environment):
    content = b"%PDF-" + b"A" * (10 * 1024 * 1024 - 5)
    response = upload(content)
    assert response.status_code == 201, response.text
    assert response.json()["file_size_bytes"] == 10 * 1024 * 1024


def test_oversized_file_returns_413_before_storage(environment):
    content = b"%PDF-" + b"A" * (10 * 1024 * 1024 - 4)
    response = upload(content)
    assert response.status_code == 413, response.text
    environment.storage.upload_file.assert_not_awaited()
    environment.create.assert_not_awaited()


@pytest.mark.parametrize(
    "filename,mime,content",
    [
        ("script.exe", "application/octet-stream", b"MZfake"),
        ("fake.pdf", "application/pdf", b"MZnot-a-pdf"),
        ("image.pdf", "image/png", b"\x89PNG\r\n\x1a\n"),
        ("image.png", "application/pdf", PDF_CONTENT),
        ("empty.pdf", "application/pdf", b""),
    ],
)
def test_invalid_mime_or_signature_returns_415(environment, filename, mime, content):
    response = upload(content, filename, mime)
    assert response.status_code == 415, response.text
    environment.storage.upload_file.assert_not_awaited()


def test_missing_authentication_returns_401(environment):
    app.dependency_overrides.pop(get_current_user)
    response = upload()
    assert response.status_code == 401
    environment.storage.upload_file.assert_not_awaited()


def test_student_cannot_upload(environment):
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=uuid4(), email="student@ufps.edu.co", role="STUDENT"
    )
    response = upload()
    assert response.status_code == 403
    environment.storage.upload_file.assert_not_awaited()


def test_other_company_cannot_upload(environment):
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=OTHER_ID, email="other@example.com", role="COMPANY"
    )
    response = upload()
    assert response.status_code == 403
    environment.storage.upload_file.assert_not_awaited()


def test_locked_challenge_cannot_upload(environment):
    environment.challenge.status = "CLOSED"
    response = upload()
    assert response.status_code == 422
    environment.storage.upload_file.assert_not_awaited()


def test_missing_challenge_returns_404(environment, monkeypatch):
    monkeypatch.setattr(ChallengeRepository, "get_by_id", AsyncMock(return_value=None))
    response = upload()
    assert response.status_code == 404


def test_list_returns_ephemeral_urls_without_storage_paths(environment, monkeypatch):
    monkeypatch.setattr(
        AttachmentRepository, "list_by_challenge", AsyncMock(return_value=[sample_attachment()])
    )
    response = TestClient(app).get(ENDPOINT)
    assert response.status_code == 200, response.text
    assert response.json()[0]["download_url"].startswith("https://storage.example/")
    assert "storage_path" not in response.json()[0]
    environment.storage.generate_signed_url.assert_awaited_once()


def test_list_rejects_other_company(environment):
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=OTHER_ID, email="other@example.com", role="COMPANY"
    )
    response = TestClient(app).get(ENDPOINT)
    assert response.status_code == 403
    environment.storage.generate_signed_url.assert_not_awaited()


def test_delete_removes_storage_object_and_metadata(environment, monkeypatch):
    monkeypatch.setattr(
        AttachmentRepository, "get_for_deletion", AsyncMock(return_value=sample_attachment())
    )
    delete = AsyncMock()
    monkeypatch.setattr(AttachmentRepository, "delete", delete)
    response = TestClient(app).delete(f"{ENDPOINT}/{ATTACHMENT_ID}")
    assert response.status_code == 204, response.text
    environment.storage.delete_file.assert_awaited_once()
    delete.assert_awaited_once()


def test_delete_missing_attachment_returns_404(environment, monkeypatch):
    monkeypatch.setattr(AttachmentRepository, "get_for_deletion", AsyncMock(return_value=None))
    response = TestClient(app).delete(f"{ENDPOINT}/{ATTACHMENT_ID}")
    assert response.status_code == 404
    environment.storage.delete_file.assert_not_awaited()


def test_storage_failure_returns_503_without_metadata(environment):
    environment.storage.upload_file.side_effect = StorageServiceError("MinIO unavailable")
    response = upload()
    assert response.status_code == 503
    environment.create.assert_not_awaited()


def test_db_failure_compensates_uploaded_object(environment):
    environment.create.side_effect = RuntimeError("DB write failed")
    with pytest.raises(RuntimeError, match="DB write failed"):
        upload()
    environment.db.rollback.assert_awaited_once()
    environment.storage.delete_file.assert_awaited_once()


@pytest.mark.parametrize(
    "filename,mime,content",
    [
        ("sketch.png", "image/png", b"\x89PNG\r\n\x1a\n" + b"png-payload"),
        ("photo.jpg", "image/jpeg", b"\xff\xd8\xff" + b"jpeg-payload"),
        ("photo.jpeg", "image/jpeg", b"\xff\xd8\xff" + b"jpeg-payload"),
        ("mock.webp", "image/webp", b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP"),
    ],
)
def test_supported_image_formats(environment, filename, mime, content):
    response = upload(content, filename, mime)
    assert response.status_code == 201, response.text
    assert response.json()["mime_type"] == mime


def test_list_signed_url_provider_failure_returns_503(environment, monkeypatch):
    monkeypatch.setattr(
        AttachmentRepository, "list_by_challenge", AsyncMock(return_value=[sample_attachment()])
    )
    environment.storage.generate_signed_url.side_effect = StorageServiceError("down")
    response = TestClient(app).get(ENDPOINT)
    assert response.status_code == 503


def test_delete_storage_failure_preserves_database_row(environment, monkeypatch):
    monkeypatch.setattr(
        AttachmentRepository, "get_for_deletion", AsyncMock(return_value=sample_attachment())
    )
    delete = AsyncMock()
    monkeypatch.setattr(AttachmentRepository, "delete", delete)
    environment.storage.delete_file.side_effect = StorageServiceError("down")
    response = TestClient(app).delete(f"{ENDPOINT}/{ATTACHMENT_ID}")
    assert response.status_code == 503
    delete.assert_not_awaited()
    environment.db.rollback.assert_awaited_once()


def test_locked_challenge_cannot_delete(environment):
    environment.challenge.status = "CLOSED"
    response = TestClient(app).delete(f"{ENDPOINT}/{ATTACHMENT_ID}")
    assert response.status_code == 422
    environment.storage.delete_file.assert_not_awaited()
