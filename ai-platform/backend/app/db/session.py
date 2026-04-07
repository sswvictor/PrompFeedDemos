import os
from pathlib import Path

from dotenv import load_dotenv
import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# app/db/session.py -> parents[2] == backend/
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_BACKEND_ROOT / ".env")
load_dotenv(_BACKEND_ROOT.parent / ".env")


# Priority:
# 1. DATABASE_URL - full connection string (Railway, AWS RDS, etc.)
# 2. DB_* vars - individual parts (optional compatibility path)
# PostgreSQL is required; non-PostgreSQL fallback is not supported.
def _build_database_url() -> str:
    if url := os.getenv("DATABASE_URL"):
        # Railway sometimes provides postgres:// but SQLAlchemy expects postgresql://
        return url.replace("postgres://", "postgresql://", 1)

    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME")
    if all([user, password, host, name]):
        return f"postgresql://{user}:{password}@{host}:{port}/{name}"

    raise RuntimeError(
        "DATABASE_URL is required (PostgreSQL). "
        "Set DATABASE_URL before starting backend or running Alembic."
    )


DATABASE_URL = _build_database_url()

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def assert_schema_up_to_date() -> None:
    """Fail fast when DB schema is not migrated to the Alembic head revision."""
    inspector = sa.inspect(engine)
    table_names = set(inspector.get_table_names())
    if "alembic_version" not in table_names:
        raise RuntimeError(
            "Database schema is not initialized. Run `python -m app.db.bootstrap` before starting the app."
        )

    with engine.connect() as conn:
        current_revisions = {
            row[0] for row in conn.execute(sa.text("SELECT version_num FROM alembic_version"))
        }

    project_root = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(project_root / "alembic"))
    expected_heads = set(ScriptDirectory.from_config(alembic_cfg).get_heads())

    if current_revisions != expected_heads:
        raise RuntimeError(
            "Database schema revision mismatch. "
            f"Current={sorted(current_revisions)} Expected={sorted(expected_heads)}. "
            "Run `python -m app.db.bootstrap`."
        )

    # Guard against model/table drift (e.g. model added but migration missing).
    required_tables = set(Base.metadata.tables.keys())
    missing_tables = sorted(required_tables - table_names)
    if missing_tables:
        raise RuntimeError(
            "Database schema is missing tables required by current models: "
            f"{missing_tables}. Run `python -m app.db.bootstrap`."
        )
