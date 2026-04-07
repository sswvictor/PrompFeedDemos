"""add_ig_stats_verification_follow_count_to_providers

Revision ID: 47f87e7beba9
Revises: 20260310_0010
Create Date: 2026-03-11 20:19:00.993062

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47f87e7beba9'
down_revision: Union[str, None] = '20260310_0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in [col["name"] for col in inspector.get_columns(table_name)]


def upgrade() -> None:
    # ig_followers_count, ig_following_count, ig_profile_picture_url, ig_stats_synced_at
    # were already added in a partial run — only add the remaining columns.
    # All guards are idempotent: safe to re-run on DBs where columns already exist.
    cols = [
        ("fixmeapp_followers_count", sa.Column("fixmeapp_followers_count", sa.Integer(), nullable=False, server_default="0")),
        ("is_verified",              sa.Column("is_verified",              sa.Boolean(), nullable=False, server_default="0")),
        ("verified_at",              sa.Column("verified_at",              sa.DateTime(), nullable=True)),
        ("verified_country",         sa.Column("verified_country",         sa.String(length=2), nullable=True)),
        ("verification_source",      sa.Column("verification_source",      sa.String(length=32), nullable=True)),
    ]
    for col_name, col_def in cols:
        if not _column_exists("providers", col_name):
            op.add_column("providers", col_def)


def downgrade() -> None:
    with op.batch_alter_table('providers', schema=None) as batch_op:
        batch_op.drop_column('verification_source')
        batch_op.drop_column('verified_country')
        batch_op.drop_column('verified_at')
        batch_op.drop_column('is_verified')
        batch_op.drop_column('fixmeapp_followers_count')
        batch_op.drop_column('ig_stats_synced_at')
        batch_op.drop_column('ig_profile_picture_url')
        batch_op.drop_column('ig_following_count')
        batch_op.drop_column('ig_followers_count')
