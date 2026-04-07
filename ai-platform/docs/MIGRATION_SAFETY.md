# Migration Safety Checklist and Template

Use this checklist for every Alembic migration to reduce local setup failures and production risk.

## Mandatory checklist

1. Forward-safe
- Fresh DB bootstrap (`python -m app.db.bootstrap`) must run cleanly.
- `upgrade()` must run cleanly when target objects already exist where practical (especially existing PostgreSQL databases).

2. Backward-safe
- `downgrade()` must reverse only what this migration added.
- `downgrade()` must not destroy unrelated data.

3. Idempotent guards (when needed)
- Guard table creation when table may already exist.
- Guard column creation when column may already exist.
- Guard index/constraint creation similarly.

4. Data migration safety
- Backfills must be deterministic and rerunnable.
- For large data migrations, split schema and data steps where possible.

5. Cross-environment compatibility
- Verify behavior on PostgreSQL (staging + production profile).
- Verify behavior on target production engine.

6. CI proof
- `alembic upgrade head` on an initialized/versioned DB must pass.
- `assert_schema_up_to_date()` must pass after migration.

## Authoring standards
- One migration per logical schema change.
- Clear revision message and concise comment at top.
- Avoid raw SQL unless Alembic op helpers are not sufficient.
- If raw SQL is required, keep it minimal and engine-aware.

## Recommended pre-merge commands
From backend directory:

```powershell
python -m app.db.bootstrap
alembic upgrade head
python -c "from app.db.session import assert_schema_up_to_date; assert_schema_up_to_date(); print(\"schema-ok\")"
```

## Template
Use:
- `docs/templates/alembic_safe_migration_template.py`

Copy it into `backend/alembic/versions/` and fill in revision ids and operations.
