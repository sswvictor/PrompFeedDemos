"""Add running-late notification fields to bookings.

Stores the minutes late and when the customer sent the notification,
so the provider can see it as an alert on their home screen.

Revision ID: 20260310_0009
Revises: 20260310_0008
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa

revision = "20260310_0009"
down_revision = "20260310_0008"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in cols


def upgrade() -> None:
    if not _column_exists("bookings", "late_notification_minutes"):
        op.add_column(
            "bookings",
            sa.Column("late_notification_minutes", sa.Integer(), nullable=True),
        )
    if not _column_exists("bookings", "late_notification_sent_at"):
        op.add_column(
            "bookings",
            sa.Column("late_notification_sent_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("bookings", "late_notification_sent_at"):
        op.drop_column("bookings", "late_notification_sent_at")
    if _column_exists("bookings", "late_notification_minutes"):
        op.drop_column("bookings", "late_notification_minutes")
