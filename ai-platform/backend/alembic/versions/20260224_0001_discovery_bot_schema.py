"""Discovery bot schema: platform-level conversations and Instagram page routing

Revision ID: 20260224_0001
Revises: (initial)
Create Date: 2026-02-24
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import NoSuchTableError

revision: str = "20260224_0001"
down_revision: Union[str, None] = None
branch_labels = None
depends_on = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    try:
        cols = _inspector().get_columns(table_name)
    except NoSuchTableError:
        return False
    return any(c["name"] == column_name for c in cols)


def _column_nullable(table_name: str, column_name: str) -> bool:
    try:
        cols = _inspector().get_columns(table_name)
    except NoSuchTableError:
        return False
    for col in cols:
        if col["name"] == column_name:
            return bool(col.get("nullable", False))
    return False


def _fk_exists(table_name: str, constraint_name: str) -> bool:
    try:
        fks = _inspector().get_foreign_keys(table_name)
    except NoSuchTableError:
        return False
    return any((fk.get("name") or "") == constraint_name for fk in fks)


def _unique_exists(table_name: str, constraint_name: str) -> bool:
    try:
        uniques = _inspector().get_unique_constraints(table_name)
    except NoSuchTableError:
        return False
    return any((uq.get("name") or "") == constraint_name for uq in uniques)


def upgrade() -> None:
    if _table_exists("conversations"):
        if not _column_exists("conversations", "conversation_type"):
            op.add_column(
                "conversations",
                sa.Column("conversation_type", sa.String(length=20), nullable=False, server_default="booking"),
            )
        if not _column_exists("conversations", "user_id"):
            op.add_column(
                "conversations",
                sa.Column("user_id", sa.String(length=36), nullable=True),
            )

        if _column_exists("conversations", "user_id") and not _fk_exists(
            "conversations", "fk_conversations_user_id_users"
        ):
            op.create_foreign_key(
                "fk_conversations_user_id_users",
                "conversations",
                "users",
                ["user_id"],
                ["user_id"],
            )

        if _column_exists("conversations", "provider_id") and not _column_nullable("conversations", "provider_id"):
            op.alter_column(
                "conversations",
                "provider_id",
                existing_type=sa.String(length=36),
                nullable=True,
            )

        if not _unique_exists("conversations", "uq_user_channel_thread"):
            op.create_unique_constraint(
                "uq_user_channel_thread",
                "conversations",
                ["user_id", "channel", "external_thread_id"],
            )

    if _table_exists("provider_instagram_pages"):
        if not _column_exists("provider_instagram_pages", "is_platform_page"):
            op.add_column(
                "provider_instagram_pages",
                sa.Column("is_platform_page", sa.Boolean(), nullable=False, server_default=sa.false()),
            )

        if _column_exists("provider_instagram_pages", "provider_id") and not _column_nullable(
            "provider_instagram_pages", "provider_id"
        ):
            op.alter_column(
                "provider_instagram_pages",
                "provider_id",
                existing_type=sa.String(length=36),
                nullable=True,
            )


def downgrade() -> None:
    if _table_exists("provider_instagram_pages"):
        if _column_exists("provider_instagram_pages", "provider_id") and _column_nullable(
            "provider_instagram_pages", "provider_id"
        ):
            op.alter_column(
                "provider_instagram_pages",
                "provider_id",
                existing_type=sa.String(length=36),
                nullable=False,
            )
        if _column_exists("provider_instagram_pages", "is_platform_page"):
            op.drop_column("provider_instagram_pages", "is_platform_page")

    if _table_exists("conversations"):
        if _fk_exists("conversations", "fk_conversations_user_id_users"):
            op.drop_constraint("fk_conversations_user_id_users", "conversations", type_="foreignkey")
        if _unique_exists("conversations", "uq_user_channel_thread"):
            op.drop_constraint("uq_user_channel_thread", "conversations", type_="unique")
        if _column_exists("conversations", "provider_id") and _column_nullable("conversations", "provider_id"):
            op.alter_column(
                "conversations",
                "provider_id",
                existing_type=sa.String(length=36),
                nullable=False,
            )
        if _column_exists("conversations", "user_id"):
            op.drop_column("conversations", "user_id")
        if _column_exists("conversations", "conversation_type"):
            op.drop_column("conversations", "conversation_type")
