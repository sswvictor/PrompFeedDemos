"""add structured conversation states

Revision ID: 20260319_0030
Revises: 20260318_0029
Create Date: 2026-03-19 16:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260319_0030"
down_revision: Union[str, None] = "20260318_0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tbl(table: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table in inspector.get_table_names()


def _idx(table: str, index: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(ix["name"] == index for ix in inspector.get_indexes(table))


def upgrade() -> None:
    if not _tbl("conversation_states"):
        op.create_table(
            "conversation_states",
            sa.Column("state_id", sa.String(length=36), nullable=False),
            sa.Column("conversation_id", sa.String(length=36), nullable=False),
            sa.Column("mode", sa.String(length=20), nullable=False),
            sa.Column("provider_id", sa.String(length=36), nullable=True),
            sa.Column("selected_provider_id", sa.String(length=36), nullable=True),
            sa.Column("selected_service_id", sa.String(length=36), nullable=True),
            sa.Column("selected_service_name", sa.String(length=255), nullable=True),
            sa.Column("selected_date", sa.String(length=10), nullable=True),
            sa.Column("selected_time", sa.String(length=5), nullable=True),
            sa.Column("contact_requested_at", sa.DateTime(), nullable=True),
            sa.Column("contact_name", sa.String(length=255), nullable=True),
            sa.Column("contact_email", sa.String(length=255), nullable=True),
            sa.Column("contact_received_at", sa.DateTime(), nullable=True),
            sa.Column("booking_status", sa.String(length=20), nullable=False, server_default="none"),
            sa.Column("handoff_status", sa.String(length=20), nullable=False, server_default="none"),
            sa.Column("last_ai_action", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.conversation_id"]),
            sa.PrimaryKeyConstraint("state_id"),
            sa.UniqueConstraint("conversation_id", name="uq_conversation_states_conversation_id"),
        )

    if not _idx("conversation_states", "ix_conversation_states_conversation_id"):
        op.create_index("ix_conversation_states_conversation_id", "conversation_states", ["conversation_id"], unique=False)
    if not _idx("conversation_states", "ix_conversation_states_provider_id"):
        op.create_index("ix_conversation_states_provider_id", "conversation_states", ["provider_id"], unique=False)
    if not _idx("conversation_states", "ix_conversation_states_selected_provider_id"):
        op.create_index("ix_conversation_states_selected_provider_id", "conversation_states", ["selected_provider_id"], unique=False)


def downgrade() -> None:
    if _tbl("conversation_states"):
        op.drop_table("conversation_states")
