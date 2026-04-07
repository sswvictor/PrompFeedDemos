from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.webhook_event import WebhookEvent


class WebhookService:

    @staticmethod
    def is_duplicate(
        db: Session,
        provider_id: str,
        platform: str,
        platform_event_id: str,
    ) -> bool:
        """Check if we already processed this webhook event."""
        return db.query(WebhookEvent).filter(
            WebhookEvent.provider_id == provider_id,
            WebhookEvent.platform == platform,
            WebhookEvent.platform_event_id == platform_event_id,
        ).first() is not None

    @staticmethod
    def record_event(
        db: Session,
        provider_id: str,
        platform: str,
        platform_event_id: str,
    ) -> WebhookEvent:
        """Record a new webhook event. Call before processing."""
        event = WebhookEvent(
            provider_id=provider_id,
            platform=platform,
            platform_event_id=platform_event_id,
            status="processing",
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def mark_processed(
        db: Session,
        event_id: str,
        error_detail: str | None = None,
    ) -> WebhookEvent:
        """Mark webhook event as processed or failed."""
        event = db.query(WebhookEvent).filter(
            WebhookEvent.event_id == event_id
        ).first()
        if not event:
            raise ValueError(f"WebhookEvent {event_id} not found")

        event.processed_at = datetime.now(timezone.utc)
        event.status = "failed" if error_detail else "processed"
        event.error_detail = error_detail
        db.commit()
        db.refresh(event)
        return event
