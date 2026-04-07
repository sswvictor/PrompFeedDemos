import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, DateTime, Text, ForeignKey, UniqueConstraint  # noqa: F401
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        UniqueConstraint("provider_id", "booking_number", name="uq_provider_booking_number"),
    )

    booking_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.customer_id"), nullable=False)
    booking_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/confirmed/completed/cancelled
    scheduled_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    actual_start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actual_end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_amount_ex_vat: Mapped[float] = mapped_column(Float, default=0.0)
    total_vat_amount: Mapped[float] = mapped_column(Float, default=0.0)
    total_amount_inc_vat: Mapped[float] = mapped_column(Float, default=0.0)
    customer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_walkin: Mapped[bool | None] = mapped_column(default=False)
    session_preferences: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list e.g. ["quiet_session","coffee_please"]
    referral_source: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "provider_link", "instagram", "qr_code"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Running-late notification ──
    # Set when a customer taps "I'm running late" — provider sees it as an alert on their home screen.
    late_notification_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    late_notification_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    provider: Mapped["Provider"] = relationship("Provider", back_populates="bookings")  # noqa: F821
    customer: Mapped["Customer"] = relationship("Customer", back_populates="bookings")  # noqa: F821
    line_items: Mapped[list["BookingLineItem"]] = relationship("BookingLineItem", back_populates="booking", cascade="all, delete-orphan")
    invoice: Mapped["Invoice | None"] = relationship("Invoice", back_populates="booking", uselist=False)  # noqa: F821
    calendar_event: Mapped["CalendarEvent | None"] = relationship("CalendarEvent", back_populates="booking", uselist=False)  # noqa: F821


class BookingLineItem(Base):
    __tablename__ = "booking_line_items"

    booking_item_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id: Mapped[str] = mapped_column(String(36), ForeignKey("bookings.booking_id"), nullable=False)
    service_type: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price_ex_vat: Mapped[float] = mapped_column(Float, nullable=False)
    vat_percent: Mapped[float] = mapped_column(Float, nullable=False)
    total_line_ex_vat: Mapped[float] = mapped_column(Float, default=0.0)
    total_line_vat: Mapped[float] = mapped_column(Float, default=0.0)
    total_line_inc_vat: Mapped[float] = mapped_column(Float, default=0.0)

    # Relationships
    booking: Mapped["Booking"] = relationship("Booking", back_populates="line_items")
