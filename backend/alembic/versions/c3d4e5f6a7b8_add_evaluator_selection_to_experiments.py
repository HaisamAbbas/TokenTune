"""add per-experiment evaluator selection (evaluator_type, evaluator_metrics)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-11 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "experiments",
        sa.Column("evaluator_type", sa.String(), nullable=False, server_default="fallback"),
    )
    op.alter_column("experiments", "evaluator_type", server_default=None)
    op.add_column("experiments", sa.Column("evaluator_metrics", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("experiments", "evaluator_metrics")
    op.drop_column("experiments", "evaluator_type")
