# Fixmeapp AI Platform

AI-first booking platform for beauty freelancers and salons. Providers onboard in minutes, customers book via shareable links or Instagram DM, and an AI layer handles scheduling, discovery, and insights.

**Repo:** [fixmeapp-ai/AI-Platform](https://github.com/fixmeapp-ai/AI-Platform)

## Quickstart

> **Prerequisites:** PostgreSQL 14+, Python 3.11+, Node 20+.
>
> Copy `.env.example` to `.env` and fill in at minimum `DATABASE_URL`, `JWT_SECRET`, and `OPENAI_API_KEY` before starting.
>
> **Database:** the team uses a shared Railway PostgreSQL instance — ask for the `DATABASE_URL` connection string. To use a local database instead: `createdb fixmeapp` then set `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fixmeapp`.

### Backend

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # macOS / Linux
cd backend
pip install -r requirements.txt
python -m app.db.bootstrap    # creates tables + runs migrations
uvicorn app.main:app --reload --host 127.0.0.1 --port 8002
```

### Web frontend

```bash
cd frontend/web
npm ci
npm run dev
```

Web frontend runs at `http://127.0.0.1:5174` and proxies API calls to `http://127.0.0.1:8002`.

### Mobile app (Expo / React Native)

Requires [Expo CLI](https://docs.expo.dev/get-started/installation/) and either the Expo Go app or an iOS/Android simulator.

```bash
cd frontend/mobile
npm ci
npm start          # opens Expo dev menu
```

> **Local dev:** before running, set `EXPO_PUBLIC_API_URL=http://<your-machine-ip>:8002` in `frontend/mobile/.env.local` so the app talks to your local backend instead of production. Use your LAN IP (not `localhost`) when testing on a real device.

### One-command dev (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev-up.ps1
# Stop with: scripts\dev-down.ps1
```

Flags: `-SkipMigrations`, `-SkipFrontendInstall`, `-ApiPort <port>`, `-WebPort <port>`

### Seed demo data

```bash
python backend/scripts/seed_demo_providers.py
```

## Architecture

```
Fixmeapp-booking-logic/
  backend/              FastAPI backend (API, models, services, migrations)
  frontend/
    web/                React SPA (Vite, Tailwind) — booking flows, provider dashboard
    mobile/             Expo React Native app — provider mobile client
  scripts/              Repo-level dev/ops scripts
  docs/                 Engineering and operations documentation
```

### Backend (`backend/`)

| Folder | Purpose |
|---|---|
| `app/api/` | FastAPI routers (onboarding, booking, provider, admin, chat, etc.) |
| `app/services/` | Business logic (booking, availability, waitlist, search, verification) |
| `app/orchestrators/` | AI chat orchestration (Instagram DM bot, discovery chat) |
| `app/models/` | SQLAlchemy ORM models |
| `app/db/` | DB session, schema guard, bootstrap |
| `app/integrations/` | External APIs (Instagram Graph, calendar providers) |
| `alembic/` | Database migrations |

### Web frontend (`frontend/web/`)

Persona-first architecture. Each user type has its own isolated folder.

| Folder | Purpose |
|---|---|
| `src/personas/customer/` | Customer auth, home, profile, onboarding |
| `src/personas/provider/` | Provider auth, home, profile, onboarding, insights |
| `src/personas/salon/` | Salon auth, home, profile, onboarding |
| `src/features/` | Cross-persona modules (auth, booking flow, chat, settings) |
| `src/components/` | Shared reusable UI components |
| `src/api/bookingApi.js` | API client for all backend calls |
| `src/app/routeCatalog.js` | Single source of truth for all route constants |
| `src/pages/admin/` | Internal ops pages (admin verification queue) |

## Routes

### Auth entry

One global entry point: `/auth` where the user picks their role.

| Role | Login | Onboarding |
|---|---|---|
| Customer | `/customer/login` | `/customer/onboarding` |
| Provider | `/provider/login` | `/provider/onboarding` |
| Salon | `/salon/login` | `/salon/onboarding` |

### Provider

| Route | Page |
|---|---|
| `/provider/home` | Dashboard with calendar (day/week/month), bookings |
| `/provider/profile` | Instagram-style profile (services, hours, policies, amenities) |
| `/provider/insights` | AI insights tab |
| `/provider/settings` | Account settings |

### Customer booking

| Route | Purpose |
|---|---|
| `/b/{provider-slug}` | Shareable booking link (Instagram bio, QR code) |
| `/?provider_id={uuid}` | Direct UUID booking link |

Booking steps: Entry > Location > Services > Date/Time > Confirm > Done (or Waitlist)

### Chat

| Route | Surface |
|---|---|
| `/demo/chat` | Provider-locked demo AI chat |
| `/fixmeapp/chat` | Discovery chat across all providers |

### Internal

| Route | Purpose |
|---|---|
| `/admin/verifications` | Ops verification review queue (token-gated) |

## Key backend API groups

| Prefix | Router file | Purpose |
|---|---|---|
| `/onboard/*` | `onboarding.py` | Provider/customer onboarding + price list scan |
| `/setup/*` | `setup.py` | URL import, website scan, business verification |
| `/bookings/*` | `routes.py` | Booking CRUD, calendar, availability |
| `/providers/*` | `provider_links.py` | Public provider profiles, services, trust signals |
| `/admin/*` | `admin.py` | Admin verification queue (approve/reject) |
| `/home/*` | `home_dashboard.py` | Provider/salon home dashboard data |
| `/auth/*` | `auth.py`, `provider_auth.py` | JWT auth, OTP login |
| `/chat/*` | `intent.py` | AI chat intent handling |
| `/subscription/*` | `subscription.py` | Stripe billing |

## Provider onboarding flow

1. Welcome screen with cinematic animation
2. Business type selection + Instagram handle
3. AI web scrape (paste booking page URL, AI extracts services, hours, policies)
4. Manual fallback: screenshot upload or manual entry
5. Provider record created with services, amenities, availability
6. Redirect to provider home with setup wizard (import profile, verify business)

## Business verification

Providers earn a Verified Pro badge by submitting credentials:

- **US providers:** State + license type + license number
- **Non-US providers:** Business registration / org number
- Optional document upload (AI reads it to cross-check)
- Submissions go to admin review queue at `/admin/verifications`
- Sensitive data (license/org numbers) wiped after admin decision

## Environment variables

See `.env.example` for the full list. Key ones:

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `JWT_SECRET` | Yes | JWT signing key |
| `OPENAI_API_KEY` | Yes | AI features (chat, scraping, verification) |
| `STRIPE_SECRET_KEY` | No | Subscription billing |
| `INSTAGRAM_*` | No | Instagram DM bot + profile fetch |
| `ADMIN_SECRET_TOKEN` | No | Admin verification queue access |

## Documentation

| File | Purpose |
|---|---|
| `docs/ONBOARDING_15_MIN.md` | New engineer setup guide |
| `docs/ENGINEERING_STANDARDS.md` | Code standards and policy |
| `docs/OPERATIONS_RUNBOOK.md` | Staging/production ops |
| `docs/CI_GUARDRAILS.md` | CI pipeline rules |
| `docs/MIGRATION_SAFETY.md` | Database migration safety |
| `docs/CALENDAR_SYNC_ARCHITECTURE.md` | Calendar sync design (WIP) |
| `DB_SCHEMA.md` | Full database schema reference (optional local export; gitignored) |
| `AGENTS.md` | AI assistant operating rules |

## Branch strategy

Trunk-based development:

- `main` is the source of truth. Always deployable.
- Feature work on short-lived `feat/*` branches, merged via PR.
- Delete branches after merge.

## Admin V1
See [docs/ADMIN_V1.md](docs/ADMIN_V1.md) for admin menu routes, API endpoints, and audit-log behavior.

