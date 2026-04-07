"""
Customer Dashboard API

Endpoints for authenticated customers:
- GET /customer/me/dashboard
- GET /customer/me/preferences
- PUT /customer/me/preferences
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.booking import Booking
from app.models.customer import Customer
from app.models.provider import Provider
from app.models.provider_incident_report import ProviderIncidentReport
from app.models.provider_follow import ProviderFollow
from app.models.user import User
from app.services.customer_reliability_service import CustomerReliabilityService
from app.services.loyalty_service import LoyaltyService
from app.utils.jwt_token import decode_access_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/customer/me", tags=["customer-dashboard"])
security = HTTPBearer()


ALLOWED_SERVICE_INTERESTS = {
    "hair",
    "nails",
    "spa",
    "massage",
    "barber",
    "lashes",
    "brows",
    "makeup",
    "skincare",
    "waxing",
}

ALLOWED_LIFESTYLE_PREFERENCES = {
    "bring_dog",
    "coffee",
    "hijab_friendly",
    "private_room",
    "eco_products",
    "bringing_child",
    "quiet_session",
    "accessible",
    "wine_please",
    "pay_by_card",
}

MAX_FAVORITE_PROVIDERS = 8
ALLOWED_PROVIDER_CATEGORIES = {
    "hair",
    "barber",
    "nails",
    "spa",
    "massage",
    "lashes",
    "brows",
    "makeup",
    "skincare",
    "waxing",
    "fitness",
    "tattoo",
    "other",
}
PROVIDER_CATEGORY_ALIASES = {
    "brow": "brows",
    "skin": "skincare",
    "wellness": "spa",
}


def get_current_customer_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Extract user_id from a valid customer JWT token."""
    try:
        payload = decode_access_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user ID",
        )

    roles = payload.get("role", [])
    if "customer" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer access required.",
        )

    return user_id


class CustomerBookingOut(BaseModel):
    booking_id: str
    booking_number: int
    provider_name: str
    provider_image_url: str | None = None
    provider_slug: str | None = None
    service_name: str
    scheduled_start: str
    scheduled_end: str
    status: str
    customer_notes: str | None = None
    provider_id: str


class FrequentServiceOut(BaseModel):
    service_name: str
    count: int
    last_scheduled_start: str


class FollowedProviderOut(BaseModel):
    provider_id: str
    name: str
    image_url: str | None = None
    slug: str | None = None
    city: str | None = None
    instagram_username: str | None = None
    rating: float | None = None
    service_categories: list[str] = Field(default_factory=list)


class CustomerDashboardOut(BaseModel):
    user_id: str
    display_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    image_url: str | None = None
    upcoming_bookings: list[CustomerBookingOut]
    past_bookings: list[CustomerBookingOut]
    frequent_services: list[FrequentServiceOut] = Field(default_factory=list)
    followed_providers: list[FollowedProviderOut] = Field(default_factory=list)
    favorite_provider_ids: list[str] = Field(default_factory=list)
    favorite_providers: list[FollowedProviderOut] = Field(default_factory=list)
    following_count: int = 0
    followers_count: int = 0
    reliability_score: float = 0.0
    reliability_tier: str = "new"
    reliability_confidence: float = 0.0
    reliability_breakdown: dict[str, float] = Field(default_factory=dict)
    reliability_reports_count: int = 0
    loyalty_score: int = 0
    loyalty_tier: str = "member"
    level_badge: str = "Member"
    is_profile_public: bool = True
    preferred_locations: list[str] = Field(default_factory=list)


class UpdateProfileIn(BaseModel):
    is_profile_public: bool | None = None
    display_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    preferred_locations: list[str] | None = None


class UpdatePreferencesIn(BaseModel):
    service_interests: list[str] = Field(default_factory=list)
    lifestyle_preferences: list[str] = Field(default_factory=list)


class UpdatePreferencesOut(BaseModel):
    service_interests: list[str]
    lifestyle_preferences: list[str]


class UpdateFavoritesIn(BaseModel):
    provider_ids: list[str] = Field(default_factory=list)


class UpdateFavoritesOut(BaseModel):
    provider_ids: list[str]


def _json_array_from_text(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if isinstance(item, str)]


def _clean_preferences(
    values: list[str],
    allowed: set[str],
    field_name: str,
    *,
    fail_on_unknown: bool = True,
) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    unknown: list[str] = []

    for raw in values:
        key = str(raw).strip().lower()
        if not key:
            continue
        if key not in allowed:
            unknown.append(key)
            continue
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(key)

    if unknown and fail_on_unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported {field_name}: {', '.join(sorted(set(unknown)))}",
        )

    if unknown and not fail_on_unknown:
        logger.info("Dropped unknown %s values for customer payload: %s", field_name, sorted(set(unknown)))

    return cleaned




def _clean_provider_ids(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()

    for raw in values:
        key = str(raw).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned.append(key)

    if len(cleaned) > MAX_FAVORITE_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"You can select at most {MAX_FAVORITE_PROVIDERS} favorite providers.",
        )

    return cleaned


def _clean_provider_categories(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()

    for raw in values:
        key = str(raw).strip().lower()
        if not key:
            continue

        key = PROVIDER_CATEGORY_ALIASES.get(key, key)
        if key not in ALLOWED_PROVIDER_CATEGORIES:
            continue
        if key in seen:
            continue

        seen.add(key)
        cleaned.append(key)

    return cleaned


def _get_customer_ids_for_user(db: Session, user_id: str) -> list[str]:
    return [
        c.customer_id
        for c in db.query(Customer.customer_id)
        .filter(Customer.user_id == user_id)
        .all()
    ]


def _get_followed_providers_for_customer_ids(db: Session, customer_ids: list[str]) -> list[FollowedProviderOut]:
    if not customer_ids:
        return []

    rows = (
        db.query(ProviderFollow, Provider)
        .join(Provider, Provider.provider_id == ProviderFollow.provider_id)
        .filter(ProviderFollow.customer_id.in_(customer_ids))
        .order_by(ProviderFollow.followed_at.asc())
        .all()
    )

    seen: set[str] = set()
    result: list[FollowedProviderOut] = []
    for _, provider in rows:
        if provider.provider_id in seen:
            continue
        seen.add(provider.provider_id)
        result.append(
            FollowedProviderOut(
                provider_id=provider.provider_id,
                name=provider.name,
                image_url=provider.ig_profile_picture_url or provider.image_url,
                slug=provider.slug,
                city=provider.city,
                instagram_username=provider.instagram_username,
                rating=float(provider.rating) if provider.rating is not None else None,
                service_categories=_clean_provider_categories(
                    _json_array_from_text(getattr(provider, "service_categories", None))
                ),
            )
        )
    return result


def _get_frequent_services(bookings: list[Booking]) -> list[FrequentServiceOut]:
    eligible_statuses = {"pending", "confirmed", "completed"}
    service_map: dict[str, dict[str, int | datetime]] = {}

    for booking in bookings:
        if booking.status not in eligible_statuses:
            continue

        service_name = booking.line_items[0].service_type if booking.line_items else "Appointment"
        existing = service_map.get(service_name)
        if existing is None:
            service_map[service_name] = {"count": 1, "last": booking.scheduled_start}
            continue

        existing["count"] = int(existing["count"]) + 1
        if booking.scheduled_start > existing["last"]:
            existing["last"] = booking.scheduled_start

    sortable_rows: list[tuple[str, int, datetime]] = []
    for service_name, data in service_map.items():
        sortable_rows.append((service_name, int(data["count"]), data["last"]))

    sortable_rows.sort(key=lambda row: (row[1], row[2]), reverse=True)

    return [
        FrequentServiceOut(
            service_name=service_name,
            count=count,
            last_scheduled_start=last_scheduled_start.isoformat(),
        )
        for service_name, count, last_scheduled_start in sortable_rows[:6]
    ]


@router.post("/bookings/{booking_id}/cancel", status_code=200)
def cancel_customer_booking(
    booking_id: str,
    user_id: str = Depends(get_current_customer_user_id),
    db: Session = Depends(get_db),
):
    """Cancel an upcoming booking that belongs to the authenticated customer."""
    # Resolve the customer_ids that belong to this user
    customer_ids = [
        c.customer_id
        for c in db.query(Customer.customer_id).filter(Customer.user_id == user_id).all()
    ]
    if not customer_ids:
        raise HTTPException(status_code=404, detail="Booking not found")

    booking = (
        db.query(Booking)
        .filter(Booking.booking_id == booking_id, Booking.customer_id.in_(customer_ids))
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status == "cancelled":
        raise HTTPException(status_code=400, detail="Booking is already cancelled")

    if booking.status == "completed":
        raise HTTPException(status_code=400, detail="Completed bookings cannot be cancelled")

    booking.status = "cancelled"
    db.commit()
    logger.info("Customer %s cancelled booking %s", user_id, booking_id)
    return {"booking_id": booking_id, "status": "cancelled"}


class RunningLateIn(BaseModel):
    minutes: int = Field(..., ge=1, le=120, description="How many minutes late the customer will be")


@router.post("/bookings/{booking_id}/running-late", status_code=200)
def send_running_late(
    booking_id: str,
    payload: RunningLateIn,
    user_id: str = Depends(get_current_customer_user_id),
    db: Session = Depends(get_db),
):
    """Record that a customer is running late and store the notification on the booking."""
    customer_ids = [
        c.customer_id
        for c in db.query(Customer.customer_id).filter(Customer.user_id == user_id).all()
    ]
    if not customer_ids:
        raise HTTPException(status_code=404, detail="Booking not found")

    booking = (
        db.query(Booking)
        .filter(Booking.booking_id == booking_id, Booking.customer_id.in_(customer_ids))
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status not in ("pending", "confirmed"):
        raise HTTPException(status_code=400, detail="Can only send running-late for upcoming bookings")

    booking.late_notification_minutes = payload.minutes
    booking.late_notification_sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    logger.info("Customer %s is running %d min late for booking %s", user_id, payload.minutes, booking_id)
    return {"booking_id": booking_id, "late_minutes": payload.minutes}



class ProviderIncidentReportIn(BaseModel):
    report_type: str = Field(..., description="no_show_provider | unsafe_behavior | policy_violation | other")
    severity: int = Field(default=1, ge=1, le=3)
    details: str | None = None


_ALLOWED_PROVIDER_REPORT_TYPES = {
    "no_show_provider",
    "unsafe_behavior",
    "policy_violation",
    "other",
}


@router.post("/bookings/{booking_id}/report", status_code=201)
def report_provider_incident(
    booking_id: str,
    payload: ProviderIncidentReportIn,
    user_id: str = Depends(get_current_customer_user_id),
    db: Session = Depends(get_db),
):
    """Customer reports a provider incident for a booking they are part of."""
    customer = (
        db.query(Customer)
        .filter(Customer.user_id == user_id, Customer.merge_status != "merged")
        .join(Booking, Booking.customer_id == Customer.customer_id)
        .filter(Booking.booking_id == booking_id)
        .first()
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Booking not found")

    booking = (
        db.query(Booking)
        .filter(Booking.booking_id == booking_id, Booking.customer_id == customer.customer_id)
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    report_type = (payload.report_type or "").strip().lower()
    if report_type not in _ALLOWED_PROVIDER_REPORT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported report_type. Allowed: {', '.join(sorted(_ALLOWED_PROVIDER_REPORT_TYPES))}",
        )

    report = (
        db.query(ProviderIncidentReport)
        .filter(
            ProviderIncidentReport.booking_id == booking.booking_id,
            ProviderIncidentReport.customer_id == customer.customer_id,
            ProviderIncidentReport.report_type == report_type,
        )
        .first()
    )

    if report:
        report.severity = max(1, min(int(payload.severity), 3))
        report.details = (payload.details or "").strip() or None
        report.created_at = datetime.now(timezone.utc).replace(tzinfo=None)
        report.status = "open"
        report.action_taken = "none"
        report.admin_notes = None
        report.resolved_at = None
        report.resolved_by = None
    else:
        report = ProviderIncidentReport(
            booking_id=booking.booking_id,
            provider_id=booking.provider_id,
            customer_id=customer.customer_id,
            report_type=report_type,
            severity=max(1, min(int(payload.severity), 3)),
            details=(payload.details or "").strip() or None,
            status="open",
            action_taken="none",
        )
        db.add(report)

    db.commit()
    db.refresh(report)

    return {
        "report_id": report.report_id,
        "booking_id": report.booking_id,
        "report_type": report.report_type,
        "status": report.status,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


@router.get("/dashboard", response_model=CustomerDashboardOut)
def get_customer_dashboard(
    user_id: str = Depends(get_current_customer_user_id),
    db: Session = Depends(get_db),
):
    """Return all bookings linked to the authenticated customer user."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    customer_ids = _get_customer_ids_for_user(db, user_id)
    user = db.query(User).filter(User.user_id == user_id).first()

    reliability = CustomerReliabilityService.calculate_for_customer_ids(db, customer_ids)
    loyalty = LoyaltyService.get_actor_snapshot(db, actor_type="customer", actor_id=user_id)
    followed_providers = _get_followed_providers_for_customer_ids(db, customer_ids)

    raw_favorite_ids = _json_array_from_text(getattr(user, "favorite_provider_ids", None)) if user else []
    followed_ids = {p.provider_id for p in followed_providers}
    favorite_provider_ids = [pid for pid in raw_favorite_ids if pid in followed_ids]
    by_id = {p.provider_id: p for p in followed_providers}
    favorite_providers = [by_id[pid] for pid in favorite_provider_ids if pid in by_id]

    if not customer_ids:
        return CustomerDashboardOut(
            user_id=user_id,
            display_name=getattr(user, "display_name", None),
            full_name=getattr(user, "full_name", None),
            email=getattr(user, "email", None),
            image_url=getattr(user, "image_url", None),
            upcoming_bookings=[],
            past_bookings=[],
            frequent_services=[],
            followed_providers=followed_providers,
            favorite_provider_ids=favorite_provider_ids,
            favorite_providers=favorite_providers,
            following_count=len(followed_providers),
            followers_count=0,
            reliability_score=float(reliability.get("reliability_score", 0.0)),
            reliability_tier=str(reliability.get("reliability_tier", "new")),
            reliability_confidence=float(reliability.get("confidence", 0.0)),
            reliability_breakdown=reliability.get("breakdown", {}),
            reliability_reports_count=int(reliability.get("signals", {}).get("anonymous_reports_count", 0)),
            loyalty_score=loyalty.score,
            loyalty_tier=loyalty.tier,
            level_badge=loyalty.level_badge,
            is_profile_public=getattr(user, "is_profile_public", True),
            preferred_locations=_json_array_from_text(getattr(user, "preferred_locations", None)),
        )

    all_bookings = (
        db.query(Booking)
        .options(
            joinedload(Booking.line_items),
            joinedload(Booking.provider),
        )
        .filter(Booking.customer_id.in_(customer_ids))
        .order_by(Booking.scheduled_start.asc())
        .all()
    )

    upcoming: list[CustomerBookingOut] = []
    past: list[CustomerBookingOut] = []

    for booking in all_bookings:
        service_name = booking.line_items[0].service_type if booking.line_items else "Appointment"
        provider = booking.provider

        entry = CustomerBookingOut(
            booking_id=booking.booking_id,
            booking_number=booking.booking_number,
            provider_name=provider.name if provider else "Unknown",
            provider_image_url=getattr(provider, "image_url", None),
            provider_slug=getattr(provider, "slug", None),
            service_name=service_name,
            scheduled_start=booking.scheduled_start.isoformat(),
            scheduled_end=booking.scheduled_end.isoformat(),
            status=booking.status,
            customer_notes=booking.customer_notes,
            provider_id=booking.provider_id,
        )

        if booking.status in ("confirmed", "pending") and booking.scheduled_start >= now:
            upcoming.append(entry)
        else:
            past.append(entry)

    upcoming.sort(key=lambda item: item.scheduled_start)
    past.sort(key=lambda item: item.scheduled_start, reverse=True)

    name = getattr(user, "display_name", None)
    if not name:
        customers_with_names = (
            db.query(Customer)
            .filter(Customer.user_id == user_id, Customer.display_name.isnot(None))
            .order_by(Customer.created_at.desc())
            .first()
        )
        name = customers_with_names.display_name if customers_with_names else None

    followers_count = len({b.provider_id for b in all_bookings if b.provider_id})

    return CustomerDashboardOut(
        user_id=user_id,
        display_name=name,
        full_name=getattr(user, "full_name", None),
        email=getattr(user, "email", None),
        image_url=getattr(user, "image_url", None),
        upcoming_bookings=upcoming,
        past_bookings=past,
        frequent_services=_get_frequent_services(all_bookings),
        followed_providers=followed_providers,
        favorite_provider_ids=favorite_provider_ids,
        favorite_providers=favorite_providers,
        following_count=len(followed_providers),
        followers_count=followers_count,
        reliability_score=float(reliability.get("reliability_score", 0.0)),
        reliability_tier=str(reliability.get("reliability_tier", "new")),
        reliability_confidence=float(reliability.get("confidence", 0.0)),
        reliability_breakdown=reliability.get("breakdown", {}),
        reliability_reports_count=int(reliability.get("signals", {}).get("anonymous_reports_count", 0)),
        loyalty_score=loyalty.score,
        loyalty_tier=loyalty.tier,
        level_badge=loyalty.level_badge,
        is_profile_public=getattr(user, "is_profile_public", True),
        preferred_locations=_json_array_from_text(getattr(user, "preferred_locations", None)),
    )


@router.patch("/profile", status_code=200)
def update_customer_profile(
    payload: UpdateProfileIn,
    user_id: str = Depends(get_current_customer_user_id),
    db: Session = Depends(get_db),
):
    """Update mutable profile fields: display_name, full_name, email, preferred_locations, is_profile_public."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.is_profile_public is not None:
        user.is_profile_public = payload.is_profile_public

    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()[:255] or None

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()[:255] or None

    if payload.email is not None:
        new_email = payload.email.strip().lower()
        if new_email and new_email != user.email:
            # Basic format validation
            if "@" not in new_email or "." not in new_email.split("@")[-1]:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid email address",
                )
            # Uniqueness check
            existing = db.query(User).filter(
                User.email == new_email,
                User.user_id != user_id,
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already in use by another account",
                )
            user.email = new_email
            logger.info("Customer %s updated email to %s", user_id, new_email)

    if payload.preferred_locations is not None:
        # Cap at 10 entries, max 100 chars each
        cleaned = [loc.strip()[:100] for loc in payload.preferred_locations if loc.strip()][:10]
        user.preferred_locations = json.dumps(cleaned)

    db.commit()
    db.refresh(user)

    return {
        "is_profile_public": user.is_profile_public,
        "display_name": user.display_name,
        "full_name": user.full_name,
        "email": user.email,
        "preferred_locations": _json_array_from_text(user.preferred_locations),
    }


@router.put("/preferences", response_model=UpdatePreferencesOut)
def update_customer_preferences(
    payload: UpdatePreferencesIn,
    user_id: str = Depends(get_current_customer_user_id),
    db: Session = Depends(get_db),
):
    """Save customer onboarding preferences on the authenticated User."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    cleaned_services = _clean_preferences(
        payload.service_interests,
        ALLOWED_SERVICE_INTERESTS,
        "service_interests",
    )
    cleaned_lifestyle = _clean_preferences(
        payload.lifestyle_preferences,
        ALLOWED_LIFESTYLE_PREFERENCES,
        "lifestyle_preferences",
    )

    user.service_interests = json.dumps(cleaned_services)
    user.lifestyle_preferences = json.dumps(cleaned_lifestyle)
    db.commit()

    logger.info(
        "Updated onboarding prefs for user %s: services=%s lifestyle=%s",
        user_id,
        cleaned_services,
        cleaned_lifestyle,
    )

    return UpdatePreferencesOut(
        service_interests=cleaned_services,
        lifestyle_preferences=cleaned_lifestyle,
    )


@router.get("/favorites", response_model=UpdateFavoritesOut)
def get_customer_favorites(
    user_id: str = Depends(get_current_customer_user_id),
    db: Session = Depends(get_db),
):
    """Get favorite providers (provider_ids) for the authenticated customer."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    customer_ids = _get_customer_ids_for_user(db, user_id)
    followed_ids = {
        row.provider_id
        for row in db.query(ProviderFollow.provider_id)
        .filter(ProviderFollow.customer_id.in_(customer_ids))
        .all()
    }
    provider_ids = [pid for pid in _json_array_from_text(user.favorite_provider_ids) if pid in followed_ids]

    return UpdateFavoritesOut(provider_ids=provider_ids)


@router.put("/favorites", response_model=UpdateFavoritesOut)
def update_customer_favorites(
    payload: UpdateFavoritesIn,
    user_id: str = Depends(get_current_customer_user_id),
    db: Session = Depends(get_db),
):
    """Save favorite provider IDs (must already be followed)."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    cleaned_ids = _clean_provider_ids(payload.provider_ids)
    previous_ids = _json_array_from_text(user.favorite_provider_ids)

    customer_ids = _get_customer_ids_for_user(db, user_id)
    followed_ids = {
        row.provider_id
        for row in db.query(ProviderFollow.provider_id)
        .filter(ProviderFollow.customer_id.in_(customer_ids))
        .all()
    }

    invalid = [pid for pid in cleaned_ids if pid not in followed_ids]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Favorites must be providers you already follow.",
        )

    user.favorite_provider_ids = json.dumps(cleaned_ids)
    db.commit()

    added_ids = [pid for pid in cleaned_ids if pid not in previous_ids]
    if added_ids:
        try:
            LoyaltyService.track_favorite_provider_additions(
                db,
                customer_user_id=user_id,
                provider_ids=added_ids,
            )
        except Exception:
            logger.exception("Favorite-provider loyalty tracking failed user=%s", user_id)

    logger.info("Updated favorite providers for user %s: %s", user_id, cleaned_ids)
    return UpdateFavoritesOut(provider_ids=cleaned_ids)


_AVATAR_DIR = Path(__file__).resolve().parents[2] / "static" / "avatars" / "customers"
_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
_MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5 MB


class AvatarOut(BaseModel):
    image_url: str


@router.post("/avatar", response_model=AvatarOut)
async def upload_customer_avatar(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_customer_user_id),
    db: Session = Depends(get_db),
):
    """Upload a profile picture for the authenticated customer."""
    if file.content_type not in _ALLOWED_MIME:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG, PNG, and WEBP images are supported.",
        )

    contents = await file.read()
    if len(contents) > _MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image must be smaller than 5 MB.",
        )

    ext = file.content_type.split("/")[-1]  # jpeg | png | webp
    filename = f"{user_id}.{ext}"
    _AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    dest = _AVATAR_DIR / filename
    dest.write_bytes(contents)

    # Cache-bust with a short random suffix so the browser picks up the new image
    bust = uuid.uuid4().hex[:8]
    relative_url = f"/static/avatars/customers/{filename}?v={bust}"

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.image_url = relative_url
    db.commit()

    logger.info("Avatar uploaded for user %s → %s", user_id, relative_url)
    return AvatarOut(image_url=relative_url)


@router.get("/preferences", response_model=UpdatePreferencesOut)
def get_customer_preferences(
    user_id: str = Depends(get_current_customer_user_id),
    db: Session = Depends(get_db),
):
    """Get customer onboarding preferences."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UpdatePreferencesOut(
        service_interests=_clean_preferences(
            _json_array_from_text(user.service_interests),
            ALLOWED_SERVICE_INTERESTS,
            "service_interests",
            fail_on_unknown=False,
        ),
        lifestyle_preferences=_clean_preferences(
            _json_array_from_text(user.lifestyle_preferences),
            ALLOWED_LIFESTYLE_PREFERENCES,
            "lifestyle_preferences",
            fail_on_unknown=False,
        ),
    )





