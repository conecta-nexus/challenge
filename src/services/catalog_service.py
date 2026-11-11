"""Public catalog query and privacy-safe projection service."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.challenge import Challenge
from src.repositories.catalog_repository import CatalogRepository
from src.schemas.catalog import (
    ChallengeCatalogDetailResponse,
    ChallengeCatalogItemResponse,
)


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
