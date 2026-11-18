"""Domain service implementing business rules and ownership enforcement for Challenges."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.challenge import Challenge
from src.repositories.challenge_repository import ChallengeRepository
from src.schemas.challenge import ChallengeCreate, ChallengeResponse, ChallengeUpdate
from src.schemas.closure import CompanyChallengeSummary, CompanyPortfolioResponse


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

    @staticmethod
    async def close_challenge(
        db: AsyncSession,
        challenge_id: UUID,
        closure_reason: str,
        user_id: UUID,
    ) -> Challenge:
        """Voluntarily close an owned challenge requiring mandatory justification (HU-08 / RB-06).

        Args:
            db: Active SQLAlchemy AsyncSession.
            challenge_id: Unique challenge UUID.
            closure_reason: Mandatory reason for closure (>= 15 characters).
            user_id: Authenticated company identifier.

        Returns:
            Challenge: The updated Challenge entity with status CLOSED.

        Raises:
            HTTPException(404): If the challenge does not exist.
            HTTPException(403): If the authenticated company is not the owner.
            HTTPException(422): If the challenge is already closed or closure reason is invalid.
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

        if challenge.status == "CLOSED":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT if hasattr(status, "HTTP_422_UNPROCESSABLE_CONTENT") else 422,
                detail="Challenge is already closed.",
            )

        reason = closure_reason.strip() if closure_reason else ""
        if len(reason) < 15:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT if hasattr(status, "HTTP_422_UNPROCESSABLE_CONTENT") else 422,
                detail="Closure reason must be at least 15 characters long.",
            )

        return await ChallengeRepository.close_challenge(
            db=db,
            db_obj=challenge,
            closure_reason=reason,
        )

    @staticmethod
    async def publish_challenge(
        db: AsyncSession,
        challenge_id: UUID,
        user_id: UUID,
    ) -> Challenge:
        """Publish a challenge transitioning status from DRAFT to OPEN (HU-08).

        Args:
            db: Active SQLAlchemy AsyncSession.
            challenge_id: Unique challenge UUID.
            user_id: Authenticated company identifier.

        Returns:
            Challenge: The published Challenge entity with status OPEN.

        Raises:
            HTTPException(404): If the challenge does not exist.
            HTTPException(403): If the authenticated company is not the owner.
            HTTPException(422): If the challenge is not in DRAFT status.
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

        if challenge.status != "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT if hasattr(status, "HTTP_422_UNPROCESSABLE_CONTENT") else 422,
                detail=f"Cannot publish challenge in {challenge.status} state. Only DRAFT challenges can be published.",
            )

        return await ChallengeRepository.publish_challenge(
            db=db,
            db_obj=challenge,
        )

    @staticmethod
    async def get_company_portfolio(
        db: AsyncSession,
        company_id: UUID,
        status_filter: str | None = None,
        page: int = 1,
        limit: int = 10,
    ) -> CompanyPortfolioResponse:
        """Retrieve paginated challenge portfolio and aggregate status metrics for company (HU-08).

        Args:
            db: Active SQLAlchemy AsyncSession.
            company_id: Authenticated company identifier.
            status_filter: Optional filter by ChallengeStatus.
            page: 1-indexed page number.
            limit: Maximum items per page.

        Returns:
            CompanyPortfolioResponse containing items and summary counts.
        """
        skip = (page - 1) * limit
        items, total, status_counts = await ChallengeRepository.get_company_portfolio(
            db=db,
            company_id=company_id,
            status_filter=status_filter,
            skip=skip,
            limit=limit,
        )

        summary = CompanyChallengeSummary(
            total=sum(status_counts.values()),
            draft=status_counts.get("DRAFT", 0),
            open=status_counts.get("OPEN", 0),
            in_progress=status_counts.get("IN_PROGRESS", 0),
            closed=status_counts.get("CLOSED", 0),
            cancelled=status_counts.get("CANCELLED", 0),
        )

        return CompanyPortfolioResponse(
            items=[ChallengeResponse.model_validate(c) for c in items],
            total=total,
            page=page,
            limit=limit,
            summary=summary,
        )
