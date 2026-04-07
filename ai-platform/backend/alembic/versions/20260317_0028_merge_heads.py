"""merge branch heads into single linear history

Revision ID: 20260317_0028
Revises: 20260317_0027, 20260311_2305
Create Date: 2026-03-17 12:00:00

Merges the ig-stats/follows/discovery branch (20260311_2305)
with the main migration chain (20260317_0027) so the history
has a single head going forward.
"""

from typing import Sequence, Union

revision: str = "20260317_0028"
down_revision: Union[str, tuple] = ("20260317_0027", "20260311_2305")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass  # merge only — no schema changes


def downgrade() -> None:
    pass  # merge only — no schema changes
