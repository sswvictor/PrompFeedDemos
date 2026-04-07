"""Create salon_link_requests table for salon/provider linking workflow.

Revision ID: 20260310_0010
Revises: 20260310_0009
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa

revision = "20260310_0010"
down_revision = "20260310_0009"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(idx.get("name") == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists("salon_link_requests"):
        op.create_table(
            "salon_link_requests",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("requester_provider_id", sa.String(36), nullable=False),
            sa.Column("salon_provider_id", sa.String(36), nullable=False),
            sa.Column("status", sa.String(20), server_default=sa.text("'pending'"), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("review_note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["requester_provider_id"], ["providers.provider_id"]),
            sa.ForeignKeyConstraint(["salon_provider_id"], ["providers.provider_id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if _table_exists("salon_link_requests") and not _index_exists(
        "salon_link_requests", "ix_salon_link_unique_pending"
    ):
        op.create_index(
            "ix_salon_link_unique_pending",
            "salon_link_requests",
            ["requester_provider_id", "salon_provider_id"],
            unique=False,
        )


def downgrade() -> None:
    if _table_exists("salon_link_requests"):
        if _index_exists("salon_link_requests", "ix_salon_link_unique_pending"):
            op.drop_index("ix_salon_link_unique_pending", table_name="salon_link_requests")
        op.drop_table("salon_link_requests")
