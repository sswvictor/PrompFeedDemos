"""conversation needs_human flag

Revision ID: 20260315_0017
Revises: 20260315_0016
Create Date: 2026-03-15 23:59:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260315_0017"
down_revision: Union[str, None] = "20260315_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in [c["name"] for c in inspector.get_columns(table)]


def upgrade() -> None:
    if not _column_exists("conversations", "needs_human"):
        op.add_column(
            "conversations",
            sa.Column("needs_human", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    if _column_exists("conversations", "needs_human"):
        op.drop_column("conversations", "needs_human")
