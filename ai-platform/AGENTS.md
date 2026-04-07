# Shared AI Strict Workflow

This file defines one strict operating mode for all AI assistants in this repo.
Single source of truth - no CLAUDE.md, no Codex config. This file is it.

## 1) Scope Discipline
- Work one task at a time.
- Touch only files required for that task.
- Never mix frontend redesign with backend logic in the same patch unless explicitly requested.
- Never perform broad regex rewrites across many files unless explicitly approved.

## 2) Ownership Discipline
- One assistant owns a file area at a time.
- If another assistant has already modified a file in this session, read it first and avoid destructive overwrites.
- Do not revert user/teammate changes unless explicitly asked.

## 3) Pre-Edit Protocol
- Before edits: state target files and expected behavior change.
- During edits: keep patches small and verifiable.
- After edits: run `scripts\ai-strict-check.ps1` when possible.

## 4) Completion Gate (must pass before "done")
- No syntax/import errors in changed Python files.
- No merge markers (`<<<<<<<`, `=======`, `>>>>>>>`).
- No accidental duplicate route/tool definitions.
- Provide line-level summary of changed behavior.

## 5) Chat/Booking Safety Rules
- Never let the bot ask the same confirmation question repeatedly.
- If user confirms and pending slot exists, progress to booking or clear next required step.
- After booking confirmation, request contact details exactly once and persist them.

## 6) Communication Rules
- Be concise, concrete, and deterministic.
- If runtime validation cannot be executed (missing interpreter/dependency), explicitly say so and provide exact command for the user terminal.

## 7) Git Safety
- Local-first unless user explicitly asks to push.
- Never push to `main` directly from exploratory work.
- Use a dedicated branch for handoff when requested.
- Canonical repo is `AI-Platform` (remote: `origin`).
- Do not use the old `AI-booking` / `Old-AI-booking` repo for new work, sync, or pushes.
- When push is requested, push to `origin` (AI-Platform) only and report explicit push result.
- Never run app/scripts from `.claude/worktrees/*` or `.codex/*` paths.
- Never run app/scripts from branches named `codex/*` or `claude/*`.
- Runtime commands must execute from canonical repo root containing both `backend/` and `frontend/`.
## 8) Persona Architecture (Frontend)
The frontend is persona-first: customer, provider, salon.

Default rule:
- Persona-specific UI/logic must live under:
  - `frontend/web/src/personas/customer/`
  - `frontend/web/src/personas/provider/`
  - `frontend/web/src/personas/salon/`

Folder conventions:
- Prefer existing subfolders (auth/, home/, navigation/, onboarding/, profile/).
- If a new persona subfolder is needed, add it only with a short rationale in the PR/task note.

Shared code:
- Shared UI: `frontend/web/src/components/`
- Shared API/data access: `frontend/web/src/api/`
- Shared state/hooks: `frontend/web/src/hooks/`
- Keep shared modules persona-agnostic.

Routes:
- Frontend routes are defined in `frontend/web/src/app/routeCatalog.js` and consumed from `ROUTES` constants.
- Do not introduce new persona route strings inline in React components.

Exceptions (allowed):
- `frontend/web/src/pages/*` may contain demo/compatibility routes only (e.g. `/demo/*`, `/fixmeapp/*`).
- Persona business logic must not be added there unless marked `TEMP_PERSONA_BYPASS` with follow-up migration note.

Anti-duplication:
- Do not implement the same persona flow in both `pages/*` and `personas/*`.
- `personas/*` is the source of truth for persona flows.

## 9) Business Verification Service Architecture
Verification is a service, not a persona feature. All business lookup and identity verification logic lives in the service layer, consumed by persona onboarding flows - never implemented inline.

Backend structure:
- `backend/app/services/business_verification/base.py` - abstract adapter interface (BusinessProfile dataclass + BaseAdapter)
- `backend/app/services/business_verification/models.py` - shared data models (BusinessProfile, VerificationResult)
- `backend/app/services/business_verification/adapters/sweden.py` - Bolagsverket / Allabolag.se (org number)
- `backend/app/services/business_verification/adapters/usa.py` - OpenCorporates (EIN / name search)
- `backend/app/services/business_verification/adapters/india.py` - GSTIN verification API
- `backend/app/services/business_verification/adapters/screenshot.py` - OCR fallback adapter (planned, not yet implemented)

Current implementation note (important):
- Screenshot OCR currently runs via onboarding endpoint `POST /onboarding/scan-price-list` in `backend/app/api/onboarding.py`.
- This is active and used by frontend onboarding/settings flows.
- `backend/app/services/business_verification/adapters/screenshot.py` is currently missing and should be added only if we move OCR fallback into the verification adapter layer.

Frontend structure:
- `frontend/web/src/components/verification/OrgNumberLookup.jsx` - reusable input + auto-fill widget
- `frontend/web/src/components/verification/PricelistUpload.jsx` - reusable OCR pricelist upload widget
- `frontend/web/src/components/verification/VerifiedBadge.jsx` - reusable badge, used on profiles and booking UI
- Verification steps belong inside the persona onboarding folders (`frontend/web/src/personas/provider/onboarding/`, `frontend/web/src/personas/salon/onboarding/`).

Instagram Graph API:
- Profile fetch client lives in `backend/app/integrations/instagram/graph_client.py`.
- Fetches: bio, follower count, profile picture, recent posts for onboarding auto-fill.
- Do not mix Graph API (profile data) with webhook/messenger (DM handling) - these are separate concerns.

Verified badge rules:
- Provider/salon: `is_verified=True` after business lookup succeeds.
- Employee: `verified_via_salon_id` set when salon invite is accepted - no separate verification needed.
- Badge display: shared `VerifiedBadge.jsx` component, never re-implemented per persona.

Adding a new country:
- Add one new adapter in `backend/app/services/business_verification/adapters/`.
- Register it in the adapter map in `base.py`.
- No changes to persona flows, routes, or frontend required.

## 10) Script Sync Policy
Scripts are production developer tooling.

- When runtime behavior changes, update impacted scripts in the same task.
- Any approved change to AI chat, onboarding, routing, seed data, or ports must align impacted scripts (`scripts/run-ai-booking-e2e.ps1`, `backend/scripts/ensure_demo_provider.py`, `backend/scripts/seed_demo_providers.py`, `scripts/web-dev.cmd`, `scripts/capture-provider-flow.cmd`).
- If scripts are intentionally not updated, document the reason in the task or PR note.

## 11) Encoding and Escape Safety (mandatory)
- Never commit literal escape tokens in file content: `\r`, `\n`, `\r\n`, or PowerShell literals like `` `r`n ``.
- Never inject escaped newline sequences via regex replacements.
- If line breaks are needed, write real newlines only.
- Before finalizing, scan changed files for accidental literal escapes and fix them before reporting done.
- Files must be UTF-8 without mojibake; if corrupted characters appear, stop and repair encoding before continuing.


## 12) Provider Shell Contract (Do Not Break)
Provider experience is locked to this shell contract unless explicitly changed by product decision:

- Provider bottom nav must always expose exactly 3 tabs:
  - Home (`/provider/home`)
  - Finance (`/provider/finance`)
  - Profile (`/provider/profile`)
- Provider Home must surface the primary switch directly under the greeting:
  - `Bookings`
  - `Inbox`
- `Inbox` is a human-attention queue, not a generic full-message archive.
- `frontend/web/src/personas/provider/profile/ProviderProfilePage.jsx` is the source-of-truth Instagram-inspired profile and must keep the middle content tab row (`TabRow` pattern).
- Provider Home source-of-truth is `frontend/web/src/personas/provider/home/ProviderHomePage.jsx`.
- Route wiring source-of-truth is `frontend/web/src/App.jsx` + `frontend/web/src/app/routeCatalog.js`.
- Any change to provider nav/routes/profile layout must include updating `scripts/ai-strict-check.ps1` contract checks in the same task.

## 13) Railway Deployment Environment

Critical environment variables — must be set in Railway dashboard under the backend service Variables tab before deploying:

| Variable | Required value | Why |
|---|---|---|
| `STRICT_STARTUP_MIGRATIONS` | `0` | The DB bootstrap runs Alembic on every startup. If any migration hiccups (conflicting heads, already-applied columns, etc.) the process raises and Railway returns 502 "Application failed to respond" to ALL requests. Setting this to `0` lets the app start even if migrations have a non-fatal issue. The DB schema is almost always already correct in production; this flag only matters during deploy. |

Rules for AI assistants:
- Never remove this variable or change it back to `1` without understanding the current Alembic state.
- When adding new migrations, always use idempotent guards (see `20260317_0027` for the pattern: check column exists before `op.add_column`).
- The Alembic migration chain must have exactly one head. If you introduce a branch (e.g. a feature branch migration), merge it immediately with a merge-only migration (see `20260317_0028` as the pattern).
- After any migration change, verify `alembic heads` returns a single revision before deploying.
