"""
Subscription — tracks a provider's active billing plan.

One row per provider. Status mirrors Stripe subscription lifecycle.
On cancellation/lapse: status changes to "cancelled" or "past_due",
but the row is never deleted (needed for billing history).

Graceful downgrade: the bot continues running with default settings
when status != "active". Custom settings (ProviderBotSettings) are
preserved so they instantly re-activate on renewal.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("provider_id", name="uq_subscriptions_provider"),
    )

    subscription_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    provider_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("providers.provider_id"), nullable=False
    )
    plan_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("plans.plan_id"), nullable=False, default="free"
    )

    # Status mirrors Stripe: active | trialing | past_due | cancelled | paused
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    # Stripe references (null for free tier)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Billing period (populated from Stripe, null for free)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    plan: Mapped["Plan"] = relationship("Plan", back_populates="subscriptions")  # noqa: F821

    @property
    def is_active(self) -> bool:
        """True when the provider has a live paid subscription."""
        return self.status in ("active", "trialing")

    @property
    def is_pro(self) -> bool:
        return self.plan_id == "pro" and self.is_active

    def __repr__(self) -> str:
        return f"<Subscription provider={self.provider_id} plan={self.plan_id} status={self.status}>"
