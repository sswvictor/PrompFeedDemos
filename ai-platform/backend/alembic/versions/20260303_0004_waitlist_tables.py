"""Waitlist tables - entries + offers

Creates:
  - waitlist_entries  - customer queue positions with day/hour preferences
  - waitlist_offers   - time-limited offers sent when slots open (10-min expiry)

Revision ID: 20260303_0004
Revises: 20260226_0003
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260303_0004"
down_revision: Union[str, None] = "20260226_0003"
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
    # waitlist_entries
    if not _table_exists("waitlist_entries"):
        op.create_table(
            "waitlist_entries",
            sa.Column("entry_id", sa.String(36), primary_key=True),
            sa.Column(
                "provider_id",
                sa.String(36),
                sa.ForeignKey("providers.provider_id"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.String(36),
                sa.ForeignKey("users.user_id"),
                nullable=True,
            ),
            sa.Column(
                "customer_id",
                sa.String(36),
                sa.ForeignKey("customers.customer_id"),
                nullable=True,
            ),
            sa.Column("customer_email", sa.String(255), nullable=False),
            sa.Column("customer_name", sa.String(255), nullable=False),
            sa.Column(
                "service_id",
                sa.String(36),
                sa.ForeignKey("services.service_id"),
                nullable=True,
            ),
            sa.Column("preferred_days", sa.Text, nullable=False),
            sa.Column("preferred_earliest_hour", sa.Integer, nullable=False),
            sa.Column("preferred_latest_hour", sa.Integer, nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("updated_at", sa.DateTime, nullable=False),
        )

    if not _index_exists("waitlist_entries", "ix_waitlist_entries_provider_id"):
        op.create_index(
            "ix_waitlist_entries_provider_id",
            "waitlist_entries",
            ["provider_id"],
        )
    if not _index_exists("waitlist_entries", "ix_waitlist_entries_provider_status"):
        op.create_index(
            "ix_waitlist_entries_provider_status",
            "waitlist_entries",
            ["provider_id", "status"],
        )

    # Partial unique index: only one active entry per (provider, email).
    # PostgreSQL partial unique index for active entries only.
    bind = op.get_bind()
    if (
        bind
        and bind.dialect.name == "postgresql"
        and not _index_exists("waitlist_entries", "ix_waitlist_entries_active_unique")
    ):
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX ix_waitlist_entries_active_unique "
                "ON waitlist_entries (provider_id, customer_email) "
                "WHERE status = 'active'"
            )
        )

    # waitlist_offers
    if not _table_exists("waitlist_offers"):
        op.create_table(
            "waitlist_offers",
            sa.Column("offer_id", sa.String(36), primary_key=True),
            sa.Column(
                "entry_id",
                sa.String(36),
                sa.ForeignKey("waitlist_entries.entry_id"),
                nullable=False,
            ),
            sa.Column(
                "provider_id",
                sa.String(36),
                sa.ForeignKey("providers.provider_id"),
                nullable=False,
            ),
            # Security: 64-char hex token required to accept/decline
            sa.Column("offer_secret", sa.String(64), nullable=False),
            sa.Column("slot_start", sa.DateTime, nullable=False),
            sa.Column("slot_end", sa.DateTime, nullable=False),
            sa.Column("expires_at", sa.DateTime, nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )

    if not _index_exists("waitlist_offers", "ix_waitlist_offers_entry_id"):
        op.create_index(
            "ix_waitlist_offers_entry_id",
            "waitlist_offers",
            ["entry_id"],
        )
    if not _index_exists("waitlist_offers", "ix_waitlist_offers_status_expires"):
        op.create_index(
            "ix_waitlist_offers_status_expires",
            "waitlist_offers",
            ["status", "expires_at"],
        )
    if not _index_exists("waitlist_offers", "ix_waitlist_offers_slot_dedup"):
        # Idempotency: fast lookup for existing pending offers on same slot
        op.create_index(
            "ix_waitlist_offers_slot_dedup",
            "waitlist_offers",
            ["provider_id", "slot_start", "slot_end", "status"],
        )


def downgrade() -> None:
    if _table_exists("waitlist_offers"):
        if _index_exists("waitlist_offers", "ix_waitlist_offers_slot_dedup"):
            op.drop_index("ix_waitlist_offers_slot_dedup", table_name="waitlist_offers")
        if _index_exists("waitlist_offers", "ix_waitlist_offers_status_expires"):
            op.drop_index("ix_waitlist_offers_status_expires", table_name="waitlist_offers")
        if _index_exists("waitlist_offers", "ix_waitlist_offers_entry_id"):
            op.drop_index("ix_waitlist_offers_entry_id", table_name="waitlist_offers")
        op.drop_table("waitlist_offers")

    bind = op.get_bind()
    if _table_exists("waitlist_entries"):
        if (
            bind
            and bind.dialect.name == "postgresql"
            and _index_exists("waitlist_entries", "ix_waitlist_entries_active_unique")
        ):
            op.drop_index("ix_waitlist_entries_active_unique", table_name="waitlist_entries")
        if _index_exists("waitlist_entries", "ix_waitlist_entries_provider_status"):
            op.drop_index("ix_waitlist_entries_provider_status", table_name="waitlist_entries")
        if _index_exists("waitlist_entries", "ix_waitlist_entries_provider_id"):
            op.drop_index("ix_waitlist_entries_provider_id", table_name="waitlist_entries")
        op.drop_table("waitlist_entries")
