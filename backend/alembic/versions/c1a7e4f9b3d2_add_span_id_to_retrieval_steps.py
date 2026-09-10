"""add span_id to retrieval_steps

Revision ID: c1a7e4f9b3d2
Revises: 9f3a2c7d5e21
Create Date: 2026-09-11 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c1a7e4f9b3d2"
down_revision: str | None = "9f3a2c7d5e21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("retrieval_steps", sa.Column("span_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("retrieval_steps", "span_id")
