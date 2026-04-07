import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CustomerReliabilityReport(Base):
    __tablename__ = "customer_reliability_reports"
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "customer_id",
            "booking_id",
            "category",
            name="uq_customer_reliability_report_booking_category",
        ),
    )

    report_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.customer_id"), nullable=False)
    booking_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("bookings.booking_id"), nullable=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    admin_action_taken: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    admin_resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
