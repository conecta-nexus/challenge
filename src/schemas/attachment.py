"""Public and owner-facing schemas for challenge attachments."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AttachmentResponse(BaseModel):
    """Return stored attachment metadata without exposing internal object keys."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    challenge_id: UUID
    file_name: str
    file_size_bytes: int = Field(ge=1, le=10 * 1024 * 1024)
    mime_type: str
    created_at: datetime


class AttachmentDownloadResponse(AttachmentResponse):
    """Add an expiring, read-only object-storage download URL."""

    download_url: str
