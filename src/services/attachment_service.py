"""Attachment workflows: validation, ownership, storage, and persistence."""

import logging
from pathlib import PurePath
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.attachment import ChallengeAttachment
from src.repositories.attachment_repository import AttachmentRepository
from src.schemas.attachment import AttachmentDownloadResponse
from src.services.challenge_service import ChallengeService
from src.services.storage_service import StorageService

logger = logging.getLogger(__name__)

MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024
READ_CHUNK_SIZE = 1024 * 1024
SIGNED_URL_TTL_SECONDS = 3600

# Client-supplied Content-Type is verified against the actual file header.
MIME_EXTENSIONS: dict[str, frozenset[str]] = {
    "application/pdf": frozenset({".pdf"}),
    "image/png": frozenset({".png"}),
    "image/jpeg": frozenset({".jpg", ".jpeg"}),
    "image/webp": frozenset({".webp"}),
}


class AttachmentValidationError(ValueError):
    """A client-supplied attachment is invalid."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class AttachmentService:
    """Manage secure attachments while reusing the existing storage adapter."""

    def __init__(self, storage: StorageService | None = None) -> None:
        self._storage = storage if storage is not None else StorageService()

    @staticmethod
    def _verify_mutable(status_name: str) -> None:
        if status_name not in {"DRAFT", "OPEN"}:
            raise HTTPException(
                status_code=422,
                detail="Attachments can only be modified on DRAFT or OPEN challenges",
            )

    @staticmethod
    def _detect_mime(header: bytes) -> str | None:
        if header.startswith(b"%PDF-"):
            return "application/pdf"
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if header.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
            return "image/webp"
        return None

    @classmethod
    async def _validate_upload(cls, file: UploadFile) -> tuple[str, str, int]:
        """Read in bounded chunks and verify filename, MIME, and binary signature."""
        filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
        filename = filename.strip()
        if not filename or filename in {".", ".."} or len(filename) > 255:
            raise AttachmentValidationError("Invalid attachment filename", 422)

        mime = (file.content_type or "").split(";", 1)[0].strip().lower()
        suffix = PurePath(filename).suffix.lower()
        if mime not in MIME_EXTENSIONS or suffix not in MIME_EXTENSIONS[mime]:
            raise AttachmentValidationError("Unsupported attachment media type", 415)

        total = 0
        header = b""
        try:
            while chunk := await file.read(READ_CHUNK_SIZE):
                total += len(chunk)
                if total > MAX_ATTACHMENT_SIZE:
                    raise AttachmentValidationError("Attachment exceeds 10 MiB", 413)
                if len(header) < 12:
                    header += chunk[: 12 - len(header)]

            if total == 0 or cls._detect_mime(header) != mime:
                raise AttachmentValidationError("Attachment MIME does not match its signature", 415)

            # Starlette uses a spooled file. Rewind it instead of allocating a second buffer.
            await file.seek(0)
            return filename, mime, total
        except Exception:
            await file.seek(0)
            raise

    async def upload(
        self,
        db: AsyncSession,
        challenge_id: UUID,
        company_id: UUID,
        file: UploadFile,
    ) -> ChallengeAttachment:
        challenge = await ChallengeService.get_challenge_for_owner(db, challenge_id, company_id)
        self._verify_mutable(challenge.status)
        filename, mime, total = await self._validate_upload(file)

        attachment_id = uuid4()
        destination = f"challenges/{challenge_id}/attachments/{attachment_id}"
        uploaded = False
        try:
            storage_path = await self._storage.upload_file(file.file, destination, mime)
            uploaded = True
            attachment = ChallengeAttachment(
                id=attachment_id,
                challenge_id=challenge_id,
                file_name=filename,
                file_size_bytes=total,
                mime_type=mime,
                storage_path=storage_path,
                uploaded_by=company_id,
            )
            return await AttachmentRepository.create(db, attachment)
        except Exception:
            await db.rollback()
            if uploaded:
                try:
                    await self._storage.delete_file(destination)
                except Exception:
                    logger.exception("Could not compensate failed attachment persistence")
            raise

    async def list_attachments(
        self,
        db: AsyncSession,
        challenge_id: UUID,
        company_id: UUID,
    ) -> list[AttachmentDownloadResponse]:
        await ChallengeService.get_challenge_for_owner(db, challenge_id, company_id)
        attachments = await AttachmentRepository.list_by_challenge(db, challenge_id)
        items: list[AttachmentDownloadResponse] = []
        for attachment in attachments:
            signed_url = await self._storage.generate_signed_url(
                attachment.storage_path, SIGNED_URL_TTL_SECONDS
            )
            items.append(
                AttachmentDownloadResponse.model_validate(
                    {
                        "id": attachment.id,
                        "challenge_id": attachment.challenge_id,
                        "file_name": attachment.file_name,
                        "file_size_bytes": attachment.file_size_bytes,
                        "mime_type": attachment.mime_type,
                        "created_at": attachment.created_at,
                        "download_url": signed_url,
                    }
                )
            )
        return items

    async def delete(
        self,
        db: AsyncSession,
        challenge_id: UUID,
        attachment_id: UUID,
        company_id: UUID,
    ) -> None:
        challenge = await ChallengeService.get_challenge_for_owner(db, challenge_id, company_id)
        self._verify_mutable(challenge.status)
        attachment = await AttachmentRepository.get_for_deletion(db, challenge_id, attachment_id)
        if attachment is None:
            raise HTTPException(status_code=404, detail="Attachment not found")

        try:
            # Remove the object before committing metadata removal. Provider failure
            # leaves the database row intact and allows a safe retry.
            await self._storage.delete_file(attachment.storage_path)
            await AttachmentRepository.delete(db, attachment)
        except Exception:
            await db.rollback()
            raise
