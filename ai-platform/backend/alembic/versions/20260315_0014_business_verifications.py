"""create business_verifications table

Revision ID: 20260315_0014
Revises: 20260315_0013
Create Date: 2026-03-15 19:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260315_0014"
down_revision: Union[str, None] = "20260315_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("business_verifications"):
        return

    op.create_table(
        "business_verifications",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "provider_id",
            sa.String(length=36),
            sa.ForeignKey("providers.provider_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("country", sa.String(length=2), nullable=False, server_default="US"),
        sa.Column("us_state", sa.String(length=2), nullable=True),
        sa.Column("license_type", sa.String(length=64), nullable=True),
        sa.Column("license_number", sa.String(length=128), nullable=True),
        sa.Column("org_number", sa.String(length=128), nullable=True),
        sa.Column("document_filename", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    if _table_exists("business_verifications"):
        op.drop_table("business_verifications")
