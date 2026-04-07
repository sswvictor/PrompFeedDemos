"""add referral payouts table for provider growth credits

Revision ID: 20260312_0011
Revises: 20260311_2305
Create Date: 2026-03-12 18:35:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import NoSuchTableError


# revision identifiers, used by Alembic.
revision: str = "20260312_0011"
down_revision: Union[str, None] = "20260311_2305"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    try:
        indexes = inspector.get_indexes(table_name)
    except NoSuchTableError:
        return False
    return any((idx.get("name") or "") == index_name for idx in indexes)


def upgrade() -> None:
    if not _table_exists("referral_payouts"):
        op.create_table(
            "referral_payouts",
            sa.Column("payout_id", sa.String(length=36), nullable=False),
            sa.Column("provider_id", sa.String(length=36), nullable=False),
            sa.Column("period_start", sa.DateTime(), nullable=False),
            sa.Column("period_end", sa.DateTime(), nullable=False),
            sa.Column("credits_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("amount_sek", sa.Float(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="SEK"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("auto_processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("external_transfer_id", sa.String(length=120), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["provider_id"], ["providers.provider_id"]),
            sa.PrimaryKeyConstraint("payout_id"),
            sa.UniqueConstraint("provider_id", "period_start", "period_end", name="uq_referral_payout_period"),
        )

    idx_provider = "ix_referral_payouts_provider_id"
    idx_period_start = "ix_referral_payouts_period_start"
    idx_period_end = "ix_referral_payouts_period_end"
    idx_status = "ix_referral_payouts_status"

    if not _index_exists("referral_payouts", idx_provider):
        with op.batch_alter_table("referral_payouts", schema=None) as batch_op:
            batch_op.create_index(idx_provider, ["provider_id"], unique=False)

    if not _index_exists("referral_payouts", idx_period_start):
        with op.batch_alter_table("referral_payouts", schema=None) as batch_op:
            batch_op.create_index(idx_period_start, ["period_start"], unique=False)

    if not _index_exists("referral_payouts", idx_period_end):
        with op.batch_alter_table("referral_payouts", schema=None) as batch_op:
            batch_op.create_index(idx_period_end, ["period_end"], unique=False)

    if not _index_exists("referral_payouts", idx_status):
        with op.batch_alter_table("referral_payouts", schema=None) as batch_op:
            batch_op.create_index(idx_status, ["status"], unique=False)


def downgrade() -> None:
    if not _table_exists("referral_payouts"):
        return

    idx_provider = "ix_referral_payouts_provider_id"
    idx_period_start = "ix_referral_payouts_period_start"
    idx_period_end = "ix_referral_payouts_period_end"
    idx_status = "ix_referral_payouts_status"

    with op.batch_alter_table("referral_payouts", schema=None) as batch_op:
        if _index_exists("referral_payouts", idx_status):
            batch_op.drop_index(idx_status)
        if _index_exists("referral_payouts", idx_period_end):
            batch_op.drop_index(idx_period_end)
        if _index_exists("referral_payouts", idx_period_start):
            batch_op.drop_index(idx_period_start)
        if _index_exists("referral_payouts", idx_provider):
            batch_op.drop_index(idx_provider)

    op.drop_table("referral_payouts")
