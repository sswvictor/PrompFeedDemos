"""
Application settings loaded from environment variables / .env file.

Reuses the same pattern as the bot project (pydantic-settings).
All sensitive values come from env; nothing is hardcoded.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Instagram / Meta
    INSTAGRAM_PAGE_ACCESS_TOKEN: str = ""
    INSTAGRAM_APP_ID: str = ""
    INSTAGRAM_APP_SECRET: str = ""
    INSTAGRAM_VERIFY_TOKEN: str = ""

    # Instagram OAuth (provider connect flow)
    INSTAGRAM_CLIENT_ID: str = ""
    INSTAGRAM_CLIENT_SECRET: str = ""
    INSTAGRAM_OAUTH_REDIRECT_URI: str = "http://127.0.0.1:8000/api/v1/instagram/connect/callback"
    INSTAGRAM_OAUTH_SCOPES: str = "pages_show_list,pages_manage_metadata,instagram_basic,instagram_manage_messages"
    INSTAGRAM_OAUTH_STATE_SECRET: str = ""

    # Official Fixmeapp IG relay Page (Facebook Page id = webhook recipient_id).
    # When set, startup upserts provider_instagram_pages with is_platform_page=True.
    PLATFORM_INSTAGRAM_PAGE_ID: str = ""
    PLATFORM_INSTAGRAM_PAGE_NAME: str = "fixmeapp"
    # Optional; defaults to INSTAGRAM_PAGE_ACCESS_TOKEN when empty.
    PLATFORM_INSTAGRAM_PAGE_ACCESS_TOKEN: str = ""

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Google Calendar (service account - for server-to-server)
    GOOGLE_CALENDAR_ID: str = "primary"
    GOOGLE_SERVICE_ACCOUNT_FILE: str = "service_account.json"

    # Google Calendar OAuth (per-provider OAuth2 flow)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:5174/provider/calendar/callback"

    # General
    DEFAULT_TIMEZONE: str = "Europe/Stockholm"
    DEMO_PROVIDER_EMAIL: str = "johanna@fixmeapp.ai"

    # Web booking flow base URL for generated links in Instagram DMs
    WEB_BOOKING_BASE_URL: str = "https://book.fixmeapp.ai"

    # Encryption for external provider tokens (Instagram etc.)
    TOKEN_ENCRYPTION_KEY: str = ""

    # Stripe
    STRIPE_SECRET_KEY: str = ""      # sk_live_... or sk_test_...
    STRIPE_WEBHOOK_SECRET: str = ""  # whsec_... from Stripe dashboard
    STRIPE_PRO_PRICE_ID: str = ""    # price_... Monthly Pro plan price ID

    # Referral credits and monthly payouts
    REFERRAL_CREDIT_SEK: float = 50.0
    REFERRAL_PAYOUT_DAY: int = 1
    REFERRAL_AUTO_PAYOUT_ENABLED: bool = True
    REFERRAL_AUTO_APPLY_TO_SUBSCRIPTION: bool = True
    REFERRAL_AUTO_MARK_PAID: bool = False

    # Ignore unknown keys in .env so legacy env files do not crash startup
    model_config = {
        "env_file": (".env", "../.env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()