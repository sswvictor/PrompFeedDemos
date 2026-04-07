import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class CalendarEvent(Base):
    """Maps a Booking to a Google Calendar event for sync."""
    __tablename__ = "calendar_events"
    __table_args__ = (
        UniqueConstraint("booking_id", name="uq_calendar_booking"),
        UniqueConstraint("provider_id", "external_event_id", name="uq_provider_external_event"),
    )

    calendar_event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id: Mapped[str] = mapped_column(String(36), ForeignKey("bookings.booking_id"), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=False)
    calendar_id: Mapped[str] = mapped_column(String(255), default="primary")  # GCal calendar ID
    external_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Google event ID
    sync_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/synced/failed/deleted
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    booking: Mapped["Booking"] = relationship("Booking", back_populates="calendar_event")  # noqa: F821
    provider: Mapped["Provider"] = relationship("Provider", back_populates="calendar_events")  # noqa: F821
