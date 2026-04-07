from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.calendar_event import CalendarEvent
from app.models.booking import Booking


class CalendarEventService:

    @staticmethod
    def create_mapping(
        db: Session,
        booking_id: str,
        provider_id: str,
        calendar_id: str = "primary",
    ) -> CalendarEvent:
        """Create a pending CalendarEvent mapping for a booking."""
        existing = db.query(CalendarEvent).filter(
            CalendarEvent.booking_id == booking_id
        ).first()
        if existing:
            return existing  # 1:1 — idempotent

        booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
        if not booking:
            raise ValueError(f"Booking {booking_id} not found")

        event = CalendarEvent(
            booking_id=booking_id,
            provider_id=provider_id,
            calendar_id=calendar_id,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def mark_synced(
        db: Session,
        calendar_event_id: str,
        external_event_id: str,
    ) -> CalendarEvent:
        """Update after successful Google Calendar API call."""
        event = db.query(CalendarEvent).filter(
            CalendarEvent.calendar_event_id == calendar_event_id
        ).first()
        if not event:
            raise ValueError(f"CalendarEvent {calendar_event_id} not found")

        event.external_event_id = external_event_id
        event.sync_status = "synced"
        event.last_synced_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def mark_failed(
        db: Session,
        calendar_event_id: str,
    ) -> CalendarEvent:
        event = db.query(CalendarEvent).filter(
            CalendarEvent.calendar_event_id == calendar_event_id
        ).first()
        if not event:
            raise ValueError(f"CalendarEvent {calendar_event_id} not found")

        event.sync_status = "failed"
        event.last_synced_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def mark_deleted(
        db: Session,
        calendar_event_id: str,
    ) -> CalendarEvent:
        event = db.query(CalendarEvent).filter(
            CalendarEvent.calendar_event_id == calendar_event_id
        ).first()
        if not event:
            raise ValueError(f"CalendarEvent {calendar_event_id} not found")

        event.sync_status = "deleted"
        event.last_synced_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def get_by_booking(db: Session, booking_id: str) -> CalendarEvent | None:
        return db.query(CalendarEvent).filter(
            CalendarEvent.booking_id == booking_id
        ).first()

    @staticmethod
    def get_pending(db: Session, provider_id: str) -> list[CalendarEvent]:
        """Get all pending events that need syncing."""
        return db.query(CalendarEvent).filter(
            CalendarEvent.provider_id == provider_id,
            CalendarEvent.sync_status == "pending",
        ).all()
