"""add_provider_follows_table

Revision ID: 40e880fc5b26
Revises: 47f87e7beba9
Create Date: 2026-03-11 20:26:11.794383

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '40e880fc5b26'
down_revision: Union[str, None] = '47f87e7beba9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("provider_follows"):
        return  # Already exists — idempotent, nothing to do.

    op.create_table(
        "provider_follows",
        sa.Column("follow_id",    sa.String(length=36), nullable=False),
        sa.Column("customer_id",  sa.String(length=36), nullable=False),
        sa.Column("provider_id",  sa.String(length=36), nullable=False),
        sa.Column("created_at",   sa.DateTime(),         nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.provider_id"]),
        sa.PrimaryKeyConstraint("follow_id"),
        sa.UniqueConstraint("customer_id", "provider_id", name="uq_provider_follow"),
    )
    with op.batch_alter_table("provider_follows", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_provider_follows_customer_id"), ["customer_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_provider_follows_provider_id"), ["provider_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("provider_follows", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_provider_follows_provider_id"))
        batch_op.drop_index(batch_op.f("ix_provider_follows_customer_id"))

    op.drop_table("provider_follows")
