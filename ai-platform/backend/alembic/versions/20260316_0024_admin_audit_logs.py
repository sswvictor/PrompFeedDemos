"""admin_audit_logs table

Revision ID: 20260316_0024
Revises: 20260316_0023
Create Date: 2026-03-16 23:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260316_0024"
down_revision: Union[str, None] = "20260316_0023"
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
    if not _table_exists("admin_audit_logs"):
        op.create_table(
            "admin_audit_logs",
            sa.Column("log_id", sa.String(36), primary_key=True),
            sa.Column("admin_actor", sa.String(255), nullable=True),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("entity_type", sa.String(50), nullable=False),
            sa.Column("entity_id", sa.String(64), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("before_json", sa.Text(), nullable=True),
            sa.Column("after_json", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    if not _index_exists("admin_audit_logs", "ix_admin_audit_entity"):
        op.create_index(
            "ix_admin_audit_entity",
            "admin_audit_logs",
            ["entity_type", "entity_id", "created_at"],
        )

    if not _index_exists("admin_audit_logs", "ix_admin_audit_action"):
        op.create_index(
            "ix_admin_audit_action",
            "admin_audit_logs",
            ["action", "created_at"],
        )


def downgrade() -> None:
    if _table_exists("admin_audit_logs"):
        if _index_exists("admin_audit_logs", "ix_admin_audit_action"):
            op.drop_index("ix_admin_audit_action", table_name="admin_audit_logs")
        if _index_exists("admin_audit_logs", "ix_admin_audit_entity"):
            op.drop_index("ix_admin_audit_entity", table_name="admin_audit_logs")
        op.drop_table("admin_audit_logs")
