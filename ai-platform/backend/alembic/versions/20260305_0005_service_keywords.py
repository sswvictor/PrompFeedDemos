"""Add keywords column to services for flexible AI service matching.

Revision ID: 20260305_0005
Revises: 20260303_0004
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa

revision = "20260305_0005"
down_revision = "20260303_0004"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col.get("name") == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _column_exists("services", "keywords"):
        op.add_column(
            "services",
            sa.Column("keywords", sa.String(512), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("services", "keywords"):
        op.drop_column("services", "keywords")
