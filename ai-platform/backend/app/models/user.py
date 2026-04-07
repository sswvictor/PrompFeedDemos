import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, Text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    instagram_user_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    instagram_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/paused/cancelled
    is_provider: Mapped[bool] = mapped_column(Boolean, default=False)
    is_customer: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Profile ──
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── Onboarding preferences (JSON arrays) ──
    service_interests: Mapped[str | None] = mapped_column(Text, nullable=True)       # e.g. '["hair","nails","spa"]'
    lifestyle_preferences: Mapped[str | None] = mapped_column(Text, nullable=True)   # e.g. '["bring_dog","coffee","hijab_friendly"]'
    favorite_provider_ids: Mapped[str | None] = mapped_column(Text, nullable=True)   # e.g. '["provider_id_1","provider_id_2"]'

    # ── Extended identity ──
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)        # real legal name — visible only to booked providers (GDPR)
    preferred_locations: Mapped[str | None] = mapped_column(Text, nullable=True)     # e.g. '["Gym - Hammarby","Office near Slussen"]' — AI booking context

    # ── Privacy ──
    is_profile_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())

    # Relationships
    provider: Mapped["Provider | None"] = relationship("Provider", back_populates="user", uselist=False)  # noqa: F821
    customers: Mapped[list["Customer"]] = relationship("Customer", back_populates="user")  # noqa: F821
    instagram_identities: Mapped[list["InstagramIdentity"]] = relationship("InstagramIdentity", back_populates="user")  # noqa: F821
    conversations: Mapped[list["Conversation"]] = relationship("Conversation", back_populates="user")  # noqa: F821
    consent_records: Mapped[list["ConsentRecord"]] = relationship("ConsentRecord", back_populates="user")  # noqa: F821

