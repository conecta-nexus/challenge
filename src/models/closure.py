"""Challenge closure audit log SQLAlchemy model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class ChallengeClosureLog(Base):
    """Record a justified voluntary closure of an open challenge."""

    __tablename__ = "challenge_closure_logs"

    __table_args__ = (
        CheckConstraint(
            "previous_status = 'OPEN'",
            name="ck_challenge_closure_logs_previous_status",
        ),
        CheckConstraint(
            "target_status IN ('CLOSED', 'CANCELLED')",
            name="ck_challenge_closure_logs_target_status",
        ),
        CheckConstraint(
            "char_length(btrim(closure_reason)) >= 15",
            name="ck_challenge_closure_logs_reason_length",
        ),
        Index("ix_challenge_closure_logs_challenge_id", "challenge_id"),
        Index("ix_challenge_closure_logs_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("challenges.id"),
        nullable=False,
    )
    closed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    previous_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    target_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    closure_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
