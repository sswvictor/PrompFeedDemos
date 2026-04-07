import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ExternalCalendarEvent(Base):
    __tablename__ = "external_calendar_events"
    __table_args__ = (
        UniqueConstraint("connection_id", "external_event_id", name="uq_ext_event_connection"),
        UniqueConstraint("connection_id", "booking_id", name="uq_ext_event_booking"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=False)
    connection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("provider_calendar_connections.connection_id"),
        nullable=False,
    )
    booking_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("bookings.booking_id"), nullable=True)

    external_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_etag: Mapped[str | None] = mapped_column(String(255), nullable=True)

    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="fixme_push", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    provider: Mapped["Provider"] = relationship("Provider")  # noqa: F821
    connection: Mapped["ProviderCalendarConnection"] = relationship("ProviderCalendarConnection")  # noqa: F821
    booking: Mapped["Booking | None"] = relationship("Booking")  # noqa: F821