"""
Feed API — returns ordered UIBlock lists for two flows:

  POST /api/v1/feed/search
      User typed a natural language prompt (search / discovery feed).
      Intent is parsed, providers are queried + sorted, blocks are assembled
      with emphasis fields derived from the detected intent signals.

  GET  /api/v1/feed/provider/{provider_id}
      User arrived directly at a provider profile (e.g. from an Instagram DM
      "continue on platform" deeplink). No intent needed — returns profile
      blocks ready for direct booking.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.provider_service import ProviderService
from app.services.availability_service import AvailabilityService
from app.services.customer_service import CustomerService
from app.services.booking_service import BookingService
from app.services.customer_preference_service import CustomerPreferenceService
from app.models.provider import Provider
from app.models.provider_intelligence import ProviderIntelligence
from app.models.provider_amenity import ProviderAmenity
from app.models.service import Service
from app.models.booking import Booking
from app.models.search_event import SearchEvent
from app.models.user import User
from app.services.loyalty_service import LoyaltyService

from app.api.intent import parse_intent, IntentResult, PRICE_LEVEL_LABELS
from app.api.ui_blocks import (
    UIBlock,
    PromptFeedRequest,
    PromptFeedResponse,
    SearchFeedRequest,
    SearchFeedResponse,
    ProviderFeedResponse,
    IntentProfile,
    FeedRecipe,
    SearchSummaryData,
    ProviderCardData,
    ProviderResultsData,
    AvailabilityPickerData,
    BookingDraftData,
    ProfileMemoryData,
    CTAButtonRowData,
    CTAButton,
    ServiceSummary,
    TimeSlot,
    PreferenceSummary,
    HeroCardData,
    ConversationalFollowUpData,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feed", tags=["feed"])

_SLOT_LOOKAHEAD_DAYS = 7      # how many days ahead to scan for next available
_PICKER_DAYS = 5              # how many days of slots to include in AvailabilityPicker

# ── Customer preference → provider matching maps ──────────────────────────────

# Maps customer lifestyle_preference keys → ProviderAmenity.amenity_key values
LIFESTYLE_TO_AMENITY: dict[str, str] = {
    "bring_dog":      "dog_friendly",
    "coffee":         "coffee",
    "hijab_friendly": "hijab_friendly",
    "eco_products":   "eco_friendly",
    "accessible":     "wheelchair_accessible",
    "wine_please":    "wine",
    "pay_by_card":    "card_payment",
    "private_room":   "private_room",
    "bringing_child": "child_friendly",
    "quiet_session":  "quiet",
}

# Maps customer service_interest keys → partial matches against Service.category
# (case-insensitive substring match is used, so "hair" matches "Hair", "Hår" won't — but
#  the provider scraping normalises categories to English slugs for new imports)
SERVICE_INTEREST_ALIASES: dict[str, list[str]] = {
    "hair":     ["hair", "frisyr", "hår", "styling", "blowout", "blowdry"],
    "nails":    ["nail", "nagel", "naglar", "manicure", "pedicure", "gel"],
    "spa":      ["spa", "facial", "ansikts"],
    "massage":  ["massage"],
    "barber":   ["barber", "herrklipp", "beard"],
    "lashes":   ["lash", "frans", "fransar", "browlift", "lashlift"],
    "brows":    ["brow", "bryn", "eyebrow", "microblading"],
    "makeup":   ["makeup", "make-up", "smink"],
    "skincare": ["skin", "hud", "facial", "peeling"],
    "waxing":   ["wax", "vaxning", "sugaring"],
}


def _fetch_customer_prefs(
    db: Session,
    customer_user_id: str,
) -> tuple[list[str], list[str]]:
    """Return (service_interests, lifestyle_preferences) for a user_id.

    Falls back to empty lists if user not found or prefs not set.
    """
    try:
        user = db.query(User).filter(User.user_id == customer_user_id).first()
        if not user:
            return [], []
        interests = json.loads(user.service_interests or "[]")
        lifestyle = json.loads(user.lifestyle_preferences or "[]")
        return interests, lifestyle
    except Exception:
        logger.exception("Failed to fetch prefs for user %s", customer_user_id)
        return [], []


def _preference_score(
    db: Session,
    provider: Provider,
    service_interests: list[str],
    lifestyle_preferences: list[str],
    provider_services: list[Service],
) -> int:
    """Score a provider against a customer's stored preferences.

    Returns an integer ≥ 0.  Higher = better match.
    One point per matched service category, one point per matched amenity.
    """
    score = 0

    # Service interest matching — does the provider offer anything in the customer's categories?
    if service_interests and provider_services:
        service_cats = " ".join(
            (s.category or "").lower() + " " + s.name.lower()
            for s in provider_services
        )
        for interest in service_interests:
            aliases = SERVICE_INTEREST_ALIASES.get(interest, [interest])
            if any(alias in service_cats for alias in aliases):
                score += 1

    # Lifestyle → amenity matching — does the provider have the amenities the customer wants?
    if lifestyle_preferences:
        amenity_keys = {
            LIFESTYLE_TO_AMENITY[lp]
            for lp in lifestyle_preferences
            if lp in LIFESTYLE_TO_AMENITY
        }
        if amenity_keys:
            active_amenities = db.query(ProviderAmenity.amenity_key).filter(
                ProviderAmenity.provider_id == provider.provider_id,
                ProviderAmenity.is_active.is_(True),
            ).all()
            active_keys = {row.amenity_key for row in active_amenities}
            score += len(amenity_keys & active_keys)

    return score


# ── DB dependency ─────────────────────────────────────────────────────────────


def _result_count_band(count: int) -> str:
    if count <= 0:
        return "none"
    if count <= 2:
        return "low"
    if count <= 7:
        return "medium"
    return "high"


def _price_preference(signals: list[str]) -> int | None:
    # 1 = budget leaning. None means no explicit price signal.
    return 1 if "price_sensitive" in signals else None


_TIME_PATTERN = re.compile(
    r"\b(today|tomorrow|tonight|this week|next week|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"morning|afternoon|evening|\d{1,2}(:\d{2})?\s?(am|pm)?)\b",
    re.IGNORECASE,
)
_BUDGET_PATTERN = re.compile(
    r"\b(cheap|budget|affordable|premium|luxury|under\s+\d+|max\s+\d+|\d+\s*(sek|kr|usd|eur))\b",
    re.IGNORECASE,
)
_INSPIRATION_PATTERN = re.compile(
    r"\b(inspiration|ideas|look|style|vibe|mood|trending|trend|not sure|unsure|explore|something like)\b",
    re.IGNORECASE,
)
_BOOKING_PATTERN = re.compile(
    r"\b(book|booking|available|availability|appointment|schedule|reserve|need it|need this)\b",
    re.IGNORECASE,
)
_COMPARISON_PATTERN = re.compile(r"\b(compare|comparison|versus|vs)\b", re.IGNORECASE)
_PROFILE_PATTERN = re.compile(r"(^@[\w\.\-]+)|\b(profile|instagram|insta)\b", re.IGNORECASE)
_PROVIDER_HINT_PATTERN = re.compile(r"(^@[\w\.\-]+)|\bwith\s+@?[\w\.\-]+\b", re.IGNORECASE)


def _certainty(value_present: bool, *, multiple_signals: bool = False) -> str:
    if not value_present:
        return "low"
    return "high" if multiple_signals else "medium"


def _detect_goal(prompt: str, intent: IntentResult, is_returning_customer: bool) -> str:
    lower = prompt.lower().strip()
    if is_returning_customer and ("same as last time" in lower or "again" in lower or "rebook" in lower):
        return "rebook"
    if _COMPARISON_PATTERN.search(prompt):
        return "comparison"
    if _INSPIRATION_PATTERN.search(prompt) and "urgency" not in intent.signals:
        return "inspiration"
    if _PROFILE_PATTERN.search(prompt) and not intent.location and not _TIME_PATTERN.search(prompt):
        return "profile_lookup"
    if _BOOKING_PATTERN.search(prompt) or "urgency" in intent.signals or _TIME_PATTERN.search(prompt):
        return "booking"
    return "discovery"


def _build_intent_profile(
    prompt: str,
    intent: IntentResult,
    *,
    customer_id: str | None = None,
) -> IntentProfile:
    is_returning_customer = bool(customer_id)
    has_time = bool(_TIME_PATTERN.search(prompt)) or "urgency" in intent.signals
    has_budget = bool(_BUDGET_PATTERN.search(prompt)) or "price_sensitive" in intent.signals
    has_provider = bool(_PROVIDER_HINT_PATTERN.search(prompt))
    goal = _detect_goal(prompt, intent, is_returning_customer)

    needs_clarification: list[str] = []
    if not intent.service_category:
        needs_clarification.append("service")
    if not intent.location:
        needs_clarification.append("location")
    if goal in {"booking", "rebook"} and not has_time:
        needs_clarification.append("time")

    explanation_style = "premium" if "quality_focused" in intent.signals else "guided"
    if goal == "profile_lookup":
        explanation_style = "concise"

    return IntentProfile(
        goal=goal,
        service_certainty=_certainty(bool(intent.service_category), multiple_signals=len(intent.service_keywords) > 0),
        provider_certainty=_certainty(has_provider, multiple_signals=prompt.strip().startswith("@")),
        time_certainty=_certainty(has_time, multiple_signals="urgency" in intent.signals),
        location_certainty=_certainty(bool(intent.location)),
        budget_certainty=_certainty(has_budget, multiple_signals="price_sensitive" in intent.signals),
        urgency="high" if "urgency" in intent.signals else ("medium" if has_time else "low"),
        is_returning_customer=is_returning_customer,
        needs_clarification=needs_clarification,
        explanation_style=explanation_style,
        query_rewrite=intent.subtitle,
    )


def _build_feed_recipe(intent_profile: IntentProfile) -> FeedRecipe:
    if intent_profile.goal == "inspiration":
        return FeedRecipe(
            template="inspiration_first",
            ordered_blocks=["HeroCard", "SearchSummaryCard", "ProviderResults", "ConversationalFollowUp"],
            primary_action="refine_search",
        )
    if intent_profile.goal == "rebook" and intent_profile.is_returning_customer:
        return FeedRecipe(
            template="returning_customer",
            ordered_blocks=["HeroCard", "ProfileMemoryCard", "ProviderResults", "CTAButtonRow", "ConversationalFollowUp"],
            primary_action="rebook",
        )
    if intent_profile.provider_certainty == "high" and intent_profile.time_certainty in {"medium", "high"}:
        return FeedRecipe(
            template="specific_booking",
            ordered_blocks=["HeroCard", "ProviderResults", "AvailabilityPicker", "CTAButtonRow", "ConversationalFollowUp"],
            primary_action="hold_slot",
        )
    if intent_profile.goal == "booking":
        return FeedRecipe(
            template="guided_booking",
            ordered_blocks=["HeroCard", "SearchSummaryCard", "ProviderResults", "AvailabilityPicker", "CTAButtonRow", "ConversationalFollowUp"],
            primary_action="open_availability",
        )
    return FeedRecipe(
        template="guided_search",
        ordered_blocks=["HeroCard", "SearchSummaryCard", "ProviderResults", "CTAButtonRow", "ConversationalFollowUp"],
        primary_action="open_profile",
    )


def _hero_copy(intent_profile: IntentProfile, intent: IntentResult) -> tuple[str, str, str]:
    service_label = (intent.service_category or "beauty services").replace("_", " ")
    title = f"Find the right {service_label}"
    subtitle = intent.subtitle or "We will adapt the feed as you narrow your search."
    tone = "guided"

    if intent_profile.goal == "inspiration":
        title = f"Explore {service_label} looks"
        subtitle = "Start broad, compare the vibe, then narrow into the right provider and time."
        tone = "explore"
    elif intent_profile.goal == "rebook":
        title = "Pick up where you left off"
        subtitle = "We are using your previous context to get you back into a smooth booking flow."
        tone = "returning"
    elif intent_profile.provider_certainty == "high" and intent_profile.time_certainty in {"medium", "high"}:
        title = f"Book {service_label} faster"
        subtitle = "You already know most of what you want, so the feed can move straight toward slots."
        tone = "decisive"

    return title, subtitle, tone


def _build_hero_block(intent_profile: IntentProfile, intent: IntentResult) -> UIBlock:
    title, subtitle, tone = _hero_copy(intent_profile, intent)
    return UIBlock(
        type="HeroCard",
        emphasis=[],
        data=HeroCardData(
            title=title,
            subtitle=subtitle,
            goal=intent_profile.goal,
            tone=tone,
        ),
    )


def _build_follow_up_block(intent_profile: IntentProfile, intent: IntentResult) -> UIBlock:
    service_label = (intent.service_category or "service").replace("_", " ")
    location = intent.location or "your area"
    suggestions: list[str] = []

    if "time" in intent_profile.needs_clarification:
        suggestions.append(f"Who is available for {service_label} this week?")
    if "location" in intent_profile.needs_clarification:
        suggestions.append(f"Show {service_label} options in Stockholm")
    if intent_profile.goal == "inspiration":
        suggestions.append(f"Show me the best {service_label}-style options in {location}")
        suggestions.append("I want something more natural")
    else:
        suggestions.append("Show me the best rated options")
        suggestions.append("Something more affordable")

    if intent_profile.provider_certainty != "high":
        suggestions.append("Who should I choose if quality matters most?")

    deduped: list[str] = []
    for suggestion in suggestions:
        if suggestion not in deduped:
            deduped.append(suggestion)

    return UIBlock(
        type="ConversationalFollowUp",
        emphasis=[],
        data=ConversationalFollowUpData(suggestions=deduped[:4]),
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _vat_price(service: Service, provider: Provider) -> float:
    vat = service.vat_percent if service.vat_percent is not None else provider.vat_percent
    return round(service.price_ex_vat * (1 + vat / 100), 2)


def _service_summary(service: Service, provider: Provider) -> ServiceSummary:
    return ServiceSummary(
        service_id=service.service_id,
        name=service.name,
        category=service.category,
        duration_minutes=service.duration_minutes,
        price_ex_vat=service.price_ex_vat,
        price_inc_vat=_vat_price(service, provider),
        home_service_available=service.home_service_available,
    )


def _get_next_available(
    db: Session,
    provider_id: str,
    services: list[Service],
    provider: Provider,
    from_date: datetime | None = None,
) -> tuple[str | None, bool]:
    """Scan ahead _SLOT_LOOKAHEAD_DAYS for the earliest open slot.

    Returns:
        (next_available_iso, available_today)
    """
    if not services:
        return None, False

    # Use the shortest service for availability scanning (fastest to fit)
    ref_service = min(services, key=lambda s: s.duration_minutes)
    now = from_date or datetime.now(timezone.utc)
    today_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

    next_available: str | None = None
    available_today = False

    for day_offset in range(_SLOT_LOOKAHEAD_DAYS):
        check_date = today_date + timedelta(days=day_offset)
        slots = AvailabilityService.get_available_slots(
            db=db,
            provider_id=provider_id,
            date=check_date,
            duration_minutes=ref_service.duration_minutes,
        )
        if slots:
            # Filter out past slots on today
            future_slots = []
            for s in slots:
                try:
                    start_dt = datetime.fromisoformat(s["start"])
                    if start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=timezone.utc)
                    if start_dt > now:
                        future_slots.append(s)
                except ValueError:
                    future_slots.append(s)

            if future_slots:
                next_available = future_slots[0]["start"]
                if day_offset == 0:
                    available_today = True
                break

    return next_available, available_today


def _get_slots_for_picker(
    db: Session,
    provider_id: str,
    services: list[Service],
    provider: Provider,
    n_days: int = _PICKER_DAYS,
) -> tuple[dict[str, list[TimeSlot]], list[str]]:
    """Build slots_by_date for AvailabilityPicker.

    Uses the first service as default (frontend can request specific service).
    Returns (slots_by_date, available_dates).
    """
    if not services:
        return {}, []

    ref_service = services[0]
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    slots_by_date: dict[str, list[TimeSlot]] = {}
    available_dates: list[str] = []
    days_found = 0

    for day_offset in range(14):  # scan up to 2 weeks
        if days_found >= n_days:
            break

        check_date = today + timedelta(days=day_offset)
        date_key = check_date.strftime("%Y-%m-%d")

        raw_slots = AvailabilityService.get_available_slots(
            db=db,
            provider_id=provider_id,
            date=check_date,
            duration_minutes=ref_service.duration_minutes,
        )

        # Filter past slots on today
        time_slots: list[TimeSlot] = []
        for s in raw_slots:
            try:
                start_dt = datetime.fromisoformat(s["start"])
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=timezone.utc)
                end_dt = datetime.fromisoformat(s["end"])
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=timezone.utc)
                if start_dt > now:
                    time_slots.append(TimeSlot(
                        start=s["start"],
                        end=s["end"],
                        time_label=start_dt.strftime("%H:%M"),
                    ))
            except ValueError:
                pass

        if time_slots:
            slots_by_date[date_key] = time_slots
            available_dates.append(date_key)
            days_found += 1

    return slots_by_date, available_dates


def _build_provider_card(
    db: Session,
    provider: Provider,
    intent: IntentResult | None,
    all_services: list[Service],
    intelligence: ProviderIntelligence | None = None,
) -> ProviderCardData:
    """Assemble a ProviderCardData for a provider."""
    service_summaries = [_service_summary(s, provider) for s in all_services]

    # Matched services — those aligning with the search intent
    if intent and intent.service_category:
        matched = [
            s for s in all_services
            if s.category and intent.service_category in s.category.lower()
        ]
    else:
        matched = all_services

    matched_summaries = [_service_summary(s, provider) for s in matched] or service_summaries

    # Cheapest service for "starting from"
    starting_from: float | None = None
    if all_services:
        cheapest = min(all_services, key=lambda s: _vat_price(s, provider))
        starting_from = _vat_price(cheapest, provider)

    next_available, available_today = _get_next_available(
        db, provider.provider_id, all_services, provider
    )

    price_level = provider.price_level or 2
    price_label = PRICE_LEVEL_LABELS.get(price_level, "Standard")

    # Vibe identity from intelligence
    vibe_tags: list[str] = []
    vibe_summary: str | None = None
    if intelligence:
        vibe_tags = json.loads(
            intelligence.confirmed_vibe_tags or intelligence.ai_vibe_tags or "[]"
        )
        vibe_summary = intelligence.vibe_summary

    return ProviderCardData(
        provider_id=provider.provider_id,
        slug=provider.slug,
        name=provider.name,
        bio=provider.bio,
        image_url=provider.image_url,
        city=provider.city,
        location_salon=provider.location_salon,
        instagram_username=getattr(provider, "instagram_username", None),
        services=service_summaries,
        matched_services=matched_summaries,
        price_level=price_level,
        price_level_label=price_label,
        starting_from=starting_from,
        rating=provider.rating or 0.0,
        review_count=provider.review_count or 0,
        revisit_rate=provider.revisit_rate or 0.0,
        total_completed_bookings=provider.total_completed_bookings or 0,
        next_available=next_available,
        available_today=available_today,
        home_service=provider.home_service,
        vibe_tags=vibe_tags,
        vibe_summary=vibe_summary,
    )


def _sort_providers(
    providers: list[Provider],
    strategy: str,
) -> list[Provider]:
    """Sort providers by the intent-derived strategy."""
    if strategy == "price_asc":
        return sorted(providers, key=lambda p: (p.price_level or 2, -(p.rating or 0)))
    elif strategy == "value_score":
        # value = rating / price_level — higher is better value for money
        def value(p: Provider) -> float:
            pl = p.price_level or 2
            r = p.rating or 0.0
            return r / pl if pl else 0
        return sorted(providers, key=value, reverse=True)
    elif strategy == "availability":
        # Sort by revisit_rate as a proxy for popularity/reliability
        return sorted(providers, key=lambda p: p.revisit_rate or 0, reverse=True)
    else:
        # Default: rating DESC, review_count as tiebreaker
        return sorted(providers, key=lambda p: (-(p.rating or 0), -(p.review_count or 0)))


def _build_profile_memory(
    db: Session,
    customer_id: str,
    provider_id: str,
) -> UIBlock | None:
    """Build a ProfileMemoryCard block if the customer has booking history."""
    try:
        customer = CustomerService.get_customer(db, customer_id)
        if not customer:
            return None

        past_bookings = db.query(Booking).filter(
            Booking.provider_id == provider_id,
            Booking.customer_id == customer_id,
            Booking.status == "completed",
        ).order_by(Booking.scheduled_start.desc()).all()

        visit_count = len(past_bookings)
        last_visit: str | None = None
        if past_bookings:
            last_visit = past_bookings[0].scheduled_start.strftime("%Y-%m-%d")

        prefs = CustomerPreferenceService.get_provider_visible_preferences(
            db, customer_id, provider_id
        )
        pref_summaries = [
            PreferenceSummary(
                category=p.category,
                key=p.key,
                value=p.value,
                source=p.source,
                confidence=p.confidence,
            )
            for p in prefs
        ]

        if visit_count == 0 and not pref_summaries:
            return None

        return UIBlock(
            type="ProfileMemoryCard",
            emphasis=[],
            data=ProfileMemoryData(
                customer_id=customer_id,
                display_name=customer.display_name,
                visit_count=visit_count,
                last_visit=last_visit,
                preferences=pref_summaries,
                is_returning=visit_count > 0,
            ),
        )
    except Exception:
        logger.exception("Failed to build ProfileMemoryCard for customer %s", customer_id)
        return None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/search", response_model=SearchFeedResponse)
def search_feed(body: SearchFeedRequest, db: Session = Depends(get_db)):
    """
    Natural language search → dynamic UIBlock feed.

    Example prompts:
      "cheap but great hairstylists in östermalm"
      "nail salon today asap"
      "balayage near me, good reviews"
    """
    intent = parse_intent(body.prompt)

    # ── Load customer preferences (if caller provided a user_id) ─────────────
    service_interests: list[str] = []
    lifestyle_preferences: list[str] = []
    if body.customer_user_id:
        service_interests, lifestyle_preferences = _fetch_customer_prefs(
            db, body.customer_user_id
        )

    # ── Query providers ───────────────────────────────────────────────────────
    # If the prompt had no service category but the customer has saved interests,
    # use the first interest as a soft category hint (intent is still the primary
    # driver — this only fills the gap when the prompt is ambiguous).
    effective_category = intent.service_category
    if not effective_category and service_interests:
        # Use the first alias of each interest as a loose category hint
        effective_category = SERVICE_INTEREST_ALIASES.get(
            service_interests[0], [service_interests[0]]
        )[0]

    providers = ProviderService.search_providers(
        db=db,
        location=intent.location,
        service_category=effective_category,
    )

    # Name/Instagram search — runs alongside intent search.
    # Strip @ prefix so "@sofiahair" → search for "sofiahair".
    # Matches bubble to the top so customers can find a specific provider by name.
    name_query = body.prompt.lstrip('@').strip()
    if name_query:
        name_matches = ProviderService.search_providers(
            db=db,
            provider_name=name_query,
        )
        if name_matches:
            seen_ids = {p.provider_id for p in name_matches}
            # name-matched providers first, then intent results that aren't duplicates
            providers = name_matches + [p for p in providers if p.provider_id not in seen_ids]

    initial_result_count = len(providers)
    # Fallback: if no results at all, return all providers (sorted by rating)
    if not providers:
        providers = ProviderService.search_providers(db=db)

    # ── Bulk-load intelligence (one query for all providers) ──────────────────
    provider_ids = [p.provider_id for p in providers]
    intel_rows = (
        db.query(ProviderIntelligence)
        .filter(ProviderIntelligence.provider_id.in_(provider_ids))
        .all()
    ) if provider_ids else []
    intel_by_provider: dict[str, ProviderIntelligence] = {
        r.provider_id: r for r in intel_rows
    }

    # ── Bulk-load services for preference scoring (one query) ─────────────────
    services_by_provider: dict[str, list[Service]] = {}
    if service_interests or lifestyle_preferences:
        all_services = db.query(Service).filter(
            Service.provider_id.in_(provider_ids),
            Service.is_active.is_(True),
        ).all()
        for svc in all_services:
            services_by_provider.setdefault(svc.provider_id, []).append(svc)

    # ── Sort — vibe-boost when vibe signal detected, else normal strategy ─────
    if "vibe" in intent.signals and intent.vibe_tags:
        def _vibe_sort_key(p: Provider) -> tuple:
            intel = intel_by_provider.get(p.provider_id)
            if intel:
                tags = json.loads(
                    intel.confirmed_vibe_tags or intel.ai_vibe_tags or "[]"
                )
                boost = sum(1 for tag in intent.vibe_tags if tag in tags)
            else:
                boost = 0
            return (-boost, -(p.rating or 0))
        providers = sorted(providers, key=_vibe_sort_key)
    else:
        providers = _sort_providers(providers, intent.sort_strategy)

    # ── Preference re-rank — secondary boost on top of intent sort ────────────
    # Applied when the customer has saved preferences. Providers that match
    # their service interests or lifestyle amenities float to the top within
    # their quality tier.
    if service_interests or lifestyle_preferences:
        pref_scores: dict[str, int] = {}
        for p in providers:
            pref_scores[p.provider_id] = _preference_score(
                db=db,
                provider=p,
                service_interests=service_interests,
                lifestyle_preferences=lifestyle_preferences,
                provider_services=services_by_provider.get(p.provider_id, []),
            )
        # Stable sort: keep intent order as tiebreaker
        providers = sorted(
            providers,
            key=lambda p: -pref_scores.get(p.provider_id, 0),
            # Python sort is stable — equal scores preserve the prior intent order
        )

    # ── Assemble blocks ───────────────────────────────────────────────────────
    blocks: list[UIBlock] = []

    # 1. Profile memory — show at top if customer is returning
    if body.customer_id:
        for provider in providers[:1]:  # memory against first matched provider
            memory_block = _build_profile_memory(db, body.customer_id, provider.provider_id)
            if memory_block:
                blocks.append(memory_block)

    # 2. Search summary
    blocks.append(UIBlock(
        type="SearchSummaryCard",
        emphasis=[],
        data=SearchSummaryData(
            query=body.prompt,
            subtitle=intent.subtitle,
            parsed_location=intent.location,
            parsed_service=intent.service_category,
            detected_signals=intent.signals,
            result_count=len(providers),
        ),
    ))

    # 3. Provider results — each card gets intent-derived emphasis
    provider_cards: list[ProviderCardData] = []
    for provider in providers:
        services = ProviderService.get_provider_services(db, provider.provider_id)
        card = _build_provider_card(
            db, provider, intent, services,
            intelligence=intel_by_provider.get(provider.provider_id),
        )
        provider_cards.append(card)

    blocks.append(UIBlock(
        type="ProviderResults",
        emphasis=intent.emphasis,
        data=ProviderResultsData(
            providers=provider_cards,
            total_found=len(provider_cards),
            sort_strategy=intent.sort_strategy,
        ),
    ))

    # 4. CTA row — for when user wants to broaden the search
    if provider_cards:
        blocks.append(UIBlock(
            type="CTAButtonRow",
            emphasis=[],
            data=CTAButtonRowData(buttons=[
                CTAButton(
                    label="Book now",
                    action="open_availability",
                    provider_id=provider_cards[0].provider_id,
                    style="primary",
                ),
                CTAButton(
                    label="View profile",
                    action="open_profile",
                    provider_id=provider_cards[0].provider_id,
                    style="secondary",
                ),
                CTAButton(
                    label="Search more",
                    action="search_more",
                    style="ghost",
                ),
            ]),
        ))


    # Log zero-PII demand event for Merkle contribution batching.
    try:
        search_event = SearchEvent(
            query_category=intent.service_category,
            city=intent.location,
            result_count=initial_result_count,
            result_count_band=_result_count_band(initial_result_count),
            price_preference=_price_preference(intent.signals),
            converted_to_booking=False,
            platform="prompt_feed",
        )
        db.add(search_event)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to log search event")

    if body.customer_user_id:
        try:
            LoyaltyService.track_meaningful_search(
                db,
                customer_user_id=body.customer_user_id,
                prompt=body.prompt,
                result_count=initial_result_count,
            )
        except Exception:
            logger.exception("Loyalty search tracking failed user=%s", body.customer_user_id)

    return SearchFeedResponse(blocks=blocks, intent=intent.to_dict())


@router.post("/prompt", response_model=PromptFeedResponse)
def prompt_feed(body: PromptFeedRequest, db: Session = Depends(get_db)):
    """
    Prompt-first discovery feed.

    This is the next-generation search entrypoint:
        prompt -> intent profile -> feed recipe -> typed blocks
    """
    intent = parse_intent(body.prompt)
    intent_profile = _build_intent_profile(
        body.prompt,
        intent,
        customer_id=body.customer_id,
    )
    recipe = _build_feed_recipe(intent_profile)

    providers = ProviderService.search_providers(
        db=db,
        location=intent.location,
        service_category=intent.service_category,
    )

    name_query = body.prompt.lstrip("@").strip()
    if name_query:
        name_matches = ProviderService.search_providers(
            db=db,
            provider_name=name_query,
        )
        if name_matches:
            seen_ids = {p.provider_id for p in name_matches}
            providers = name_matches + [p for p in providers if p.provider_id not in seen_ids]

    if not providers:
        providers = ProviderService.search_providers(db=db)

    provider_ids = [p.provider_id for p in providers]
    intel_rows = (
        db.query(ProviderIntelligence)
        .filter(ProviderIntelligence.provider_id.in_(provider_ids))
        .all()
    ) if provider_ids else []
    intel_by_provider: dict[str, ProviderIntelligence] = {
        row.provider_id: row for row in intel_rows
    }

    if "vibe" in intent.signals and intent.vibe_tags:
        def _prompt_vibe_sort_key(provider: Provider) -> tuple:
            intelligence = intel_by_provider.get(provider.provider_id)
            if intelligence:
                tags = json.loads(
                    intelligence.confirmed_vibe_tags or intelligence.ai_vibe_tags or "[]"
                )
                vibe_boost = sum(1 for tag in intent.vibe_tags if tag in tags)
            else:
                vibe_boost = 0
            return (-vibe_boost, -(provider.rating or 0), provider.price_level or 2)

        providers = sorted(providers, key=_prompt_vibe_sort_key)
    else:
        providers = _sort_providers(providers, intent.sort_strategy)

    provider_cards: list[ProviderCardData] = []
    services_by_provider: dict[str, list[Service]] = {}
    for provider in providers:
        provider_services = ProviderService.get_provider_services(db, provider.provider_id)
        services_by_provider[provider.provider_id] = provider_services
        provider_cards.append(
            _build_provider_card(
                db,
                provider,
                intent,
                provider_services,
                intelligence=intel_by_provider.get(provider.provider_id),
            )
        )

    blocks_by_type: dict[str, UIBlock] = {
        "HeroCard": _build_hero_block(intent_profile, intent),
        "SearchSummaryCard": UIBlock(
            type="SearchSummaryCard",
            emphasis=[],
            data=SearchSummaryData(
                query=body.prompt,
                subtitle=intent.subtitle,
                parsed_location=intent.location,
                parsed_service=intent.service_category,
                detected_signals=intent.signals,
                result_count=len(provider_cards),
            ),
        ),
        "ProviderResults": UIBlock(
            type="ProviderResults",
            emphasis=intent.emphasis,
            data=ProviderResultsData(
                providers=provider_cards,
                total_found=len(provider_cards),
                sort_strategy=intent.sort_strategy,
            ),
        ),
        "CTAButtonRow": UIBlock(
            type="CTAButtonRow",
            emphasis=[],
            data=CTAButtonRowData(
                buttons=[
                    CTAButton(
                        label=(
                            "See times"
                            if recipe.primary_action == "open_availability"
                            else "Start booking"
                            if recipe.primary_action == "hold_slot"
                            else "View provider"
                        ),
                        action=recipe.primary_action,
                        provider_id=provider_cards[0].provider_id if provider_cards else None,
                        style="primary",
                    ),
                    CTAButton(
                        label="Refine search",
                        action="search_more",
                        style="secondary",
                    ),
                ]
            ),
        ),
        "ConversationalFollowUp": _build_follow_up_block(intent_profile, intent),
    }

    if body.customer_id and providers:
        memory_block = _build_profile_memory(db, body.customer_id, providers[0].provider_id)
        if memory_block:
            blocks_by_type["ProfileMemoryCard"] = memory_block

    if providers:
        top_provider = providers[0]
        top_services = services_by_provider.get(top_provider.provider_id, [])
        if top_services:
            slots_by_date, available_dates = _get_slots_for_picker(
                db,
                top_provider.provider_id,
                top_services,
                top_provider,
            )
            if available_dates:
                blocks_by_type["AvailabilityPicker"] = UIBlock(
                    type="AvailabilityPicker",
                    emphasis=["available_dates", "slots_by_date"],
                    data=AvailabilityPickerData(
                        provider_id=top_provider.provider_id,
                        provider_name=top_provider.name,
                        service_options=[_service_summary(service, top_provider) for service in top_services],
                        slots_by_date=slots_by_date,
                        available_dates=available_dates,
                    ),
                )

    ordered_blocks = [
        blocks_by_type[block_type]
        for block_type in recipe.ordered_blocks
        if block_type in blocks_by_type
    ]

    return PromptFeedResponse(
        blocks=ordered_blocks,
        intent=intent.to_dict(),
        intent_profile=intent_profile,
        recipe=recipe,
    )


@router.get("/provider/{provider_id}", response_model=ProviderFeedResponse)
def provider_feed(
    provider_id: str,
    customer_id: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Direct provider profile feed — used from Instagram DM deeplink.

    Returns:
        ProfileMemoryCard (if returning customer)
        ProviderCard (full profile, no search-driven emphasis)
        AvailabilityPicker (next 5 available days)
        CTAButtonRow
    """
    provider = ProviderService.get_provider(db, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    services = ProviderService.get_provider_services(db, provider_id)
    intel = db.query(ProviderIntelligence).filter(
        ProviderIntelligence.provider_id == provider_id
    ).first()
    blocks: list[UIBlock] = []

    # 1. Profile memory for returning customers
    if customer_id:
        memory_block = _build_profile_memory(db, customer_id, provider_id)
        if memory_block:
            blocks.append(memory_block)

    # 2. Provider card — no intent emphasis, show everything balanced
    card = _build_provider_card(db, provider, intent=None, all_services=services, intelligence=intel)
    blocks.append(UIBlock(
        type="ProviderCard",
        emphasis=["rating", "revisit_rate", "services", "next_available"],
        data=card,
    ))

    # 3. Availability picker
    slots_by_date, available_dates = _get_slots_for_picker(db, provider_id, services, provider)
    service_summaries = [_service_summary(s, provider) for s in services]
    blocks.append(UIBlock(
        type="AvailabilityPicker",
        emphasis=["available_dates", "slots_by_date"],
        data=AvailabilityPickerData(
            provider_id=provider_id,
            provider_name=provider.name,
            service_options=service_summaries,
            slots_by_date=slots_by_date,
            available_dates=available_dates,
        ),
    ))

    # 4. CTA
    blocks.append(UIBlock(
        type="CTAButtonRow",
        emphasis=[],
        data=CTAButtonRowData(buttons=[
            CTAButton(
                label="Book appointment",
                action="book_now",
                provider_id=provider_id,
                style="primary",
            ),
            CTAButton(
                label="Message provider",
                action="open_dm",
                provider_id=provider_id,
                style="secondary",
            ),
        ]),
    ))

    return ProviderFeedResponse(blocks=blocks)
