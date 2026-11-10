"""Unit tests for ChallengeAttachment ORM model definition, columns, and constraints."""

import importlib.util
import inspect
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import BigInteger, String
from sqlalchemy.dialects.postgresql import BIGINT, TIMESTAMP, UUID

from src.core.database import Base
from src.models.attachment import ChallengeAttachment


def _load_migration_002():
    """Load the 002 migration module dynamically."""
    migration_path = (
        Path(__file__).parent.parent / "alembic" / "versions" / "002_create_attachments_table.py"
    )
    spec = importlib.util.spec_from_file_location("migration_002", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_attachment_inherits_from_base():
    """1, 2. Verify ChallengeAttachment inherits from Base and maps to 'challenge_attachments'."""
    assert issubclass(ChallengeAttachment, Base)
    assert ChallengeAttachment.__tablename__ == "challenge_attachments"
    assert ChallengeAttachment.__table__.name == "challenge_attachments"


def test_attachment_columns_existence():
    """3. Verify all 8 mandatory columns exist in challenge_attachments table."""
    expected_columns = {
        "id",
        "challenge_id",
        "file_name",
        "file_size_bytes",
        "mime_type",
        "storage_path",
        "uploaded_by",
        "created_at",
    }
    actual_columns = set(ChallengeAttachment.__table__.columns.keys())
    assert actual_columns == expected_columns
    assert len(actual_columns) == 8


def test_attachment_column_types_and_nullability():
    """4-12. Verify each column has correct native type, length, and nullability."""
    cols = ChallengeAttachment.__table__.columns

    # 4. id: UUID
    assert isinstance(cols["id"].type, UUID)
    assert cols["id"].type.as_uuid is True
    assert cols["id"].nullable is False

    # 5. challenge_id: UUID
    assert isinstance(cols["challenge_id"].type, UUID)
    assert cols["challenge_id"].type.as_uuid is True
    assert cols["challenge_id"].nullable is False

    # 6. uploaded_by: UUID
    assert isinstance(cols["uploaded_by"].type, UUID)
    assert cols["uploaded_by"].type.as_uuid is True
    assert cols["uploaded_by"].nullable is False

    # 7. file_size_bytes: BIGINT
    assert isinstance(cols["file_size_bytes"].type, (BIGINT, BigInteger))
    assert cols["file_size_bytes"].nullable is False

    # 8. file_name: VARCHAR(255)
    assert isinstance(cols["file_name"].type, String)
    assert cols["file_name"].type.length == 255
    assert cols["file_name"].nullable is False

    # 9. mime_type: VARCHAR(100)
    assert isinstance(cols["mime_type"].type, String)
    assert cols["mime_type"].type.length == 100
    assert cols["mime_type"].nullable is False

    # 10. storage_path: VARCHAR(512)
    assert isinstance(cols["storage_path"].type, String)
    assert cols["storage_path"].type.length == 512
    assert cols["storage_path"].nullable is False

    # 11. created_at: TIMESTAMPTZ
    assert isinstance(cols["created_at"].type, TIMESTAMP)
    assert cols["created_at"].type.timezone is True
    assert cols["created_at"].nullable is False


def test_attachment_primary_key_and_uuid_default():
    """13, 14. Verify primary key configuration and server default for UUID generation."""
    col = ChallengeAttachment.__table__.columns["id"]
    assert col.primary_key is True
    assert col.server_default is not None
    assert "gen_random_uuid()" in str(col.server_default.arg)


def test_attachment_foreign_key_and_cascade():
    """15, 16. Verify FK points to challenges.id with ON DELETE CASCADE."""
    col = ChallengeAttachment.__table__.columns["challenge_id"]
    assert len(col.foreign_keys) == 1
    fk = list(col.foreign_keys)[0]
    assert fk.target_fullname == "challenges.id"
    assert fk.ondelete is not None
    assert fk.ondelete.upper() == "CASCADE"


def test_attachment_challenge_id_indexed():
    """17. Verify challenge_id has an index defined with consistent name."""
    col = ChallengeAttachment.__table__.columns["challenge_id"]
    assert col.index is True or any(
        "challenge_id" in [c.name for c in idx.columns]
        for idx in ChallengeAttachment.__table__.indexes
    )

    index_names = {idx.name for idx in ChallengeAttachment.__table__.indexes}
    assert any("ix_challenge_attachments_challenge_id" in name for name in index_names)


def test_attachment_file_size_check_constraint():
    """18, 19. Verify file_size_bytes CHECK constraint exists and contains 10485760."""
    constraints = {
        c.name: str(c.sqltext)
        for c in ChallengeAttachment.__table__.constraints
        if hasattr(c, "sqltext")
    }

    assert "ck_challenge_attachments_file_size_bytes" in constraints
    size_sql = constraints["ck_challenge_attachments_file_size_bytes"]
    assert "10485760" in size_sql
    assert "file_size_bytes" in size_sql


def test_attachment_mime_type_check_constraint():
    """20, 21. Verify mime_type CHECK constraint exists and contains exactly 4 allowed MIME types."""
    constraints = {
        c.name: str(c.sqltext)
        for c in ChallengeAttachment.__table__.constraints
        if hasattr(c, "sqltext")
    }

    assert "ck_challenge_attachments_mime_type" in constraints
    mime_sql = constraints["ck_challenge_attachments_mime_type"]
    for mime in [
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/webp",
    ]:
        assert mime in mime_sql


def test_attachment_created_at_timezone_and_defaults():
    """22, 23. Verify created_at is timezone-aware and has server default and python default."""
    col = ChallengeAttachment.__table__.columns["created_at"]
    assert col.type.timezone is True
    assert col.server_default is not None
    assert col.default is not None

    instance = ChallengeAttachment(
        challenge_id=uuid.uuid4(),
        file_name="doc.pdf",
        file_size_bytes=1024,
        mime_type="application/pdf",
        storage_path="challenges/uuid/doc.pdf",
        uploaded_by=uuid.uuid4(),
    )
    assert instance.file_name == "doc.pdf"
    assert instance.file_size_bytes == 1024


def test_migration_002_metadata():
    """24, 25. Verify migration 002 revision identifiers."""
    migration = _load_migration_002()
    assert migration.revision == "002"
    assert migration.down_revision == "001"
    assert inspect.isfunction(migration.upgrade)
    assert inspect.isfunction(migration.downgrade)


def test_migration_002_upgrade_downgrade_structure():
    """26, 27. Verify migration 002 calls create_table, create_index on upgrade, and drop on downgrade."""
    migration = _load_migration_002()

    with patch("alembic.op.create_table") as mock_create_table, \
         patch("alembic.op.create_index") as mock_create_index, \
         patch("alembic.op.drop_index") as mock_drop_index, \
         patch("alembic.op.drop_table") as mock_drop_table:

        migration.upgrade()
        mock_create_table.assert_called_once()
        args, _ = mock_create_table.call_args
        assert args[0] == "challenge_attachments"
        mock_create_index.assert_called_once()
        index_args, _ = mock_create_index.call_args
        assert "ix_challenge_attachments_challenge_id" in index_args[0]

        migration.downgrade()
        mock_drop_index.assert_called_once()
        mock_drop_table.assert_called_once_with("challenge_attachments")
