"""Private technical attachment endpoints (HU-07)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.dependencies import require_role
from src.core.security import AuthenticatedUser
from src.schemas.attachment import AttachmentDownloadResponse, AttachmentResponse
from src.services.attachment_service import AttachmentService, AttachmentValidationError
from src.services.storage_service import StorageServiceError

router = APIRouter(prefix="/challenges/{challenge_id}/attachments", tags=["Attachments"])


def get_attachment_service() -> AttachmentService:
    """Provide an injectable attachment service for request handlers and tests."""
    return AttachmentService()


@router.post(
    "",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={413: {"description": "File exceeds 10 MiB"}, 415: {"description": "Unsupported file"}},
)
async def upload_attachment(
    challenge_id: UUID,
    file: Annotated[UploadFile, File(description="PDF, PNG, JPEG, or WebP (up to 10 MiB)")],
    current_user: Annotated[AuthenticatedUser, Depends(require_role("COMPANY"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AttachmentService, Depends(get_attachment_service)],
) -> AttachmentResponse:
    try:
        attachment = await service.upload(db, challenge_id, current_user.id, file)
        return AttachmentResponse.model_validate(attachment)
    except AttachmentValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except StorageServiceError as exc:
        raise HTTPException(status_code=503, detail="Attachment storage unavailable") from exc


@router.get("", response_model=list[AttachmentDownloadResponse])
async def list_attachments(
    challenge_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_role("COMPANY"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AttachmentService, Depends(get_attachment_service)],
) -> list[AttachmentDownloadResponse]:
    try:
        return await service.list_attachments(db, challenge_id, current_user.id)
    except StorageServiceError as exc:
        raise HTTPException(status_code=503, detail="Attachment storage unavailable") from exc


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    challenge_id: UUID,
    attachment_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_role("COMPANY"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AttachmentService, Depends(get_attachment_service)],
) -> None:
    try:
        await service.delete(db, challenge_id, attachment_id, current_user.id)
    except StorageServiceError as exc:
        raise HTTPException(status_code=503, detail="Attachment storage unavailable") from exc
