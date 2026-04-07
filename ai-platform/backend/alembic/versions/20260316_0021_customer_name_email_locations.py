"""customer full_name and preferred_locations

Revision ID: 20260316_0021
Revises: 20260316_0020
Create Date: 2026-03-16 17:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260316_0021"
down_revision: Union[str, None] = "20260316_0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in [col["name"] for col in inspector.get_columns(table_name)]


def upgrade() -> None:
    # full_name: real legal name — only visible to providers the customer has booked with (GDPR)
    if not _column_exists("users", "full_name"):
        op.add_column(
            "users",
            sa.Column("full_name", sa.String(255), nullable=True),
        )

    # preferred_locations: JSON array of location strings used by the AI for booking context
    # e.g. '["Gym - Hammarby", "Office near Slussen"]'
    if not _column_exists("users", "preferred_locations"):
        op.add_column(
            "users",
            sa.Column("preferred_locations", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("users", "preferred_locations"):
        op.drop_column("users", "preferred_locations")
    if _column_exists("users", "full_name"):
        op.drop_column("users", "full_name")
