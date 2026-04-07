"""
Provider shareable booking links, public profiles & referral stats.

Powers the viral growth loop:
  1. Provider gets a shareable booking link (auto-generated slug)
  2. Customers book through that link ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â referral_source is tracked
  3. Provider sees referral stats on their dashboard
  4. Public profile page drives organic SEO traffic

Routes:
    GET  /providers/me/booking-link          ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â get/generate my shareable link
    GET  /providers/by-slug/{slug}           ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â public: look up provider by slug
    GET  /providers/by-slug/{slug}/profile   ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â public: full profile (services, amenities, trust)
    GET  /providers/me/referral-stats        ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â how many bookings came from my link
    GET  /providers/search?q=...             ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â public: search salon owners by name (chair renter onboarding)
"""

import json
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from app.config import settings
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.auth import get_current_provider
from app.db.session import get_db
from app.models.availability import Availability
from app.models.booking import Booking
from app.models.provider import Provider
from app.models.service import Service
from app.models.provider_amenity import ProviderAmenity
from app.services.loyalty_service import LoyaltyService

router = APIRouter(tags=["provider-links"])


# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Schemas ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

class BookingLinkOut(BaseModel):
    slug: str
    booking_url: str       # Full shareable URL
    qr_value: str          # URL to encode in a QR code


class ReferralStatsOut(BaseModel):
    total_referred_bookings: int
    referred_this_month: int
    top_source: str | None   # e.g. "provider_link", "instagram"


class ProviderPublicOut(BaseModel):
    provider_id: str
    name: str
    city: str | None
    bio: str | None
    image_url: str | None
    slug: str | None
    rating: float
    review_count: int
    service_categories: str | None  # JSON
    currency: str = "SEK"

    model_config = {"from_attributes": True}


# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Full profile schemas ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

class ServicePublicOut(BaseModel):
    service_id: str
    name: str
    category: str | None
    description: str | None
    duration_minutes: int
    price_ex_vat: float
    home_service_available: bool

    model_config = {"from_attributes": True}


class TrustSignalsOut(BaseModel):
    rating: float
    review_count: int
    revisit_rate: float
    total_completed_bookings: int


class WorkingHoursOut(BaseModel):
    open: bool
    start: str | None = None
    end: str | None = None


class ProviderProfileOut(BaseModel):
    """Everything the public profile page needs in one call."""
    provider_id: str
    name: str
    city: str | None
    bio: str | None
    image_url: str | None
    ig_profile_picture_url: str | None = None
    instagram_username: str | None = None
    slug: str | None
    business_type: str | None
    price_level: int
    home_service: bool
    location_salon: str | None

    # Parsed categories
    categories: list[str]

    # Trust
    trust: TrustSignalsOut

    # Services grouped by category
    services: list[ServicePublicOut]

    # Amenity keys
    amenities: list[str]
    working_hours: dict[str, WorkingHoursOut]
    booking_policy: str | None = None
    cancellation_policy: str | None = None

    # Currency
    currency: str = "SEK"

    # Booking link
    booking_url: str

    # Followers & verification (new fields)
    fixmeapp_followers_count: int = 0
    ig_followers_count: int | None = None
    ig_following_count: int | None = None
    is_verified: bool = False

    loyalty_tier: str = "member"
    level_badge: str = "Member"


# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Slug helpers ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

def _slugify(text: str) -> str:
    """Convert text to a URL-friendly slug. Handles Swedish characters."""
    s = text.lower().strip()
    # Swedish ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ ASCII
    for src, dst in [("ÃƒÆ’Ã‚Â¥", "a"), ("ÃƒÆ’Ã‚Â¤", "a"), ("ÃƒÆ’Ã‚Â¶", "o"), ("ÃƒÆ’Ã‚Â¼", "u"), ("ÃƒÆ’Ã‚Â©", "e")]:
        s = s.replace(src, dst)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    s = re.sub(r"-+", "-", s)
    return s or "provider"


def _generate_unique_slug(db: Session, name: str, city: str | None = None) -> str:
    """Generate a unique slug, appending -2, -3, ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ on collision."""
    base = _slugify(name)
    if city:
        base += "-" + _slugify(city)
    slug = base
    counter = 2
    while db.query(Provider).filter(Provider.slug == slug).first():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def _ensure_slug(db: Session, provider: Provider) -> str:
    """Return provider's slug, generating one if they don't have one yet."""
    if provider.slug:
        return provider.slug
    slug = _generate_unique_slug(db, provider.name, provider.city)
    provider.slug = slug
    db.commit()
    return slug


def _booking_url(slug: str) -> str:
    """Build the shareable booking URL from provider slug.

    Uses settings.WEB_BOOKING_BASE_URL (from .env/env).
    Falls back to relative path when no base URL is configured.
    """
    base = (settings.WEB_BOOKING_BASE_URL or "").strip().rstrip("/")
    if not base:
        return f"/b/{slug}"
    return f"{base}/b/{slug}"


def _minutes_to_hhmm(value: int) -> str:
    hours = max(0, min(23, int(value) // 60))
    minutes = max(0, min(59, int(value) % 60))
    return f"{hours:02d}:{minutes:02d}"


def _build_working_hours(slots: list[Availability]) -> dict[str, WorkingHoursOut]:
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    hours: dict[str, WorkingHoursOut] = {
        day: WorkingHoursOut(open=False, start=None, end=None) for day in labels
    }
    for slot in slots:
        if slot.day_of_week < 0 or slot.day_of_week > 6:
            continue
        day = labels[slot.day_of_week]
        hours[day] = WorkingHoursOut(
            open=True,
            start=_minutes_to_hhmm(slot.start_minutes),
            end=_minutes_to_hhmm(slot.end_minutes),
        )
    return hours

# Routes -------------------------------------------------------------


class SalonSearchResult(BaseModel):
    provider_id: str
    name: str
    city: str | None
    slug: str | None
    image_url: str | None


@router.get("/providers/search", response_model=list[SalonSearchResult])
def search_salons(
    q: str = Query(..., min_length=2, description="Salon name search term"),
    db: Session = Depends(get_db),
):
    """
    Public search for salon/studio providers.
    Used by freelancers and chair renters to find a salon to link to during onboarding.
    """
    from app.models.provider import BUSINESS_TYPE_OWNER
    results = (
        db.query(Provider)
        .filter(
            Provider.business_type == BUSINESS_TYPE_OWNER,
            Provider.name.ilike(f"%{q}%"),
        )
        .limit(5)
        .all()
    )
    return [
        SalonSearchResult(
            provider_id=p.provider_id,
            name=p.name,
            city=p.city,
            slug=p.slug,
            image_url=p.image_url,
        )
        for p in results
    ]


@router.get("/providers/me/booking-link", response_model=BookingLinkOut)
def get_my_booking_link(
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """
    Return the provider's shareable booking link.
    Generates a slug on first call (lazy ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â no migration needed for existing providers).
    """
    provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    slug = _ensure_slug(db, provider)
    url = _booking_url(slug)

    return BookingLinkOut(slug=slug, booking_url=url, qr_value=url)


@router.get("/providers/by-slug/{slug}", response_model=ProviderPublicOut)
def get_provider_by_slug(slug: str, db: Session = Depends(get_db)):
    """Public endpoint ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â used by the web booking frontend when a customer visits /b/{slug}."""
    provider = db.query(Provider).filter(Provider.slug == slug).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.get("/providers/me/referral-stats", response_model=ReferralStatsOut)
def get_referral_stats(
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """How many bookings came through the provider's shareable link."""
    from datetime import datetime, timezone

    # Total referred bookings (any with a referral_source set)
    total = (
        db.query(func.count(Booking.booking_id))
        .filter(
            Booking.provider_id == provider_id,
            Booking.referral_source.isnot(None),
        )
        .scalar()
    ) or 0

    # This month
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month = (
        db.query(func.count(Booking.booking_id))
        .filter(
            Booking.provider_id == provider_id,
            Booking.referral_source.isnot(None),
            Booking.created_at >= month_start,
        )
        .scalar()
    ) or 0

    # Top source
    top = (
        db.query(Booking.referral_source, func.count(Booking.booking_id).label("cnt"))
        .filter(
            Booking.provider_id == provider_id,
            Booking.referral_source.isnot(None),
        )
        .group_by(Booking.referral_source)
        .order_by(func.count(Booking.booking_id).desc())
        .first()
    )

    return ReferralStatsOut(
        total_referred_bookings=total,
        referred_this_month=this_month,
        top_source=top[0] if top else None,
    )


@router.get("/providers/by-slug/{slug}/profile", response_model=ProviderProfileOut)
def get_provider_profile(slug: str, db: Session = Depends(get_db)):
    """
    Public endpoint ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â full provider profile for the /p/{slug} web page.
    Returns everything in one call: provider info, services, amenities, trust signals.
    Designed for SEO-friendly, Airbnb-style public profile pages.
    """
    provider = (
        db.query(Provider)
        .options(joinedload(Provider.services), joinedload(Provider.amenities), joinedload(Provider.availability_slots))
        .filter(Provider.slug == slug)
        .first()
    )
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    # Parse service categories from JSON
    categories: list[str] = []
    if provider.service_categories:
        try:
            categories = json.loads(provider.service_categories)
        except Exception:
            categories = []

    # Active services only
    services = [
        ServicePublicOut.model_validate(s)
        for s in provider.services
        if s.is_active
    ]

    # Amenity keys
    amenities = [a.amenity_key for a in provider.amenities if a.is_active]
    if provider.home_service and "home_visits" not in amenities:
        amenities.append("home_visits")

    working_hours = _build_working_hours(provider.availability_slots or [])

    # Trust signals
    trust = TrustSignalsOut(
        rating=provider.rating or 5.0,
        review_count=provider.review_count or 0,
        revisit_rate=provider.revisit_rate or 0.0,
        total_completed_bookings=provider.total_completed_bookings or 0,
    )

    # Booking link
    slug_val = _ensure_slug(db, provider)
    booking_url = _booking_url(slug_val)

    try:
        loyalty = LoyaltyService.get_actor_snapshot(db, actor_type="provider", actor_id=provider.provider_id)
        loyalty_tier = loyalty.tier
        level_badge = loyalty.level_badge
    except Exception:
        loyalty_tier = "member"
        level_badge = "Member"

    return ProviderProfileOut(
        provider_id=provider.provider_id,
        name=provider.name,
        city=provider.city,
        bio=provider.bio,
        image_url=provider.image_url,
        ig_profile_picture_url=getattr(provider, "ig_profile_picture_url", None),
        instagram_username=provider.instagram_username,
        slug=slug_val,
        business_type=provider.business_type,
        price_level=provider.price_level or 2,
        home_service=bool(provider.home_service),
        location_salon=provider.location_salon,
        categories=categories,
        trust=trust,
        services=services,
        amenities=amenities,
        working_hours=working_hours,
        booking_policy=provider.booking_policy,
        cancellation_policy=provider.cancellation_policy,
        currency=getattr(provider, "currency", None) or "SEK",
        booking_url=booking_url,
        fixmeapp_followers_count=getattr(provider, "fixmeapp_followers_count", 0) or 0,
        ig_followers_count=getattr(provider, "ig_followers_count", None),
        ig_following_count=getattr(provider, "ig_following_count", None),
        is_verified=bool(getattr(provider, "is_verified", False)),
        loyalty_tier=loyalty_tier,
        level_badge=level_badge,
    )


@router.get("/providers/{provider_id}/profile", response_model=ProviderProfileOut)
def get_provider_profile_by_id(provider_id: str, db: Session = Depends(get_db)):
    """
    Public endpoint — full provider profile looked up by provider_id.
    Mirrors /providers/by-slug/{slug}/profile but accepts the UUID directly.
    Used when a slug is not available (e.g. search results before slug is cached).
    """
    provider = (
        db.query(Provider)
        .options(joinedload(Provider.services), joinedload(Provider.amenities), joinedload(Provider.availability_slots))
        .filter(Provider.provider_id == provider_id)
        .first()
    )
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    categories: list[str] = []
    if provider.service_categories:
        try:
            categories = json.loads(provider.service_categories)
        except Exception:
            categories = []

    services = [
        ServicePublicOut.model_validate(s)
        for s in provider.services
        if s.is_active
    ]
    amenities = [a.amenity_key for a in provider.amenities if a.is_active]
    if provider.home_service and "home_visits" not in amenities:
        amenities.append("home_visits")

    working_hours = _build_working_hours(provider.availability_slots or [])
    trust = TrustSignalsOut(
        rating=provider.rating or 5.0,
        review_count=provider.review_count or 0,
        revisit_rate=provider.revisit_rate or 0.0,
        total_completed_bookings=provider.total_completed_bookings or 0,
    )
    slug_val = _ensure_slug(db, provider)
    booking_url = _booking_url(slug_val)

    try:
        loyalty = LoyaltyService.get_actor_snapshot(db, actor_type="provider", actor_id=provider.provider_id)
        loyalty_tier = loyalty.tier
        level_badge = loyalty.level_badge
    except Exception:
        loyalty_tier = "member"
        level_badge = "Member"

    return ProviderProfileOut(
        provider_id=provider.provider_id,
        name=provider.name,
        city=provider.city,
        bio=provider.bio,
        image_url=provider.image_url,
        ig_profile_picture_url=getattr(provider, "ig_profile_picture_url", None),
        instagram_username=provider.instagram_username,
        slug=slug_val,
        business_type=provider.business_type,
        price_level=provider.price_level or 2,
        home_service=bool(provider.home_service),
        location_salon=provider.location_salon,
        categories=categories,
        trust=trust,
        services=services,
        amenities=amenities,
        working_hours=working_hours,
        booking_policy=provider.booking_policy,
        cancellation_policy=provider.cancellation_policy,
        currency=getattr(provider, "currency", None) or "SEK",
        booking_url=booking_url,
        fixmeapp_followers_count=getattr(provider, "fixmeapp_followers_count", 0) or 0,
        ig_followers_count=getattr(provider, "ig_followers_count", None),
        ig_following_count=getattr(provider, "ig_following_count", None),
        is_verified=bool(getattr(provider, "is_verified", False)),
        loyalty_tier=loyalty_tier,
        level_badge=level_badge,
    )
