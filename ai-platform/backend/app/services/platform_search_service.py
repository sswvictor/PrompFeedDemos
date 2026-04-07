"""
PlatformSearchService - cross-provider search for the @fixmeapp discovery bot.

Customers DM @fixmeapp asking for a hairdresser / nail salon / etc. nearby.
This service searches across ALL providers on the platform and returns ranked
results with real-time availability.

Design principles:
- DB-level text search first (fast, no GPT cost)
- Availability checked per matched (provider, service) pair
- Optional hard filters for required amenities (e.g. dog_friendly + wine)
- Results ranked by intent score
- Max 5 results to keep DM replies readable
"""

import json
import logging
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.provider import Provider
from app.models.provider_amenity import ProviderAmenity
from app.models.provider_intelligence import ProviderIntelligence
from app.models.service import Service
from app.api.intent import _VIBE_KEYWORDS
from app.services.availability_service import AvailabilityService

logger = logging.getLogger(__name__)

MAX_RESULTS = 5
MAX_SLOTS_SHOWN = 3  # Slots per provider shown in results


def search_providers(
    db: Session,
    service_query: str,
    city: str | None = None,
    date: datetime | None = None,
    max_price_inc_vat: float | None = None,
    amenity_keys: list[str] | None = None,
    vibe_tags: list[str] | None = None,
) -> list[dict]:
    """Search providers by service + city + optional date/price/amenity/vibe filters."""
    q = service_query.strip().lower()

    # Detect vibe tags from the query if not provided by caller
    if vibe_tags is None:
        detected: list[str] = []
        for kw in sorted(_VIBE_KEYWORDS.keys(), key=len, reverse=True):
            if kw in q:
                tag = _VIBE_KEYWORDS[kw]
                if tag not in detected:
                    detected.append(tag)
        vibe_tags = detected or None

    # Step 1: DB-level service search (name + keywords)
    query = (
        db.query(Service, Provider)
        .join(Provider, Service.provider_id == Provider.provider_id)
        .filter(
            Service.is_active == True,  # noqa: E712
            or_(
                Service.name.ilike(f"%{q}%"),
                Service.keywords.ilike(f"%{q}%"),
                Service.category.ilike(f"%{q}%"),
            ),
        )
    )

    if city:
        city_q = city.strip().lower()
        query = query.filter(Provider.city.ilike(f"%{city_q}%"))

    if max_price_inc_vat:
        max_ex_vat = max_price_inc_vat / 1.25
        query = query.filter(Service.price_ex_vat <= max_ex_vat)

    matches = query.limit(40).all()

    if not matches:
        logger.info("platform.search no_results query=%r city=%r", service_query, city)
        return []

    required_amenities = {
        key.strip().lower()
        for key in (amenity_keys or [])
        if isinstance(key, str) and key.strip()
    }

    if required_amenities:
        provider_ids = {provider.provider_id for _, provider in matches}
        amenity_rows = (
            db.query(ProviderAmenity.provider_id, ProviderAmenity.amenity_key)
            .filter(
                ProviderAmenity.provider_id.in_(provider_ids),
                ProviderAmenity.is_active == True,  # noqa: E712
                ProviderAmenity.amenity_key.in_(required_amenities),
            )
            .all()
        )

        provider_to_keys: dict[str, set[str]] = {}
        for provider_id, amenity_key in amenity_rows:
            provider_to_keys.setdefault(provider_id, set()).add(amenity_key)

        matches = [
            (service, provider)
            for service, provider in matches
            if required_amenities.issubset(provider_to_keys.get(provider.provider_id, set()))
        ]

        if not matches:
            logger.info(
                "platform.search no_results_amenities query=%r city=%r amenities=%s",
                service_query,
                city,
                sorted(required_amenities),
            )
            return []

    # Step 2: Check availability per (provider, service)
    results = []
    seen_providers = set()

    for service, provider in matches:
        if provider.provider_id in seen_providers:
            continue

        slots = []
        has_availability = False

        if date:
            try:
                raw_slots = AvailabilityService.get_available_slots(
                    db=db,
                    provider_id=provider.provider_id,
                    date=date,
                    duration_minutes=service.duration_minutes,
                )
                slots = [s["start"] for s in raw_slots[:MAX_SLOTS_SHOWN]]
                has_availability = len(raw_slots) > 0
            except Exception as e:
                logger.warning("platform.search availability_error provider=%s: %s", provider.provider_id, e)
                has_availability = None
        else:
            has_availability = None

        if date and has_availability is False:
            continue

        price_inc_vat = round(service.price_ex_vat * 1.25)

        results.append(
            {
                "provider_id": provider.provider_id,
                "provider_name": provider.name,
                "city": provider.city or "",
                "service_id": service.service_id,
                "service_name": service.name,
                "duration_minutes": service.duration_minutes,
                "price_inc_vat": price_inc_vat,
                "slots": slots,
                "has_availability": has_availability,
                "instagram_username": provider.instagram_username,
                "slug": provider.slug,
            }
        )
        seen_providers.add(provider.provider_id)

        if len(results) >= MAX_RESULTS:
            break

    # Step 3: Score by customer intent
    # Bulk-load intelligence for vibe scoring (one query, not N)
    intel_by_provider: dict[str, ProviderIntelligence] = {}
    if vibe_tags and results:
        result_provider_ids = [r["provider_id"] for r in results]
        intel_rows = (
            db.query(ProviderIntelligence)
            .filter(ProviderIntelligence.provider_id.in_(result_provider_ids))
            .all()
        )
        intel_by_provider = {row.provider_id: row for row in intel_rows}

    def _intent_score(r: dict) -> float:
        score = 0.0

        sname = r["service_name"].lower()
        if q == sname:
            score += 10.0
        elif q in sname or sname in q:
            score += 7.0
        else:
            score += 3.0

        score += min(len(r["slots"]) * 2.0, 6.0)

        if r.get("instagram_username"):
            score += 2.0
        if r.get("slug"):
            score += 1.0

        price = r["price_inc_vat"]
        if price <= 500:
            score += 4.0
        elif price <= 800:
            score += 3.0
        elif price <= 1200:
            score += 2.0
        elif price <= 2000:
            score += 1.0

        # Vibe match bonus (+3 per matched tag)
        if vibe_tags:
            intel = intel_by_provider.get(r["provider_id"])
            if intel:
                tags = json.loads(intel.confirmed_vibe_tags or intel.ai_vibe_tags or "[]")
                score += sum(3.0 for tag in vibe_tags if tag in tags)

        return score

    results.sort(key=_intent_score, reverse=True)

    logger.info(
        "platform.search query=%r city=%r date=%s amenities=%s results=%d",
        service_query,
        city,
        date.strftime("%Y-%m-%d") if date else "any",
        sorted(required_amenities) if required_amenities else [],
        len(results),
    )
    return results
