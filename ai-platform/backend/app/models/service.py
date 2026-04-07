import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Service(Base):
    """A service offered by a provider (e.g. Haircut, Balayage, Nail Art)."""
    __tablename__ = "services"

    service_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)  # hair, nails, skin, etc.
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    price_ex_vat: Mapped[float] = mapped_column(Float, nullable=False)
    vat_percent: Mapped[float | None] = mapped_column(Float, nullable=True)  # Falls back to provider default
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    home_service_available: Mapped[bool] = mapped_column(Boolean, default=False)
    # Comma-separated alternative names the AI uses for matching customer requests.
    # e.g. "wash set, shampoo and set, wash and style"
    keywords: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    provider: Mapped["Provider"] = relationship("Provider", back_populates="services")  # noqa: F821
