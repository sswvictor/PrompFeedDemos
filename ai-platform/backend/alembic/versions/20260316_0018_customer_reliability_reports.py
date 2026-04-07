"""customer reliability reports

Revision ID: 20260316_0018
Revises: 20260315_0017
Create Date: 2026-03-16 10:40:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260316_0018"
down_revision: Union[str, None] = "20260315_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return index_name in [idx["name"] for idx in inspector.get_indexes(table_name)]


def upgrade() -> None:
    if not _table_exists("customer_reliability_reports"):
        op.create_table(
            "customer_reliability_reports",
            sa.Column("report_id", sa.String(length=36), primary_key=True),
            sa.Column("provider_id", sa.String(length=36), sa.ForeignKey("providers.provider_id"), nullable=False),
            sa.Column("customer_id", sa.String(length=36), sa.ForeignKey("customers.customer_id"), nullable=False),
            sa.Column("booking_id", sa.String(length=36), sa.ForeignKey("bookings.booking_id"), nullable=True),
            sa.Column("category", sa.String(length=40), nullable=False),
            sa.Column("severity", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                "provider_id",
                "customer_id",
                "booking_id",
                "category",
                name="uq_customer_reliability_report_booking_category",
            ),
        )

    if _table_exists("customer_reliability_reports") and not _index_exists(
        "customer_reliability_reports", "ix_customer_reliability_reports_customer_created"
    ):
        op.create_index(
            "ix_customer_reliability_reports_customer_created",
            "customer_reliability_reports",
            ["customer_id", "created_at"],
        )


def downgrade() -> None:
    if _table_exists("customer_reliability_reports"):
        if _index_exists("customer_reliability_reports", "ix_customer_reliability_reports_customer_created"):
            op.drop_index("ix_customer_reliability_reports_customer_created", table_name="customer_reliability_reports")
        op.drop_table("customer_reliability_reports")
