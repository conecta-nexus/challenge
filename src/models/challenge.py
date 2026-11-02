"""Challenge SQLAlchemy ORM model definition."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class Challenge(Base):
    """Challenge ORM model representing business challenges published on Conecta Nexus."""

    __tablename__ = "challenges"

    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'OPEN', 'IN_PROGRESS', 'CLOSED', 'CANCELLED')",
            name="ck_challenges_status",
        ),
        CheckConstraint(
            "difficulty_level IN ('BEGINNER', 'INTERMEDIATE', 'ADVANCED')",
            name="ck_challenges_difficulty_level",
        ),
        CheckConstraint(
            "modality IN ('REMOTE', 'HYBRID', 'ON_SITE')",
            name="ck_challenges_modality",
        ),
        CheckConstraint(
            "min_semester BETWEEN 6 AND 10",
            name="ck_challenges_min_semester",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    business_process: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="DRAFT",
        server_default=text("'DRAFT'"),
    )
    difficulty_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    modality: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    min_semester: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=6,
        server_default=text("6"),
    )
    economic_sector: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    required_skills: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    knowledge_areas: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    def __init__(self, **kwargs: Any) -> None:
        """Initialize Challenge model instance with default ORM values."""
        kwargs.setdefault("status", "DRAFT")
        kwargs.setdefault("min_semester", 6)
        if "required_skills" not in kwargs or kwargs["required_skills"] is None:
            kwargs["required_skills"] = []
        if "knowledge_areas" not in kwargs or kwargs["knowledge_areas"] is None:
            kwargs["knowledge_areas"] = []
        super().__init__(**kwargs)
