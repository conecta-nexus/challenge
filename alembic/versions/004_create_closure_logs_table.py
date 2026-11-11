"""Create challenge closure audit log table.

Revision ID: 004
Revises: 003
Create Date: 2026-11-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "challenge_closure_logs",
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
            "closed_by",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("previous_status", sa.String(length=20), nullable=False),
        sa.Column("target_status", sa.String(length=20), nullable=False),
        sa.Column("closure_reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "previous_status = 'OPEN'",
            name="ck_challenge_closure_logs_previous_status",
        ),
        sa.CheckConstraint(
            "target_status IN ('CLOSED', 'CANCELLED')",
            name="ck_challenge_closure_logs_target_status",
        ),
        sa.CheckConstraint(
            "char_length(btrim(closure_reason)) >= 15",
            name="ck_challenge_closure_logs_reason_length",
        ),
        sa.ForeignKeyConstraint(
            ["challenge_id"],
            ["challenges.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_challenge_closure_logs_challenge_id",
        "challenge_closure_logs",
        ["challenge_id"],
        unique=False,
    )
    op.create_index(
        "ix_challenge_closure_logs_created_at",
        "challenge_closure_logs",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_challenge_closure_logs_created_at",
        table_name="challenge_closure_logs",
    )
    op.drop_index(
        "ix_challenge_closure_logs_challenge_id",
        table_name="challenge_closure_logs",
    )
    op.drop_table("challenge_closure_logs")
