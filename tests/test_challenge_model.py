"""Unit tests for Challenge ORM model definition, columns, and constraints."""

import uuid
from datetime import datetime

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

from src.core.database import Base
from src.models.challenge import Challenge


def test_challenge_inherits_from_base():
    """Verify Challenge inherits from Declarative Base and maps to 'challenges' table."""
    assert issubclass(Challenge, Base)
    assert Challenge.__tablename__ == "challenges"
    assert Challenge.__table__.name == "challenges"


def test_challenge_columns_existence():
    """Verify all 14 mandatory columns exist in the challenges table."""
    expected_columns = {
        "id",
        "company_id",
        "title",
        "description",
        "business_process",
        "status",
        "difficulty_level",
        "modality",
        "min_semester",
        "economic_sector",
        "required_skills",
        "knowledge_areas",
        "created_at",
        "updated_at",
    }
    actual_columns = set(Challenge.__table__.columns.keys())
    assert actual_columns == expected_columns
    assert len(actual_columns) == 14


def test_challenge_column_types():
    """Verify each column uses the exact required PostgreSQL native type."""
    cols = Challenge.__table__.columns

    assert isinstance(cols["id"].type, UUID)
    assert cols["id"].type.as_uuid is True

    assert isinstance(cols["company_id"].type, UUID)
    assert cols["company_id"].type.as_uuid is True
    assert cols["company_id"].nullable is False

    assert isinstance(cols["title"].type, String)
    assert cols["title"].type.length == 255
    assert cols["title"].nullable is False

    assert isinstance(cols["description"].type, Text)
    assert cols["description"].nullable is False

    assert isinstance(cols["business_process"].type, String)
    assert cols["business_process"].type.length == 255
    assert cols["business_process"].nullable is False

    assert isinstance(cols["status"].type, String)
    assert cols["status"].type.length == 20
    assert cols["status"].nullable is False

    assert isinstance(cols["difficulty_level"].type, String)
    assert cols["difficulty_level"].type.length == 20
    assert cols["difficulty_level"].nullable is False

    assert isinstance(cols["modality"].type, String)
    assert cols["modality"].type.length == 20
    assert cols["modality"].nullable is False

    assert isinstance(cols["min_semester"].type, Integer)
    assert cols["min_semester"].nullable is False

    assert isinstance(cols["economic_sector"].type, String)
    assert cols["economic_sector"].type.length == 100
    assert cols["economic_sector"].nullable is False

    assert isinstance(cols["required_skills"].type, JSONB)
    assert cols["required_skills"].nullable is False

    assert isinstance(cols["knowledge_areas"].type, JSONB)
    assert cols["knowledge_areas"].nullable is False

    assert isinstance(cols["created_at"].type, TIMESTAMP)
    assert cols["created_at"].type.timezone is True
    assert cols["created_at"].nullable is False

    assert isinstance(cols["updated_at"].type, TIMESTAMP)
    assert cols["updated_at"].type.timezone is True
    assert cols["updated_at"].nullable is False


def test_challenge_primary_key_and_uuid_default():
    """Verify primary key configuration and server default for UUID generation."""
    col = Challenge.__table__.columns["id"]
    assert col.primary_key is True
    assert col.server_default is not None
    assert "gen_random_uuid()" in str(col.server_default.arg)


def test_challenge_company_id_index():
    """Verify company_id has an index defined and does not define a foreign key."""
    col = Challenge.__table__.columns["company_id"]
    assert len(col.foreign_keys) == 0

    # Verify index presence in table indexes
    indexed_columns = {
        col.name
        for index in Challenge.__table__.indexes
        for col in index.columns
    }
    assert "company_id" in indexed_columns


def test_challenge_default_status_draft():
    """Verify status defaults to 'DRAFT' both in Python ORM and database server_default."""
    col = Challenge.__table__.columns["status"]
    assert col.default.arg == "DRAFT"
    assert "'DRAFT'" in str(col.server_default.arg)

    instance = Challenge(
        company_id=uuid.uuid4(),
        title="Test Title",
        description="Test Desc",
        business_process="Process",
        difficulty_level="INTERMEDIATE",
        modality="REMOTE",
        economic_sector="Technology",
    )
    assert instance.status == "DRAFT"


def test_challenge_default_min_semester():
    """Verify min_semester defaults to 6 in both Python ORM and database server_default."""
    col = Challenge.__table__.columns["min_semester"]
    assert col.default.arg == 6
    assert "6" in str(col.server_default.arg)

    instance = Challenge(
        company_id=uuid.uuid4(),
        title="Test Title",
        description="Test Desc",
        business_process="Process",
        difficulty_level="INTERMEDIATE",
        modality="REMOTE",
        economic_sector="Technology",
    )
    assert instance.min_semester == 6


def test_challenge_default_jsonb_lists():
    """Verify required_skills and knowledge_areas default to empty lists without shared mutation."""
    col_skills = Challenge.__table__.columns["required_skills"]
    col_areas = Challenge.__table__.columns["knowledge_areas"]

    assert callable(col_skills.default.arg)
    assert col_skills.default.arg(None) == []
    assert callable(col_areas.default.arg)
    assert col_areas.default.arg(None) == []
    assert "'[]'::jsonb" in str(col_skills.server_default.arg)
    assert "'[]'::jsonb" in str(col_areas.server_default.arg)

    inst1 = Challenge(
        company_id=uuid.uuid4(),
        title="T1",
        description="D1",
        business_process="P1",
        difficulty_level="BEGINNER",
        modality="REMOTE",
        economic_sector="Sector",
    )
    inst2 = Challenge(
        company_id=uuid.uuid4(),
        title="T2",
        description="D2",
        business_process="P2",
        difficulty_level="BEGINNER",
        modality="REMOTE",
        economic_sector="Sector",
    )

    assert inst1.required_skills == []
    assert inst1.knowledge_areas == []
    assert inst1.required_skills is not inst2.required_skills
    assert inst1.knowledge_areas is not inst2.knowledge_areas


def test_challenge_timestamp_defaults():
    """Verify created_at and updated_at have timezone enabled and server defaults."""
    col_created = Challenge.__table__.columns["created_at"]
    col_updated = Challenge.__table__.columns["updated_at"]

    assert col_created.type.timezone is True
    assert col_updated.type.timezone is True
    assert col_created.server_default is not None
    assert col_updated.server_default is not None


def test_challenge_check_constraints_registered_in_metadata():
    """Verify all four mandatory CHECK constraints are registered in table metadata."""
    constraints = {c.name: str(c.sqltext) for c in Challenge.__table__.constraints if hasattr(c, "sqltext")}

    assert "ck_challenges_status" in constraints
    assert "ck_challenges_difficulty_level" in constraints
    assert "ck_challenges_modality" in constraints
    assert "ck_challenges_min_semester" in constraints

    # Verify status constraint values
    status_sql = constraints["ck_challenges_status"]
    for expected_status in ["DRAFT", "OPEN", "IN_PROGRESS", "CLOSED", "CANCELLED"]:
        assert expected_status in status_sql

    # Verify difficulty_level constraint values
    diff_sql = constraints["ck_challenges_difficulty_level"]
    for expected_diff in ["BEGINNER", "INTERMEDIATE", "ADVANCED"]:
        assert expected_diff in diff_sql

    # Verify modality constraint values
    mod_sql = constraints["ck_challenges_modality"]
    for expected_mod in ["REMOTE", "HYBRID", "ON_SITE"]:
        assert expected_mod in mod_sql

    # Verify min_semester constraint range
    sem_sql = constraints["ck_challenges_min_semester"]
    assert "BETWEEN 6 AND 10" in sem_sql or ("6" in sem_sql and "10" in sem_sql)
