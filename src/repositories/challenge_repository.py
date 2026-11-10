"""Repository pattern implementation for Challenge entities."""

from uuid import UUID

from sqlalchemy import select
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
