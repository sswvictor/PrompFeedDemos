"""Add onboarding preference columns to users table.

service_interests and lifestyle_preferences store JSON arrays
chosen during customer onboarding (e.g. ["hair","nails"], ["bring_dog","coffee"]).

Revision ID: 20260309_0006
Revises: 20260305_0005
Create Date: 2026-03-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260309_0006"
down_revision = "20260305_0005"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col.get("name") == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _column_exists("users", "service_interests"):
        op.add_column(
            "users",
            sa.Column("service_interests", sa.Text(), nullable=True),
        )
    if not _column_exists("users", "lifestyle_preferences"):
        op.add_column(
            "users",
            sa.Column("lifestyle_preferences", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("users", "lifestyle_preferences"):
        op.drop_column("users", "lifestyle_preferences")
    if _column_exists("users", "service_interests"):
        op.drop_column("users", "service_interests")
