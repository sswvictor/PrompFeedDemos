"""
SalonLinkRequest — approval workflow for chair renters / freelancers joining a salon.

When a freelancer or chair renter selects a salon during onboarding, a request
is created here with status "pending". The salon owner must approve it before
the relationship is activated (i.e. before parent_provider_id is set).

Status lifecycle:
    pending → approved   (owner accepted — parent_provider_id is written on the requester's Provider)
    pending → rejected   (owner declined — requester stays unlinked)
    approved → removed   (either party ends the relationship later)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

# Status constants
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_REMOVED = "removed"


class SalonLinkRequest(Base):
    __tablename__ = "salon_link_requests"
    __table_args__ = (
        # Prevent duplicate pending requests for the same pair
        Index("ix_salon_link_unique_pending", "requester_provider_id", "salon_provider_id", unique=False),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # The freelancer / chair renter making the request
    requester_provider_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("providers.provider_id"), nullable=False
    )

    # The salon being requested to join
    salon_provider_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("providers.provider_id"), nullable=False
    )

    # "pending" | "approved" | "rejected" | "removed"
    status: Mapped[str] = mapped_column(String(20), default=STATUS_PENDING, nullable=False)

    # Optional message from the requester ("Hi, I've been renting chair 3 for 2 years")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional note from the salon owner when reviewing
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    requester: Mapped["Provider"] = relationship(  # noqa: F821
        "Provider", foreign_keys=[requester_provider_id]
    )
    salon: Mapped["Provider"] = relationship(  # noqa: F821
        "Provider", foreign_keys=[salon_provider_id]
    )
