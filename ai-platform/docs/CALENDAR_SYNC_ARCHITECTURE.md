# Calendar Sync Architecture (Launch Plan)

This document defines the production architecture for provider phone-calendar sync and real-time AI booking decisions.

## Launch goals
- Two-way sync for Google Calendar and Outlook Calendar.
- One-way ICS subscription for Apple Calendar and universal fallback.
- Real-time availability decisions for booking flow and AI chat bot.
- Idempotent, retry-safe sync that cannot create duplicate bookings/events.

## Scope for launch
- In scope:
  - Google OAuth connect + webhook + delta sync
  - Microsoft OAuth connect + webhook + delta sync
  - ICS feed generation per provider
  - Unified busy-slot read model used by app and AI bot
- Out of scope (post-launch):
  - Full CalDAV write sync
  - Multi-calendar conflict UI per worker

## Core architecture

### 1) Canonical source of booking truth
- `bookings` remains Fixmeapp canonical source for customer/provider booking state.
- External calendars are synchronized views, not primary booking storage.

### 2) Provider calendar connections
- New table: `provider_calendar_connections`
- One row per connected external account/calendar.
- Stores provider, connector type, external calendar id, OAuth tokens, and sync state.

### 3) Event mapping table
- New table: `external_calendar_events`
- Maps `booking_id` <-> external provider event id.
- Prevents duplicates and supports upsert/update/delete.

### 4) Outbox + sync worker
- New table: `sync_jobs`
- Booking mutations enqueue sync jobs in same DB transaction.
- Worker processes jobs asynchronously with retry/backoff.
- This keeps API latency low and avoids dropped sync operations.

### 5) External delta ingestion
- Webhook endpoints receive external calendar changes.
- Webhook stores normalized events, then enqueues ingest jobs.
- Ingest worker applies conflict policy and updates Fixmeapp bookings or local block overlays.

### 6) Unified availability read model
- Availability query merges:
  - working hours
  - internal bookings
  - manual blocks
  - external busy windows (from synced calendars)
- Exposed as one API so frontend booking flow and AI bot use the same truth.

## Real-time AI bot access path
- AI bot must not read provider calendars directly.
- AI bot calls canonical tools only:
  - `check_availability`
  - `create_booking`
  - `reschedule_booking`
  - `cancel_booking`
- These tools use the same unified availability service and enqueue sync jobs.
- Result: AI decisions and app UI always align.

## Proposed data model

### `provider_calendar_connections`
- `connection_id` (pk)
- `provider_id` (fk providers)
- `connector` (`google` | `microsoft` | `ics`)
- `external_account_id`
- `external_calendar_id`
- `display_name`
- `access_token_encrypted`
- `refresh_token_encrypted`
- `token_expires_at`
- `webhook_channel_id`
- `webhook_resource_id`
- `sync_enabled` (bool)
- `sync_direction` (`read_write` | `read_only`)
- `last_sync_cursor`
- `last_synced_at`
- `last_error`
- `created_at`, `updated_at`

### `external_calendar_events`
- `id` (pk)
- `provider_id` (fk providers)
- `connection_id` (fk provider_calendar_connections)
- `booking_id` (nullable fk bookings)
- `external_event_id`
- `external_etag`
- `start_at`, `end_at`
- `status` (`active` | `cancelled`)
- `source` (`fixme_push` | `external_pull`)
- `created_at`, `updated_at`
- unique: (`connection_id`, `external_event_id`)
- unique nullable: (`connection_id`, `booking_id`)

### `sync_jobs`
- `job_id` (pk)
- `provider_id` (fk providers)
- `connection_id` (nullable fk provider_calendar_connections)
- `job_type` (`push_create`, `push_update`, `push_delete`, `pull_delta`, `reconcile`)
- `booking_id` (nullable)
- `payload_json`
- `status` (`queued`, `running`, `done`, `failed`, `dead_letter`)
- `attempt_count`
- `next_run_at`
- `last_error`
- `idempotency_key`
- `created_at`, `updated_at`
- unique: `idempotency_key`

## API contract (backend)

### Provider settings
- `GET /api/v1/provider/calendar/connections`
- `POST /api/v1/provider/calendar/google/connect-url`
- `GET /api/v1/provider/calendar/google/callback`
- `POST /api/v1/provider/calendar/microsoft/connect-url`
- `GET /api/v1/provider/calendar/microsoft/callback`
- `POST /api/v1/provider/calendar/connections/{connection_id}/disconnect`
- `POST /api/v1/provider/calendar/connections/{connection_id}/sync-now`

### ICS
- `GET /api/v1/provider/calendar/ics/{provider_id}/{token}.ics`
- `POST /api/v1/provider/calendar/ics/rotate-token`

### Webhooks
- `POST /api/v1/webhooks/google/calendar`
- `POST /api/v1/webhooks/microsoft/calendar`

### Unified availability
- `GET /api/v1/providers/{provider_id}/availability/unified`
  - Inputs: `from`, `to`, `service_id` or `duration_minutes`
  - Output: slot list with `available=true/false` and reason (`internal_booking`, `external_busy`, `manual_block`)

## Conflict policy (launch default)
- If external change conflicts with already confirmed customer booking:
  - keep Fixmeapp booking as canonical
  - mark conflict record
  - notify provider in dashboard
- If external event is new and overlaps free hours:
  - create `manual block` style busy window locally (not a customer booking)
- All conflict handling is logged and retry-safe.

## Provider phone-calendar behavior
- Google and Outlook apps: two-way sync.
- Apple Calendar: subscribe to ICS URL for up-to-date bookings on iPhone.
- If provider edits in Google/Outlook, webhook/delta pulls update Fixmeapp availability quickly.

## Reliability requirements
- Every booking mutation writes outbox/sync jobs in same transaction.
- Worker retries with exponential backoff.
- Dead-letter queue visible in admin tooling.
- Idempotency keys on all sync jobs and webhook events.
- Metrics: sync lag, failed jobs, conflict count, webhook error rate.

## Security requirements
- OAuth tokens encrypted at rest.
- ICS feed token is random, revocable, and rotatable.
- Webhook signature verification enabled for Google and Microsoft.
- Principle of least privilege for OAuth scopes.

## Team split for 3 parallel AIs

### AI 1 - Backend sync core
- Files:
  - `backend/app/models/*` (new sync models)
  - `backend/alembic/versions/*` (schema)
  - `backend/app/services/calendar_sync_service.py`
  - `backend/app/workers/calendar_sync_worker.py`
- Deliverables:
  - outbox jobs
  - provider connections
  - unified availability merge

### AI 2 - Integrations + provider APIs
- Files:
  - `backend/app/integrations/google_calendar/*`
  - `backend/app/integrations/microsoft_calendar/*`
  - `backend/app/api/provider_calendar.py`
  - `backend/app/api/webhooks_calendar.py`
- Deliverables:
  - OAuth connect/disconnect
  - webhook ingestion
  - delta sync cursors

### AI 3 - Frontend + QA
- Files:
  - `frontend/src/personas/provider/settings/*`
  - `frontend/src/api/bookingApi.js`
  - E2E scripts in `scripts/`
- Deliverables:
  - connect calendar UI
  - sync status and error states
  - E2E matrix (create/reschedule/cancel + external edit)

## Rollout sequence
1. Google OAuth + push sync from booking service.
2. Google webhook/delta pull.
3. Outlook OAuth + webhook/delta pull.
4. ICS endpoint + token rotation.
5. Final QA and launch checks.

## Definition of done
- Provider can connect Google/Outlook from settings.
- Booking created in Fixmeapp appears in connected calendar within seconds.
- Booking moved/cancelled updates external calendar reliably.
- External calendar changes affect Fixmeapp availability in near real-time.
- AI bot and booking flow return identical availability for same provider/time window.
