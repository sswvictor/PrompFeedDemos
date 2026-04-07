"""Add image_url and display_name to users table.

Stores the customer's chosen display name and their uploaded profile
avatar URL so the customer profile page can show a personalised header.

Revision ID: 20260310_0007
Revises: 20260309_0006
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa

revision = "20260310_0007"
down_revision = "20260309_0006"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col.get("name") == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _column_exists("users", "display_name"):
        op.add_column(
            "users",
            sa.Column("display_name", sa.String(255), nullable=True),
        )
    if not _column_exists("users", "image_url"):
        op.add_column(
            "users",
            sa.Column("image_url", sa.String(500), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("users", "image_url"):
        op.drop_column("users", "image_url")
    if _column_exists("users", "display_name"):
        op.drop_column("users", "display_name")
