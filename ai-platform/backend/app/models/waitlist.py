import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class WaitlistEntry(Base):
    """A customer's place in the waitlist queue for a provider."""

    __tablename__ = "waitlist_entries"

    entry_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    provider_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("providers.provider_id"), nullable=False, index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.user_id"), nullable=True
    )
    customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.customer_id"), nullable=True
    )
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    service_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("services.service_id"), nullable=True
    )

    # Preferences: which days and hours the customer wants
    # preferred_days stored as JSON string, e.g. "[0,1,2,3,4]" (Mon=0, Sun=6)
    preferred_days: Mapped[str] = mapped_column(Text, nullable=False)
    preferred_earliest_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    preferred_latest_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=18)

    # active = waiting | fulfilled = got a booking | cancelled = removed themselves
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    offers: Mapped[list["WaitlistOffer"]] = relationship(back_populates="entry")


class WaitlistOffer(Base):
    """A time-limited offer sent to a waitlisted customer when a slot opens."""

    __tablename__ = "waitlist_offers"

    offer_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    entry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("waitlist_entries.entry_id"), nullable=False, index=True
    )
    provider_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("providers.provider_id"), nullable=False
    )

    # Security: random secret required to accept/decline (prevents URL guessing)
    offer_secret: Mapped[str] = mapped_column(
        String(64), nullable=False, default=lambda: secrets.token_hex(32)
    )

    # The freed slot being offered
    slot_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    slot_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # 10-minute acceptance window
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # pending = waiting for response | accepted | expired | declined
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    entry: Mapped["WaitlistEntry"] = relationship(back_populates="offers")

