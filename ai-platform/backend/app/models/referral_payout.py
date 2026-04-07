import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, DateTime, Text, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ReferralPayout(Base):
    __tablename__ = "referral_payouts"
    __table_args__ = (
        UniqueConstraint("provider_id", "period_start", "period_end", name="uq_referral_payout_period"),
    )

    payout_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    credits_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    amount_sek: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="SEK")

    # pending -> paid / failed / cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    auto_processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_transfer_id: Mapped[str | None] = mapped_column(String(120), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    provider: Mapped["Provider"] = relationship("Provider")  # noqa: F821
