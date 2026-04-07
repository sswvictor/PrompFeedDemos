import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("provider_id", "customer_number", name="uq_provider_customer_number"),
    )

    customer_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.user_id"), nullable=True)
    instagram_username_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Identity & Profile fields ──
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_channel: Mapped[str | None] = mapped_column(String(50), nullable=True)  # instagram_dm, walkin, app, chatgpt_operator

    # ── Merge tracking ──
    merge_status: Mapped[str] = mapped_column(String(20), default="primary")  # primary | merged
    merged_into_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("customers.customer_id"), nullable=True)

    # ── Consent ──
    consent_preferences: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON blob for future consent tracking

    # Relationships
    provider: Mapped["Provider"] = relationship("Provider", back_populates="customers")  # noqa: F821
    user: Mapped["User | None"] = relationship("User", back_populates="customers")  # noqa: F821
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="customer")  # noqa: F821
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="customer")  # noqa: F821
    instagram_identities: Mapped[list["InstagramIdentity"]] = relationship("InstagramIdentity", back_populates="customer")  # noqa: F821
    preferences: Mapped[list["CustomerPreference"]] = relationship("CustomerPreference", back_populates="customer", cascade="all, delete-orphan")  # noqa: F821
    merged_from: Mapped[list["Customer"]] = relationship("Customer", back_populates="merged_into", remote_side="Customer.customer_id")  # noqa: F821
    merged_into: Mapped["Customer | None"] = relationship("Customer", back_populates="merged_from", remote_side=[merged_into_id])  # noqa: F821
