import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Boolean, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

# ── Supported ISO 4217 currency codes ─────────────────────────────────────────
SUPPORTED_CURRENCIES = frozenset([
    "SEK", "EUR", "USD", "GBP", "NOK", "DKK", "CHF", "PLN", "ISK",
    "CZK", "HUF", "RON", "BGN", "HRK", "TRY", "AUD", "CAD", "JPY",
    "KRW", "INR", "BRL", "MXN", "THB", "SGD", "NZD",
])

# Country → default currency mapping (ISO 3166-1 alpha-2 → ISO 4217)
_EUROZONE = frozenset([
    "FR", "DE", "IT", "ES", "NL", "BE", "AT", "IE", "FI", "PT", "GR",
    "MC", "LU", "MT", "CY", "EE", "LV", "LT", "SK", "SI", "HR",
])

COUNTRY_TO_CURRENCY: dict[str, str] = {
    "SE": "SEK", "NO": "NOK", "DK": "DKK",
    "US": "USD", "GB": "GBP", "CH": "CHF",
    "JP": "JPY", "IN": "INR", "AU": "AUD", "CA": "CAD",
    "NZ": "NZD", "SG": "SGD", "TH": "THB", "KR": "KRW",
    "BR": "BRL", "MX": "MXN", "PL": "PLN", "CZ": "CZK",
    "HU": "HUF", "RO": "RON", "BG": "BGN", "TR": "TRY",
    "IS": "ISK",
    **{c: "EUR" for c in _EUROZONE},
}


def currency_for_country(country_code: str) -> str:
    """Return ISO 4217 currency for a country code, defaulting to EUR."""
    return COUNTRY_TO_CURRENCY.get(country_code.upper().strip(), "EUR")


# ── Business type constants ────────────────────────────────────────────────────
BUSINESS_TYPE_OWNER = "owner"                # Owns the salon/studio — has staff or rents chairs out
BUSINESS_TYPE_FREELANCER = "freelancer"      # Works independently (mobile / own studio)
BUSINESS_TYPE_CHAIR_RENTER = "chair_renter"  # Rents a chair/booth at someone else's salon

# ── Service category slugs ─────────────────────────────────────────────────────
# Stored as JSON array in service_categories column, e.g. '["hair","nails"]'
CATEGORIES = [
    "hair",       # Hair & Styling
    "barber",     # Barbering
    "nails",      # Nails & Beauty
    "spa",        # Spa & Wellness
    "massage",    # Massage Therapy
    "fitness",    # Gym & Personal Training
    "makeup",     # Makeup Artist
    "skincare",   # Skincare & Aesthetics
    "lashes",     # Lashes & Brows
    "tattoo",     # Tattoo & Piercing
    "other",      # Other
]


class Provider(Base):
    __tablename__ = "providers"

    provider_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.user_id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    org_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vat_percent: Mapped[float] = mapped_column(Float, default=25.0)
    location_salon: Mapped[str | None] = mapped_column(String(255), nullable=True)
    home_service: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Business identity (set during onboarding) ─────────────────────────────
    # "owner" | "freelancer" | "chair_renter"  (see constants above)
    business_type: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # JSON array of category slugs, e.g. '["hair", "nails", "spa"]'
    service_categories: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Chair renters link to the salon they work at (self-referential FK)
    parent_provider_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("providers.provider_id"), nullable=True
    )

    # Instagram display username (convenience cache; full token data in ProviderInstagramPage)
    instagram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Instagram Graph API stats (cached at onboarding and refreshed periodically)
    ig_followers_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ig_following_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ig_profile_picture_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ig_stats_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # URL-friendly slug for shareable booking links (e.g., "sofia-nails-stockholm")
    slug: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True, index=True)

    # ── Feed / Discovery fields ──
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    booking_policy: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cancellation_policy: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price_level: Mapped[int] = mapped_column(Integer, default=2)  # 1=budget 2=normal 3=premium 4=luxury

    # ── Trust signals ──
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    revisit_rate: Mapped[float] = mapped_column(Float, default=0.0)    # 0.0-1.0, calculated from booking data
    total_completed_bookings: Mapped[int] = mapped_column(Integer, default=0)

    # Native Fixmeapp follower count (denormalised for fast reads; kept in sync by follow/unfollow service)
    fixmeapp_followers_count: Mapped[int] = mapped_column(Integer, default=0)

    # ── Business verification ──
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_country: Mapped[str | None] = mapped_column(String(2), nullable=True)   # ISO-3166 e.g. SE, US, IN
    verification_source: Mapped[str | None] = mapped_column(String(32), nullable=True)  # bolagsverket | gstin | opencorporates | screenshot

    # Relationships
    user: Mapped["User | None"] = relationship("User", back_populates="provider")  # noqa: F821
    customers: Mapped[list["Customer"]] = relationship("Customer", back_populates="provider")  # noqa: F821
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="provider")  # noqa: F821
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="provider")  # noqa: F821
    instagram_identities: Mapped[list["InstagramIdentity"]] = relationship("InstagramIdentity", back_populates="provider")  # noqa: F821
    services: Mapped[list["Service"]] = relationship("Service", back_populates="provider")  # noqa: F821
    availability_slots: Mapped[list["Availability"]] = relationship("Availability", back_populates="provider")  # noqa: F821
    availability_overrides: Mapped[list["AvailabilityOverride"]] = relationship("AvailabilityOverride", back_populates="provider")  # noqa: F821
    conversations: Mapped[list["Conversation"]] = relationship("Conversation", back_populates="provider")  # noqa: F821
    webhook_events: Mapped[list["WebhookEvent"]] = relationship("WebhookEvent", back_populates="provider")  # noqa: F821
    calendar_events: Mapped[list["CalendarEvent"]] = relationship("CalendarEvent", back_populates="provider")  # noqa: F821
    timeslot_holds: Mapped[list["TimeSlotHold"]] = relationship("TimeSlotHold", back_populates="provider")  # noqa: F821
    instagram_pages: Mapped[list["ProviderInstagramPage"]] = relationship("ProviderInstagramPage", back_populates="provider")  # noqa: F821
    workers: Mapped[list["Worker"]] = relationship("Worker", back_populates="provider", cascade="all, delete-orphan")  # noqa: F821
    amenities: Mapped[list["ProviderAmenity"]] = relationship("ProviderAmenity", back_populates="provider", cascade="all, delete-orphan")  # noqa: F821
    time_blocks: Mapped[list["ProviderTimeBlock"]] = relationship("ProviderTimeBlock", back_populates="provider", cascade="all, delete-orphan")  # noqa: F821

    # ── Currency ──
    # ISO 4217 code — canonical pricing currency for all services, bookings, invoices
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="SEK")

    # ── Mobile push notifications ──
    # Expo push token from the provider's mobile device (ExponentPushToken[...])
    # Single token — providers use one primary device
    push_token: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Self-referential: salon owner ←→ chair renters
    chair_renters: Mapped[list["Provider"]] = relationship(
        "Provider",
        foreign_keys=[parent_provider_id],
        back_populates="parent_salon",
        uselist=True,
    )
    parent_salon: Mapped["Provider | None"] = relationship(
        "Provider",
        foreign_keys=[parent_provider_id],
        back_populates="chair_renters",
        remote_side=[provider_id],
    )
