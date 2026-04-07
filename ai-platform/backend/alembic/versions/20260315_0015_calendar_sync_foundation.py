"""calendar sync foundation tables

Revision ID: 20260315_0015
Revises: 20260315_0014
Create Date: 2026-03-15 23:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260315_0015"
down_revision: Union[str, None] = "20260315_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("provider_calendar_connections"):
        op.create_table(
            "provider_calendar_connections",
            sa.Column("connection_id", sa.String(length=36), primary_key=True),
            sa.Column("provider_id", sa.String(length=36), sa.ForeignKey("providers.provider_id"), nullable=False),
            sa.Column("connector", sa.String(length=20), nullable=False),
            sa.Column("external_account_id", sa.String(length=255), nullable=True),
            sa.Column("external_calendar_id", sa.String(length=255), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=True),
            sa.Column("access_token_encrypted", sa.Text(), nullable=True),
            sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
            sa.Column("token_expires_at", sa.DateTime(), nullable=True),
            sa.Column("webhook_channel_id", sa.String(length=255), nullable=True),
            sa.Column("webhook_resource_id", sa.String(length=255), nullable=True),
            sa.Column("sync_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("sync_direction", sa.String(length=20), nullable=False, server_default=sa.text("'read_write'")),
            sa.Column("last_sync_cursor", sa.Text(), nullable=True),
            sa.Column("last_synced_at", sa.DateTime(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("provider_id", "connector", "external_calendar_id", name="uq_provider_connector_calendar"),
        )

    if not _table_exists("external_calendar_events"):
        op.create_table(
            "external_calendar_events",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("provider_id", sa.String(length=36), sa.ForeignKey("providers.provider_id"), nullable=False),
            sa.Column(
                "connection_id",
                sa.String(length=36),
                sa.ForeignKey("provider_calendar_connections.connection_id"),
                nullable=False,
            ),
            sa.Column("booking_id", sa.String(length=36), sa.ForeignKey("bookings.booking_id"), nullable=True),
            sa.Column("external_event_id", sa.String(length=255), nullable=False),
            sa.Column("external_etag", sa.String(length=255), nullable=True),
            sa.Column("start_at", sa.DateTime(), nullable=False),
            sa.Column("end_at", sa.DateTime(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
            sa.Column("source", sa.String(length=20), nullable=False, server_default=sa.text("'fixme_push'")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("connection_id", "external_event_id", name="uq_ext_event_connection"),
            sa.UniqueConstraint("connection_id", "booking_id", name="uq_ext_event_booking"),
        )

    if not _table_exists("sync_jobs"):
        op.create_table(
            "sync_jobs",
            sa.Column("job_id", sa.String(length=36), primary_key=True),
            sa.Column("provider_id", sa.String(length=36), sa.ForeignKey("providers.provider_id"), nullable=False),
            sa.Column(
                "connection_id",
                sa.String(length=36),
                sa.ForeignKey("provider_calendar_connections.connection_id"),
                nullable=True,
            ),
            sa.Column("booking_id", sa.String(length=36), sa.ForeignKey("bookings.booking_id"), nullable=True),
            sa.Column("job_type", sa.String(length=40), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'queued'")),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("next_run_at", sa.DateTime(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("idempotency_key", sa.String(length=100), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("idempotency_key", name="uq_sync_job_idempotency"),
        )


def downgrade() -> None:
    if _table_exists("sync_jobs"):
        op.drop_table("sync_jobs")
    if _table_exists("external_calendar_events"):
        op.drop_table("external_calendar_events")
    if _table_exists("provider_calendar_connections"):
        op.drop_table("provider_calendar_connections")