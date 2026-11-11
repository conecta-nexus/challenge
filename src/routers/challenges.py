"""Router providing private Challenge management endpoints for companies (HU-06)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.dependencies import get_current_user, require_role
from src.core.security import AuthenticatedUser
from src.schemas.challenge import (
    ChallengeCreate,
    ChallengeResponse,
    ChallengeStatus,
    ChallengeUpdate,
)
from src.schemas.closure import ChallengeClosureRequest, CompanyPortfolioResponse
from src.services.challenge_service import ChallengeService

router = APIRouter(
    prefix="/challenges",
    tags=["Challenges"],
)


@router.post(
    "",
    response_model=ChallengeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new challenge",
    description="Allows authenticated companies to publish or draft a new challenge.",
)
@router.post(
    "/",
    response_model=ChallengeResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_challenge(
    challenge_in: ChallengeCreate,
    current_user: Annotated[AuthenticatedUser, Depends(require_role("COMPANY"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChallengeResponse:
    """Create a new challenge owned by the authenticated company."""
    challenge = await ChallengeService.create_challenge(
        db=db,
        challenge_in=challenge_in,
        company_id=current_user.id,
    )
    return ChallengeResponse.model_validate(challenge)


@router.get(
    "/company/me",
    response_model=CompanyPortfolioResponse,
    summary="List company challenge portfolio",
    description="Retrieve paginated list of challenges owned by the authenticated company with summary metrics (HU-08).",
)
async def get_my_company_challenges(
    current_user: Annotated[AuthenticatedUser, Depends(require_role("COMPANY"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[ChallengeStatus | None, Query(description="Filter by challenge status")] = None,
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed)")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 10,
) -> CompanyPortfolioResponse:
    """Retrieve private challenge portfolio and aggregate status counts for the authenticated company."""
    return await ChallengeService.get_company_portfolio(
        db=db,
        company_id=current_user.id,
        status_filter=status,
        page=page,
        limit=limit,
    )


@router.get(
    "/{id}",
    response_model=ChallengeResponse,
    summary="Get challenge details for owner",
    description="Retrieve full challenge details, enforcing company ownership (RB-06).",
)
async def get_challenge_by_id(
    id: Annotated[UUID, Path(description="Unique challenge UUID")],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChallengeResponse:
    """Retrieve full challenge details for the owning company."""
    challenge = await ChallengeService.get_challenge_for_owner(
        db=db,
        challenge_id=id,
        user_id=current_user.id,
    )
    return ChallengeResponse.model_validate(challenge)


@router.patch(
    "/{id}",
    response_model=ChallengeResponse,
    summary="Update challenge details",
    description="Modify functional challenge attributes while in DRAFT or OPEN status (RB-06).",
)
async def update_challenge(
    id: Annotated[UUID, Path(description="Unique challenge UUID")],
    challenge_in: ChallengeUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(require_role("COMPANY"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChallengeResponse:
    """Update challenge functional attributes enforcing ownership and state locking."""
    challenge = await ChallengeService.update_challenge(
        db=db,
        challenge_id=id,
        obj_in=challenge_in,
        user_id=current_user.id,
    )
    return ChallengeResponse.model_validate(challenge)


@router.post(
    "/{id}/close",
    response_model=ChallengeResponse,
    summary="Voluntarily close challenge",
    description="Voluntarily close an owned challenge requiring mandatory justification (HU-08 / RB-06).",
)
async def close_challenge(
    id: Annotated[UUID, Path(description="Unique challenge UUID")],
    closure_in: ChallengeClosureRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_role("COMPANY"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChallengeResponse:
    """Close an owned challenge with a mandatory justification reason of at least 15 characters."""
    challenge = await ChallengeService.close_challenge(
        db=db,
        challenge_id=id,
        closure_reason=closure_in.closure_reason,
        user_id=current_user.id,
    )
    return ChallengeResponse.model_validate(challenge)


@router.post(
    "/{id}/publish",
    response_model=ChallengeResponse,
    summary="Publish draft challenge",
    description="Transition challenge status from DRAFT to OPEN (HU-08).",
)
async def publish_challenge(
    id: Annotated[UUID, Path(description="Unique challenge UUID")],
    current_user: Annotated[AuthenticatedUser, Depends(require_role("COMPANY"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChallengeResponse:
    """Publish a draft challenge to make it visible in the public opportunity catalog."""
    challenge = await ChallengeService.publish_challenge(
        db=db,
        challenge_id=id,
        user_id=current_user.id,
    )
    return ChallengeResponse.model_validate(challenge)
