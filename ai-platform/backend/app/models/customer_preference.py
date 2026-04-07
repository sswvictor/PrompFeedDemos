"""
CustomerPreference — AI-learned and manual insights about a customer.

Each preference is a key-value pair with approval status:
  - approved:  visible to provider, confirmed by customer (or auto-approved for safe categories)
  - pending:   learned by AI but awaiting customer confirmation (health/personal)
  - denied:    customer explicitly rejected this insight — hidden from provider
  - archived:  outdated or replaced by newer insight

Categories determine default approval behavior:
  - service_preference:  auto-approved  (e.g. "Likes gel over acrylic")
  - scheduling_pattern:  auto-approved  (e.g. "Books every 3 weeks")
  - allergy_sensitivity: pending        (e.g. "Sensitive to certain adhesives")
  - personal:            pending        (e.g. "Mentioned skin condition")
  - communication:       auto-approved  (e.g. "Prefers Swedish language")
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

# Categories that are auto-approved (low sensitivity)
AUTO_APPROVE_CATEGORIES = {"service_preference", "scheduling_pattern", "communication"}

# Categories that require customer confirmation (higher sensitivity)
PENDING_CATEGORIES = {"allergy_sensitivity", "personal", "health_signal"}


class CustomerPreference(Base):
    __tablename__ = "customer_preferences"

    preference_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.customer_id"), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=False)

    # What the preference is
    category: Mapped[str] = mapped_column(String(50), nullable=False)   # service_preference, scheduling_pattern, allergy_sensitivity, personal, communication
    key: Mapped[str] = mapped_column(String(128), nullable=False)       # e.g. "preferred_nail_style", "booking_frequency", "allergy_note"
    value: Mapped[str] = mapped_column(Text, nullable=False)            # e.g. "Minimalist designs, pink tones", "Every 3 weeks", "Sensitive to certain adhesives"

    # Where it came from
    source: Mapped[str] = mapped_column(String(30), nullable=False)     # ai_learned, manual, imported
    source_conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # which conversation the AI extracted this from

    # Approval status — customer controls this
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # approved, pending, denied, archived
    confidence: Mapped[float | None] = mapped_column(nullable=True)     # 0.0-1.0, AI confidence score

    # Timestamps
    learned_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # when customer approved/denied

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="preferences")  # noqa: F821
    provider: Mapped["Provider"] = relationship("Provider")  # noqa: F821
