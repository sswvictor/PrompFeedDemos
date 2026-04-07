"""loyalty_events table

Revision ID: 20260316_0023
Revises: 20260316_0022
Create Date: 2026-03-16 22:40:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260316_0023"
down_revision: Union[str, None] = "20260316_0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    indexes = inspector.get_indexes(table_name)
    return any(idx.get("name") == index_name for idx in indexes)


def upgrade() -> None:
    if not _table_exists("loyalty_events"):
        op.create_table(
            "loyalty_events",
            sa.Column("event_id", sa.String(36), primary_key=True),
            sa.Column("actor_type", sa.String(16), nullable=False),
            sa.Column("actor_id", sa.String(36), nullable=False),
            sa.Column("event_type", sa.String(64), nullable=False),
            sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("source", sa.String(64), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("unique_event_key", sa.String(191), nullable=True, unique=True),
            sa.Column("occurred_at", sa.DateTime(), nullable=False),
        )

    if not _index_exists("loyalty_events", "ix_loyalty_actor_time"):
        op.create_index(
            "ix_loyalty_actor_time",
            "loyalty_events",
            ["actor_type", "actor_id", "occurred_at"],
        )

    if not _index_exists("loyalty_events", "ix_loyalty_event_type"):
        op.create_index(
            "ix_loyalty_event_type",
            "loyalty_events",
            ["event_type"],
        )


def downgrade() -> None:
    if _table_exists("loyalty_events"):
        if _index_exists("loyalty_events", "ix_loyalty_event_type"):
            op.drop_index("ix_loyalty_event_type", table_name="loyalty_events")
        if _index_exists("loyalty_events", "ix_loyalty_actor_time"):
            op.drop_index("ix_loyalty_actor_time", table_name="loyalty_events")
        op.drop_table("loyalty_events")
