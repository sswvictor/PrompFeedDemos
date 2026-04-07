"""customer favorite providers

Revision ID: 20260316_0020
Revises: 20260316_0019
Create Date: 2026-03-16 18:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260316_0020"
down_revision: Union[str, None] = "20260316_0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in [col["name"] for col in inspector.get_columns(table_name)]


def upgrade() -> None:
    if not _column_exists("users", "favorite_provider_ids"):
        op.add_column(
            "users",
            sa.Column("favorite_provider_ids", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("users", "favorite_provider_ids"):
        op.drop_column("users", "favorite_provider_ids")
