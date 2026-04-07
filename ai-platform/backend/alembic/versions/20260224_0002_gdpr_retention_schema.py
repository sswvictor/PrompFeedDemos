"""GDPR retention schema: consent_records, data_retention_log, retention columns.

Revision ID: 20260224_0002
Revises: 20260224_0001
Create Date: 2026-02-24
"""
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260224_0002"
down_revision: Union[str, None] = "20260224_0001"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _table_exists(name: str) -> bool:
    return _inspector().has_table(name)


def _column_exists(table: str, col: str) -> bool:
    return any(c["name"] == col for c in _inspector().get_columns(table))


def _index_exists(table: str, index_name: str) -> bool:
    return any(i["name"] == index_name for i in _inspector().get_indexes(table))


def upgrade() -> None:
    # 1) consent_records
    if not _table_exists("consent_records"):
        op.create_table(
            "consent_records",
            sa.Column("consent_id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.user_id"), nullable=False),
            sa.Column("consent_type", sa.String(50), nullable=False),
            sa.Column("given_at", sa.DateTime(), nullable=False),
            sa.Column("channel", sa.String(30), nullable=False),
            sa.Column("version", sa.String(20), nullable=False),
            sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
            sa.Column("withdrawal_reason", sa.String(100), nullable=True),
        )
    if _table_exists("consent_records") and not _index_exists("consent_records", "ix_consent_user_type"):
        op.create_index("ix_consent_user_type", "consent_records", ["user_id", "consent_type"])

    # 2) data_retention_log
    if not _table_exists("data_retention_log"):
        op.create_table(
            "data_retention_log",
            sa.Column("log_id", sa.String(36), primary_key=True),
            sa.Column("action", sa.String(50), nullable=False),
            sa.Column("target_type", sa.String(50), nullable=False),
            sa.Column("target_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("retention_policy", sa.String(50), nullable=False),
            sa.Column("executed_at", sa.DateTime(), nullable=False),
            sa.Column("target_ids", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
        )
    if _table_exists("data_retention_log") and not _index_exists("data_retention_log", "ix_retention_log_executed_at"):
        op.create_index("ix_retention_log_executed_at", "data_retention_log", ["executed_at"])
    if _table_exists("data_retention_log") and not _index_exists("data_retention_log", "ix_retention_log_action"):
        op.create_index("ix_retention_log_action", "data_retention_log", ["action"])

    # 3) conversations columns
    if _table_exists("conversations"):
        with op.batch_alter_table("conversations", schema=None) as batch_op:
            if not _column_exists("conversations", "closed_at"):
                batch_op.add_column(sa.Column("closed_at", sa.DateTime(), nullable=True))
            if not _column_exists("conversations", "signals_extracted_at"):
                batch_op.add_column(sa.Column("signals_extracted_at", sa.DateTime(), nullable=True))
            if not _column_exists("conversations", "scheduled_delete_at"):
                batch_op.add_column(sa.Column("scheduled_delete_at", sa.DateTime(), nullable=True))
            if not _column_exists("conversations", "consent_given"):
                batch_op.add_column(sa.Column("consent_given", sa.Boolean(), nullable=False, server_default=sa.false()))

    # 4) messages column
    if _table_exists("messages") and not _column_exists("messages", "content_deleted_at"):
        with op.batch_alter_table("messages", schema=None) as batch_op:
            batch_op.add_column(sa.Column("content_deleted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Conservative downgrade for local/dev safety.
    # We keep no-op behavior if objects are absent.
    if _table_exists("messages") and _column_exists("messages", "content_deleted_at"):
        with op.batch_alter_table("messages", schema=None) as batch_op:
            batch_op.drop_column("content_deleted_at")

    if _table_exists("conversations"):
        with op.batch_alter_table("conversations", schema=None) as batch_op:
            if _column_exists("conversations", "consent_given"):
                batch_op.drop_column("consent_given")
            if _column_exists("conversations", "scheduled_delete_at"):
                batch_op.drop_column("scheduled_delete_at")
            if _column_exists("conversations", "signals_extracted_at"):
                batch_op.drop_column("signals_extracted_at")
            if _column_exists("conversations", "closed_at"):
                batch_op.drop_column("closed_at")

    if _table_exists("data_retention_log"):
        if _index_exists("data_retention_log", "ix_retention_log_action"):
            op.drop_index("ix_retention_log_action", table_name="data_retention_log")
        if _index_exists("data_retention_log", "ix_retention_log_executed_at"):
            op.drop_index("ix_retention_log_executed_at", table_name="data_retention_log")
        op.drop_table("data_retention_log")

    if _table_exists("consent_records"):
        if _index_exists("consent_records", "ix_consent_user_type"):
            op.drop_index("ix_consent_user_type", table_name="consent_records")
        op.drop_table("consent_records")
