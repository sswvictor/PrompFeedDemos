"""add search_events and discovery_events tables for merkle event feeds

Revision ID: 20260311_2305
Revises: 40e880fc5b26
Create Date: 2026-03-11 23:05:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260311_2305"
down_revision: Union[str, None] = "40e880fc5b26"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(ix["name"] == index_name for ix in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists("search_events"):
        op.create_table(
            "search_events",
            sa.Column("search_id", sa.String(length=36), nullable=False),
            sa.Column("query_category", sa.String(length=50), nullable=True),
            sa.Column("city", sa.String(length=100), nullable=True),
            sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("result_count_band", sa.String(length=20), nullable=False, server_default="none"),
            sa.Column("price_preference", sa.Integer(), nullable=True),
            sa.Column("converted_to_booking", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("platform", sa.String(length=30), nullable=False, server_default="prompt_feed"),
            sa.Column("searched_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("search_id"),
        )
        op.create_index("ix_search_events_searched_at", "search_events", ["searched_at"], unique=False)
        op.create_index("ix_search_events_query_category", "search_events", ["query_category"], unique=False)
        op.create_index("ix_search_events_city", "search_events", ["city"], unique=False)

    if not _table_exists("discovery_events"):
        op.create_table(
            "discovery_events",
            sa.Column("discovery_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=True),
            sa.Column("conversation_id", sa.String(length=36), nullable=True),
            sa.Column("service_category", sa.String(length=50), nullable=True),
            sa.Column("city", sa.String(length=100), nullable=True),
            sa.Column("provider_found", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("availability_found", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("converted_to_booking", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("channel", sa.String(length=30), nullable=False),
            sa.Column("discovered_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.conversation_id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
            sa.PrimaryKeyConstraint("discovery_id"),
        )
        op.create_index("ix_discovery_events_discovered_at", "discovery_events", ["discovered_at"], unique=False)
        op.create_index("ix_discovery_events_user_id", "discovery_events", ["user_id"], unique=False)
        op.create_index("ix_discovery_events_channel", "discovery_events", ["channel"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_discovery_events_channel", table_name="discovery_events")
    op.drop_index("ix_discovery_events_user_id", table_name="discovery_events")
    op.drop_index("ix_discovery_events_discovered_at", table_name="discovery_events")
    op.drop_table("discovery_events")

    op.drop_index("ix_search_events_city", table_name="search_events")
    op.drop_index("ix_search_events_query_category", table_name="search_events")
    op.drop_index("ix_search_events_searched_at", table_name="search_events")
    op.drop_table("search_events")
