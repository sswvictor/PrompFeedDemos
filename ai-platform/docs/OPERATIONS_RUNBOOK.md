# Operations Runbook

Canonical operational guide for staging and production.

## Services
- Backend: FastAPI app in this repo
- Frontend: `frontend` static build
- Database: PostgreSQL in AWS

## Required backend environment variables
- `DATABASE_URL` (PostgreSQL connection string, required)
- `OPENAI_API_KEY`
- `DEFAULT_TIMEZONE`
- `WEB_BOOKING_BASE_URL`
- `INSTAGRAM_VERIFY_TOKEN`
- `INSTAGRAM_PAGE_ACCESS_TOKEN`
- `INSTAGRAM_APP_SECRET`
- `SMTP_*` (if waitlist email offers are enabled)

## Required frontend environment variables
- `VITE_API_TARGET`

## Deployment order
1. Database reachable
2. Run `cd backend && python -m app.db.bootstrap` on target environment
3. Deploy backend
4. Verify `/healthz`
5. Deploy frontend
6. Verify onboarding + booking flow

## Release checks
- Backend health endpoint returns OK
- Frontend build passes
- Booking flow creates rows in DB
- Provider settings endpoint returns 200 with valid token

## Emergency rollback
- Re-deploy previous backend image
- Roll forward DB with corrective migration (preferred)
- Avoid manual schema edits in production

## CI/CD references
- CI workflow: `.github/workflows/ci.yml`
- Staging deploy workflow: `.github/workflows/deploy-aws-staging.yml`
## Referral payout operations
- Monthly referral payouts are generated from completed bookings with `referral_source=provider_link`.
- Automatic mode (recommended):
  - Enable `REFERRAL_AUTO_PAYOUT_ENABLED=true`.
  - Set `REFERRAL_PAYOUT_DAY` (1-28, default 1).
  - Optional Stripe billing offset: `REFERRAL_AUTO_APPLY_TO_SUBSCRIPTION=true`.
  - Backend startup runs a safe idempotent payout check for the previous month and applies Stripe customer credits when possible.
- Manual mode (fallback / backfill):
  - `python backend/scripts/process_referral_payouts.py`
- Dry run for audit:
  - `python backend/scripts/process_referral_payouts.py --dry-run`
- Force a specific month:
  - `python backend/scripts/process_referral_payouts.py --year 2026 --month 2`
- Force Stripe subscription-credit application for a month:
  - `python backend/scripts/process_referral_payouts.py --year 2026 --month 2 --apply-subscription-credit`
- Optional auto-mark paid mode (only if your transfer process is already automated):
  - `python backend/scripts/process_referral_payouts.py --mark-paid`
