# Engineering Standards

These standards are mandatory for all contributors.

## Database and migrations
- Alembic is the single source of truth for schema.
- Every schema change must include a migration.
- Runtime schema creation is forbidden.
- CI must pass migration smoke checks on a fresh database.

## Seeding and local data
- Use only `python backend/scripts/seed_demo_providers.py`.
- Seed scripts must be idempotent.
- Do not add alternative seed entrypoints.

## Repository structure
- Backend code: `backend/app/`
- Migrations: `backend/alembic/`
- Frontend code: `frontend/`
- Utility scripts: `scripts/`
- Canonical documentation: `docs/`

## CI quality gates
- Backend dependency install and compile checks
- Fresh DB migration to head
- Schema revision assertion after migration
- Frontend install and production build

## Documentation policy
- Keep one canonical document per topic.
- Delete superseded docs instead of keeping duplicates.
- Update README links when docs move.

## PR policy
- Small, reviewable changes.
- Migration + app behavior must be validated together.
- No bypasses for failing checks.

## Branch protection
- Follow `docs/CI_GUARDRAILS.md` for required checks and protected-branch settings.
- Required CI checks on `main`: `repo-guardrails`, `backend-check`, `frontend-build`.

## Migration safety
- Follow `docs/MIGRATION_SAFETY.md` for migration authoring and review checklist.
- Start new migrations from `docs/templates/alembic_safe_migration_template.py`.

## Dev startup scripts
- Use `scripts/dev-up.ps1` and `scripts/dev-down.ps1` as the canonical local stack lifecycle commands.
