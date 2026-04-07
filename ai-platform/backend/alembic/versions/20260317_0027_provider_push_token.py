"""provider push token for Expo push notifications

Revision ID: 20260317_0027
Revises: 20260316_0026
Create Date: 2026-03-17 09:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260317_0027"
down_revision: Union[str, None] = "20260316_0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(c["name"] == column_name for c in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _column_exists("providers", "push_token"):
        op.add_column(
            "providers",
            sa.Column("push_token", sa.String(length=255), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("providers", "push_token"):
        op.drop_column("providers", "push_token")
