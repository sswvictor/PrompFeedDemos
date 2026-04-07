"""
Setup API — post-onboarding profile enrichment.

Routes:
    POST /setup/import-url      — Scrape an existing booking page/website and
                                   extract services, hours, bio, city, policies
                                   via AI. Returns structured preview for the
                                   provider to confirm before applying.

    POST /setup/import-apply    — Apply a previously-scraped profile payload to
                                   the provider's profile, services, hours, and
                                   policy settings.

    POST /setup/verify-business — Submit org number (+ optional document) for
                                   business verification. AI reads the document
                                   and extracts registration details. Human
                                   review finalises the Verified Pro badge.

All endpoints require an authenticated provider JWT (get_current_provider).
"""

import json
import logging
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from app.api.auth import get_current_provider, get_current_user_id
from app.config import settings
from app.db.session import get_db
from app.models.provider import Provider
from app.models.availability import Availability
from app.models.provider_amenity import ProviderAmenity
from app.models.service import Service
from app.models.business_verification import BusinessVerification
from app.services.availability_service import AvailabilityService
from openai import OpenAI

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/setup", tags=["setup"])
client = OpenAI(api_key=settings.OPENAI_API_KEY)

MAX_DOC_BYTES = 20 * 1024 * 1024   # 20 MB
ALLOWED_DOC_TYPES = {"image/jpeg", "image/png", "application/pdf"}
DAY_INDEX = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ImportUrlRequest(BaseModel):
    url: str


class ScrapedService(BaseModel):
    name: str
    category: Optional[str] = None
    duration_minutes: Optional[int] = None
    price: Optional[float] = None
    description: Optional[str] = None


class ScrapedHours(BaseModel):
    open: bool
    start: Optional[str] = None   # "HH:MM"
    end: Optional[str] = None     # "HH:MM"


class ImportUrlResponse(BaseModel):
    source_url: str
    name: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None   # Street address (e.g. "Kungsgatan 12")
    bio: Optional[str] = None
    services: list[ScrapedService] = []
    working_hours: Optional[dict[str, ScrapedHours]] = None
    amenity_keys: list[str] = []
    booking_policy: Optional[str] = None
    cancellation_policy: Optional[str] = None


class ImportApplyRequest(BaseModel):
    """
    Apply a confirmed import payload to the provider profile.
    source_url is optional so the mobile app can send partial payloads
    (e.g. just working_hours) without requiring the full scan result.
    """
    source_url: Optional[str] = None
    name: Optional[str] = None
    city: Optional[str] = None
    bio: Optional[str] = None
    services: list[ScrapedService] = []
    working_hours: Optional[dict[str, ScrapedHours]] = None
    amenity_keys: list[str] = []
    booking_policy: Optional[str] = None
    cancellation_policy: Optional[str] = None


class VibeTagScore(BaseModel):
    tag: str
    score: float
    dimension: str


class ScanWebsiteResponse(ImportUrlResponse):
    """
    Extended response for the /setup/scan-website endpoint.
    Includes richer AI-profile fields used by the discovery engine.
    """
    specialties:    list[str]         = []
    price_tier:     Optional[str]     = None   # budget | mid-range | premium | luxury
    target_audience: Optional[str]   = None
    unique_value:   Optional[str]     = None
    social_proof:   list[str]         = []

    # AI-suggested vibe tags (for onboarding vibe confirmation step)
    ai_vibe_tags:   list[VibeTagScore] = []
    vibe_summary:   Optional[str]     = None


class VerifyBusinessResponse(BaseModel):
    submitted: bool
    org_number: str
    extracted_name: Optional[str] = None
    extracted_country: Optional[str] = None
    message: str


# ── Helpers ───────────────────────────────────────────────────────────────────


def _to_minutes(hhmm: str) -> int:
    hour_str, minute_str = hhmm.split(":")
    return int(hour_str) * 60 + int(minute_str)


def _to_price_ex_vat(price_inc_or_ex: float | None, vat_percent: float) -> float:
    if price_inc_or_ex is None:
        return 0.0
    value = max(float(price_inc_or_ex), 0.0)
    if vat_percent <= 0:
        return round(value, 2)
    return round(value / (1 + vat_percent / 100.0), 2)


def _upsert_import_services(
    db: Session,
    provider: Provider,
    services: list[ScrapedService],
) -> None:
    existing_rows = (
        db.query(Service)
        .filter(Service.provider_id == provider.provider_id)
        .all()
    )
    existing_by_name = {s.name.strip().lower(): s for s in existing_rows if s.name}
    vat_percent = float(provider.vat_percent or 25.0)

    for svc in services:
        name = (svc.name or "").strip()
        if not name:
            continue

        key = name.lower()
        duration = int(svc.duration_minutes or 60)
        duration = max(5, min(duration, 480))
        price_ex_vat = _to_price_ex_vat(svc.price, vat_percent)

        row = existing_by_name.get(key)
        if row:
            row.duration_minutes = duration
            row.price_ex_vat = price_ex_vat
            row.vat_percent = vat_percent
            row.is_active = True
            if svc.description:
                row.description = svc.description[:1024]
            continue

        db.add(
            Service(
                service_id=str(uuid.uuid4()),
                provider_id=provider.provider_id,
                name=name[:255],
                category=(svc.category[:128] if svc.category else None),
                description=(svc.description or None),
                duration_minutes=duration,
                price_ex_vat=price_ex_vat,
                vat_percent=vat_percent,
                is_active=True,
                home_service_available=bool(provider.home_service),
            )
        )

    db.commit()


def _fetch_html(url: str) -> str:
    """
    Fetch a URL and return the HTML as a UTF-8 string.

    Uses resp.content.decode() rather than resp.text to avoid silent encoding
    failures on gzip-compressed pages with non-ASCII (e.g. Swedish) content.
    resp.text lets httpx auto-detect charset, which sometimes misdetects UTF-8
    pages as cp1252 and returns garbled bytes instead of text.
    """
    import httpx
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "sv-SE,sv;q=0.9,en-US,en;q=0.8",
    }
    try:
        resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=20)
        # Always decode from raw bytes as UTF-8 — avoids charset mis-detection
        # on gzip-compressed Swedish/Unicode pages when using resp.text.
        return resp.content.decode("utf-8", errors="replace")
    except Exception as exc:
        logger.warning("URL fetch failed for %s: %s", url, exc)
        return ""


# ── Bokadirekt dedicated scraper ──────────────────────────────────────────────

_SKIP_CATEGORIES = {"Presentkort"}  # gift card category — not a bookable service
_SKIP_SERVICE_NAMES = {"presentkort"}  # gift card services inside other categories


def _parse_bokadirekt(url: str, html: str) -> dict | None:
    """
    Extract structured profile data from a Bokadirekt place page.

    Bokadirekt embeds all service data as window.__PRELOADED_STATE__ in the
    server-rendered HTML, so no JS execution or AI call is needed.

    Returns a dict matching ImportUrlResponse fields, or None if the state
    block is not found (page is not a Bokadirekt place page).
    """
    match = re.search(r'window\.__PRELOADED_STATE__\s*=\s*(\{)', html)
    if not match:
        return None

    # Extract balanced JSON starting from the opening brace
    start = match.start(1)
    depth = 0
    end = start
    for i in range(start, min(start + 2_000_000, len(html))):
        c = html[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    try:
        state = json.loads(html[start:end])
    except Exception as exc:
        logger.warning("Bokadirekt: __PRELOADED_STATE__ JSON parse failed: %s", exc)
        return None

    place = state.get("place", {})
    about = place.get("about", {})
    contact = place.get("contact", {})

    name = about.get("name") or place.get("name")
    bio = about.get("description") or about.get("about") or ""
    if bio:
        # Strip markdown-style newlines and trim to 500 chars
        bio = re.sub(r"\n{2,}", " | ", bio).strip()[:500]

    # Street address + city from contact block
    address_obj = contact.get("address", {})
    city = address_obj.get("city") or address_obj.get("addressLocality") or "Stockholm"
    street_address = address_obj.get("streetAddress") or address_obj.get("street") or None

    # ── Services ─────────────────────────────────────────────────────────────
    services: list[dict] = []
    for group in place.get("services", []):
        category_name = (group.get("name") or "").strip()
        if category_name in _SKIP_CATEGORIES:
            continue

        for svc in group.get("services", []):
            svc_name = (svc.get("name") or "").strip()
            if not svc_name:
                continue
            if svc_name.lower() in _SKIP_SERVICE_NAMES:
                continue

            # duration: Bokadirekt stores in seconds; displayDuration preferred
            svc_about = svc.get("about", {})
            raw_duration = (
                svc_about.get("displayDuration")
                or svc.get("duration")
                or 3600
            )
            duration_minutes = max(5, int(raw_duration) // 60)

            # price: use max (svc["price"]) — inc VAT; _upsert strips VAT later.
            # For range services the "price" field already holds the max.
            price_inc_vat = svc.get("price")
            if price_inc_vat is None:
                # Try parsing the priceLabel "1 200 kr" or "299-600 kr"
                label = svc.get("priceLabel", "")
                nums = re.findall(r"\d[\d\s]*", label)
                if nums:
                    price_inc_vat = float(nums[-1].replace(" ", ""))

            description = (svc_about.get("description") or "").strip()[:512] or None

            services.append({
                "name": svc_name,
                "category": category_name,
                "duration_minutes": duration_minutes,
                "price": float(price_inc_vat) if price_inc_vat is not None else None,
                "description": description,
            })

    # ── Opening hours from HTML body (all days are in a single <ul> after the heading) ──
    working_hours: dict | None = None
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        hours_heading = soup.find(
            lambda t: t.name in ("h2", "h3", "h4") and "ppettider" in (t.get_text() or "")
        )
        if hours_heading:
            # Bokadirekt puts all days in one <ul> immediately after the heading.
            # Grab that ul and read the full text — all days are in one block.
            ul = hours_heading.find_next_sibling("ul")
            block_text = (ul.get_text(separator=" ", strip=True) if ul else "").lower()

            day_map = {
                "måndag": "Mon", "tisdag": "Tue", "onsdag": "Wed",
                "torsdag": "Thu", "fredag": "Fri", "lördag": "Sat",
                "söndag": "Sun",
            }
            hours: dict[str, dict] = {}
            # Split on day names and extract time ranges
            for swe, eng in day_map.items():
                if swe not in block_text:
                    continue
                # Find the slice of text after this day name
                idx = block_text.index(swe) + len(swe)
                snippet = block_text[idx:idx + 30]
                time_match = re.search(r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})", snippet)
                if time_match:
                    hours[eng] = {
                        "open": True,
                        "start": time_match.group(1),
                        "end": time_match.group(2),
                    }
                elif "stängt" in snippet or "closed" in snippet:
                    hours[eng] = {"open": False}
            if hours:
                working_hours = hours
    except Exception as exc:
        logger.debug("Bokadirekt hours parse failed: %s", exc)

    return {
        "name": name,
        "city": city,
        "address": street_address,
        "bio": bio or None,
        "services": services,
        "working_hours": working_hours,
        "amenity_keys": [],
        "booking_policy": None,
        "cancellation_policy": None,
    }


def _is_bokadirekt_url(url: str) -> bool:
    return "bokadirekt.se/places/" in url.lower()


def _scrape_url_content(url: str) -> str:
    """
    Fetch and extract text content from a URL.

    Strategy (in priority order):
    1. JSON-LD structured data (richest, most reliable)
    2. Open Graph / meta tags (title, description, keywords)
    3. Main body text — headings, paragraphs, list items (BeautifulSoup)
    """
    import httpx
    try:
        from bs4 import BeautifulSoup
        _has_bs4 = True
    except ImportError:
        _has_bs4 = False

    html = _fetch_html(url)
    if not html:
        return ""

    if not _has_bs4:
        # Fallback: regex strip
        text = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s{3,}", "\n", text)
        return text[:12000]

    soup = BeautifulSoup(html, "lxml")

    parts: list[str] = []

    # ── 1. JSON-LD structured data ───────────────────────────────────────────
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                for field in ("name", "description", "telephone", "address",
                              "openingHours", "priceRange", "servesCuisine",
                              "hasOfferCatalog", "url"):
                    val = item.get(field)
                    if val:
                        parts.append(f"{field}: {val}")
        except Exception:
            pass

    # ── 2. Open Graph / meta tags ────────────────────────────────────────────
    og_map = {
        "og:title": "og:title", "og:description": "og:description",
        "og:site_name": "og:site_name",
        "description": "description", "keywords": "keywords",
    }
    for name, label in og_map.items():
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            parts.append(f"{label}: {tag['content']}")

    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        parts.append(f"page_title: {title_tag.string.strip()}")

    # ── 3. Body text — headings, paragraphs, list items ──────────────────────
    for tag in soup.find_all(["h1", "h2", "h3", "p", "li", "span", "td", "th"]):
        if tag.find_parent(["nav", "footer", "header", "aside"]):
            continue
        classes = " ".join(tag.get("class", []))
        if any(k in classes.lower() for k in ("cookie", "banner", "popup", "modal", "nav", "menu")):
            continue
        text = tag.get_text(separator=" ", strip=True)
        if len(text) > 20:
            parts.append(text)

    combined = "\n".join(parts)
    combined = re.sub(r" {3,}", " ", combined)
    combined = re.sub(r"\n{4,}", "\n\n", combined)
    return combined[:14000]


def _ai_extract_profile(url: str, page_text: str) -> dict:
    """
    Ask GPT-4o to extract structured profile data from raw page text.
    Returns a dict matching ImportUrlResponse fields.
    """
    system_prompt = (
        "You are a data-extraction assistant for a beauty & wellness booking platform. "
        "Given the raw text from a provider's booking or website page, extract the following "
        "fields as a JSON object (omit fields you cannot find):\n\n"
        "- name (string): provider or business name\n"
        "- city (string): city where the business operates\n"
        "- address (string): street address e.g. 'Kungsgatan 12' — omit house number if not found\n"
        "- bio (string): short about/description, max 300 chars\n"
        "- services (array): [{name, category, duration_minutes, price, description}] — include all services found\n"
        "- working_hours (object): {Mon,Tue,Wed,Thu,Fri,Sat,Sun: {open: bool, start: 'HH:MM', end: 'HH:MM'}}\n"
        "- amenity_keys (array of strings): e.g. ['wifi','parking','card_payment','cash_only']\n"
        "- booking_policy (string): booking/deposit policy text, max 200 chars\n"
        "- cancellation_policy (string): cancellation policy text, max 200 chars\n\n"
        "Return ONLY valid JSON, no markdown fences."
    )
    user_content = f"URL: {url}\n\nPage content:\n{page_text}"

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
            max_tokens=2000,
        )
        raw = response.choices[0].message.content.strip()
        return json.loads(raw)
    except Exception as exc:
        logger.error("AI extraction failed: %s", exc)
        return {}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/import-url", response_model=ImportUrlResponse)
async def import_url(
    body: ImportUrlRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Scrape a booking page or website URL and return extracted profile data
    for the provider to review before applying.

    Supported platforms with dedicated scrapers:
        Bokadirekt — uses __PRELOADED_STATE__ (exact services, prices, durations)

    All other URLs: generic HTML scrape + GPT-4o-mini extraction.
    """
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Try Bokadirekt dedicated parser first (no AI needed, exact data)
    if _is_bokadirekt_url(url):
        html = _fetch_html(url)
        if not html:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not fetch that URL. Check it's publicly accessible and try again.",
            )
        extracted = _parse_bokadirekt(url, html)
        if not extracted:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not parse Bokadirekt page. The URL may not be a place page.",
            )
    else:
        page_text = _scrape_url_content(url)
        if not page_text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not fetch that URL. Check it's publicly accessible and try again.",
            )
        extracted = _ai_extract_profile(url, page_text)
        if not extracted:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Couldn't extract profile data from that page. Try a different URL.",
            )

    # Parse and validate working_hours sub-model if present
    working_hours = None
    if raw_hours := extracted.get("working_hours"):
        try:
            working_hours = {
                day: ScrapedHours(**vals)
                for day, vals in raw_hours.items()
                if day in {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
            }
        except Exception:
            working_hours = None

    return ImportUrlResponse(
        source_url=url,
        name=extracted.get("name"),
        city=extracted.get("city"),
        address=extracted.get("address"),
        bio=extracted.get("bio"),
        services=[ScrapedService(**s) for s in extracted.get("services", []) if isinstance(s, dict)],
        working_hours=working_hours,
        amenity_keys=extracted.get("amenity_keys", []),
        booking_policy=extracted.get("booking_policy"),
        cancellation_policy=extracted.get("cancellation_policy"),
    )


@router.post("/import-apply", status_code=status.HTTP_200_OK)
async def import_apply(
    body: ImportApplyRequest,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """
    Apply a confirmed import payload to the provider's profile.

    Updates: provider bio, city, amenities, booking/cancellation policy.
    Services and working hours are upserted via their own tables.
    """
    provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    # Update provider fields
    if body.bio:
        provider.bio = body.bio[:500]
    if body.city:
        provider.city = body.city
    if body.booking_policy:
        provider.booking_policy = body.booking_policy[:500]
    if body.cancellation_policy:
        provider.cancellation_policy = body.cancellation_policy[:500]

    # Upsert amenities
    if body.amenity_keys:
        existing_keys = {a.amenity_key for a in provider.amenities}
        for key in body.amenity_keys:
            if key not in existing_keys:
                db.add(ProviderAmenity(provider_id=provider.provider_id, amenity_key=key, is_active=True))

        # Keep boolean flag in sync with amenities.
        if "home_visits" in body.amenity_keys:
            provider.home_service = True

    # Upsert weekly working hours from scraped payload.
    if body.working_hours:
        for day, values in body.working_hours.items():
            day_idx = DAY_INDEX.get(day)
            if day_idx is None:
                continue

            if not values.open:
                (
                    db.query(Availability)
                    .filter(
                        Availability.provider_id == provider.provider_id,
                        Availability.day_of_week == day_idx,
                    )
                    .delete()
                )
                continue

            if not values.start or not values.end:
                continue

            try:
                AvailabilityService.set_working_hours(
                    db=db,
                    provider_id=provider.provider_id,
                    day_of_week=day_idx,
                    start_minutes=_to_minutes(values.start),
                    end_minutes=_to_minutes(values.end),
                )
            except Exception as exc:
                logger.warning("Working-hours upsert failed for day %s: %s", day, exc)

    db.commit()
    db.refresh(provider)

    # Upsert scraped services (non-blocking fail)
    if body.services:
        try:
            _upsert_import_services(db, provider, body.services)
        except Exception as exc:
            logger.warning("Service upsert failed during import-apply: %s", exc)

    return {"applied": True, "provider_id": provider.provider_id}


def _ai_extract_website_profile(url: str, page_text: str) -> dict:
    """
    Enhanced extraction for the website-scan endpoint.
    Returns all ImportUrlResponse fields PLUS richer AI-profile fields
    (specialties, price_tier, target_audience, unique_value, social_proof).
    """
    system_prompt = (
        "You are an AI data-extraction assistant for a beauty & wellness discovery platform. "
        "Analyze the given website page text and extract a comprehensive structured profile "
        "to power our AI discovery engine. Return ONLY valid JSON (no markdown fences).\n\n"
        "Required fields (omit if not found):\n"
        "- name (string): business or provider name\n"
        "- city (string): city where they operate\n"
        "- address (string): street address e.g. 'Kungsgatan 12' — omit if not found\n"
        "- bio (string): compelling description in their voice, 150–300 chars\n"
        "- services (array): [{name, duration_minutes, price, description}] — all services/treatments\n"
        "- working_hours (object): {Mon,Tue,Wed,Thu,Fri,Sat,Sun: {open:bool, start:'HH:MM', end:'HH:MM'}}\n"
        "- amenity_keys (array of strings): e.g. ['wifi','parking','card_payment','private_room']\n"
        "- booking_policy (string): booking/deposit policy, max 200 chars\n"
        "- cancellation_policy (string): cancellation policy, max 200 chars\n\n"
        "Enhanced AI-profile fields:\n"
        "- specialties (array of 3–6 strings): unique skills or signature services\n"
        "- price_tier (string): one of 'budget' | 'mid-range' | 'premium' | 'luxury'\n"
        "- target_audience (string): who they primarily serve, max 100 chars\n"
        "- unique_value (string): what makes them stand out from competitors, max 200 chars\n"
        "- social_proof (array of up to 3 strings): verbatim testimonial or review quotes found on page\n\n"
        "Vibe & aesthetic analysis:\n"
        "- vibe_tags (array of objects): [{tag, score, dimension}] — pick 3-6 tags from these dimensions:\n"
        "  aesthetic: minimalist, maximalist, editorial, boho, classic, avant-garde, natural, glamorous, industrial, vintage\n"
        "  energy: calm, energetic, luxurious, cozy, edgy, playful, sophisticated, zen, bold, intimate\n"
        "  style_era: modern, retro, timeless, trendsetting, traditional\n"
        "  brand_personality: artistic, clinical, boutique, eco-conscious, tech-forward, family-friendly, exclusive, community-driven\n"
        "  Each tag object: {\"tag\": \"minimalist\", \"score\": 0.85, \"dimension\": \"aesthetic\"}\n"
        "- vibe_summary (string): 1-2 sentences describing their overall vibe, max 150 chars\n"
    )
    user_content = f"URL: {url}\n\nPage content:\n{page_text}"

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content},
            ],
            temperature=0.1,
            max_tokens=2500,
        )
        raw = response.choices[0].message.content.strip()
        return json.loads(raw)
    except Exception as exc:
        logger.error("Enhanced AI website extraction failed: %s", exc)
        return {}


@router.post("/scan-website", response_model=ScanWebsiteResponse)
async def scan_website(
    body: ImportUrlRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Scan any website (homepage, social page, booking platform) and return
    a rich AI-profile payload for the provider to review and confirm.

    This is the primary onboarding endpoint — it extracts everything needed
    for the Fixmeapp discovery engine: services, hours, bio, specialties,
    price tier, testimonials, and unique value proposition.

    Bokadirekt place pages use __PRELOADED_STATE__ (exact data, no AI needed).
    All other URLs fall back to generic HTML + GPT-4o-mini extraction.
    """
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Bokadirekt: exact data from __PRELOADED_STATE__, no AI token cost
    if _is_bokadirekt_url(url):
        html = _fetch_html(url)
        if not html:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not fetch that URL. Check it's publicly accessible and try again.",
            )
        extracted = _parse_bokadirekt(url, html)
        if not extracted:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not parse Bokadirekt page. The URL may not be a place page.",
            )
        # Bokadirekt doesn't provide AI-enriched fields; use defaults
        extracted.setdefault("specialties", [])
        extracted.setdefault("price_tier", None)
        extracted.setdefault("target_audience", None)
        extracted.setdefault("unique_value", None)
        extracted.setdefault("social_proof", [])
        extracted.setdefault("vibe_tags", [])
        extracted.setdefault("vibe_summary", None)
    else:
        page_text = _scrape_url_content(url)
        if not page_text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not fetch that URL. Check it's publicly accessible and try again.",
            )
        extracted = _ai_extract_website_profile(url, page_text)
        if not extracted:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Couldn't extract profile data from that page. Try a different URL.",
            )

    # Parse working_hours
    working_hours = None
    if raw_hours := extracted.get("working_hours"):
        try:
            working_hours = {
                day: ScrapedHours(**vals)
                for day, vals in raw_hours.items()
                if day in {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
            }
        except Exception:
            working_hours = None

    # Parse vibe tags from AI response
    raw_vibe_tags = extracted.get("vibe_tags", [])
    ai_vibe_tags = []
    for vt in raw_vibe_tags:
        if isinstance(vt, dict) and "tag" in vt:
            ai_vibe_tags.append(VibeTagScore(
                tag=vt["tag"],
                score=vt.get("score", 0.5),
                dimension=vt.get("dimension", "unknown"),
            ))

    return ScanWebsiteResponse(
        source_url=url,
        name=extracted.get("name"),
        city=extracted.get("city"),
        address=extracted.get("address"),
        bio=extracted.get("bio"),
        services=[
            ScrapedService(**s)
            for s in extracted.get("services", [])
            if isinstance(s, dict)
        ],
        working_hours=working_hours,
        amenity_keys=extracted.get("amenity_keys", []),
        booking_policy=extracted.get("booking_policy"),
        cancellation_policy=extracted.get("cancellation_policy"),
        specialties=extracted.get("specialties", []),
        price_tier=extracted.get("price_tier"),
        target_audience=extracted.get("target_audience"),
        unique_value=extracted.get("unique_value"),
        social_proof=extracted.get("social_proof", []),
        ai_vibe_tags=ai_vibe_tags,
        vibe_summary=extracted.get("vibe_summary"),
    )


@router.post("/verify-business", response_model=VerifyBusinessResponse)
async def verify_business(
    # US professional-license fields
    country: str = Form(default="US", description="ISO-3166 country code, e.g. US, SE, GB"),
    us_state: Optional[str] = Form(default=None, description="US state code, e.g. CA (US only)"),
    license_type: Optional[str] = Form(default=None, description="e.g. cosmetologist, barber (US only)"),
    license_number: Optional[str] = Form(default=None, description="Professional license number (US)"),
    # Non-US business reg number
    org_number: Optional[str] = Form(default=None, description="Business registration / org number (non-US)"),
    # Optional supporting document
    document: Optional[UploadFile] = File(
        default=None,
        description="License certificate or business reg doc (PDF, JPG, PNG). Speeds up review.",
    ),
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """
    Submit for business / professional-license verification to earn the Verified Pro badge.

    US providers: submit state + license_type + license_number.
    Non-US providers: submit org_number (business registration).
    An optional document upload speeds up manual review.

    All submissions go to a manual review queue. Sensitive identifiers are
    deleted from the database immediately after an admin approves or rejects.
    """
    provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    country = (country or "US").strip().upper()[:2]

    # Validate required fields per country
    if country == "US":
        if not license_number or not license_number.strip():
            raise HTTPException(status_code=400, detail="license_number is required for US providers")
    else:
        if not org_number or not org_number.strip():
            raise HTTPException(status_code=400, detail="org_number is required for non-US providers")

    # Normalise
    license_number = license_number.strip() if license_number else None
    org_number = org_number.strip() if org_number else None
    us_state = us_state.strip().upper()[:2] if us_state else None
    license_type = license_type.strip().lower() if license_type else None

    extracted_name: Optional[str] = None
    document_filename: Optional[str] = None

    # ── AI document read (if provided) ──────────────────────────────────────
    if document:
        if document.content_type not in ALLOWED_DOC_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported document type: {document.content_type}. Use PDF, JPG or PNG.",
            )
        doc_bytes = await document.read()
        if len(doc_bytes) > MAX_DOC_BYTES:
            raise HTTPException(status_code=400, detail="Document exceeds 20 MB limit.")

        document_filename = document.filename

        try:
            import base64
            b64 = base64.b64encode(doc_bytes).decode()
            mime = document.content_type

            if mime != "application/pdf":
                # Image: use GPT-4o Vision to cross-check name / number
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "This is a professional license or business registration certificate. "
                                    "Extract as JSON: {holder_name, license_number, license_type, state, country, expiry_date}. "
                                    "Return ONLY valid JSON, null for missing fields."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{b64}"},
                            },
                        ],
                    }],
                    max_tokens=300,
                )
                raw = response.choices[0].message.content.strip()
                parsed = json.loads(raw)
                extracted_name = parsed.get("holder_name")
        except Exception as exc:
            logger.warning("Document AI extraction failed: %s", exc)

    # ── Check for existing pending submission ────────────────────────────────
    existing = (
        db.query(BusinessVerification)
        .filter(
            BusinessVerification.provider_id == provider_id,
            BusinessVerification.status == "pending",
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="You already have a pending verification request. We'll review it within 24 h.",
        )

    # ── Store to business_verifications table ────────────────────────────────
    verification = BusinessVerification(
        provider_id=provider_id,
        country=country,
        us_state=us_state,
        license_type=license_type,
        license_number=license_number,
        org_number=org_number,
        document_filename=document_filename,
        status="pending",
    )
    db.add(verification)

    # Mark provider as pending (not yet verified)
    provider.verification_source = "manual_review_pending"
    db.commit()

    logger.info(
        "Business verification submitted: provider=%s country=%s state=%s type=%s extracted_name=%s",
        provider_id, country, us_state, license_type, extracted_name,
    )

    return VerifyBusinessResponse(
        submitted=True,
        org_number=org_number or license_number or "",
        extracted_name=extracted_name,
        extracted_country=country,
        message=(
            "Verification submitted! We'll review within 24 hours. "
            "Your Verified Pro badge will appear once approved."
        ),
    )
