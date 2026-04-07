"""
Business Home Dashboard API

Single endpoint that powers the salon owner's home screen.
Returns everything the screen needs in one call - workers, upcoming bookings,
booking update requests, pending booking requests, and worker join requests.

GET /home/dashboard
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.auth import get_current_provider
from app.db.session import get_db
from app.models.booking import Booking
from app.models.provider import Provider
from app.models.salon_link_request import SalonLinkRequest, STATUS_PENDING
from app.models.worker import Worker
from app.services.referral_service import ReferralService
from app.services.provider_trust_service import ProviderTrustService
from app.services.loyalty_service import LoyaltyService
from app.services.customer_service import CustomerService
from app.services.customer_reliability_service import CustomerReliabilityService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/home", tags=["home"])


# -- Schemas ------------------------------------------------------------------

class TeamMemberOut(BaseModel):
    id: str                    # worker_id or provider_id
    display_name: str
    role: str | None
    image_url: str | None
    member_type: str           # "worker" (staff) | "freelancer" | "chair_renter"
    rating: float              # 0.0 if unknown
    is_working_today: bool     # True if they have a booking today


class UpcomingBookingOut(BaseModel):
    booking_id: str
    booking_number: int
    customer_id: str
    customer_name: str
    customer_image_url: str | None
    service_name: str          # First line item service type
    scheduled_start: str       # ISO string
    scheduled_end: str
    is_home_visit: bool
    status: str
    session_preferences: list[str] = []   # e.g. ["quiet_session", "bringing_dog"]
    customer_notes: str | None = None
    visit_count: int = 0       # total confirmed+completed bookings for this customer
    late_alert_minutes: int | None = None   # Set when customer sends "running late"
    late_alert_sent_at: str | None = None   # ISO string of when alert was sent


class BookingUpdateOut(BaseModel):
    booking_id: str
    booking_number: int
    customer_name: str
    customer_image_url: str | None
    customer_rating: float
    service_name: str
    original_start: str
    original_end: str
    requested_start: str       # New time being requested
    requested_end: str
    is_home_visit: bool


class RequestOut(BaseModel):
    """
    Unified request card - can be a booking request OR a worker join request.
    The 'request_type' field tells the UI which kind of card to render.
    """
    request_id: str
    request_type: str          # "booking" | "worker"

    # Shared
    person_name: str
    person_image_url: str | None

    # Booking request fields (populated when request_type == "booking")
    service_name: str | None = None
    scheduled_start: str | None = None
    is_home_visit: bool | None = None
    customer_note: str | None = None
    session_preferences: list[str] = []   # customer visit preferences

    # Worker request fields (populated when request_type == "worker")
    worker_role: str | None = None       # e.g. "Hair expert"
    worker_message: str | None = None    # intro message from freelancer
    worker_city: str | None = None
    business_type: str | None = None     # "freelancer" | "chair_renter"


class DashboardOut(BaseModel):
    provider_id: str
    provider_name: str
    today_label: str           # e.g. "Monday, 23 Feb"
    team: list[TeamMemberOut]
    upcoming_bookings: list[UpcomingBookingOut]
    booking_updates: list[BookingUpdateOut]
    requests: list[RequestOut]
    pending_requests_count: int   # Badge count for the tab/section
    booking_link: str | None = None         # shareable booking URL (/b/slug)
    referred_bookings_count: int = 0        # total bookings from shareable link
    referral_completed_bookings_count: int = 0
    referral_credit_rate_sek: float = 0.0
    referral_earned_total_sek: float = 0.0
    referral_earned_this_month_sek: float = 0.0
    referral_pending_payout_sek: float = 0.0
    referral_paid_total_sek: float = 0.0
    referral_balance_sek: float = 0.0
    referral_last_payout_at: str | None = None
    waitlist_count: int = 0                 # active waitlist entries
    trust_score: float = 0.0
    trust_tier: str = "developing"
    trust_confidence: float = 0.0
    trust_breakdown: dict[str, float] = Field(default_factory=dict)


# -- Helpers ------------------------------------------------------------------

def _format_dt(dt: datetime) -> str:
    return dt.isoformat()


def _is_today(dt: datetime) -> bool:
    today = datetime.now(timezone.utc).date()
    return dt.date() == today


_LATE_ALERT_TTL_HOURS = 3  # Hide late alerts older than this


def _late_alert(booking: "Booking") -> tuple[int | None, str | None]:
    """Return (minutes, iso_sent_at) if a fresh late notification exists, else (None, None)."""
    if not booking.late_notification_minutes or not booking.late_notification_sent_at:
        return None, None
    sent_at = booking.late_notification_sent_at
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=_LATE_ALERT_TTL_HOURS)
    if sent_at < cutoff:
        return None, None
    return booking.late_notification_minutes, sent_at.isoformat()


# -- Route --------------------------------------------------------------------

@router.get("/dashboard", response_model=DashboardOut)
def get_home_dashboard(
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """
    Powers the Business Home screen.

    Returns in a single call:
    - Provider name for the welcome header
    - All team members (staff workers + linked freelancers/chair renters)
      with a flag showing who has bookings today
    - Next 20 upcoming confirmed/pending bookings
    - Bookings with pending reschedule/change requests
    - All pending requests (booking requests + worker join requests), unified
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()

    trust_score = 0.0
    trust_tier = "developing"
    trust_confidence = 0.0
    trust_breakdown = {"experience": 0.0, "reliability": 0.0, "retention": 0.0}

    if provider:
        try:
            LoyaltyService.award_provider_active_month_if_eligible(db, provider_id)
        except Exception:
            logger.exception("home.dashboard provider-activity loyalty block failed for provider=%s", provider_id)

    if provider:
        try:
            trust = ProviderTrustService.calculate_provider_trust(db, provider_id)
            trust_score = float(trust.get("trust_score", 0.0))
            trust_tier = str(trust.get("trust_tier", "developing"))
            trust_confidence = float(trust.get("confidence", 0.0))
            trust_breakdown = trust.get("breakdown", trust_breakdown)
        except Exception:
            logger.exception("home.dashboard trust-score block failed for provider=%s", provider_id)

    # -- 1. Build today label --------------------------------------------------
    today_label = now.strftime("%A, %d %b")  # e.g. "Monday, 23 Feb"

    # -- 2. Team members -------------------------------------------------------

    # Bookings today to flag who's working
    today_booking_provider_ids: set[str] = set()
    today_bookings_all = (
        db.query(Booking)
        .filter(
            Booking.provider_id == provider_id,
            Booking.scheduled_start >= today_start,
            Booking.scheduled_start < today_end,
            Booking.status.in_(["confirmed", "pending"]),
        )
        .all()
    )
    # (In a worker-aware system you'd filter by assigned worker; for now flag by salon)
    if today_bookings_all:
        today_booking_provider_ids.add(provider_id)

    team: list[TeamMemberOut] = []

    # Staff workers (in workers table)
    workers = (
        db.query(Worker)
        .filter(Worker.provider_id == provider_id, Worker.is_active == True)
        .all()
    )
    for w in workers:
        team.append(TeamMemberOut(
            id=w.worker_id,
            display_name=w.display_name,
            role=w.role,
            image_url=w.image_url,
            member_type="worker",
            rating=0.0,
            is_working_today=bool(today_booking_provider_ids),
        ))

    # Linked freelancers / chair renters (providers with parent_provider_id = this salon)
    linked_providers = (
        db.query(Provider)
        .filter(Provider.parent_provider_id == provider_id)
        .all()
    )
    for lp in linked_providers:
        team.append(TeamMemberOut(
            id=lp.provider_id,
            display_name=lp.name,
            role=lp.service_categories,   # Could show their category
            image_url=lp.image_url,
            member_type=lp.business_type or "freelancer",
            rating=lp.rating or 0.0,
            is_working_today=lp.provider_id in today_booking_provider_ids,
        ))

    # -- 3. Upcoming bookings (next 20 confirmed/pending) ----------------------
    upcoming_raw = (
        db.query(Booking)
        .options(joinedload(Booking.customer), joinedload(Booking.line_items))
        .filter(
            Booking.provider_id == provider_id,
            Booking.status.in_(["confirmed", "pending"]),
            Booking.scheduled_start >= now,
        )
        .order_by(Booking.scheduled_start.asc())
        .limit(20)
        .all()
    )

    upcoming_bookings: list[UpcomingBookingOut] = []
    for b in upcoming_raw:
        service_name = (
            b.line_items[0].service_type if b.line_items else "Appointment"
        )
        cust = b.customer if hasattr(b, "customer") else None
        customer_name = (
            cust.display_name
            or cust.instagram_username_snapshot
            or cust.customer_email
            or f"Customer #{cust.customer_number}"
        ) if cust else "Unknown"
        customer_image = getattr(cust, "image_url", None)

        prefs: list[str] = []
        if b.session_preferences:
            try:
                prefs = json.loads(b.session_preferences)
            except Exception:
                prefs = []

        visit_count = (
            db.query(func.count(Booking.booking_id))
            .filter(
                Booking.customer_id == b.customer_id,
                Booking.provider_id == provider_id,
                Booking.status.in_(["confirmed", "completed"]),
            )
            .scalar()
        ) or 0

        late_mins, late_sent = _late_alert(b)
        upcoming_bookings.append(UpcomingBookingOut(
            booking_id=b.booking_id,
            booking_number=b.booking_number,
            customer_id=b.customer_id,
            customer_name=customer_name,
            customer_image_url=customer_image,
            service_name=service_name,
            scheduled_start=_format_dt(b.scheduled_start),
            scheduled_end=_format_dt(b.scheduled_end),
            is_home_visit=bool(b.is_walkin),  # re-using field; add home_visit field later
            status=b.status,
            session_preferences=prefs,
            customer_notes=b.customer_notes,
            visit_count=visit_count,
            late_alert_minutes=late_mins,
            late_alert_sent_at=late_sent,
        ))

    # -- 4. Booking updates (reschedule_requested) -----------------------------
    # We look for bookings tagged with status "reschedule_requested"
    update_raw = (
        db.query(Booking)
        .options(joinedload(Booking.customer), joinedload(Booking.line_items))
        .filter(
            Booking.provider_id == provider_id,
            Booking.status == "reschedule_requested",
        )
        .order_by(Booking.scheduled_start.asc())
        .limit(10)
        .all()
    )

    booking_updates: list[BookingUpdateOut] = []
    for b in update_raw:
        service_name = b.line_items[0].service_type if b.line_items else "Appointment"
        customer = getattr(b, "customer", None)
        customer_name = (
            customer.display_name
            or customer.instagram_username_snapshot
            or customer.customer_email
            or f"Customer #{customer.customer_number}"
        ) if customer else "Unknown"
        customer_image = getattr(customer, "image_url", None) if customer else None
        customer_rating = 0.0
        if customer and CustomerService.provider_can_view_customer_rating(
            db, provider_id=provider_id, customer_id=customer.customer_id
        ):
            try:
                rel = CustomerReliabilityService.calculate_for_customer(db, customer.customer_id)
                raw = float(rel.get("reliability_score", 0.0))
                conf = float(rel.get("confidence", 0.0))
                customer_rating = 5.0 if (raw == 0.0 and conf == 0.0) else round(raw / 20, 1)
            except Exception:
                customer_rating = 0.0

        # Requested new time is stored in provider_notes as JSON for now
        # TODO: add reschedule_requested_start / reschedule_requested_end columns
        # For now use +2h as placeholder until columns are added
        booking_updates.append(BookingUpdateOut(
            booking_id=b.booking_id,
            booking_number=b.booking_number,
            customer_id=b.customer_id,
            customer_name=customer_name,
            customer_image_url=customer_image,
            customer_rating=float(customer_rating),
            service_name=service_name,
            original_start=_format_dt(b.scheduled_start),
            original_end=_format_dt(b.scheduled_end),
            requested_start=_format_dt(b.scheduled_start - timedelta(hours=1)),
            requested_end=_format_dt(b.scheduled_end - timedelta(hours=1)),
            is_home_visit=bool(b.is_walkin),
        ))

    # -- 5. Requests: booking requests + worker join requests ------------------
    requests: list[RequestOut] = []

    # 5a. Pending booking requests (customer booked but needs owner confirmation)
    booking_requests = (
        db.query(Booking)
        .options(joinedload(Booking.customer), joinedload(Booking.line_items))
        .filter(
            Booking.provider_id == provider_id,
            Booking.status == "pending",
        )
        .order_by(Booking.created_at.desc())
        .limit(20)
        .all()
    )

    for b in booking_requests:
        service_name = b.line_items[0].service_type if b.line_items else "Appointment"
        customer = getattr(b, "customer", None)
        customer_name = (
            customer.display_name
            or customer.instagram_username_snapshot
            or customer.customer_email
            or f"Customer #{customer.customer_number}"
        ) if customer else "Unknown"
        customer_image = getattr(customer, "image_url", None) if customer else None

        req_prefs: list[str] = []
        if b.session_preferences:
            try:
                req_prefs = json.loads(b.session_preferences)
            except Exception:
                req_prefs = []

        requests.append(RequestOut(
            request_id=b.booking_id,
            request_type="booking",
            person_name=customer_name,
            person_image_url=customer_image,
            service_name=service_name,
            scheduled_start=_format_dt(b.scheduled_start),
            is_home_visit=bool(b.is_walkin),
            customer_note=b.customer_notes,
            session_preferences=req_prefs,
        ))
    # 5b. Worker join requests (salon link requests)
    try:
        worker_requests = (
            db.query(SalonLinkRequest)
            .filter(
                SalonLinkRequest.salon_provider_id == provider_id,
                SalonLinkRequest.status == STATUS_PENDING,
            )
            .order_by(SalonLinkRequest.created_at.desc())
            .all()
        )
    except Exception:
        logger.exception("home.dashboard worker-requests block failed for provider=%s", provider_id)
        worker_requests = []

    for wr in worker_requests:
        requester = db.query(Provider).filter(
            Provider.provider_id == wr.requester_provider_id
        ).first()
        if not requester:
            continue

        # Get their specialty from service categories
        role_label = None
        if requester.service_categories:
            try:
                cats = json.loads(requester.service_categories)
                # Map first category slug to readable label
                cat_map = {
                    "hair": "Hair expert", "barber": "Barber", "nails": "Nail technician",
                    "spa": "Spa therapist", "massage": "Massage therapist",
                    "fitness": "Personal trainer", "makeup": "Makeup artist",
                    "skincare": "Skin specialist", "lashes": "Lash artist",
                    "tattoo": "Tattoo artist",
                }
                role_label = cat_map.get(cats[0], cats[0].capitalize()) if cats else None
            except Exception:
                pass

        requests.append(RequestOut(
            request_id=wr.id,
            request_type="worker",
            person_name=requester.name,
            person_image_url=requester.image_url,
            worker_role=role_label,
            worker_message=wr.message,
            worker_city=requester.city,
            business_type=requester.business_type,
        ))

    pending_count = len([r for r in requests if r.request_type != "booking"])

    # -- 6. Booking link + referral stats ------------------------------------
    booking_link = None
    referred_count = 0
    referral_completed_count = 0
    referral_credit_rate = 0.0
    referral_earned_total = 0.0
    referral_earned_this_month = 0.0
    referral_pending_payout = 0.0
    referral_paid_total = 0.0
    referral_balance = 0.0
    referral_last_payout_at = None

    if provider:
        try:
            from app.api.provider_links import _ensure_slug, _booking_url
            slug = _ensure_slug(db, provider)
            booking_link = _booking_url(slug)
            referred_count = (
                db.query(func.count(Booking.booking_id))
                .filter(
                    Booking.provider_id == provider_id,
                    Booking.referral_source.isnot(None),
                )
                .scalar()
            ) or 0

            referral_summary = ReferralService.get_provider_summary(db, provider_id)
            referral_completed_count = referral_summary.total_completed_referrals
            referral_credit_rate = referral_summary.credit_rate_sek
            referral_earned_total = referral_summary.earned_total_sek
            referral_earned_this_month = referral_summary.earned_this_month_sek
            referral_pending_payout = referral_summary.pending_payout_sek
            referral_paid_total = referral_summary.paid_total_sek
            referral_balance = referral_summary.available_balance_sek
            referral_last_payout_at = referral_summary.last_paid_at_iso
        except Exception:
            logger.exception("home.dashboard booking-link/referral block failed for provider=%s", provider_id)
            booking_link = None
            referred_count = 0
            referral_completed_count = 0
            referral_credit_rate = 0.0
            referral_earned_total = 0.0
            referral_earned_this_month = 0.0
            referral_pending_payout = 0.0
            referral_paid_total = 0.0
            referral_balance = 0.0
            referral_last_payout_at = None

    # -- 7. Waitlist count -------------------------------------------------
    try:
        from app.models.waitlist import WaitlistEntry
        waitlist_count = (
            db.query(func.count(WaitlistEntry.entry_id))
            .filter(
                WaitlistEntry.provider_id == provider_id,
                WaitlistEntry.status == "active",
            )
            .scalar()
        ) or 0
    except Exception:
        logger.exception("home.dashboard waitlist block failed for provider=%s", provider_id)
        waitlist_count = 0

    return DashboardOut(
        provider_id=provider_id,
        provider_name=provider.name if provider else "Your Salon",
        today_label=today_label,
        team=team,
        upcoming_bookings=upcoming_bookings,
        booking_updates=booking_updates,
        requests=requests,
        pending_requests_count=pending_count,
        booking_link=booking_link,
        referred_bookings_count=referred_count,
        referral_completed_bookings_count=referral_completed_count,
        referral_credit_rate_sek=referral_credit_rate,
        referral_earned_total_sek=referral_earned_total,
        referral_earned_this_month_sek=referral_earned_this_month,
        referral_pending_payout_sek=referral_pending_payout,
        referral_paid_total_sek=referral_paid_total,
        referral_balance_sek=referral_balance,
        referral_last_payout_at=referral_last_payout_at,
        trust_score=trust_score,
        trust_tier=trust_tier,
        trust_confidence=trust_confidence,
        trust_breakdown=trust_breakdown,
        waitlist_count=waitlist_count,
    )


# -- /providers/me/home - schedule home screen --------------------------------
# Separate router so the URL is /api/v1/providers/me/home instead of /home/*

providers_router = APIRouter(prefix="/providers", tags=["providers-home"])


class ProviderHomeOut(BaseModel):
    upcoming_bookings: list[UpcomingBookingOut]
    booking_updates: list[BookingUpdateOut]


@providers_router.get("/me/home", response_model=ProviderHomeOut)
def get_provider_home(
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """
    Provider schedule home screen.
    Returns upcoming confirmed/pending bookings + any reschedule requests.
    """
    now = datetime.now(timezone.utc)

    # -- Upcoming confirmed/pending bookings (next 10) --------------------------
    upcoming_raw = (
        db.query(Booking)
        .options(joinedload(Booking.customer), joinedload(Booking.line_items))
        .filter(
            Booking.provider_id == provider_id,
            Booking.status.in_(["confirmed", "pending"]),
            Booking.scheduled_start >= now,
        )
        .order_by(Booking.scheduled_start.asc())
        .limit(10)
        .all()
    )

    upcoming_bookings: list[UpcomingBookingOut] = []
    for b in upcoming_raw:
        service_name = b.line_items[0].service_type if b.line_items else "Appointment"
        cust = b.customer if hasattr(b, "customer") else None
        customer_name = (
            cust.display_name
            or cust.instagram_username_snapshot
            or cust.customer_email
            or f"Customer #{cust.customer_number}"
        ) if cust else "Unknown"
        customer_image = getattr(cust, "image_url", None)

        prefs: list[str] = []
        if b.session_preferences:
            try:
                prefs = json.loads(b.session_preferences)
            except Exception:
                prefs = []

        visit_count = (
            db.query(func.count(Booking.booking_id))
            .filter(
                Booking.customer_id == b.customer_id,
                Booking.provider_id == provider_id,
                Booking.status.in_(["confirmed", "completed"]),
            )
            .scalar()
        ) or 0

        late_mins, late_sent = _late_alert(b)
        upcoming_bookings.append(UpcomingBookingOut(
            booking_id=b.booking_id,
            booking_number=b.booking_number,
            customer_id=b.customer_id,
            customer_name=customer_name,
            customer_image_url=customer_image,
            service_name=service_name,
            scheduled_start=_format_dt(b.scheduled_start),
            scheduled_end=_format_dt(b.scheduled_end),
            is_home_visit=bool(b.is_walkin),
            status=b.status,
            session_preferences=prefs,
            customer_notes=b.customer_notes,
            visit_count=visit_count,
            late_alert_minutes=late_mins,
            late_alert_sent_at=late_sent,
        ))

    # -- Reschedule requests ---------------------------------------------------
    update_raw = (
        db.query(Booking)
        .options(joinedload(Booking.customer), joinedload(Booking.line_items))
        .filter(
            Booking.provider_id == provider_id,
            Booking.status == "reschedule_requested",
        )
        .order_by(Booking.scheduled_start.asc())
        .limit(10)
        .all()
    )

    booking_updates: list[BookingUpdateOut] = []
    for b in update_raw:
        service_name = b.line_items[0].service_type if b.line_items else "Appointment"
        customer = getattr(b, "customer", None)
        customer_name = (
            customer.display_name
            or customer.instagram_username_snapshot
            or customer.customer_email
            or f"Customer #{customer.customer_number}"
        ) if customer else "Unknown"
        customer_image = getattr(customer, "image_url", None) if customer else None
        customer_rating = 0.0
        if customer and CustomerService.provider_can_view_customer_rating(
            db, provider_id=provider_id, customer_id=customer.customer_id
        ):
            try:
                rel = CustomerReliabilityService.calculate_for_customer(db, customer.customer_id)
                raw = float(rel.get("reliability_score", 0.0))
                conf = float(rel.get("confidence", 0.0))
                customer_rating = 5.0 if (raw == 0.0 and conf == 0.0) else round(raw / 20, 1)
            except Exception:
                customer_rating = 0.0

        booking_updates.append(BookingUpdateOut(
            booking_id=b.booking_id,
            booking_number=b.booking_number,
            customer_id=b.customer_id,
            customer_name=customer_name,
            customer_image_url=customer_image,
            customer_rating=float(customer_rating),
            service_name=service_name,
            original_start=_format_dt(b.scheduled_start),
            original_end=_format_dt(b.scheduled_end),
            requested_start=_format_dt(b.scheduled_start - timedelta(hours=1)),
            requested_end=_format_dt(b.scheduled_end - timedelta(hours=1)),
            is_home_visit=bool(b.is_walkin),
        ))

    return ProviderHomeOut(
        upcoming_bookings=upcoming_bookings,
        booking_updates=booking_updates,
    )





