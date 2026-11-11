"""Tests for privacy-safe public catalog schemas and projections."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.models.challenge import Challenge
from src.schemas.catalog import (
    ChallengeCatalogDetailResponse,
    ChallengeCatalogItemResponse,
)
from src.services.catalog_service import CatalogService


PRIVATE_CONTACT_FIELDS = {
    "email",
    "phone",
    "contact_email",
    "contact_phone",
    "company_email",
    "company_phone",
}


def build_challenge(description: str = "Optimize a complex business workflow.") -> Challenge:
    """Build an open challenge for public projection tests."""
    now = datetime.now(timezone.utc)
    return Challenge(
        id=uuid4(),
        company_id=uuid4(),
        title="Workflow Optimization",
        description=description,
        business_process="Operations",
        status="OPEN",
        difficulty_level="INTERMEDIATE",
        modality="HYBRID",
        min_semester=7,
        economic_sector="Technology",
        required_skills=["Python", "Process Modeling"],
        knowledge_areas=["Software Engineering"],
        created_at=now,
        updated_at=now,
    )


def assert_contacts_are_masked(payload: dict) -> None:
    """Assert that no direct company contact field is publicly serialized."""
    assert PRIVATE_CONTACT_FIELDS.isdisjoint(payload)


def test_description_snippet_normalizes_whitespace() -> None:
    """Collapse whitespace when a description fits within the card limit."""
    result = CatalogService.create_description_snippet(
        "  Optimize\n\nwarehouse   routing.  "
    )

    assert result == "Optimize warehouse routing."


def test_description_snippet_truncates_to_configured_limit() -> None:
    """Keep the ellipsis inside the requested maximum length."""
    result = CatalogService.create_description_snippet("A" * 30, max_length=15)

    assert result == f"{'A' * 14}…"
    assert len(result) == 15


@pytest.mark.parametrize("max_length", [0, 1])
def test_description_snippet_rejects_unusable_limits(max_length: int) -> None:
    """Reject limits that cannot contain content and an ellipsis."""
    with pytest.raises(ValueError, match="at least 2"):
        CatalogService.create_description_snippet("Description", max_length)


def test_catalog_item_projection_masks_contacts() -> None:
    """Expose card fields and omit all direct company contact fields."""
    projection = CatalogService.to_catalog_item(build_challenge())
    payload = projection.model_dump()

    assert isinstance(projection, ChallengeCatalogItemResponse)
    assert payload["description_snippet"] == "Optimize a complex business workflow."
    assert "description" not in payload
    assert "business_process" not in payload
    assert_contacts_are_masked(payload)


def test_catalog_detail_projection_masks_contacts() -> None:
    """Expose full challenge requirements without direct contact channels."""
    projection = CatalogService.to_catalog_detail(build_challenge())
    payload = projection.model_dump()

    assert isinstance(projection, ChallengeCatalogDetailResponse)
    assert payload["status"] == "OPEN"
    assert payload["description"] == "Optimize a complex business workflow."
    assert payload["business_process"] == "Operations"
    assert_contacts_are_masked(payload)


def test_public_schemas_ignore_injected_contact_fields() -> None:
    """Prevent contact fields from leaking even when present in source data."""
    challenge = build_challenge()
    source = {
        "id": challenge.id,
        "company_id": challenge.company_id,
        "title": challenge.title,
        "description": challenge.description,
        "business_process": challenge.business_process,
        "status": challenge.status,
        "difficulty_level": challenge.difficulty_level,
        "modality": challenge.modality,
        "min_semester": challenge.min_semester,
        "economic_sector": challenge.economic_sector,
        "required_skills": challenge.required_skills,
        "knowledge_areas": challenge.knowledge_areas,
        "created_at": challenge.created_at,
        "updated_at": challenge.updated_at,
        "company_email": "private@example.com",
        "company_phone": "+57 300 000 0000",
    }

    payload = ChallengeCatalogDetailResponse.model_validate(source).model_dump()

    assert_contacts_are_masked(payload)
    assert "private@example.com" not in str(payload)
    assert "+57 300 000 0000" not in str(payload)


@pytest.mark.asyncio
async def test_query_catalog_forces_open_status_and_projects_items() -> None:
    """Always query OPEN challenges and return privacy-safe item schemas."""
    db = AsyncMock()
    challenge = build_challenge()

    with patch(
        "src.services.catalog_service.CatalogRepository.filter_catalog",
        new=AsyncMock(return_value=([challenge], 1)),
    ) as filter_catalog:
        items, total = await CatalogService.query_catalog(
            db,
            q="workflow",
            skip=0,
            limit=10,
        )

    filter_catalog.assert_awaited_once_with(
        db,
        q="workflow",
        skip=0,
        limit=10,
        status="OPEN",
    )
    assert total == 1
    assert len(items) == 1
    assert isinstance(items[0], ChallengeCatalogItemResponse)
    assert_contacts_are_masked(items[0].model_dump())
