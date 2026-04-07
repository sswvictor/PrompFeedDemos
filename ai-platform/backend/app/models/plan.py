"""
Plan — defines available subscription tiers (free, pro).

Rows are seeded via migration and never created at runtime.
The plan_id is a human-readable slug ("free", "pro") so it
can be referenced directly in code without FK lookups.
"""
import json
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Plan(Base):
    __tablename__ = "plans"

    plan_id: Mapped[str] = mapped_column(String(20), primary_key=True)  # "free" | "pro"
    name: Mapped[str] = mapped_column(String(50), nullable=False)        # "Free" | "Pro"
    price_sek: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # monthly, 0 for free
    stripe_price_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # JSON array of feature key strings, e.g. ["bot_personalization", "priority_support"]
    features_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    subscriptions: Mapped[list["Subscription"]] = relationship(  # noqa: F821
        "Subscription", back_populates="plan"
    )

    @property
    def features(self) -> list[str]:
        return json.loads(self.features_json)

    def __repr__(self) -> str:
        return f"<Plan {self.plan_id} ({self.price_sek} SEK/mo)>"
