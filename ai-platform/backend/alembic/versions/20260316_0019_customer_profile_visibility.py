"""customer profile visibility

Revision ID: 20260316_0019
Revises: 20260316_0018
Create Date: 2026-03-16 14:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260316_0019"
down_revision: Union[str, None] = "20260316_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in [col["name"] for col in inspector.get_columns(table_name)]


def upgrade() -> None:
    if not _column_exists("users", "is_profile_public"):
        op.add_column(
            "users",
            sa.Column(
                "is_profile_public",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
        )


def downgrade() -> None:
    if _column_exists("users", "is_profile_public"):
        op.drop_column("users", "is_profile_public")
