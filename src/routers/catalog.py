"""Catalog router providing public opportunity browsing, multi-criteria filtering, and empty-state metadata (HU-09, HU-10)."""

from typing import Annotated, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.repositories.catalog_repository import CatalogRepository
from src.schemas.catalog import EmptyStateMetadata, PaginatedCatalogResponse
from src.schemas.challenge import DifficultyLevel, Modality
from src.services.catalog_service import CatalogService

router = APIRouter(
    prefix="/challenges",
    tags=["Catalog"],
)


@router.get(
    "/catalog",
    response_model=PaginatedCatalogResponse,
    summary="Browse and filter opportunity catalog",
    description="Multi-criteria query against active challenges with GIN-indexed JSONB filters and empty-state metadata.",
)
@router.get(
    "",
    response_model=PaginatedCatalogResponse,
    summary="Browse and filter opportunity catalog (root alias)",
    include_in_schema=False,
)
async def get_catalog(
    q: Annotated[str | None, Query(description="Search term in title, description, or process")] = None,
    sector: Annotated[str | None, Query(description="Economic sector alias")] = None,
    economic_sector: Annotated[str | None, Query(description="Economic sector filter")] = None,
    modality: Annotated[Modality | None, Query(description="Modality filter (REMOTE, HYBRID, ON_SITE)")] = None,
    difficulty: Annotated[DifficultyLevel | None, Query(description="Difficulty alias")] = None,
    difficulty_level: Annotated[DifficultyLevel | None, Query(description="Difficulty level")] = None,
    skill: Annotated[str | None, Query(description="Single required skill filter")] = None,
    skills: Annotated[list[str] | None, Query(description="Multiple required skills filter")] = None,
    knowledge_area: Annotated[str | None, Query(description="Single knowledge area filter")] = None,
    knowledge_areas: Annotated[list[str] | None, Query(description="Multiple knowledge areas filter")] = None,
    min_semester: Annotated[int | None, Query(ge=1, le=10, description="Semester eligibility check")] = None,
    max_semester: Annotated[int | None, Query(ge=1, le=10, description="Semester eligibility alias")] = None,
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size limit")] = 10,
    page_size: Annotated[int | None, Query(ge=1, le=100, description="Page size alias")] = None,
    db: AsyncSession = Depends(get_db),
) -> PaginatedCatalogResponse:
    """Query open challenges using dynamic multi-criteria filters."""
    # Resolve parameter aliases
    effective_sector = (economic_sector or sector or "").strip() or None
    effective_difficulty = difficulty_level or difficulty
    effective_semester = min_semester if min_semester is not None else max_semester
    effective_limit = page_size if page_size is not None else limit
    effective_q = q.strip() if q and q.strip() else None

    # Calculate pagination offset
    skip = (page - 1) * effective_limit

    items, total = await CatalogService.query_catalog(
        db,
        q=effective_q,
        economic_sector=effective_sector,
        modality=modality,
        difficulty_level=effective_difficulty,
        skill=skill,
        skills=skills,
        knowledge_area=knowledge_area,
        knowledge_areas=knowledge_areas,
        min_semester=effective_semester,
        skip=skip,
        limit=effective_limit,
    )

    pages = (total + effective_limit - 1) // effective_limit if total > 0 else 1

    empty_state: EmptyStateMetadata | None = None
    if total == 0:
        # Build dictionary of non-empty applied filters for empty-state feedback
        applied: dict[str, Any] = {}
        if effective_q:
            applied["q"] = effective_q
        if effective_sector:
            applied["economic_sector"] = effective_sector
        if modality:
            applied["modality"] = modality
        if effective_difficulty:
            applied["difficulty_level"] = effective_difficulty
        if skill:
            applied["skill"] = skill
        if skills:
            applied["skills"] = skills
        if knowledge_area:
            applied["knowledge_area"] = knowledge_area
        if knowledge_areas:
            applied["knowledge_areas"] = knowledge_areas
        if effective_semester is not None:
            applied["min_semester"] = effective_semester

        active_count = await CatalogRepository.count_active_challenges(db)
        empty_state = EmptyStateMetadata(
            query_params=applied,
            total_active_challenges=active_count,
        )

    return PaginatedCatalogResponse(
        items=items,
        total=total,
        page=page,
        limit=effective_limit,
        pages=pages,
        empty_state=empty_state,
    )
