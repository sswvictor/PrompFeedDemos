"""add provider booking and cancellation policy columns

Revision ID: 20260315_0013
Revises: 20260315_0012
Create Date: 2026-03-15 18:30:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260315_0013"
down_revision: Union[str, None] = "20260315_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    cols = inspector.get_columns(table_name)
    return any(c["name"] == column_name for c in cols)


def upgrade() -> None:
    with op.batch_alter_table("providers", schema=None) as batch_op:
        if not _column_exists("providers", "booking_policy"):
            batch_op.add_column(sa.Column("booking_policy", sa.String(length=500), nullable=True))
        if not _column_exists("providers", "cancellation_policy"):
            batch_op.add_column(sa.Column("cancellation_policy", sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("providers", schema=None) as batch_op:
        if _column_exists("providers", "cancellation_policy"):
            batch_op.drop_column("cancellation_policy")
        if _column_exists("providers", "booking_policy"):
            batch_op.drop_column("booking_policy")
