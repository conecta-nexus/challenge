"""Domain service implementing business rules and ownership enforcement for Challenges."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.challenge import Challenge
from src.repositories.challenge_repository import ChallengeRepository
from src.schemas.challenge import ChallengeCreate, ChallengeUpdate


class ChallengeService:
    """Service providing challenge lifecycle operations with strict RB-06 ownership enforcement."""

    @staticmethod
    async def create_challenge(
        db: AsyncSession,
        challenge_in: ChallengeCreate,
        company_id: UUID,
    ) -> Challenge:
        """Create a new challenge owned by the authenticated company.

        Args:
            db: Active SQLAlchemy AsyncSession.
            challenge_in: Validated ChallengeCreate schema.
            company_id: Authenticated company identifier.

        Returns:
            The newly created Challenge entity.
        """
        return await ChallengeRepository.create(
            db=db,
            challenge_in=challenge_in,
            company_id=company_id,
        )

    @staticmethod
    async def get_challenge_for_owner(
        db: AsyncSession,
        challenge_id: UUID,
        user_id: UUID,
    ) -> Challenge:
        """Retrieve full challenge details ensuring strict company ownership (RB-06 / RF15).

        Args:
            db: Active SQLAlchemy AsyncSession.
            challenge_id: Unique challenge UUID.
            user_id: Authenticated user identifier.

        Returns:
            Challenge: The owned Challenge entity.

        Raises:
            HTTPException(404): If the challenge does not exist.
            HTTPException(403): If the authenticated user is not the challenge owner.
        """
        challenge = await ChallengeRepository.get_by_id(db, challenge_id)
        if challenge is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Challenge not found",
            )

        if challenge.company_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have ownership of this challenge",
            )

        return challenge

    @staticmethod
    async def update_challenge(
        db: AsyncSession,
        challenge_id: UUID,
        obj_in: ChallengeUpdate,
        user_id: UUID,
    ) -> Challenge:
        """Update challenge functional attributes enforcing ownership and state locking (RB-06).

        Args:
            db: Active SQLAlchemy AsyncSession.
            challenge_id: Unique challenge UUID.
            obj_in: ChallengeUpdate schema with modified attributes.
            user_id: Authenticated user identifier.

        Returns:
            Challenge: The updated Challenge entity.

        Raises:
            HTTPException(404): If the challenge does not exist.
            HTTPException(403): If the authenticated user is not the challenge owner.
            HTTPException(422): If the challenge is in IN_PROGRESS, CLOSED, or CANCELLED status.
        """
        challenge = await ChallengeRepository.get_by_id(db, challenge_id)
        if challenge is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Challenge not found",
            )

        if challenge.company_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have ownership of this challenge",
            )

        if challenge.status not in ("DRAFT", "OPEN"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT if hasattr(status, "HTTP_422_UNPROCESSABLE_CONTENT") else 422,
                detail=f"Cannot modify challenge in {challenge.status} state. Only DRAFT or OPEN challenges can be edited.",
            )

        return await ChallengeRepository.update(
            db=db,
            db_obj=challenge,
            obj_in=obj_in,
        )
