"""merge orphan 20260310_0010 head into main chain

Revision ID: 20260330_0032
Revises: 20260330_0031, 20260310_0010
Create Date: 2026-03-30 10:30:00

Migration 20260310_0010 (salon_link_requests) was never referenced by
any subsequent migration, leaving it as a dangling head. This merge
migration folds it into the main chain so alembic has a single head.
"""

from typing import Sequence, Union

revision: str = "20260330_0032"
down_revision: Union[str, tuple] = ("20260330_0031", "20260310_0010")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass  # merge only — no schema changes


def downgrade() -> None:
    pass  # merge only — no schema changes
