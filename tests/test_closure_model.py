"""Unit tests for the challenge closure audit model and migration."""

import importlib.util
import inspect
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

from src.core.database import Base
from src.models.closure import ChallengeClosureLog


def load_migration_004():
    """Load the closure log migration module dynamically."""
    migration_path = (
        Path(__file__).parent.parent
        / "alembic"
        / "versions"
        / "004_create_closure_logs_table.py"
    )
    spec = importlib.util.spec_from_file_location("migration_004", migration_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_closure_log_model_metadata() -> None:
    """Map the audit model to the expected table and columns."""
    assert issubclass(ChallengeClosureLog, Base)
    assert ChallengeClosureLog.__tablename__ == "challenge_closure_logs"
    assert set(ChallengeClosureLog.__table__.columns.keys()) == {
        "id",
        "challenge_id",
        "closed_by",
        "previous_status",
        "target_status",
        "closure_reason",
        "created_at",
    }


def test_closure_log_column_types_and_foreign_key() -> None:
    """Use UUID identifiers, bounded statuses, text reason, and timestamps."""
    columns = ChallengeClosureLog.__table__.columns

    assert isinstance(columns["id"].type, UUID)
    assert isinstance(columns["challenge_id"].type, UUID)
    assert isinstance(columns["closed_by"].type, UUID)
    assert isinstance(columns["previous_status"].type, String)
    assert isinstance(columns["target_status"].type, String)
    assert isinstance(columns["closure_reason"].type, Text)
    assert isinstance(columns["created_at"].type, TIMESTAMP)
    assert columns["created_at"].type.timezone is True

    foreign_key = next(iter(columns["challenge_id"].foreign_keys))
    assert foreign_key.target_fullname == "challenges.id"


def test_closure_log_constraints_and_indexes() -> None:
    """Enforce valid closure states and meaningful justifications in PostgreSQL."""
    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in ChallengeClosureLog.__table__.constraints
        if hasattr(constraint, "sqltext")
    }
    assert "ck_challenge_closure_logs_previous_status" in constraints
    assert "ck_challenge_closure_logs_target_status" in constraints
    assert "ck_challenge_closure_logs_reason_length" in constraints
    assert "15" in constraints["ck_challenge_closure_logs_reason_length"]

    index_names = {index.name for index in ChallengeClosureLog.__table__.indexes}
    assert index_names == {
        "ix_challenge_closure_logs_challenge_id",
        "ix_challenge_closure_logs_created_at",
    }


def test_migration_004_metadata() -> None:
    """Continue the existing migration chain after catalog revision 003."""
    migration = load_migration_004()

    assert migration.revision == "004"
    assert migration.down_revision == "003"
    assert inspect.isfunction(migration.upgrade)
    assert inspect.isfunction(migration.downgrade)


def test_migration_004_upgrade_and_downgrade_structure() -> None:
    """Create and remove the table and both supporting indexes."""
    migration = load_migration_004()

    with (
        patch("alembic.op.create_table") as create_table,
        patch("alembic.op.create_index") as create_index,
        patch("alembic.op.drop_index") as drop_index,
        patch("alembic.op.drop_table") as drop_table,
    ):
        migration.upgrade()

        create_table.assert_called_once()
        assert create_table.call_args.args[0] == "challenge_closure_logs"
        assert create_index.call_count == 2

        migration.downgrade()

        assert drop_index.call_count == 2
        drop_table.assert_called_once_with("challenge_closure_logs")
