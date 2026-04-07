import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from app.integrations.google_calendar import calendar_adapter
from app.models.booking import Booking
from app.models.external_calendar_event import ExternalCalendarEvent
from app.models.provider_calendar_connection import ProviderCalendarConnection
from app.models.sync_job import SyncJob


class CalendarSyncService:

    @staticmethod
    def list_connections(db: Session, provider_id: str) -> list[ProviderCalendarConnection]:
        return (
            db.query(ProviderCalendarConnection)
            .filter(ProviderCalendarConnection.provider_id == provider_id)
            .order_by(ProviderCalendarConnection.created_at.desc())
            .all()
        )

    @staticmethod
    def queue_sync_job(
        db: Session,
        provider_id: str,
        job_type: str,
        connection_id: str | None = None,
        booking_id: str | None = None,
        payload: dict | None = None,
        idempotency_key: str | None = None,
    ) -> SyncJob:
        key = idempotency_key or f"{job_type}:{provider_id}:{uuid.uuid4().hex[:12]}"
        existing = db.query(SyncJob).filter(SyncJob.idempotency_key == key).first()
        if existing:
            return existing

        job = SyncJob(
            provider_id=provider_id,
            connection_id=connection_id,
            booking_id=booking_id,
            job_type=job_type,
            payload_json=json.dumps(payload or {}, separators=(",", ":")),
            status="queued",
            attempt_count=0,
            next_run_at=datetime.now(timezone.utc),
            idempotency_key=key,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def disable_connection(db: Session, provider_id: str, connection_id: str) -> ProviderCalendarConnection | None:
        connection = (
            db.query(ProviderCalendarConnection)
            .filter(
                ProviderCalendarConnection.connection_id == connection_id,
                ProviderCalendarConnection.provider_id == provider_id,
            )
            .first()
        )
        if not connection:
            return None

        connection.sync_enabled = False
        connection.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(connection)
        return connection

    @staticmethod
    def upsert_connection(
        db: Session,
        provider_id: str,
        connector: str,
        external_account_id: str,
        external_calendar_id: str,
        display_name: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        token_expires_at: datetime | None = None,
    ) -> ProviderCalendarConnection:
        row = (
            db.query(ProviderCalendarConnection)
            .filter(
                ProviderCalendarConnection.provider_id == provider_id,
                ProviderCalendarConnection.connector == connector,
                ProviderCalendarConnection.external_calendar_id == external_calendar_id,
            )
            .first()
        )

        now = datetime.now(timezone.utc)
        if row:
            row.external_account_id = external_account_id
            row.display_name = display_name
            row.sync_enabled = True
            row.last_error = None
            row.updated_at = now
        else:
            row = ProviderCalendarConnection(
                provider_id=provider_id,
                connector=connector,
                external_account_id=external_account_id,
                external_calendar_id=external_calendar_id,
                display_name=display_name,
                sync_enabled=True,
                sync_direction="read_write",
                created_at=now,
                updated_at=now,
            )
            db.add(row)

        # Store OAuth tokens when provided (TODO: encrypt at rest)
        if access_token is not None:
            row.access_token_encrypted = access_token
        if refresh_token is not None:
            row.refresh_token_encrypted = refresh_token
        if token_expires_at is not None:
            row.token_expires_at = token_expires_at

        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def rotate_ics_token(db: Session, provider_id: str) -> tuple[ProviderCalendarConnection, str]:
        raw_token = secrets.token_urlsafe(30)
        hashed = CalendarSyncService._hash_token(raw_token)

        row = (
            db.query(ProviderCalendarConnection)
            .filter(
                ProviderCalendarConnection.provider_id == provider_id,
                ProviderCalendarConnection.connector == "ics",
            )
            .first()
        )

        now = datetime.now(timezone.utc)
        if row:
            row.access_token_encrypted = hashed
            row.refresh_token_encrypted = raw_token  # TODO: encrypt at rest
            row.sync_enabled = True
            row.sync_direction = "read_only"
            row.updated_at = now
            row.last_error = None
        else:
            row = ProviderCalendarConnection(
                provider_id=provider_id,
                connector="ics",
                external_account_id="ics-feed",
                external_calendar_id="feed",
                display_name="Fixmeapp iCal Feed",
                access_token_encrypted=hashed,
                refresh_token_encrypted=raw_token,
                sync_enabled=True,
                sync_direction="read_only",
                created_at=now,
                updated_at=now,
            )
            db.add(row)

        db.commit()
        db.refresh(row)
        return row, raw_token

    @staticmethod
    def get_ics_token(db: Session, provider_id: str) -> str | None:
        row = (
            db.query(ProviderCalendarConnection)
            .filter(
                ProviderCalendarConnection.provider_id == provider_id,
                ProviderCalendarConnection.connector == "ics",
                ProviderCalendarConnection.sync_enabled.is_(True),
            )
            .first()
        )
        if not row:
            return None
        return row.refresh_token_encrypted

    @staticmethod
    def verify_ics_token(db: Session, provider_id: str, token: str) -> bool:
        row = (
            db.query(ProviderCalendarConnection)
            .filter(
                ProviderCalendarConnection.provider_id == provider_id,
                ProviderCalendarConnection.connector == "ics",
                ProviderCalendarConnection.sync_enabled.is_(True),
            )
            .first()
        )
        if not row or not row.access_token_encrypted:
            return False
        return row.access_token_encrypted == CalendarSyncService._hash_token(token)

    @staticmethod
    def sync_google_connection(db: Session, connection: ProviderCalendarConnection) -> dict[str, int]:
        if connection.connector != "google":
            raise ValueError("Only google connector supports sync in this phase")

        # Require OAuth tokens — provider must have completed the Google connect flow
        access_token = connection.access_token_encrypted
        refresh_token = connection.refresh_token_encrypted
        if not access_token:
            connection.last_error = "No OAuth token stored. Provider must reconnect Google Calendar."
            connection.updated_at = datetime.now(timezone.utc)
            db.commit()
            return {"created": 0, "updated": 0, "deleted": 0, "failed": 0}

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        from_dt = now - timedelta(days=2)

        bookings = (
            db.query(Booking)
            .options(joinedload(Booking.customer), joinedload(Booking.line_items))
            .filter(
                Booking.provider_id == connection.provider_id,
                Booking.scheduled_end >= from_dt,
                Booking.status.in_(["pending", "confirmed", "cancelled"]),
            )
            .all()
        )

        mappings = (
            db.query(ExternalCalendarEvent)
            .filter(
                ExternalCalendarEvent.connection_id == connection.connection_id,
                ExternalCalendarEvent.provider_id == connection.provider_id,
            )
            .all()
        )
        map_by_booking = {m.booking_id: m for m in mappings if m.booking_id}

        created = 0
        updated = 0
        deleted = 0
        failed = 0

        for booking in bookings:
            service_name = booking.line_items[0].service_type if booking.line_items else "Appointment"
            customer_name = (
                (booking.customer.display_name if booking.customer else None)
                or (booking.customer.instagram_username_snapshot if booking.customer else None)
                or "Customer"
            )
            summary = f"{service_name} - {customer_name}"
            description = (
                f"Fixmeapp booking #{booking.booking_number}\\n"
                f"Booking ID: {booking.booking_id}\\n"
                f"Customer: {customer_name}"
            )

            mapping = map_by_booking.get(booking.booking_id)

            try:
                if booking.status == "cancelled":
                    if mapping and mapping.external_event_id and mapping.status != "cancelled":
                        ok, new_token = calendar_adapter.delete_event_with_token(
                            access_token, refresh_token,
                            connection.external_calendar_id, mapping.external_event_id,
                        )
                        if new_token:
                            connection.access_token_encrypted = new_token
                            access_token = new_token
                        if ok:
                            mapping.status = "cancelled"
                            mapping.updated_at = datetime.now(timezone.utc)
                            deleted += 1
                        else:
                            failed += 1
                    continue

                if mapping and mapping.external_event_id and mapping.status != "cancelled":
                    ok, new_token = calendar_adapter.update_event_with_token(
                        access_token, refresh_token,
                        calendar_id=connection.external_calendar_id,
                        event_id=mapping.external_event_id,
                        summary=summary,
                        start=booking.scheduled_start,
                        end=booking.scheduled_end,
                        description=description,
                    )
                    if new_token:
                        connection.access_token_encrypted = new_token
                        access_token = new_token
                    if ok:
                        mapping.start_at = booking.scheduled_start
                        mapping.end_at = booking.scheduled_end
                        mapping.status = "active"
                        mapping.source = "fixme_push"
                        mapping.updated_at = datetime.now(timezone.utc)
                        updated += 1
                    else:
                        failed += 1
                else:
                    external_id, new_token = calendar_adapter.create_event_with_token(
                        access_token, refresh_token,
                        calendar_id=connection.external_calendar_id,
                        summary=summary,
                        start=booking.scheduled_start,
                        end=booking.scheduled_end,
                        description=description,
                    )
                    if new_token:
                        connection.access_token_encrypted = new_token
                        access_token = new_token
                    if external_id:
                        new_map = ExternalCalendarEvent(
                            provider_id=connection.provider_id,
                            connection_id=connection.connection_id,
                            booking_id=booking.booking_id,
                            external_event_id=external_id,
                            start_at=booking.scheduled_start,
                            end_at=booking.scheduled_end,
                            status="active",
                            source="fixme_push",
                        )
                        db.add(new_map)
                        created += 1
                    else:
                        failed += 1
            except Exception:
                failed += 1

        connection.last_synced_at = datetime.now(timezone.utc)
        connection.last_error = None if failed == 0 else f"{failed} event(s) failed during sync"
        connection.updated_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "created": created,
            "updated": updated,
            "deleted": deleted,
            "failed": failed,
        }

