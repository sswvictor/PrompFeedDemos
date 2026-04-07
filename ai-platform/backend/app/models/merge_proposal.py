"""
MergeProposal — Identity stitching for multi-channel customers.

When the system detects that two customer records may be the same person
(e.g. same email from IG DM and walk-in), it creates a MergeProposal.

Match strength determines the flow:
  - strong  (same email or same IG handle):  auto-merged, customer notified
  - medium  (similar name + email domain):   proposal created, customer confirms
  - weak    (only name similarity):          logged internally, no action

The CUSTOMER confirms merges — not the provider. Providers never do manual
identity work. They just see one unified profile.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class MergeProposal(Base):
    __tablename__ = "merge_proposals"

    proposal_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=False)

    # The two customer records that might be the same person
    customer_a_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.customer_id"), nullable=False)
    customer_b_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.customer_id"), nullable=False)

    # How we matched them
    match_type: Mapped[str] = mapped_column(String(30), nullable=False)    # email, instagram, phone, name_similarity
    match_strength: Mapped[str] = mapped_column(String(20), nullable=False)  # strong, medium, weak
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)    # 0.0 - 1.0
    match_details: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: what fields matched, evidence

    # Status — customer decides
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, auto_merged, customer_approved, customer_denied
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Timestamps
    proposed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    provider: Mapped["Provider"] = relationship("Provider")  # noqa: F821
    customer_a: Mapped["Customer"] = relationship("Customer", foreign_keys=[customer_a_id])  # noqa: F821
    customer_b: Mapped["Customer"] = relationship("Customer", foreign_keys=[customer_b_id])  # noqa: F821
