"""Add chat magic-link verification tokens.

Creates one-time token storage for secure email verification before
finalizing chat bookings.

Revision ID: 20260310_0008
Revises: 20260310_0007
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa

revision = "20260310_0008"
down_revision = "20260310_0007"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(idx.get("name") == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists("chat_magic_links"):
        op.create_table(
            "chat_magic_links",
            sa.Column("token_id", sa.String(36), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("provider_id", sa.String(36), nullable=True),
            sa.Column("customer_id", sa.String(36), nullable=True),
            sa.Column("conversation_id", sa.String(36), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("consumed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["provider_id"], ["providers.provider_id"]),
            sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.conversation_id"]),
            sa.PrimaryKeyConstraint("token_id"),
        )

    if _table_exists("chat_magic_links") and not _index_exists("chat_magic_links", "ix_chat_magic_links_email"):
        op.create_index("ix_chat_magic_links_email", "chat_magic_links", ["email"], unique=False)

    if _table_exists("chat_magic_links") and not _index_exists("chat_magic_links", "ix_chat_magic_links_customer"):
        op.create_index("ix_chat_magic_links_customer", "chat_magic_links", ["customer_id"], unique=False)


def downgrade() -> None:
    if _table_exists("chat_magic_links"):
        if _index_exists("chat_magic_links", "ix_chat_magic_links_customer"):
            op.drop_index("ix_chat_magic_links_customer", table_name="chat_magic_links")
        if _index_exists("chat_magic_links", "ix_chat_magic_links_email"):
            op.drop_index("ix_chat_magic_links_email", table_name="chat_magic_links")
        op.drop_table("chat_magic_links")
