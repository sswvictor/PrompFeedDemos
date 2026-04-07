# Admin V1 (Fixmeapp)

## Scope
Admin V1 is an internal operations surface for:
- global search across users/providers/bookings
- booking edits and manual booking creation
- manual account creation (customer/provider/salon)
- provider/customer level inspection
- immutable admin audit log
- existing verification queue and GDPR queue

## Frontend menu routes
- `/admin` (redirects to operations)
- `/admin/operations`
- `/admin/bookings`
- `/admin/accounts`
- `/admin/levels`
- `/admin/audit`
- `/admin/verifications`
- `/admin/gdpr-requests`

## Backend admin endpoints
Existing:
- `GET /api/v1/admin/verifications`
- `POST /api/v1/admin/verifications/{id}/approve`
- `POST /api/v1/admin/verifications/{id}/reject`
- `GET /api/v1/admin/verifications/stats`
- `GET /api/v1/admin/gdpr-requests`
- `PATCH /api/v1/admin/gdpr-requests/{id}`
- `GET /api/v1/admin/gdpr-requests/stats`

New V1:
- `GET /api/v1/admin/search`
- `GET /api/v1/admin/users/{user_id}`
- `PATCH /api/v1/admin/users/{user_id}`
- `GET /api/v1/admin/providers/{provider_id}`
- `PATCH /api/v1/admin/providers/{provider_id}`
- `GET /api/v1/admin/bookings`
- `PATCH /api/v1/admin/bookings/{booking_id}`
- `POST /api/v1/admin/bookings/manual`
- `POST /api/v1/admin/accounts/manual`
- `GET /api/v1/admin/level/{actor_type}/{actor_id}`
- `GET /api/v1/admin/audit-logs`

## Security
All endpoints require X-Admin-Token matching ADMIN_SECRET_TOKEN.

Identity header: X-Admin-Actor (admin email) is now used for role resolution.

Super admin allowlist:
- env var ADMIN_SUPER_ADMINS (comma separated emails)
- default includes johanna@fixmeapp.ai`n
POST /admin/accounts/manual and POST /admin/bookings/manual require super_admin.

## Audit log
Every admin mutating action writes to `admin_audit_logs`.
Columns include:
- `admin_actor`
- `action`
- `entity_type`
- `entity_id`
- `reason`
- `before_json`
- `after_json`
- `metadata_json`
- `created_at`

## Notes
- Manual account creation creates a shell account only; user signs in with normal OTP flow.
- Manual booking creation can create a linked user/customer record if missing.

