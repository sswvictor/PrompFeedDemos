"""add provider_intelligence table for AI-derived vibe profiles

Revision ID: 20260315_0012
Revises: 20260312_0011
Create Date: 2026-03-15 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import NoSuchTableError


# revision identifiers, used by Alembic.
revision: str = "20260315_0012"
down_revision: Union[str, None] = "20260312_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    try:
        indexes = inspector.get_indexes(table_name)
    except NoSuchTableError:
        return False
    return any((idx.get("name") or "") == index_name for idx in indexes)


def upgrade() -> None:
    if not _table_exists("provider_intelligence"):
        op.create_table(
            "provider_intelligence",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("provider_id", sa.String(length=36), nullable=False),

            # Layer 2: Contextual
            sa.Column("specialties", sa.Text(), nullable=True),
            sa.Column("price_tier", sa.String(length=20), nullable=True),
            sa.Column("target_audience", sa.String(length=200), nullable=True),
            sa.Column("unique_value", sa.Text(), nullable=True),
            sa.Column("social_proof", sa.Text(), nullable=True),

            # Layer 3: Identity / Vibe
            sa.Column("ai_vibe_tags", sa.Text(), nullable=True),
            sa.Column("confirmed_vibe_tags", sa.Text(), nullable=True),
            sa.Column("vibe_scores", sa.Text(), nullable=True),
            sa.Column("vibe_summary", sa.Text(), nullable=True),

            # Source tracking
            sa.Column("source_url", sa.String(length=500), nullable=True),
            sa.Column("ig_posts_analyzed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("data_sources", sa.Text(), nullable=True),

            # Processing status
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("analyzed_at", sa.DateTime(), nullable=True),
            sa.Column("confirmed_at", sa.DateTime(), nullable=True),

            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),

            sa.ForeignKeyConstraint(["provider_id"], ["providers.provider_id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("provider_id", name="uq_provider_intelligence_provider"),
        )

    idx_provider = "ix_provider_intelligence_provider_id"
    idx_status = "ix_provider_intelligence_status"

    if not _index_exists("provider_intelligence", idx_provider):
        with op.batch_alter_table("provider_intelligence", schema=None) as batch_op:
            batch_op.create_index(idx_provider, ["provider_id"], unique=True)

    if not _index_exists("provider_intelligence", idx_status):
        with op.batch_alter_table("provider_intelligence", schema=None) as batch_op:
            batch_op.create_index(idx_status, ["status"], unique=False)


def downgrade() -> None:
    if not _table_exists("provider_intelligence"):
        return

    idx_provider = "ix_provider_intelligence_provider_id"
    idx_status = "ix_provider_intelligence_status"

    with op.batch_alter_table("provider_intelligence", schema=None) as batch_op:
        if _index_exists("provider_intelligence", idx_status):
            batch_op.drop_index(idx_status)
        if _index_exists("provider_intelligence", idx_provider):
            batch_op.drop_index(idx_provider)

    op.drop_table("provider_intelligence")
