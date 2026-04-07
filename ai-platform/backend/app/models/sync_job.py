import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class SyncJob(Base):
    __tablename__ = "sync_jobs"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_sync_job_idempotency"),)

    job_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=False)
    connection_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("provider_calendar_connections.connection_id"),
        nullable=True,
    )
    booking_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("bookings.booking_id"), nullable=True)

    job_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    provider: Mapped["Provider"] = relationship("Provider")  # noqa: F821
    connection: Mapped["ProviderCalendarConnection | None"] = relationship("ProviderCalendarConnection")  # noqa: F821
    booking: Mapped["Booking | None"] = relationship("Booking")  # noqa: F821