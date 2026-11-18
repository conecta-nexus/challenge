"""Public catalog query and privacy-safe projection service."""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.challenge import Challenge
from src.repositories.catalog_repository import CatalogRepository
from src.schemas.catalog import (
    CatalogAttachmentResponse,
    ChallengeCatalogDetailResponse,
    ChallengeCatalogItemResponse,
)
from src.services.storage_service import StorageService


class CatalogChallengeNotFoundError(LookupError):
    """Raised when a challenge is not available in the public catalog."""


class CatalogService:
    """Query open challenges and expose only public catalog fields."""

    DESCRIPTION_SNIPPET_MAX_LENGTH = 160

    @classmethod
    def create_description_snippet(
        cls,
        description: str,
        max_length: int | None = None,
    ) -> str:
        """Normalize and truncate a description without exceeding the limit."""
        limit = (
            cls.DESCRIPTION_SNIPPET_MAX_LENGTH
            if max_length is None
            else max_length
        )
        if limit < 2:
            raise ValueError("Description snippet length must be at least 2")

        normalized = " ".join(description.split())
        if len(normalized) <= limit:
            return normalized

        return f"{normalized[: limit - 1].rstrip()}…"

    @classmethod
    def to_catalog_item(cls, challenge: Challenge) -> ChallengeCatalogItemResponse:
        """Project an ORM challenge into a privacy-safe discovery item."""
        return ChallengeCatalogItemResponse.model_validate(
            {
                "id": challenge.id,
                "company_id": challenge.company_id,
                "title": challenge.title,
                "description_snippet": cls.create_description_snippet(
                    challenge.description
                ),
                "difficulty_level": challenge.difficulty_level,
                "modality": challenge.modality,
                "min_semester": challenge.min_semester,
                "economic_sector": challenge.economic_sector,
                "required_skills": challenge.required_skills,
                "knowledge_areas": challenge.knowledge_areas,
                "created_at": challenge.created_at,
            }
        )

    @staticmethod
    def to_catalog_detail(challenge: Challenge) -> ChallengeCatalogDetailResponse:
        """Project an open challenge into its privacy-safe public detail shape."""
        return ChallengeCatalogDetailResponse.model_validate(challenge)

    @classmethod
    async def get_catalog_detail(
        cls,
        db: AsyncSession,
        challenge_id: UUID,
        storage_service: StorageService | None = None,
    ) -> ChallengeCatalogDetailResponse:
        """Return an open challenge with signed, read-only attachment URLs."""
        challenge = await CatalogRepository.get_open_challenge(db, challenge_id)
        if challenge is None:
            raise CatalogChallengeNotFoundError(
                f"Open challenge '{challenge_id}' was not found"
            )

        attachments = await CatalogRepository.list_public_attachments(
            db,
            challenge_id,
        )
        storage = storage_service or StorageService()
        public_attachments: list[CatalogAttachmentResponse] = []

        for attachment in attachments:
            download_url = await storage.generate_signed_url(attachment.storage_path)
            public_attachments.append(
                CatalogAttachmentResponse(
                    id=attachment.id,
                    file_name=attachment.file_name,
                    file_size_bytes=attachment.file_size_bytes,
                    mime_type=attachment.mime_type,
                    download_url=download_url,
                    created_at=attachment.created_at,
                )
            )

        detail = cls.to_catalog_detail(challenge)
        return detail.model_copy(update={"attachments": public_attachments})

    @classmethod
    async def query_catalog(
        cls,
        db: AsyncSession,
        **filters: Any,
    ) -> tuple[list[ChallengeCatalogItemResponse], int]:
        """Query only open challenges and return public discovery projections."""
        challenges, total = await CatalogRepository.filter_catalog(
            db,
            **filters,
            status="OPEN",
        )
        return [cls.to_catalog_item(item) for item in challenges], total
