"""Schemas package initialization."""

from src.schemas.catalog import EmptyStateMetadata, PaginatedCatalogResponse
from src.schemas.challenge import (
    ChallengeCreate,
    ChallengeResponse,
    ChallengeUpdate,
)

__all__ = [
    "ChallengeCreate",
    "ChallengeResponse",
    "ChallengeUpdate",
    "EmptyStateMetadata",
    "PaginatedCatalogResponse",
]
