"""Catch-up migration: add all columns/tables that were in the ig-stats branch
but were never applied to Railway DB because it skipped the branch.

The Railway DB went 0010→0011 directly (before the branch was created).
When the branches were merged (0028), Alembic assumed the branch was already
in the ancestors of 0016 and skipped re-applying it.

This migration adds every column and table idempotently (IF NOT EXISTS guards).
Safe to run on DBs that already have these objects — it becomes a no-op.

Revision ID: 20260318_0029
Revises: 20260317_0028
Create Date: 2026-03-18 08:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260318_0029"
down_revision: Union[str, None] = "20260317_0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col(table: str, col: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return col in {c["name"] for c in inspector.get_columns(table)}


def _tbl(table: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table in inspector.get_table_names()


def _idx(table: str, index: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(ix["name"] == index for ix in inspector.get_indexes(table))


def upgrade() -> None:
    # ── providers: Instagram stats (partial-run columns never in a migration) ──
    provider_ig_cols = [
        ("ig_followers_count",   sa.Column("ig_followers_count",   sa.Integer(),      nullable=True)),
        ("ig_following_count",   sa.Column("ig_following_count",   sa.Integer(),      nullable=True)),
        ("ig_profile_picture_url", sa.Column("ig_profile_picture_url", sa.String(500), nullable=True)),
        ("ig_stats_synced_at",   sa.Column("ig_stats_synced_at",   sa.DateTime(),     nullable=True)),
    ]
    for col_name, col_def in provider_ig_cols:
        if not _col("providers", col_name):
            op.add_column("providers", col_def)

    # ── providers: Verification & follower count (from branch 47f87e7beba9) ──
    provider_verify_cols = [
        ("fixmeapp_followers_count", sa.Column("fixmeapp_followers_count", sa.Integer(),    nullable=False, server_default="0")),
        ("is_verified",              sa.Column("is_verified",              sa.Boolean(),    nullable=False, server_default="0")),
        ("verified_at",              sa.Column("verified_at",              sa.DateTime(),   nullable=True)),
        ("verified_country",         sa.Column("verified_country",         sa.String(2),    nullable=True)),
        ("verification_source",      sa.Column("verification_source",      sa.String(32),   nullable=True)),
    ]
    for col_name, col_def in provider_verify_cols:
        if not _col("providers", col_name):
            op.add_column("providers", col_def)

    # ── providers: Push token (from 0027 — should already be there, guard anyway) ──
    if not _col("providers", "push_token"):
        op.add_column("providers", sa.Column("push_token", sa.String(255), nullable=True))

    # ── provider_follows table (from branch 40e880fc5b26) ──
    if not _tbl("provider_follows"):
        op.create_table(
            "provider_follows",
            sa.Column("follow_id",   sa.String(36),  nullable=False),
            sa.Column("customer_id", sa.String(36),  nullable=False),
            sa.Column("provider_id", sa.String(36),  nullable=False),
            sa.Column("created_at",  sa.DateTime(),  nullable=False),
            sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
            sa.ForeignKeyConstraint(["provider_id"], ["providers.provider_id"]),
            sa.PrimaryKeyConstraint("follow_id"),
            sa.UniqueConstraint("customer_id", "provider_id", name="uq_provider_follow"),
        )
        op.create_index("ix_provider_follows_customer_id", "provider_follows", ["customer_id"])
        op.create_index("ix_provider_follows_provider_id", "provider_follows", ["provider_id"])

    # ── search_events table (from branch 20260311_2305) ──
    if not _tbl("search_events"):
        op.create_table(
            "search_events",
            sa.Column("search_id",          sa.String(36),  nullable=False),
            sa.Column("query_category",     sa.String(50),  nullable=True),
            sa.Column("city",               sa.String(100), nullable=True),
            sa.Column("result_count",       sa.Integer(),   nullable=False, server_default="0"),
            sa.Column("result_count_band",  sa.String(20),  nullable=False, server_default="none"),
            sa.Column("price_preference",   sa.Integer(),   nullable=True),
            sa.Column("converted_to_booking", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("platform",           sa.String(30),  nullable=False, server_default="prompt_feed"),
            sa.Column("searched_at",        sa.DateTime(),  nullable=False),
            sa.PrimaryKeyConstraint("search_id"),
        )
        if not _idx("search_events", "ix_search_events_searched_at"):
            op.create_index("ix_search_events_searched_at",    "search_events", ["searched_at"])
        if not _idx("search_events", "ix_search_events_query_category"):
            op.create_index("ix_search_events_query_category", "search_events", ["query_category"])
        if not _idx("search_events", "ix_search_events_city"):
            op.create_index("ix_search_events_city",           "search_events", ["city"])

    # ── discovery_events table (from branch 20260311_2305) ──
    if not _tbl("discovery_events"):
        op.create_table(
            "discovery_events",
            sa.Column("discovery_id",         sa.String(36),  nullable=False),
            sa.Column("user_id",              sa.String(36),  nullable=True),
            sa.Column("conversation_id",      sa.String(36),  nullable=True),
            sa.Column("service_category",     sa.String(50),  nullable=True),
            sa.Column("city",                 sa.String(100), nullable=True),
            sa.Column("provider_found",       sa.Boolean(),   nullable=False, server_default=sa.text("0")),
            sa.Column("availability_found",   sa.Boolean(),   nullable=False, server_default=sa.text("0")),
            sa.Column("converted_to_booking", sa.Boolean(),   nullable=False, server_default=sa.text("0")),
            sa.Column("channel",              sa.String(30),  nullable=False),
            sa.Column("discovered_at",        sa.DateTime(),  nullable=False),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.conversation_id"]),
            sa.ForeignKeyConstraint(["user_id"],         ["users.user_id"]),
            sa.PrimaryKeyConstraint("discovery_id"),
        )
        if not _idx("discovery_events", "ix_discovery_events_discovered_at"):
            op.create_index("ix_discovery_events_discovered_at", "discovery_events", ["discovered_at"])
        if not _idx("discovery_events", "ix_discovery_events_user_id"):
            op.create_index("ix_discovery_events_user_id",       "discovery_events", ["user_id"])
        if not _idx("discovery_events", "ix_discovery_events_channel"):
            op.create_index("ix_discovery_events_channel",       "discovery_events", ["channel"])


def downgrade() -> None:
    # Tables
    for tbl in ("discovery_events", "search_events", "provider_follows"):
        if _tbl(tbl):
            op.drop_table(tbl)

    # Provider columns — only drop if we added them (check existence first)
    cols_to_drop = [
        "push_token", "verification_source", "verified_country", "verified_at",
        "is_verified", "fixmeapp_followers_count",
        "ig_stats_synced_at", "ig_profile_picture_url", "ig_following_count", "ig_followers_count",
    ]
    for col in cols_to_drop:
        if _col("providers", col):
            op.drop_column("providers", col)
