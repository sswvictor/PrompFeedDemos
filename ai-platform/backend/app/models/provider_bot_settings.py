"""
ProviderBotSettings — Pro-tier personalisation for the AI booking bot.

One row per provider (created on first save, null = use defaults).
Settings are preserved even after a subscription lapses so they
instantly re-activate when the provider renews.

Defaults (applied by the orchestrator when no row exists or plan != pro):
    bot_name              → None  (bot introduces itself as "your booking assistant")
    tone                  → "friendly"
    language              → "auto"  (detect from customer message)
    custom_welcome_message→ None  (use the platform default welcome)
    auto_confirm_bookings → True
    out_of_hours_behavior → "show_hours"
    max_advance_booking_days → None (no limit)
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

# Valid values for enum-like fields
TONE_OPTIONS = ("friendly", "formal", "casual")
LANGUAGE_OPTIONS = ("auto", "sv", "en")
OUT_OF_HOURS_OPTIONS = ("show_hours", "send_link")


class ProviderBotSettings(Base):
    __tablename__ = "provider_bot_settings"
    __table_args__ = (
        UniqueConstraint("provider_id", name="uq_bot_settings_provider"),
    )

    settings_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    provider_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("providers.provider_id"), nullable=False
    )

    # ── Personality ──────────────────────────────────────────
    # Custom name shown in the bot's first message, e.g. "Hi, I'm Lisa 👋"
    bot_name: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Tone of voice applied to the system prompt
    tone: Mapped[str] = mapped_column(String(20), nullable=False, default="friendly")

    # Language: "auto" = detect from customer, "sv" = force Swedish, "en" = force English
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="auto")

    # ── Messaging ────────────────────────────────────────────
    # Replaces the default platform welcome sent on first message
    custom_welcome_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Booking behaviour ────────────────────────────────────
    # True = bookings land as "confirmed" immediately (default)
    # False = bookings land as "pending", provider must approve
    auto_confirm_bookings: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    # What the bot says when a customer messages outside working hours
    # "show_hours" = tell them opening hours and ask to come back
    # "send_link"  = send the web booking link so they can self-serve
    out_of_hours_behavior: Mapped[str] = mapped_column(
        String(20), nullable=False, default="show_hours"
    )

    # How many days ahead customers can book (None = unlimited)
    max_advance_booking_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<ProviderBotSettings provider={self.provider_id} tone={self.tone}>"
