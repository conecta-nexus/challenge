"""Unit tests for CatalogRepository multi-criteria query builder and GIN/B-tree indexes."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from src.models.challenge import Challenge
from src.repositories.catalog_repository import CatalogRepository


def test_challenge_indexes_metadata():
    """Verify ORM model declares GIN indexes for JSONB arrays and B-Tree indexes for catalog filters."""
    indexes = {idx.name: idx for idx in Challenge.__table__.indexes}

    # GIN indexes
    assert "ix_challenges_required_skills_gin" in indexes
    assert indexes["ix_challenges_required_skills_gin"].dialect_options["postgresql"]["using"] == "gin"

    assert "ix_challenges_knowledge_areas_gin" in indexes
    assert indexes["ix_challenges_knowledge_areas_gin"].dialect_options["postgresql"]["using"] == "gin"

    # B-Tree indexes
    assert "ix_challenges_status" in indexes
    assert "ix_challenges_created_at" in indexes
    assert "ix_challenges_economic_sector" in indexes
    assert "ix_challenges_modality" in indexes
    assert "ix_challenges_difficulty_level" in indexes
    assert "ix_challenges_status_created_at" in indexes


def test_build_filter_clauses_default():
    """Verify default filter clauses filter by status='OPEN'."""
    clauses = CatalogRepository.build_filter_clauses()
    assert len(clauses) == 1
    compiled = str(clauses[0].compile(dialect=postgresql.dialect()))
    assert "challenges.status = " in compiled


def test_build_filter_clauses_keyword_search():
    """Verify keyword search produces ILIKE clauses across title, description, and business_process."""
    clauses = CatalogRepository.build_filter_clauses(q="logistic optimization", status=None)
    assert len(clauses) == 1
    compiled = str(clauses[0].compile(dialect=postgresql.dialect()))
    assert "challenges.title ILIKE" in compiled
    assert "challenges.description ILIKE" in compiled
    assert "challenges.business_process ILIKE" in compiled


def test_build_filter_clauses_categorical():
    """Verify sector, modality, difficulty, and semester clauses."""
    clauses = CatalogRepository.build_filter_clauses(
        economic_sector="Logistics",
        modality="REMOTE",
        difficulty_level="ADVANCED",
        min_semester=8,
        status="OPEN",
    )
    assert len(clauses) == 5
    stmt = select(Challenge).where(*clauses)
    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "challenges.economic_sector ILIKE" in compiled
    assert "challenges.modality = " in compiled
    assert "challenges.difficulty_level = " in compiled
    assert "challenges.min_semester <= " in compiled
    assert "challenges.status = " in compiled


def test_build_filter_clauses_jsonb_containment():
    """Verify JSONB required_skills and knowledge_areas compile with PostgreSQL @> containment operator."""
    clauses = CatalogRepository.build_filter_clauses(
        skill="Python",
        skills=["FastAPI", "Docker"],
        knowledge_area="Software Engineering",
        knowledge_areas=["Cloud Computing"],
        status=None,
    )
    assert len(clauses) == 2
    stmt = select(Challenge).where(*clauses)
    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "challenges.required_skills @>" in compiled
    assert "challenges.knowledge_areas @>" in compiled


def test_build_filter_clauses_ignores_empty_and_whitespace():
    """Verify empty or whitespace strings are safely ignored and do not add redundant clauses."""
    clauses = CatalogRepository.build_filter_clauses(
        q="   ",
        economic_sector="",
        modality=None,
        difficulty_level=None,
        skill="   ",
        skills=["", "  "],
        knowledge_area=None,
        status=None,
    )
    assert len(clauses) == 0


@pytest.mark.asyncio
async def test_filter_catalog_execution():
    """Verify filter_catalog executes both count and paginated query ordered by created_at DESC."""
    mock_db = AsyncMock()

    # Mock count query scalar return
    mock_count_result = MagicMock()
    mock_count_result.scalar_one.return_value = 1

    # Mock items query scalar return
    mock_challenge = Challenge(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        title="Predictive AI Maintenance",
        description="Predict industrial machinery failures using ML.",
        business_process="Plant Operations",
        status="OPEN",
        difficulty_level="INTERMEDIATE",
        modality="REMOTE",
        min_semester=7,
        economic_sector="Manufacturing",
        required_skills=["Python", "TensorFlow"],
        knowledge_areas=["Machine Learning"],
        created_at=datetime.now(timezone.utc),
    )
    mock_items_result = MagicMock()
    mock_items_result.scalars.return_value.all.return_value = [mock_challenge]

    mock_db.execute.side_effect = [mock_count_result, mock_items_result]

    items, total = await CatalogRepository.filter_catalog(
        mock_db,
        q="Predictive",
        skill="Python",
        skip=0,
        limit=10,
    )

    assert total == 1
    assert len(items) == 1
    assert items[0].title == "Predictive AI Maintenance"
    assert mock_db.execute.call_count == 2


@pytest.mark.asyncio
async def test_count_active_challenges():
    """Verify count_active_challenges executes count query for OPEN challenges."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 42
    mock_db.execute.return_value = mock_result

    count = await CatalogRepository.count_active_challenges(mock_db)
    assert count == 42
    mock_db.execute.assert_called_once()
