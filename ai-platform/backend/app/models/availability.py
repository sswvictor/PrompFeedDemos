import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Availability(Base):
    """Provider's recurring weekly working hours.

    day_of_week: 0=Monday ... 6=Sunday
    start_minutes / end_minutes: minutes from midnight (e.g. 540 = 09:00, 1020 = 17:00)
    """
    __tablename__ = "availability"

    availability_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Mon, 6=Sun
    start_minutes: Mapped[int] = mapped_column(Integer, nullable=False)  # minutes from midnight
    end_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    provider: Mapped["Provider"] = relationship("Provider", back_populates="availability_slots")  # noqa: F821


class AvailabilityOverride(Base):
    """One-off date overrides: days off, special hours, holidays."""
    __tablename__ = "availability_overrides"

    override_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # The specific date
    is_closed: Mapped[bool] = mapped_column(default=False)  # True = day off
    start_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Custom hours if not closed
    end_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    provider: Mapped["Provider"] = relationship("Provider", back_populates="availability_overrides")  # noqa: F821
