"""Public catalog schemas with privacy-safe field projections."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PublicCatalogChallengeBase(BaseModel):
    """Shared public fields that intentionally exclude company contact data."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    company_id: UUID
    title: str
    difficulty_level: str
    modality: str
    min_semester: int
    economic_sector: str
    required_skills: list[str]
    knowledge_areas: list[str]
    created_at: datetime


class ChallengeCatalogItemResponse(PublicCatalogChallengeBase):
    """Privacy-safe discovery card for an open challenge."""

    description_snippet: str


class ChallengeCatalogDetailResponse(PublicCatalogChallengeBase):
    """Privacy-safe public detail projection for an open challenge."""

    description: str
    business_process: str
    status: Literal["OPEN"]
    updated_at: datetime


class EmptyStateMetadata(BaseModel):
    """Structured empty-state feedback when catalog filters yield zero results (HU-10)."""

    code: Literal["NO_MATCHING_CHALLENGES"] = Field(
        default="NO_MATCHING_CHALLENGES",
        description="Machine-readable empty state reason code.",
    )
    message: str = Field(
        default="No challenges match your selected search criteria.",
        description="User-friendly guidance message.",
    )
    query_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Map of non-empty search and filter criteria that resulted in zero matches.",
    )
    suggested_reset: bool = Field(
        default=True,
        description="Indicates whether the UI should provide an immediate reset/clear filters action.",
    )
    total_active_challenges: int = Field(
        default=0,
        ge=0,
        description="Total number of active opportunities currently open in the catalog.",
    )


class PaginatedCatalogResponse(BaseModel):
    """Paginated opportunity catalog response containing results or empty-state metadata."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ChallengeCatalogItemResponse] = Field(
        default_factory=list,
        description="List of challenge items matching filter criteria for the current page.",
    )
    total: int = Field(
        default=0,
        ge=0,
        description="Total number of challenges across all pages matching filter criteria.",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Current 1-based page number.",
    )
    limit: int = Field(
        default=10,
        ge=1,
        description="Maximum number of items per page.",
    )
    pages: int = Field(
        default=1,
        ge=0,
        description="Total number of pages based on total and limit.",
    )
    empty_state: EmptyStateMetadata | None = Field(
        default=None,
        description="Metadata populated only when total matches equal zero.",
    )
