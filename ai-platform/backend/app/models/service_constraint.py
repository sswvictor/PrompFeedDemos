"""ServiceConstraint — safety rules between services.

Examples:
  - min_days_between: bleach → keratin requires 14 days gap
  - cannot_combine: can't do botox and filler same day
  - requires_consultation: first-time botox needs consultation
"""
import uuid

from sqlalchemy import String, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ServiceConstraint(Base):
    __tablename__ = "service_constraints"

    constraint_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=False)
    service_id: Mapped[str] = mapped_column(String(36), ForeignKey("services.service_id"), nullable=False)
    constraint_type: Mapped[str] = mapped_column(String(50), nullable=False)  # min_days_between, cannot_combine, requires_consultation
    other_service_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("services.service_id"), nullable=True)
    min_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message_to_user: Mapped[str] = mapped_column(Text, default="")

    # Relationships
    service: Mapped["Service"] = relationship("Service", foreign_keys=[service_id])  # noqa: F821
