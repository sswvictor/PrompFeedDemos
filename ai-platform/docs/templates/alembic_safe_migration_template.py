"""Safe Alembic migration template.

Copy this file into alembic/versions/<revision>_<slug>.py and fill in values.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = "YYYYMMDD_NNNN"
down_revision = "PREVIOUS_REVISION"
branch_labels = None
depends_on = None


def _inspector(bind) -> Inspector:
    return sa.inspect(bind)


def _table_exists(bind, table_name: str) -> bool:
    return table_name in _inspector(bind).get_table_names()


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    if not _table_exists(bind, table_name):
        return False
    columns = _inspector(bind).get_columns(table_name)
    return any(col.get("name") == column_name for col in columns)


def upgrade() -> None:
    bind = op.get_bind()

    # Example: create table only if it does not exist.
    if not _table_exists(bind, "example_table"):
        op.create_table(
            "example_table",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    # Example: add column only if it does not exist.
    if _table_exists(bind, "services") and not _column_exists(bind, "services", "keywords"):
        op.add_column("services", sa.Column("keywords", sa.String(512), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()

    # Reverse only what this migration introduced.
    if _column_exists(bind, "services", "keywords"):
        op.drop_column("services", "keywords")

    if _table_exists(bind, "example_table"):
        op.drop_table("example_table")
