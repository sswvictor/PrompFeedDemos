"""customer reliability admin handling fields

Revision ID: 20260316_0025
Revises: 20260316_0024
Create Date: 2026-03-16 13:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260316_0025"
down_revision: Union[str, None] = "20260316_0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    try:
        cols = inspector.get_columns(table_name)
    except Exception:
        return False
    return any(col.get("name") == column_name for col in cols)


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    try:
        indexes = inspector.get_indexes(table_name)
    except Exception:
        return False
    return any(idx.get("name") == index_name for idx in indexes)


def upgrade() -> None:
    table = "customer_reliability_reports"
    if not _table_exists(table):
        return

    if not _column_exists(table, "admin_status"):
        op.add_column(
            table,
            sa.Column("admin_status", sa.String(length=20), nullable=False, server_default=sa.text("'open'")),
        )
    if not _column_exists(table, "admin_action_taken"):
        op.add_column(
            table,
            sa.Column("admin_action_taken", sa.String(length=20), nullable=False, server_default=sa.text("'none'")),
        )
    if not _column_exists(table, "admin_notes"):
        op.add_column(table, sa.Column("admin_notes", sa.Text(), nullable=True))
    if not _column_exists(table, "admin_resolved_at"):
        op.add_column(table, sa.Column("admin_resolved_at", sa.DateTime(), nullable=True))
    if not _column_exists(table, "admin_resolved_by"):
        op.add_column(table, sa.Column("admin_resolved_by", sa.String(length=255), nullable=True))

    if not _index_exists(table, "ix_customer_reliability_reports_admin_status"):
        op.create_index(
            "ix_customer_reliability_reports_admin_status",
            table,
            ["admin_status", "created_at"],
        )


def downgrade() -> None:
    table = "customer_reliability_reports"
    if not _table_exists(table):
        return

    if _index_exists(table, "ix_customer_reliability_reports_admin_status"):
        op.drop_index("ix_customer_reliability_reports_admin_status", table_name=table)

    if _column_exists(table, "admin_resolved_by"):
        op.drop_column(table, "admin_resolved_by")
    if _column_exists(table, "admin_resolved_at"):
        op.drop_column(table, "admin_resolved_at")
    if _column_exists(table, "admin_notes"):
        op.drop_column(table, "admin_notes")
    if _column_exists(table, "admin_action_taken"):
        op.drop_column(table, "admin_action_taken")
    if _column_exists(table, "admin_status"):
        op.drop_column(table, "admin_status")
