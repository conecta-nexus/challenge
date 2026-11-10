"""ChallengeAttachment SQLAlchemy ORM model definition."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import BIGINT, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class ChallengeAttachment(Base):
    """ChallengeAttachment ORM model representing file attachments for challenges."""

    __tablename__ = "challenge_attachments"

    __table_args__ = (
        CheckConstraint(
            "file_size_bytes <= 10485760",
            name="ck_challenge_attachments_file_size_bytes",
        ),
        CheckConstraint(
            "mime_type IN ('application/pdf', 'image/png', 'image/jpeg', 'image/webp')",
            name="ck_challenge_attachments_mime_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("challenges.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BIGINT,
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    storage_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
