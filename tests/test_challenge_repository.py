"""Unit tests for Challenge Pydantic v2 schemas and ChallengeRepository."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy.engine import ScalarResult

from src.models.challenge import Challenge
from src.repositories.challenge_repository import ChallengeRepository
from src.schemas.challenge import (
    ChallengeCreate,
    ChallengeResponse,
    ChallengeUpdate,
)


# ==============================================================================
# 1. SCHEMAS TESTS
# ==============================================================================


def test_challenge_create_valid():
    """1. ChallengeCreate valid with all required fields."""
    data = {
        "title": "Optimization of Logistical Routes",
        "description": "Develop an algorithm to optimize transport schedules.",
        "business_process": "Supply Chain Dispatch",
        "difficulty_level": "INTERMEDIATE",
        "modality": "REMOTE",
        "min_semester": 7,
        "economic_sector": "Logistics & Transport",
        "required_skills": ["Python", "Algorithms", "Graph Theory"],
        "knowledge_areas": ["Operations Research", "Backend Development"],
    }
    schema = ChallengeCreate(**data)
    assert schema.title == "Optimization of Logistical Routes"
    assert schema.description == "Develop an algorithm to optimize transport schedules."
    assert schema.business_process == "Supply Chain Dispatch"
    assert schema.difficulty_level == "INTERMEDIATE"
    assert schema.modality == "REMOTE"
    assert schema.min_semester == 7
    assert schema.economic_sector == "Logistics & Transport"
    assert schema.required_skills == ["Python", "Algorithms", "Graph Theory"]
    assert schema.knowledge_areas == ["Operations Research", "Backend Development"]
    assert schema.status == "DRAFT"


def test_challenge_create_default_status_draft():
    """2. Verify default status is DRAFT when omitted."""
    schema = ChallengeCreate(
        title="Title",
        description="Desc",
        business_process="Process",
        difficulty_level="BEGINNER",
        modality="HYBRID",
        min_semester=6,
        economic_sector="Finance",
    )
    assert schema.status == "DRAFT"


def test_challenge_create_status_open_valid():
    """3. Verify status OPEN is valid on creation."""
    schema = ChallengeCreate(
        title="Title",
        description="Desc",
        business_process="Process",
        difficulty_level="ADVANCED",
        modality="ON_SITE",
        min_semester=8,
        economic_sector="Healthcare",
        status="OPEN",
    )
    assert schema.status == "OPEN"


@pytest.mark.parametrize(
    "invalid_status",
    [
        "IN_PROGRESS",  # 4. Rejection of IN_PROGRESS
        "CLOSED",       # 5. Rejection of CLOSED
        "CANCELLED",    # 6. Rejection of CANCELLED
        "ARCHIVED",
        "UNKNOWN",
    ],
)
def test_challenge_create_invalid_statuses(invalid_status: str):
    """4, 5, 6. Reject invalid initial creation statuses."""
    with pytest.raises(ValidationError) as exc_info:
        ChallengeCreate(
            title="Title",
            description="Desc",
            business_process="Process",
            difficulty_level="BEGINNER",
            modality="REMOTE",
            min_semester=6,
            economic_sector="Retail",
            status=invalid_status,
        )
    assert "status" in str(exc_info.value)


@pytest.mark.parametrize("diff", ["BEGINNER", "INTERMEDIATE", "ADVANCED"])
def test_challenge_create_valid_difficulty(diff: str):
    """7. Valid difficulty levels."""
    schema = ChallengeCreate(
        title="Title",
        description="Desc",
        business_process="Process",
        difficulty_level=diff,
        modality="REMOTE",
        min_semester=6,
        economic_sector="Sector",
    )
    assert schema.difficulty_level == diff


@pytest.mark.parametrize("invalid_diff", ["EASY", "HARD", "EXPERT", "", "intermediate"])
def test_challenge_create_invalid_difficulty(invalid_diff: str):
    """8. Invalid difficulty levels."""
    with pytest.raises(ValidationError) as exc_info:
        ChallengeCreate(
            title="Title",
            description="Desc",
            business_process="Process",
            difficulty_level=invalid_diff,
            modality="REMOTE",
            min_semester=6,
            economic_sector="Sector",
        )
    assert "difficulty_level" in str(exc_info.value)


@pytest.mark.parametrize("mod", ["REMOTE", "HYBRID", "ON_SITE"])
def test_challenge_create_valid_modality(mod: str):
    """9. Valid modality values."""
    schema = ChallengeCreate(
        title="Title",
        description="Desc",
        business_process="Process",
        difficulty_level="BEGINNER",
        modality=mod,
        min_semester=6,
        economic_sector="Sector",
    )
    assert schema.modality == mod


@pytest.mark.parametrize("invalid_mod", ["VIRTUAL", "PRESENTIAL", "ONLINE", "", "remote"])
def test_challenge_create_invalid_modality(invalid_mod: str):
    """10. Invalid modality values."""
    with pytest.raises(ValidationError) as exc_info:
        ChallengeCreate(
            title="Title",
            description="Desc",
            business_process="Process",
            difficulty_level="BEGINNER",
            modality=invalid_mod,
            min_semester=6,
            economic_sector="Sector",
        )
    assert "modality" in str(exc_info.value)


def test_challenge_create_min_semester_6_valid():
    """11. min_semester = 6 is valid."""
    schema = ChallengeCreate(
        title="Title",
        description="Desc",
        business_process="Process",
        difficulty_level="BEGINNER",
        modality="REMOTE",
        min_semester=6,
        economic_sector="Sector",
    )
    assert schema.min_semester == 6


def test_challenge_create_min_semester_10_valid():
    """12. min_semester = 10 is valid."""
    schema = ChallengeCreate(
        title="Title",
        description="Desc",
        business_process="Process",
        difficulty_level="BEGINNER",
        modality="REMOTE",
        min_semester=10,
        economic_sector="Sector",
    )
    assert schema.min_semester == 10


def test_challenge_create_min_semester_5_invalid():
    """13. min_semester = 5 is invalid (below lower bound 6)."""
    with pytest.raises(ValidationError) as exc_info:
        ChallengeCreate(
            title="Title",
            description="Desc",
            business_process="Process",
            difficulty_level="BEGINNER",
            modality="REMOTE",
            min_semester=5,
            economic_sector="Sector",
        )
    assert "min_semester" in str(exc_info.value)


def test_challenge_create_min_semester_11_invalid():
    """14. min_semester = 11 is invalid (above upper bound 10)."""
    with pytest.raises(ValidationError) as exc_info:
        ChallengeCreate(
            title="Title",
            description="Desc",
            business_process="Process",
            difficulty_level="BEGINNER",
            modality="REMOTE",
            min_semester=11,
            economic_sector="Sector",
        )
    assert "min_semester" in str(exc_info.value)


@pytest.mark.parametrize("invalid_sem", ["6", 6.5, True, False, None])
def test_challenge_create_min_semester_strict_integer(invalid_sem):
    """min_semester must be a strict integer."""
    with pytest.raises(ValidationError) as exc_info:
        ChallengeCreate(
            title="Title",
            description="Desc",
            business_process="Process",
            difficulty_level="BEGINNER",
            modality="REMOTE",
            min_semester=invalid_sem,
            economic_sector="Sector",
        )
    assert "min_semester" in str(exc_info.value)


@pytest.mark.parametrize(
    "field_name",
    ["title", "description", "business_process", "economic_sector"],
)
def test_challenge_create_mandatory_string_fields(field_name: str):
    """15. Mandatory string fields cannot be omitted, empty, or whitespace-only."""
    valid_kwargs = {
        "title": "Title",
        "description": "Description",
        "business_process": "Process",
        "difficulty_level": "BEGINNER",
        "modality": "REMOTE",
        "min_semester": 6,
        "economic_sector": "Sector",
    }

    # Missing field
    kwargs_missing = {k: v for k, v in valid_kwargs.items() if k != field_name}
    with pytest.raises(ValidationError) as exc_missing:
        ChallengeCreate(**kwargs_missing)
    assert field_name in str(exc_missing.value)

    # Empty string
    kwargs_empty = {**valid_kwargs, field_name: ""}
    with pytest.raises(ValidationError) as exc_empty:
        ChallengeCreate(**kwargs_empty)
    assert field_name in str(exc_empty.value)

    # Whitespace-only string
    kwargs_ws = {**valid_kwargs, field_name: "   \t\n  "}
    with pytest.raises(ValidationError) as exc_ws:
        ChallengeCreate(**kwargs_ws)
    assert field_name in str(exc_ws.value)


def test_challenge_create_length_limits():
    """16. Length boundaries as defined by PostgreSQL columns."""
    valid_base = {
        "description": "Valid description",
        "difficulty_level": "BEGINNER",
        "modality": "REMOTE",
        "min_semester": 6,
    }

    # title max length 255
    ChallengeCreate(
        title="T" * 255,
        business_process="P",
        economic_sector="S",
        **valid_base,
    )
    with pytest.raises(ValidationError):
        ChallengeCreate(
            title="T" * 256,
            business_process="P",
            economic_sector="S",
            **valid_base,
        )

    # business_process max length 255
    ChallengeCreate(
        title="T",
        business_process="P" * 255,
        economic_sector="S",
        **valid_base,
    )
    with pytest.raises(ValidationError):
        ChallengeCreate(
            title="T",
            business_process="P" * 256,
            economic_sector="S",
            **valid_base,
        )

    # economic_sector max length 100
    ChallengeCreate(
        title="T",
        business_process="P",
        economic_sector="S" * 100,
        **valid_base,
    )
    with pytest.raises(ValidationError):
        ChallengeCreate(
            title="T",
            business_process="P",
            economic_sector="S" * 101,
            **valid_base,
        )


def test_challenge_create_required_skills_validation():
    """17. Validation of required_skills list."""
    valid_base = {
        "title": "Title",
        "description": "Description",
        "business_process": "Process",
        "difficulty_level": "BEGINNER",
        "modality": "REMOTE",
        "min_semester": 6,
        "economic_sector": "Sector",
    }

    # Valid empty and non-empty lists
    schema_empty = ChallengeCreate(**valid_base, required_skills=[])
    assert schema_empty.required_skills == []

    schema_items = ChallengeCreate(**valid_base, required_skills=[" Python ", "FastAPI"])
    assert schema_items.required_skills == ["Python", "FastAPI"]

    # Incompatible element types
    with pytest.raises(ValidationError):
        ChallengeCreate(**valid_base, required_skills=[123, "Python"])

    with pytest.raises(ValidationError):
        ChallengeCreate(**valid_base, required_skills=["Python", None])

    # Empty string inside list
    with pytest.raises(ValidationError):
        ChallengeCreate(**valid_base, required_skills=["Python", "   "])

    # Non-list type
    with pytest.raises(ValidationError):
        ChallengeCreate(**valid_base, required_skills="Python")


def test_challenge_create_knowledge_areas_validation():
    """18. Validation of knowledge_areas list."""
    valid_base = {
        "title": "Title",
        "description": "Description",
        "business_process": "Process",
        "difficulty_level": "BEGINNER",
        "modality": "REMOTE",
        "min_semester": 6,
        "economic_sector": "Sector",
    }

    schema_empty = ChallengeCreate(**valid_base, knowledge_areas=[])
    assert schema_empty.knowledge_areas == []

    schema_items = ChallengeCreate(**valid_base, knowledge_areas=[" AI / ML ", "Data Science"])
    assert schema_items.knowledge_areas == ["AI / ML", "Data Science"]

    with pytest.raises(ValidationError):
        ChallengeCreate(**valid_base, knowledge_areas=[456])

    with pytest.raises(ValidationError):
        ChallengeCreate(**valid_base, knowledge_areas=[""])


def test_challenge_update_partial():
    """19. ChallengeUpdate supports partial updates distinguishing unset from set."""
    # Completely empty update
    empty_update = ChallengeUpdate()
    assert empty_update.model_dump(exclude_unset=True) == {}

    # Partial update with some fields
    partial = ChallengeUpdate(
        title="Updated Title",
        min_semester=8,
        difficulty_level="ADVANCED",
    )
    dumped = partial.model_dump(exclude_unset=True)
    assert dumped == {
        "title": "Updated Title",
        "min_semester": 8,
        "difficulty_level": "ADVANCED",
    }
    assert "description" not in dumped
    assert "status" not in dumped

    # Rejection of explicit None on not-null columns
    with pytest.raises(ValidationError):
        ChallengeUpdate(title=None)

    with pytest.raises(ValidationError):
        ChallengeUpdate(min_semester=None)

    with pytest.raises(ValidationError):
        ChallengeUpdate(difficulty_level=None)


@pytest.mark.parametrize("invalid_status", ["IN_PROGRESS", "CLOSED", "CANCELLED", "RANDOM"])
def test_challenge_update_invalid_status(invalid_status: str):
    """20. Rejection of forbidden statuses in ChallengeUpdate."""
    with pytest.raises(ValidationError) as exc_info:
        ChallengeUpdate(status=invalid_status)
    assert "status" in str(exc_info.value)


def test_challenge_response_from_orm():
    """21. ChallengeResponse supports serialization from ORM object."""
    fixed_id = uuid.uuid4()
    fixed_company = uuid.uuid4()
    now = datetime.now(timezone.utc)

    orm_instance = Challenge(
        id=fixed_id,
        company_id=fixed_company,
        title="ORM Challenge Title",
        description="ORM Challenge Description",
        business_process="Process Alpha",
        status="OPEN",
        difficulty_level="ADVANCED",
        modality="REMOTE",
        min_semester=9,
        economic_sector="Aerospace",
        required_skills=["C++", "CUDA"],
        knowledge_areas=["High Performance Computing"],
        created_at=now,
        updated_at=now,
    )

    response = ChallengeResponse.model_validate(orm_instance)

    assert response.id == fixed_id
    assert response.company_id == fixed_company
    assert response.title == "ORM Challenge Title"
    assert response.description == "ORM Challenge Description"
    assert response.business_process == "Process Alpha"
    assert response.status == "OPEN"
    assert response.difficulty_level == "ADVANCED"
    assert response.modality == "REMOTE"
    assert response.min_semester == 9
    assert response.economic_sector == "Aerospace"
    assert response.required_skills == ["C++", "CUDA"]
    assert response.knowledge_areas == ["High Performance Computing"]
    assert response.created_at == now
    assert response.updated_at == now


# ==============================================================================
# 2. REPOSITORY TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_repository_create_success():
    """Repository create builds model, sets company_id, adds, commits, refreshes, returns entity."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    company_id = uuid.uuid4()

    challenge_in = ChallengeCreate(
        title="Inventory AI",
        description="Forecast demand with deep learning.",
        business_process="Logistics Inventory",
        difficulty_level="ADVANCED",
        modality="REMOTE",
        min_semester=7,
        economic_sector="Retail",
        required_skills=["Python", "PyTorch"],
        knowledge_areas=["Machine Learning"],
        status="OPEN",
    )

    result = await ChallengeRepository.create(mock_db, challenge_in, company_id)

    assert isinstance(result, Challenge)
    assert result.company_id == company_id
    assert result.title == "Inventory AI"
    assert result.description == "Forecast demand with deep learning."
    assert result.business_process == "Logistics Inventory"
    assert result.difficulty_level == "ADVANCED"
    assert result.modality == "REMOTE"
    assert result.min_semester == 7
    assert result.economic_sector == "Retail"
    assert result.required_skills == ["Python", "PyTorch"]
    assert result.knowledge_areas == ["Machine Learning"]
    assert result.status == "OPEN"

    mock_db.add.assert_called_once_with(result)
    mock_db.commit.assert_awaited_once()
    mock_db.refresh.assert_awaited_once_with(result)
    mock_db.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_repository_create_rollback_on_failure():
    """Repository create rolls back and re-raises on commit exception."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit.side_effect = RuntimeError("Database connection lost")
    company_id = uuid.uuid4()

    challenge_in = ChallengeCreate(
        title="Title",
        description="Description",
        business_process="Process",
        difficulty_level="BEGINNER",
        modality="REMOTE",
        min_semester=6,
        economic_sector="Sector",
    )

    with pytest.raises(RuntimeError, match="Database connection lost"):
        await ChallengeRepository.create(mock_db, challenge_in, company_id)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()
    mock_db.rollback.assert_awaited_once()
    mock_db.refresh.assert_not_called()


@pytest.mark.asyncio
async def test_repository_get_by_id_found():
    """Repository get_by_id returns Challenge when entity exists."""
    mock_db = AsyncMock()
    target_id = uuid.uuid4()
    company_id = uuid.uuid4()

    expected_challenge = Challenge(
        id=target_id,
        company_id=company_id,
        title="Existing Challenge",
        description="Desc",
        business_process="Process",
        difficulty_level="BEGINNER",
        modality="REMOTE",
        min_semester=6,
        economic_sector="Sector",
    )

    mock_scalar_result = MagicMock()
    mock_scalar_result.scalar_one_or_none.return_value = expected_challenge
    mock_db.execute.return_value = mock_scalar_result

    result = await ChallengeRepository.get_by_id(mock_db, target_id)

    assert result is expected_challenge
    mock_db.execute.assert_awaited_once()
    # Verify execute was called with a Select statement targeting target_id
    call_args = mock_db.execute.call_args[0]
    executed_stmt = call_args[0]
    assert "challenges.id =" in str(executed_stmt)


@pytest.mark.asyncio
async def test_repository_get_by_id_not_found():
    """Repository get_by_id returns None when entity does not exist."""
    mock_db = AsyncMock()
    target_id = uuid.uuid4()

    mock_scalar_result = MagicMock()
    mock_scalar_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_scalar_result

    result = await ChallengeRepository.get_by_id(mock_db, target_id)

    assert result is None
    mock_db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_repository_update_success():
    """Repository update applies partial fields, preserves omitted fields, commits, and refreshes."""
    mock_db = AsyncMock()
    orig_id = uuid.uuid4()
    orig_company = uuid.uuid4()
    orig_created_at = datetime.now(timezone.utc)

    existing_challenge = Challenge(
        id=orig_id,
        company_id=orig_company,
        title="Original Title",
        description="Original Description",
        business_process="Original Process",
        difficulty_level="BEGINNER",
        modality="REMOTE",
        min_semester=6,
        economic_sector="Old Sector",
        required_skills=["Java"],
        knowledge_areas=["OOP"],
        status="DRAFT",
        created_at=orig_created_at,
    )

    update_in = ChallengeUpdate(
        title="Updated Title",
        difficulty_level="INTERMEDIATE",
        status="OPEN",
    )

    updated = await ChallengeRepository.update(mock_db, existing_challenge, update_in)

    assert updated is existing_challenge
    # Modified fields
    assert updated.title == "Updated Title"
    assert updated.difficulty_level == "INTERMEDIATE"
    assert updated.status == "OPEN"
    # Preserved fields
    assert updated.id == orig_id
    assert updated.company_id == orig_company
    assert updated.description == "Original Description"
    assert updated.business_process == "Original Process"
    assert updated.modality == "REMOTE"
    assert updated.min_semester == 6
    assert updated.economic_sector == "Old Sector"
    assert updated.required_skills == ["Java"]
    assert updated.knowledge_areas == ["OOP"]
    assert updated.created_at == orig_created_at

    mock_db.commit.assert_awaited_once()
    mock_db.refresh.assert_awaited_once_with(existing_challenge)
    mock_db.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_repository_update_does_not_modify_identifiers():
    """Repository update ignores attempts to modify id, company_id, or created_at."""
    mock_db = AsyncMock()
    orig_id = uuid.uuid4()
    orig_company = uuid.uuid4()
    orig_created_at = datetime.now(timezone.utc)

    existing_challenge = Challenge(
        id=orig_id,
        company_id=orig_company,
        title="Title",
        description="Description",
        business_process="Process",
        difficulty_level="BEGINNER",
        modality="REMOTE",
        min_semester=6,
        economic_sector="Sector",
        created_at=orig_created_at,
    )

    # Subclass or mock schema dump containing protected keys
    mock_update_schema = MagicMock(spec=ChallengeUpdate)
    mock_update_schema.model_dump.return_value = {
        "id": uuid.uuid4(),
        "company_id": uuid.uuid4(),
        "created_at": datetime.now(timezone.utc),
        "title": "Legitimate Title Update",
    }

    updated = await ChallengeRepository.update(mock_db, existing_challenge, mock_update_schema)

    assert updated.id == orig_id
    assert updated.company_id == orig_company
    assert updated.created_at == orig_created_at
    assert updated.title == "Legitimate Title Update"


@pytest.mark.asyncio
async def test_repository_update_rollback_on_failure():
    """Repository update rolls back and re-raises on commit exception."""
    mock_db = AsyncMock()
    mock_db.commit.side_effect = RuntimeError("Commit failed")

    existing_challenge = Challenge(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        title="Title",
        description="Desc",
        business_process="Process",
        difficulty_level="BEGINNER",
        modality="REMOTE",
        min_semester=6,
        economic_sector="Sector",
    )

    update_in = ChallengeUpdate(title="New Title")

    with pytest.raises(RuntimeError, match="Commit failed"):
        await ChallengeRepository.update(mock_db, existing_challenge, update_in)

    mock_db.commit.assert_awaited_once()
    mock_db.rollback.assert_awaited_once()
    mock_db.refresh.assert_not_called()


@pytest.mark.asyncio
async def test_repository_list_by_company():
    """Repository list_by_company filters by company_id and applies skip/limit pagination."""
    mock_db = AsyncMock()
    target_company = uuid.uuid4()

    c1 = Challenge(
        id=uuid.uuid4(),
        company_id=target_company,
        title="Challenge 1",
        description="Desc 1",
        business_process="Process 1",
        difficulty_level="BEGINNER",
        modality="REMOTE",
        min_semester=6,
        economic_sector="Sector 1",
    )
    c2 = Challenge(
        id=uuid.uuid4(),
        company_id=target_company,
        title="Challenge 2",
        description="Desc 2",
        business_process="Process 2",
        difficulty_level="INTERMEDIATE",
        modality="HYBRID",
        min_semester=7,
        economic_sector="Sector 2",
    )

    mock_scalar_result = MagicMock(spec=ScalarResult)
    mock_scalar_result.all.return_value = [c1, c2]

    mock_exec_result = MagicMock()
    mock_exec_result.scalars.return_value = mock_scalar_result
    mock_db.execute.return_value = mock_exec_result

    results = await ChallengeRepository.list_by_company(
        mock_db,
        company_id=target_company,
        skip=5,
        limit=10,
    )

    assert results == [c1, c2]
    mock_db.execute.assert_awaited_once()

    # Inspect executed select statement
    call_args = mock_db.execute.call_args[0]
    executed_stmt = call_args[0]
    stmt_str = str(executed_stmt)

    assert "challenges.company_id =" in stmt_str
    assert "OFFSET :param_1" in stmt_str or "OFFSET" in stmt_str
    assert "LIMIT :param_2" in stmt_str or "LIMIT" in stmt_str
