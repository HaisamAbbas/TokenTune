"""add V2 evidence/savings/confidence_bucket fields to optimization_recommendations

Revision ID: a1b2c3d4e5f6
Revises: 17f32cc917f9
Create Date: 2026-09-11 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "17f32cc917f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "optimization_recommendations", sa.Column("confidence_bucket", sa.String(), nullable=True)
    )
    op.add_column(
        "optimization_recommendations", sa.Column("evidence", sa.JSON(), nullable=True)
    )
    op.add_column(
        "optimization_recommendations",
        sa.Column("estimated_savings_low", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "optimization_recommendations",
        sa.Column("estimated_savings_high", sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("optimization_recommendations", "estimated_savings_high")
    op.drop_column("optimization_recommendations", "estimated_savings_low")
    op.drop_column("optimization_recommendations", "evidence")
    op.drop_column("optimization_recommendations", "confidence_bucket")
