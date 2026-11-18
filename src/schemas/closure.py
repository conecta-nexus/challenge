"""Schemas for challenge voluntary closure and company challenge portfolio (HU-08)."""

from typing import Any
from pydantic import BaseModel, Field, ValidationInfo, field_validator

from src.schemas.challenge import ChallengeResponse


class ChallengeClosureRequest(BaseModel):
    """Schema for voluntary challenge closure request (HU-08 / RB-06)."""

    closure_reason: str = Field(
        ...,
        min_length=15,
        description="Mandatory justification for closing the challenge (minimum 15 characters).",
    )

    @field_validator("closure_reason", mode="before")
    @classmethod
    def validate_closure_reason(cls, v: Any, info: ValidationInfo) -> str:
        """Validate that closure_reason is a non-empty string of at least 15 characters."""
        if v is None:
            raise ValueError("closure_reason is required and cannot be null")
        if not isinstance(v, str):
            raise ValueError("closure_reason must be a string")
        stripped = v.strip()
        if len(stripped) < 15:
            raise ValueError("closure_reason must be at least 15 characters long")
        return stripped


class CompanyChallengeSummary(BaseModel):
    """Summary metrics of company challenges grouped by lifecycle status."""

    total: int = 0
    draft: int = 0
    open: int = 0
    in_progress: int = 0
    closed: int = 0
    cancelled: int = 0


class CompanyPortfolioResponse(BaseModel):
    """Paginated portfolio of challenges owned by the authenticated company with summary metrics."""

    items: list[ChallengeResponse]
    total: int
    page: int
    limit: int
    summary: CompanyChallengeSummary
