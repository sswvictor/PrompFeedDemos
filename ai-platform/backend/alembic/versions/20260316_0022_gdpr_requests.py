"""gdpr_requests table

Revision ID: 20260316_0022
Revises: 20260316_0021
Create Date: 2026-03-16 20:00:00

Stores customer GDPR/data rights requests (export, deletion, etc.).
Admins handle requests manually; this table is the intake queue.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260316_0022"
down_revision: Union[str, None] = "20260316_0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("gdpr_requests"):
        op.create_table(
            "gdpr_requests",
            sa.Column("request_id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.user_id"), nullable=False),
            # "export" | "deletion"
            sa.Column("request_type", sa.String(32), nullable=False),
            # "pending" | "in_progress" | "completed" | "rejected"
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("notes", sa.Text(), nullable=True),          # user's optional message
            sa.Column("admin_notes", sa.Text(), nullable=True),    # internal ops notes
            sa.Column("requested_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_gdpr_requests_user_id", "gdpr_requests", ["user_id"])
        op.create_index("ix_gdpr_requests_status", "gdpr_requests", ["status"])


def downgrade() -> None:
    if _table_exists("gdpr_requests"):
        op.drop_index("ix_gdpr_requests_status", table_name="gdpr_requests")
        op.drop_index("ix_gdpr_requests_user_id", table_name="gdpr_requests")
        op.drop_table("gdpr_requests")
