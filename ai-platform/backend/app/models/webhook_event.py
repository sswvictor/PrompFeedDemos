import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class WebhookEvent(Base):
    """Idempotency guard for inbound webhook payloads."""
    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("provider_id", "platform", "platform_event_id", name="uq_provider_platform_event"),
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)  # instagram, google_calendar
    platform_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="received")  # received/processing/processed/failed
    received_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    provider: Mapped["Provider"] = relationship("Provider", back_populates="webhook_events")  # noqa: F821
