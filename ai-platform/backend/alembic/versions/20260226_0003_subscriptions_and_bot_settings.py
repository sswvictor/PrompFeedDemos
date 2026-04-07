"""Subscriptions, plans, and provider bot settings.

Revision ID: 20260226_0003
Revises: 20260224_0002
"""

import json
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260226_0003"
down_revision: Union[str, None] = "20260224_0002"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _table_exists(name: str) -> bool:
    return _inspector().has_table(name)


def _index_exists(table: str, index_name: str) -> bool:
    return any(i["name"] == index_name for i in _inspector().get_indexes(table))


def _plan_exists(plan_id: str) -> bool:
    row = op.get_bind().execute(
        sa.text("SELECT plan_id FROM plans WHERE plan_id = :pid LIMIT 1"),
        {"pid": plan_id},
    ).first()
    return row is not None


def upgrade() -> None:
    # plans
    if not _table_exists("plans"):
        op.create_table(
            "plans",
            sa.Column("plan_id", sa.String(20), primary_key=True),
            sa.Column("name", sa.String(50), nullable=False),
            sa.Column("price_sek", sa.Integer, nullable=False, server_default="0"),
            sa.Column("stripe_price_id", sa.String(100), nullable=True),
            sa.Column("features_json", sa.Text, nullable=False, server_default="[]"),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )

    if _table_exists("plans") and not _plan_exists("free"):
        op.get_bind().execute(
            sa.text(
                """
                INSERT INTO plans (plan_id, name, price_sek, stripe_price_id, features_json, is_active, created_at)
                VALUES (:plan_id, :name, :price_sek, :stripe_price_id, :features_json, :is_active, CURRENT_TIMESTAMP)
                """
            ),
            {
                "plan_id": "free",
                "name": "Free",
                "price_sek": 0,
                "stripe_price_id": None,
                "features_json": json.dumps([
                    "ai_booking_bot",
                    "booking_management",
                    "instagram_dm",
                    "web_booking_link",
                ]),
                "is_active": True,
            },
        )

    if _table_exists("plans") and not _plan_exists("pro"):
        op.get_bind().execute(
            sa.text(
                """
                INSERT INTO plans (plan_id, name, price_sek, stripe_price_id, features_json, is_active, created_at)
                VALUES (:plan_id, :name, :price_sek, :stripe_price_id, :features_json, :is_active, CURRENT_TIMESTAMP)
                """
            ),
            {
                "plan_id": "pro",
                "name": "Pro",
                "price_sek": 299,
                "stripe_price_id": None,
                "features_json": json.dumps([
                    "ai_booking_bot",
                    "booking_management",
                    "instagram_dm",
                    "web_booking_link",
                    "bot_personalization",
                    "custom_welcome_message",
                    "auto_confirm_toggle",
                    "out_of_hours_control",
                    "booking_window_control",
                    "priority_support",
                ]),
                "is_active": True,
            },
        )

    # subscriptions
    if not _table_exists("subscriptions"):
        op.create_table(
            "subscriptions",
            sa.Column("subscription_id", sa.String(36), primary_key=True),
            sa.Column("provider_id", sa.String(36), sa.ForeignKey("providers.provider_id"), nullable=False),
            sa.Column("plan_id", sa.String(20), sa.ForeignKey("plans.plan_id"), nullable=False, server_default="free"),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column("stripe_customer_id", sa.String(100), nullable=True),
            sa.Column("stripe_subscription_id", sa.String(100), nullable=True),
            sa.Column("current_period_start", sa.DateTime, nullable=True),
            sa.Column("current_period_end", sa.DateTime, nullable=True),
            sa.Column("cancelled_at", sa.DateTime, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("updated_at", sa.DateTime, nullable=False),
            sa.UniqueConstraint("provider_id", name="uq_subscriptions_provider"),
        )

    if _table_exists("subscriptions") and not _index_exists("subscriptions", "ix_subscriptions_stripe_subscription_id"):
        op.create_index("ix_subscriptions_stripe_subscription_id", "subscriptions", ["stripe_subscription_id"])

    if _table_exists("subscriptions") and not _index_exists("subscriptions", "ix_subscriptions_stripe_customer_id"):
        op.create_index("ix_subscriptions_stripe_customer_id", "subscriptions", ["stripe_customer_id"])

    # provider_bot_settings
    if not _table_exists("provider_bot_settings"):
        op.create_table(
            "provider_bot_settings",
            sa.Column("settings_id", sa.String(36), primary_key=True),
            sa.Column("provider_id", sa.String(36), sa.ForeignKey("providers.provider_id"), nullable=False),
            sa.Column("bot_name", sa.String(50), nullable=True),
            sa.Column("tone", sa.String(20), nullable=False, server_default="friendly"),
            sa.Column("language", sa.String(10), nullable=False, server_default="auto"),
            sa.Column("custom_welcome_message", sa.Text, nullable=True),
            sa.Column("auto_confirm_bookings", sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column("out_of_hours_behavior", sa.String(20), nullable=False, server_default="show_hours"),
            sa.Column("max_advance_booking_days", sa.Integer, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("updated_at", sa.DateTime, nullable=False),
            sa.UniqueConstraint("provider_id", name="uq_bot_settings_provider"),
        )


def downgrade() -> None:
    if _table_exists("provider_bot_settings"):
        op.drop_table("provider_bot_settings")

    if _table_exists("subscriptions"):
        if _index_exists("subscriptions", "ix_subscriptions_stripe_customer_id"):
            op.drop_index("ix_subscriptions_stripe_customer_id", table_name="subscriptions")
        if _index_exists("subscriptions", "ix_subscriptions_stripe_subscription_id"):
            op.drop_index("ix_subscriptions_stripe_subscription_id", table_name="subscriptions")
        op.drop_table("subscriptions")

    if _table_exists("plans"):
        op.drop_table("plans")

