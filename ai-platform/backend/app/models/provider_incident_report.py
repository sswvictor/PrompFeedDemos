import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ProviderIncidentReport(Base):
    __tablename__ = "provider_incident_reports"
    __table_args__ = (
        UniqueConstraint(
            "booking_id",
            "customer_id",
            "report_type",
            name="uq_provider_incident_report_booking_customer_type",
        ),
    )

    report_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id: Mapped[str] = mapped_column(String(36), ForeignKey("bookings.booking_id"), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.customer_id"), nullable=False)

    report_type: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    action_taken: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
