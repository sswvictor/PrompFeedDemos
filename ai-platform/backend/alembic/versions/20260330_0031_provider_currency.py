"""add provider currency column (ISO 4217)

Revision ID: 20260330_0031
Revises: 20260319_0030
Create Date: 2026-03-30 10:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260330_0031"
down_revision: Union[str, None] = "20260319_0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(c["name"] == column_name for c in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _column_exists("providers", "currency"):
        op.add_column(
            "providers",
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="SEK"),
        )


def downgrade() -> None:
    if _column_exists("providers", "currency"):
        op.drop_column("providers", "currency")
