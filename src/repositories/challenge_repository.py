"""Repository pattern implementation for Challenge entities."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.challenge import Challenge
from src.schemas.challenge import ChallengeCreate, ChallengeUpdate


class ChallengeRepository:
    """Stateless asynchronous repository for Challenge persistence operations."""

    @staticmethod
    async def create(
        db: AsyncSession,
        challenge_in: ChallengeCreate,
        company_id: UUID,
    ) -> Challenge:
        """Create and persist a new Challenge entity.

        Args:
            db: Active SQLAlchemy AsyncSession.
            challenge_in: Validated ChallengeCreate schema.
            company_id: Authenticated company identifier.

        Returns:
            The newly created and refreshed Challenge entity.
        """
        challenge_data = challenge_in.model_dump()
        db_obj = Challenge(
            **challenge_data,
            company_id=company_id,
        )
        db.add(db_obj)
        try:
            await db.commit()
            await db.refresh(db_obj)
            return db_obj
        except Exception:
            await db.rollback()
            raise

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        challenge_id: UUID,
    ) -> Challenge | None:
        """Fetch a Challenge entity by its primary key UUID.

        Args:
            db: Active SQLAlchemy AsyncSession.
            challenge_id: Unique challenge UUID.

        Returns:
            The Challenge instance if found, or None.
        """
        stmt = select(Challenge).where(Challenge.id == challenge_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def update(
        db: AsyncSession,
        db_obj: Challenge,
        obj_in: ChallengeUpdate,
    ) -> Challenge:
        """Apply partial updates to a Challenge entity.

        Args:
            db: Active SQLAlchemy AsyncSession.
            db_obj: Existing Challenge instance to update.
            obj_in: ChallengeUpdate schema containing fields to update.

        Returns:
            The updated and refreshed Challenge entity.
        """
        update_data = obj_in.model_dump(exclude_unset=True)
        forbidden_fields = {"id", "company_id", "created_at"}

        for field, value in update_data.items():
            if field in forbidden_fields:
                continue
            if value is not None and hasattr(db_obj, field):
                setattr(db_obj, field, value)

        try:
            await db.commit()
            await db.refresh(db_obj)
            return db_obj
        except Exception:
            await db.rollback()
            raise

    @staticmethod
    async def list_by_company(
        db: AsyncSession,
        company_id: UUID,
        skip: int,
        limit: int,
    ) -> list[Challenge]:
        """List challenges belonging to a specific company with pagination offsets.

        Args:
            db: Active SQLAlchemy AsyncSession.
            company_id: Company identifier to filter by.
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            A list of Challenge entities.
        """
        stmt = (
            select(Challenge)
            .where(Challenge.company_id == company_id)
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def close_challenge(
        db: AsyncSession,
        db_obj: Challenge,
        closure_reason: str,
    ) -> Challenge:
        """Mark a challenge as CLOSED with mandatory justification.

        Args:
            db: Active SQLAlchemy AsyncSession.
            db_obj: Existing Challenge instance.
            closure_reason: Mandatory closure reason string.

        Returns:
            The updated Challenge entity.
        """
        db_obj.status = "CLOSED"
        db_obj.closure_reason = closure_reason
        try:
            await db.commit()
            await db.refresh(db_obj)
            return db_obj
        except Exception:
            await db.rollback()
            raise

    @staticmethod
    async def publish_challenge(
        db: AsyncSession,
        db_obj: Challenge,
    ) -> Challenge:
        """Transition challenge from DRAFT to OPEN status.

        Args:
            db: Active SQLAlchemy AsyncSession.
            db_obj: Existing Challenge instance.

        Returns:
            The updated Challenge entity.
        """
        db_obj.status = "OPEN"
        try:
            await db.commit()
            await db.refresh(db_obj)
            return db_obj
        except Exception:
            await db.rollback()
            raise

    @staticmethod
    async def get_company_portfolio(
        db: AsyncSession,
        company_id: UUID,
        status_filter: str | None = None,
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[list[Challenge], int, dict[str, int]]:
        """Fetch paginated company challenges and aggregate portfolio summary counts.

        Args:
            db: Active SQLAlchemy AsyncSession.
            company_id: Authenticated company identifier.
            status_filter: Optional status filter.
            skip: Pagination offset.
            limit: Maximum items to return.

        Returns:
            Tuple of (items, total_filtered, status_counts_dict).
        """
        # 1. Summary status counts across all company challenges
        summary_stmt = (
            select(Challenge.status, func.count(Challenge.id))
            .where(Challenge.company_id == company_id)
            .group_by(Challenge.status)
        )
        summary_result = await db.execute(summary_stmt)
        status_counts = {status: count for status, count in summary_result.all()}

        # 2. Filtered list query
        query = select(Challenge).where(Challenge.company_id == company_id)
        if status_filter:
            query = query.where(Challenge.status == status_filter.upper())

        count_stmt = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        items_stmt = query.order_by(Challenge.created_at.desc()).offset(skip).limit(limit)
        items_result = await db.execute(items_stmt)
        items = list(items_result.scalars().all())

        return items, total, status_counts
