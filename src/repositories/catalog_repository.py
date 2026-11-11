"""Catalog repository for high-performance multi-criteria search and filtering."""

from typing import Any
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.challenge import Challenge


class CatalogRepository:
    """Repository implementing dynamic multi-criteria SQL queries for the opportunity catalog (HU-09, HU-10)."""

    @classmethod
    def build_filter_clauses(
        cls,
        *,
        q: str | None = None,
        economic_sector: str | None = None,
        modality: str | None = None,
        difficulty_level: str | None = None,
        skill: str | None = None,
        skills: list[str] | None = None,
        knowledge_area: str | None = None,
        knowledge_areas: list[str] | None = None,
        min_semester: int | None = None,
        status: str | None = "OPEN",
    ) -> list[Any]:
        """Build dynamic SQLAlchemy boolean filter clauses.

        Args:
            q: Keyword search text against title, description, and business_process.
            economic_sector: Economic sector name (case-insensitive ILIKE).
            modality: Modality enum (REMOTE, HYBRID, ON_SITE).
            difficulty_level: Difficulty level enum (BEGINNER, INTERMEDIATE, ADVANCED).
            skill: Single required skill name.
            skills: List of required skills.
            knowledge_area: Single knowledge area name.
            knowledge_areas: List of knowledge areas.
            min_semester: Maximum min_semester constraint (student eligibility).
            status: Challenge lifecycle status (defaults to 'OPEN' for public catalog).

        Returns:
            List of SQLAlchemy binary expressions to be combined with and_().
        """
        clauses: list[Any] = []

        if status:
            clauses.append(Challenge.status == status)

        if q and q.strip():
            search_term = f"%{q.strip()}%"
            clauses.append(
                or_(
                    Challenge.title.ilike(search_term),
                    Challenge.description.ilike(search_term),
                    Challenge.business_process.ilike(search_term),
                )
            )

        if economic_sector and economic_sector.strip():
            clauses.append(Challenge.economic_sector.ilike(economic_sector.strip()))

        if modality and modality.strip():
            clauses.append(Challenge.modality == modality.strip())

        if difficulty_level and difficulty_level.strip():
            clauses.append(Challenge.difficulty_level == difficulty_level.strip())

        if min_semester is not None:
            clauses.append(Challenge.min_semester <= min_semester)

        # JSONB containment for skills (supports single, list, or comma-separated tokens)
        all_skills: list[str] = []
        if skill and skill.strip():
            all_skills.extend([s.strip() for s in skill.split(",") if s.strip()])
        if skills:
            for item in skills:
                if item and item.strip():
                    all_skills.extend([s.strip() for s in item.split(",") if s.strip()])
        if all_skills:
            unique_skills = list(dict.fromkeys(all_skills))
            clauses.append(Challenge.required_skills.contains(unique_skills))

        # JSONB containment for knowledge areas (supports single, list, or comma-separated tokens)
        all_areas: list[str] = []
        if knowledge_area and knowledge_area.strip():
            all_areas.extend([a.strip() for a in knowledge_area.split(",") if a.strip()])
        if knowledge_areas:
            for item in knowledge_areas:
                if item and item.strip():
                    all_areas.extend([a.strip() for a in item.split(",") if a.strip()])
        if all_areas:
            unique_areas = list(dict.fromkeys(all_areas))
            clauses.append(Challenge.knowledge_areas.contains(unique_areas))

        return clauses

    @classmethod
    async def filter_catalog(
        cls,
        db: AsyncSession,
        *,
        q: str | None = None,
        economic_sector: str | None = None,
        modality: str | None = None,
        difficulty_level: str | None = None,
        skill: str | None = None,
        skills: list[str] | None = None,
        knowledge_area: str | None = None,
        knowledge_areas: list[str] | None = None,
        min_semester: int | None = None,
        status: str | None = "OPEN",
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[list[Challenge], int]:
        """Execute paginated multi-criteria catalog query with total count.

        Args:
            db: Active SQLAlchemy AsyncSession.
            q: Keyword search term.
            economic_sector: Sector filter.
            modality: Modality filter.
            difficulty_level: Difficulty filter.
            skill: Single skill filter.
            skills: Multiple skills filter.
            knowledge_area: Single knowledge area filter.
            knowledge_areas: Multiple knowledge areas filter.
            min_semester: Student semester eligibility check.
            status: Status filter (default: 'OPEN').
            skip: Pagination offset (records to skip).
            limit: Maximum records to return.

        Returns:
            A tuple of (items, total_count).
        """
        clauses = cls.build_filter_clauses(
            q=q,
            economic_sector=economic_sector,
            modality=modality,
            difficulty_level=difficulty_level,
            skill=skill,
            skills=skills,
            knowledge_area=knowledge_area,
            knowledge_areas=knowledge_areas,
            min_semester=min_semester,
            status=status,
        )

        # Count total matching records
        count_stmt = select(func.count(Challenge.id)).where(*clauses)
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one() or 0

        # Query paginated rows ordered by newest first
        query_stmt = (
            select(Challenge)
            .where(*clauses)
            .order_by(Challenge.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items_result = await db.execute(query_stmt)
        items = list(items_result.scalars().all())

        return items, total

    @classmethod
    async def count_active_challenges(cls, db: AsyncSession) -> int:
        """Count total number of open/active challenges in the catalog."""
        stmt = select(func.count(Challenge.id)).where(Challenge.status == "OPEN")
        result = await db.execute(stmt)
        return result.scalar_one() or 0
