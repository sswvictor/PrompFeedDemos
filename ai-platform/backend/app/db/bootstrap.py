"""Database bootstrap for container startup.

Behavior:
- Fresh DB (no tables): create schema from models, then alembic stamp head.
- Existing DB: run alembic upgrade head.
- Legacy/misaligned DB with missing baseline tables and no alembic_version:
  fallback to create schema + stamp head.
"""

from __future__ import annotations

import os
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import NoSuchTableError

from app.db.session import Base, engine
import app.models  # noqa: F401  # Ensure model metadata is fully loaded.


def _alembic_config() -> Config:
    backend_root = Path(__file__).resolve().parents[2]
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    return cfg


def _bootstrap_fresh(cfg: Config) -> None:
    Base.metadata.create_all(bind=engine)
    command.stamp(cfg, "head")
    print("[db-bootstrap] Fresh schema created and stamped to alembic head.")


def _repair_missing_columns() -> None:
    """Emergency repair: add provider columns that may be missing due to
    Alembic merge-migration issues on Railway (branch ig-stats was never
    applied, so the merge migration 0028 is blocked and 0029/0030 never ran).
    Uses ADD COLUMN IF NOT EXISTS — safe to run on any existing DB.
    Runs BEFORE alembic upgrade so the app never 500s on startup.
    """
    inspector = sa.inspect(engine)
    if "providers" not in inspector.get_table_names():
        return  # Fresh DB — migrations will create the full schema.

    repair_ddls = [
        "ALTER TABLE providers ADD COLUMN IF NOT EXISTS ig_followers_count INTEGER",
        "ALTER TABLE providers ADD COLUMN IF NOT EXISTS ig_following_count INTEGER",
        "ALTER TABLE providers ADD COLUMN IF NOT EXISTS ig_profile_picture_url VARCHAR(500)",
        "ALTER TABLE providers ADD COLUMN IF NOT EXISTS ig_stats_synced_at TIMESTAMP",
        "ALTER TABLE providers ADD COLUMN IF NOT EXISTS fixmeapp_followers_count INTEGER DEFAULT 0",
        "ALTER TABLE providers ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE",
        "ALTER TABLE providers ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP",
        "ALTER TABLE providers ADD COLUMN IF NOT EXISTS verified_country VARCHAR(2)",
        "ALTER TABLE providers ADD COLUMN IF NOT EXISTS verification_source VARCHAR(32)",
        "ALTER TABLE providers ADD COLUMN IF NOT EXISTS push_token VARCHAR(255)",
    ]

    with engine.connect() as conn:
        for ddl in repair_ddls:
            try:
                conn.execute(sa.text(ddl))
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                print(f"[db-bootstrap] Repair DDL skipped ({exc})")

    print("[db-bootstrap] Provider column repair complete.")


def _unblock_merge_migration() -> None:
    """Migration 20260317_0028 is a merge that requires BOTH parents:
      - 20260317_0027  (main chain — push_token)
      - 20260311_2305  (ig-stats branch)

    Railway DBs that only have the main chain can't advance past the merge.
    Since migration 0029 adds all branch schema idempotently, it is safe to
    stamp the branch revision so Alembic can proceed to 0028 → 0029 → 0030.
    """
    try:
        with engine.connect() as conn:
            current = {
                row[0]
                for row in conn.execute(sa.text("SELECT version_num FROM alembic_version"))
            }
    except Exception:  # noqa: BLE001
        return  # No alembic_version table yet — nothing to unblock.

    main_parent = "20260317_0027"
    branch_parent = "20260311_2305"

    if main_parent in current and branch_parent not in current:
        print(
            f"[db-bootstrap] Injecting missing branch stamp {branch_parent} "
            "to unblock merge migration 0028."
        )
        with engine.connect() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO alembic_version (version_num) "
                    "VALUES (:rev) ON CONFLICT DO NOTHING"
                ),
                {"rev": branch_parent},
            )
            conn.commit()


def main() -> None:
    # Tell alembic/env.py not to fileConfig() — that clobbers uvicorn & app logging.
    os.environ["ALEMBIC_EMBEDDED"] = "1"
    try:
        cfg = _alembic_config()
        inspector = sa.inspect(engine)
        tables = set(inspector.get_table_names())

        # Completely fresh DB.
        if not tables:
            _bootstrap_fresh(cfg)
            return

        has_alembic_version = "alembic_version" in tables

        # ── Pre-flight repairs ────────────────────────────────────────────────
        # 1. Add any provider columns missing due to the Alembic merge issue so
        #    the app never crashes on SELECT queries even before Alembic runs.
        _repair_missing_columns()
        # 2. Inject the ig-stats branch stamp if needed so the merge migration
        #    (0028) can be applied and the full migration chain can proceed.
        _unblock_merge_migration()
        # ─────────────────────────────────────────────────────────────────────

        try:
            # Single head now (branches merged in 0028)
            command.upgrade(cfg, "head")
            print("[db-bootstrap] Alembic upgrade head completed.")
        except NoSuchTableError:
            # Migrations assume legacy base tables but DB is unversioned.
            if not has_alembic_version:
                _bootstrap_fresh(cfg)
                return
            raise

        # Verify head is stamped
        from alembic.script import ScriptDirectory

        expected_head = set(ScriptDirectory.from_config(cfg).get_heads())
        with engine.connect() as conn:
            current = {row[0] for row in conn.execute(sa.text("SELECT version_num FROM alembic_version"))}
        if current != expected_head:
            print(f"[db-bootstrap] Stamping all head {expected_head} (was {current}).")
            command.stamp(cfg, "head")
    finally:
        os.environ.pop("ALEMBIC_EMBEDDED", None)


if __name__ == "__main__":
    main()