"""Create GIN and B-Tree indexes for challenge catalog multi-criteria search.

Revision ID: 003
Revises: 002
Create Date: 2026-11-10
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL GIN indexes for JSONB arrays
    op.create_index(
        "ix_challenges_required_skills_gin",
        "challenges",
        ["required_skills"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_challenges_knowledge_areas_gin",
        "challenges",
        ["knowledge_areas"],
        unique=False,
        postgresql_using="gin",
    )

    # PostgreSQL B-Tree indexes for catalog filters and sorting
    op.create_index(
        "ix_challenges_status",
        "challenges",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_challenges_created_at",
        "challenges",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_challenges_economic_sector",
        "challenges",
        ["economic_sector"],
        unique=False,
    )
    op.create_index(
        "ix_challenges_modality",
        "challenges",
        ["modality"],
        unique=False,
    )
    op.create_index(
        "ix_challenges_difficulty_level",
        "challenges",
        ["difficulty_level"],
        unique=False,
    )
    op.create_index(
        "ix_challenges_status_created_at",
        "challenges",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_challenges_status_created_at", table_name="challenges")
    op.drop_index("ix_challenges_difficulty_level", table_name="challenges")
    op.drop_index("ix_challenges_modality", table_name="challenges")
    op.drop_index("ix_challenges_economic_sector", table_name="challenges")
    op.drop_index("ix_challenges_created_at", table_name="challenges")
    op.drop_index("ix_challenges_status", table_name="challenges")
    op.drop_index("ix_challenges_knowledge_areas_gin", table_name="challenges", postgresql_using="gin")
    op.drop_index("ix_challenges_required_skills_gin", table_name="challenges", postgresql_using="gin")
