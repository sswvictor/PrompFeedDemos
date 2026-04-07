"""provider incident reports from customers

Revision ID: 20260316_0026
Revises: 20260316_0025
Create Date: 2026-03-16 13:35:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260316_0026"
down_revision: Union[str, None] = "20260316_0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    try:
        indexes = inspector.get_indexes(table_name)
    except Exception:
        return False
    return any(idx.get("name") == index_name for idx in indexes)


def upgrade() -> None:
    table = "provider_incident_reports"
    if not _table_exists(table):
        op.create_table(
            table,
            sa.Column("report_id", sa.String(length=36), primary_key=True),
            sa.Column("booking_id", sa.String(length=36), sa.ForeignKey("bookings.booking_id"), nullable=False),
            sa.Column("provider_id", sa.String(length=36), sa.ForeignKey("providers.provider_id"), nullable=False),
            sa.Column("customer_id", sa.String(length=36), sa.ForeignKey("customers.customer_id"), nullable=False),
            sa.Column("report_type", sa.String(length=40), nullable=False),
            sa.Column("severity", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'open'")),
            sa.Column("action_taken", sa.String(length=20), nullable=False, server_default=sa.text("'none'")),
            sa.Column("admin_notes", sa.Text(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("resolved_by", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                "booking_id",
                "customer_id",
                "report_type",
                name="uq_provider_incident_report_booking_customer_type",
            ),
        )

    if _table_exists(table) and not _index_exists(table, "ix_provider_incident_reports_status_created"):
        op.create_index(
            "ix_provider_incident_reports_status_created",
            table,
            ["status", "created_at"],
        )


def downgrade() -> None:
    table = "provider_incident_reports"
    if _table_exists(table):
        if _index_exists(table, "ix_provider_incident_reports_status_created"):
            op.drop_index("ix_provider_incident_reports_status_created", table_name=table)
        op.drop_table(table)
