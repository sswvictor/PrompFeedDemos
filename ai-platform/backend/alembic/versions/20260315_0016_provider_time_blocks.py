"""provider intraday time blocks

Revision ID: 20260315_0016
Revises: 20260315_0015
Create Date: 2026-03-15 23:55:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260315_0016"
down_revision: Union[str, None] = "20260315_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("provider_time_blocks"):
        return

    op.create_table(
        "provider_time_blocks",
        sa.Column("block_id", sa.String(length=36), primary_key=True),
        sa.Column("provider_id", sa.String(length=36), sa.ForeignKey("providers.provider_id"), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default=sa.text("'private'")),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_provider_time_blocks_provider_start", "provider_time_blocks", ["provider_id", "start_at"])


def downgrade() -> None:
    if not _table_exists("provider_time_blocks"):
        return

    op.drop_index("ix_provider_time_blocks_provider_start", table_name="provider_time_blocks")
    op.drop_table("provider_time_blocks")
