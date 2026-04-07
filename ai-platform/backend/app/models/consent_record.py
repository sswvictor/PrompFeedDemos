"""
ConsentRecord — GDPR Article 7 / Article 9 consent audit trail.

Every consent given or withdrawn by a user is stored here as an immutable
append-only log. Records are never updated — withdrawal creates a new row
with withdrawn_at set, leaving the original grant row intact for the audit trail.

Consent types:
  marketplace_signals   — user agrees their anonymised activity feeds the
                          Merkle contribution pipeline (Art. 6(1)(a))
  health_data_processing — explicit consent for AI to detect and extract
                            health/beauty signals from conversations (Art. 9(2)(a))
  third_party_sharing   — user agrees anonymised signals may be sold to
                          third-party buyers via the marketplace (Art. 6(1)(a))

GDPR references:
  Art. 7  — conditions for consent (must be freely given, specific, informed)
  Art. 9  — special category data (health mentions require explicit consent)
  Art. 13 — information to be provided at collection time (version field)
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


CONSENT_TYPES = {
    "marketplace_signals",
    "health_data_processing",
    "third_party_sharing",
}


class ConsentRecord(Base):
    __tablename__ = "consent_records"
    __table_args__ = (
        # Fast lookup: all active consents for a user
        Index("ix_consent_user_type", "user_id", "consent_type"),
    )

    consent_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.user_id"), nullable=False
    )
    consent_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # see CONSENT_TYPES above

    # Grant
    given_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    channel: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # instagram_dm / web / app — how consent was collected
    version: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # privacy policy version at time of consent e.g. "2026-02"

    # Withdrawal — NULL means consent is still active
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    withdrawal_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="consent_records")  # noqa: F821

    @property
    def is_active(self) -> bool:
        return self.withdrawn_at is None
