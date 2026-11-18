"""Schemas package initialization."""

from src.schemas.catalog import (
    ChallengeCatalogDetailResponse,
    ChallengeCatalogItemResponse,
    CatalogAttachmentResponse,
    EmptyStateMetadata,
    PaginatedCatalogResponse,
)
from src.schemas.challenge import (
    ChallengeCreate,
    ChallengeResponse,
    ChallengeUpdate,
)

__all__ = [
    "ChallengeCreate",
    "ChallengeCatalogDetailResponse",
    "ChallengeCatalogItemResponse",
    "CatalogAttachmentResponse",
    "ChallengeResponse",
    "ChallengeUpdate",
    "EmptyStateMetadata",
    "PaginatedCatalogResponse",
]
