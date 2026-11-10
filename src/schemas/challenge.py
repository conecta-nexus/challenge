"""Pydantic v2 schemas for Challenge domain."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

DifficultyLevel = Literal["BEGINNER", "INTERMEDIATE", "ADVANCED"]
Modality = Literal["REMOTE", "HYBRID", "ON_SITE"]
InitialChallengeStatus = Literal["DRAFT", "OPEN"]
ChallengeStatus = Literal["DRAFT", "OPEN", "IN_PROGRESS", "CLOSED", "CANCELLED"]


class ChallengeBase(BaseModel):
    """Base schema holding shared functional challenge attributes."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    business_process: str = Field(..., min_length=1, max_length=255)
    difficulty_level: DifficultyLevel
    modality: Modality
    min_semester: int = Field(..., ge=6, le=10, strict=True)
    economic_sector: str = Field(..., min_length=1, max_length=100)
    required_skills: list[str] = Field(default_factory=list)
    knowledge_areas: list[str] = Field(default_factory=list)

    @field_validator(
        "title",
        "description",
        "business_process",
        "economic_sector",
        mode="before",
    )
    @classmethod
    def validate_non_empty_string(cls, v: Any, info: ValidationInfo) -> str:
        """Validate that string fields are non-empty after stripping whitespace."""
        if v is None:
            raise ValueError(f"{info.field_name} is required and cannot be null")
        if not isinstance(v, str):
            raise ValueError(f"{info.field_name} must be a string")
        v = v.strip()
        if not v:
            raise ValueError(f"{info.field_name} cannot be empty or whitespace only")
        return v

    @field_validator("required_skills", "knowledge_areas", mode="before")
    @classmethod
    def validate_string_list(cls, v: Any, info: ValidationInfo) -> list[str]:
        """Validate that list fields contain only non-empty strings."""
        if v is None:
            raise ValueError(f"{info.field_name} cannot be null")
        if not isinstance(v, list):
            raise ValueError(f"{info.field_name} must be a list of strings")
        cleaned: list[str] = []
        for idx, item in enumerate(v):
            if not isinstance(item, str):
                raise ValueError(
                    f"All elements in {info.field_name} must be strings, "
                    f"got {type(item).__name__} at index {idx}"
                )
            stripped = item.strip()
            if not stripped:
                raise ValueError(f"Elements in {info.field_name} cannot be empty or blank")
            cleaned.append(stripped)
        return cleaned


class ChallengeCreate(ChallengeBase):
    """Schema for Challenge creation requests.

    Status defaults to 'DRAFT' and can optionally be initialized as 'OPEN'.
    No other status transitions are permitted upon creation.
    company_id must NOT be included in this schema.
    """

    status: InitialChallengeStatus = Field(default="DRAFT")


class ChallengeUpdate(BaseModel):
    """Schema for partial updates on Challenge functional attributes.

    All fields are optional. Only DRAFT and OPEN statuses are permitted.
    Explicit null values are rejected for NOT NULL database columns.
    """

    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    business_process: str | None = Field(default=None, max_length=255)
    difficulty_level: DifficultyLevel | None = None
    modality: Modality | None = None
    min_semester: int | None = Field(default=None, ge=6, le=10, strict=True)
    economic_sector: str | None = Field(default=None, max_length=100)
    required_skills: list[str] | None = None
    knowledge_areas: list[str] | None = None
    status: InitialChallengeStatus | None = None

    @field_validator(
        "title",
        "description",
        "business_process",
        "economic_sector",
        mode="before",
    )
    @classmethod
    def validate_optional_string(cls, v: Any, info: ValidationInfo) -> str | None:
        """Validate that optional string fields, if provided, are not null or blank."""
        if v is None:
            raise ValueError(f"{info.field_name} cannot be null")
        if not isinstance(v, str):
            raise ValueError(f"{info.field_name} must be a string")
        v = v.strip()
        if not v:
            raise ValueError(f"{info.field_name} cannot be empty or whitespace only")
        return v

    @field_validator("difficulty_level", "modality", "status", mode="before")
    @classmethod
    def validate_optional_not_none(cls, v: Any, info: ValidationInfo) -> Any:
        """Reject explicit null for categorical fields."""
        if v is None:
            raise ValueError(f"{info.field_name} cannot be null")
        return v

    @field_validator("min_semester", mode="before")
    @classmethod
    def validate_optional_min_semester(cls, v: Any) -> Any:
        """Reject explicit null for min_semester."""
        if v is None:
            raise ValueError("min_semester cannot be null")
        return v

    @field_validator("required_skills", "knowledge_areas", mode="before")
    @classmethod
    def validate_optional_string_list(cls, v: Any, info: ValidationInfo) -> list[str] | None:
        """Validate optional string list fields if provided."""
        if v is None:
            raise ValueError(f"{info.field_name} cannot be null")
        if not isinstance(v, list):
            raise ValueError(f"{info.field_name} must be a list of strings")
        cleaned: list[str] = []
        for idx, item in enumerate(v):
            if not isinstance(item, str):
                raise ValueError(
                    f"All elements in {info.field_name} must be strings, "
                    f"got {type(item).__name__} at index {idx}"
                )
            stripped = item.strip()
            if not stripped:
                raise ValueError(f"Elements in {info.field_name} cannot be empty or blank")
            cleaned.append(stripped)
        return cleaned


class ChallengeResponse(BaseModel):
    """Complete representation of a persisted Challenge.

    Supports serialization from SQLAlchemy ORM objects.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    title: str
    description: str
    business_process: str
    status: str
    difficulty_level: str
    modality: str
    min_semester: int
    economic_sector: str
    required_skills: list[str]
    knowledge_areas: list[str]
    created_at: datetime
    updated_at: datetime
