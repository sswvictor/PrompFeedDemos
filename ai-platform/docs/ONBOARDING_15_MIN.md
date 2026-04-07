# 15-Minute Onboarding

This is the only supported setup path for backend + frontend.

## Prerequisites
- Python 3.11+
- Node 20+
- Git
- PostgreSQL (local or hosted)

## 1) Clone and install
```bash
git clone https://github.com/fixmeapp-ai/AI-Platform.git
cd AI-Platform
python -m venv .venv
. .venv/Scripts/activate
cd backend
pip install -r requirements.txt
cd ../frontend
npm ci
cd ..
```

## 2) Configure database
```bash
# example
set DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fixmeapp
```

## 3) Bootstrap database schema
```bash
cd backend
python -m app.db.bootstrap
cd ..
```

If this fails, stop and fix DB bootstrap/migrations first. Do not bypass with runtime schema creation.

## 4) Seed demo data (optional but recommended)
```bash
python backend/scripts/seed_demo_providers.py
```

This is the only supported seed entrypoint.

## 5) Run backend
```bash
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check:
```bash
curl -s http://127.0.0.1:8000/healthz
```

## 6) Run frontend
```bash
cd frontend
npm run dev
```

## 7) First-day checks
- `cd backend && alembic current` matches latest head
- `GET /healthz` returns `{ "status": "ok" }`
- Frontend loads and can reach backend via configured API target

## Troubleshooting
- Migration mismatch: run `cd backend && python -m app.db.bootstrap`
- DB points to wrong target: verify `DATABASE_URL` env var
- Never create schema via ORM runtime calls

