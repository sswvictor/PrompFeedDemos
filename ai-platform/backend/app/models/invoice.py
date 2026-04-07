import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("provider_id", "invoice_number", name="uq_provider_invoice_number"),
    )

    invoice_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=False)
    booking_id: Mapped[str] = mapped_column(String(36), ForeignKey("bookings.booking_id"), unique=True, nullable=False)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.customer_id"), nullable=False)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invoice_number: Mapped[int] = mapped_column(Integer, nullable=False)
    issued_date: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    total_ex_vat: Mapped[float] = mapped_column(Float, default=0.0)
    total_vat: Mapped[float] = mapped_column(Float, default=0.0)
    total_inc_vat: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft/sent/paid

    # Relationships
    provider: Mapped["Provider"] = relationship("Provider", back_populates="invoices")  # noqa: F821
    booking: Mapped["Booking"] = relationship("Booking", back_populates="invoice")  # noqa: F821
    customer: Mapped["Customer"] = relationship("Customer", back_populates="invoices")  # noqa: F821
