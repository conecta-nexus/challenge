"""Create challenges table.

Revision ID: 001
Revises:
Create Date: 2026-11-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "challenges",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "business_process",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'DRAFT'"),
            nullable=False,
        ),
        sa.Column(
            "difficulty_level",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "modality",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "min_semester",
            sa.Integer(),
            server_default=sa.text("6"),
            nullable=False,
        ),
        sa.Column(
            "economic_sector",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "required_skills",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "knowledge_areas",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'OPEN', 'IN_PROGRESS', 'CLOSED', 'CANCELLED')",
            name="ck_challenges_status",
        ),
        sa.CheckConstraint(
            "difficulty_level IN ('BEGINNER', 'INTERMEDIATE', 'ADVANCED')",
            name="ck_challenges_difficulty_level",
        ),
        sa.CheckConstraint(
            "modality IN ('REMOTE', 'HYBRID', 'ON_SITE')",
            name="ck_challenges_modality",
        ),
        sa.CheckConstraint(
            "min_semester BETWEEN 6 AND 10",
            name="ck_challenges_min_semester",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_challenges_company_id",
        "challenges",
        ["company_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_challenges_company_id", table_name="challenges")
    op.drop_table("challenges")
