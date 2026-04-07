"""
BotSettingsService — get and update provider bot personalisation (Pro feature).

All write operations require an active Pro subscription.
The service never checks the plan itself — the API route does that
and returns 403 before calling update(). This keeps the service layer
decoupled from billing logic.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.provider_bot_settings import (
    ProviderBotSettings,
    TONE_OPTIONS,
    LANGUAGE_OPTIONS,
    OUT_OF_HOURS_OPTIONS,
)

logger = logging.getLogger(__name__)

# Platform defaults — returned when no settings row exists
DEFAULT_SETTINGS = {
    "bot_name": None,
    "tone": "friendly",
    "language": "auto",
    "custom_welcome_message": None,
    "auto_confirm_bookings": True,
    "out_of_hours_behavior": "show_hours",
    "max_advance_booking_days": None,
}


class BotSettingsService:

    @staticmethod
    def get_settings(db: Session, provider_id: str) -> ProviderBotSettings | None:
        """Return the settings row, or None if not yet customised."""
        return db.query(ProviderBotSettings).filter(
            ProviderBotSettings.provider_id == provider_id
        ).first()

    @staticmethod
    def get_settings_dict(db: Session, provider_id: str) -> dict:
        """Return settings as a plain dict, falling back to platform defaults."""
        row = BotSettingsService.get_settings(db, provider_id)
        if not row:
            return {**DEFAULT_SETTINGS, "provider_id": provider_id}
        return {
            "provider_id": row.provider_id,
            "bot_name": row.bot_name,
            "tone": row.tone,
            "language": row.language,
            "custom_welcome_message": row.custom_welcome_message,
            "auto_confirm_bookings": row.auto_confirm_bookings,
            "out_of_hours_behavior": row.out_of_hours_behavior,
            "max_advance_booking_days": row.max_advance_booking_days,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def update_settings(db: Session, provider_id: str, updates: dict) -> ProviderBotSettings:
        """Create or update bot settings for a provider.

        Validates enum fields and returns the updated row.
        Caller must verify Pro subscription before calling this.
        """
        # Validate enum fields
        if "tone" in updates and updates["tone"] not in TONE_OPTIONS:
            raise ValueError(f"tone must be one of: {TONE_OPTIONS}")
        if "language" in updates and updates["language"] not in LANGUAGE_OPTIONS:
            raise ValueError(f"language must be one of: {LANGUAGE_OPTIONS}")
        if "out_of_hours_behavior" in updates and updates["out_of_hours_behavior"] not in OUT_OF_HOURS_OPTIONS:
            raise ValueError(f"out_of_hours_behavior must be one of: {OUT_OF_HOURS_OPTIONS}")
        if "max_advance_booking_days" in updates and updates["max_advance_booking_days"] is not None:
            days = updates["max_advance_booking_days"]
            if not isinstance(days, int) or days < 1 or days > 365:
                raise ValueError("max_advance_booking_days must be between 1 and 365")

        row = BotSettingsService.get_settings(db, provider_id)
        if not row:
            row = ProviderBotSettings(provider_id=provider_id)
            db.add(row)

        allowed_fields = {
            "bot_name", "tone", "language", "custom_welcome_message",
            "auto_confirm_bookings", "out_of_hours_behavior", "max_advance_booking_days",
        }
        for field, value in updates.items():
            if field in allowed_fields:
                setattr(row, field, value)

        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)

        logger.info("Bot settings updated for provider %s", provider_id)
        return row

    @staticmethod
    def reset_to_defaults(db: Session, provider_id: str) -> None:
        """Delete custom settings — bot reverts to platform defaults."""
        row = BotSettingsService.get_settings(db, provider_id)
        if row:
            db.delete(row)
            db.commit()
            logger.info("Bot settings reset for provider %s", provider_id)
