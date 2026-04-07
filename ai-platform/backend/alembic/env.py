"""
Alembic environment configuration for Fixmeapp.

Database URL resolution (priority):
1. DATABASE_URL environment variable
2. DB_* environment variables (optional compatibility path)

PostgreSQL is required; non-PostgreSQL fallback is not supported.
"""

import logging
import os
import sys
from pathlib import Path
from logging.config import fileConfig

from alembic import context
import sqlalchemy as sa
from sqlalchemy import engine_from_config, pool

# Make sure project root is importable regardless of shell/cwd behavior.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.models  # noqa: F401
from app.db.session import Base

config = context.config


def _alembic_embedded() -> bool:
    """True when migrations run inside the app (bootstrap / uvicorn startup).

    In that case we must not call fileConfig(alembic.ini): it sets root to WARN/INFO
    and replaces handlers, which suppresses uvicorn.access and app loggers at INFO.
    """
    return os.environ.get("ALEMBIC_EMBEDDED", "").lower() in {"1", "true", "yes", "on"}


def _configure_alembic_logging() -> None:
    if not config.config_file_name:
        return
    if _alembic_embedded():
        alembic_log = logging.getLogger("alembic")
        alembic_log.setLevel(logging.INFO)
        if not alembic_log.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(levelname)-5.5s [%(name)s] %(message)s"))
            alembic_log.addHandler(handler)
            alembic_log.propagate = False
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    else:
        fileConfig(config.config_file_name, disable_existing_loggers=False)


_configure_alembic_logging()

target_metadata = Base.metadata


def _build_database_url() -> str:
    if url := os.getenv("DATABASE_URL"):
        return url.replace("postgres://", "postgresql://", 1)

    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME")
    if all([user, password, host, name]):
        return f"postgresql://{user}:{password}@{host}:{port}/{name}"

    raise RuntimeError(
        "DATABASE_URL is required for Alembic (PostgreSQL). "
        "Set DATABASE_URL before running migrations."
    )


DATABASE_URL = _build_database_url()
config.set_main_option("sqlalchemy.url", DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    # Pre-flight empty-DB check on its own connection. Do not reuse that
    # Connection for migrations: SA 2.x autobegin on introspection can leave the
    # connection inside a transaction and cause Alembic's batch to end in ROLLBACK
    # (no alembic_version persisted even though upgrade logs succeeded).
    with connectable.connect() as pre_conn:
        table_names = set(sa.inspect(pre_conn).get_table_names())
        if not table_names:
            raise RuntimeError(
                "Direct `alembic upgrade head` is not supported on an empty database in this repo. "
                "Run `python -m app.db.bootstrap` from backend/ first."
            )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
