"""
ProviderFollow model — native Fixmeapp follow system.

A customer (or any user) follows a provider on the platform.
This is independent of Instagram followers — it tracks engagement
within Fixmeapp itself and feeds the growth/discovery strategy.

The denormalised `fixmeapp_followers_count` on the Provider model is
kept in sync by the follow/unfollow service layer (not here directly).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ProviderFollow(Base):
    __tablename__ = "provider_follows"

    follow_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # The customer who is following
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.customer_id"), nullable=False, index=True
    )

    # The provider being followed
    provider_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("providers.provider_id"), nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer")  # noqa: F821
    provider: Mapped["Provider"] = relationship("Provider")  # noqa: F821

    # A customer can only follow a provider once
    __table_args__ = (
        UniqueConstraint("customer_id", "provider_id", name="uq_provider_follow"),
    )
