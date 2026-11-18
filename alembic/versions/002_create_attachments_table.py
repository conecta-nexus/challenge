"""Create challenge attachments table.

Revision ID: 002
Revises: 001
Create Date: 2026-11-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "challenge_attachments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "challenge_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "file_name",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "file_size_bytes",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "mime_type",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "storage_path",
            sa.String(length=512),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["challenge_id"],
            ["challenges.id"],
            name="fk_challenge_attachments_challenge_id_challenges",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "file_size_bytes <= 10485760",
            name="ck_challenge_attachments_file_size_bytes",
        ),
        sa.CheckConstraint(
            "mime_type IN ('application/pdf', 'image/png', 'image/jpeg', 'image/webp')",
            name="ck_challenge_attachments_mime_type",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_challenge_attachments_challenge_id",
        "challenge_attachments",
        ["challenge_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_challenge_attachments_challenge_id",
        table_name="challenge_attachments",
    )
    op.drop_table("challenge_attachments")
