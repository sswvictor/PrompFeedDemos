"""
Onboarding API â€” new provider setup endpoints.

Routes:
    POST /onboarding/scan-price-list   â€” GPT-4o Vision reads a price list image
    POST /onboarding/provider          â€” Create a new provider during onboarding
    GET  /onboarding/status            â€” Check if onboarding is complete

These endpoints handle the first-run experience for a new business signing up.
The auth requirement is get_current_user_id (not get_current_provider) because
the provider record does not exist yet when these routes are called.
"""

import base64
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user_id, get_current_provider
from app.config import settings
from app.db.session import get_db
from app.models.provider_amenity import ProviderAmenity
from app.models.provider import Provider, currency_for_country
from app.models.provider_instagram_page import ProviderInstagramPage
from app.models.service import Service
from app.integrations.instagram.graph_client import fetch_provider_profile, fetch_recent_media, InstagramGraphError
from app.services.business_verification import verify_business
from app.services.token_crypto import encrypt_token
from openai import OpenAI

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/onboarding", tags=["onboarding"])
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Max image size: 10 MB
MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


# â”€â”€ Pydantic schemas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class ExtractedService(BaseModel):
    name: str
    duration_minutes: int
    price_ex_vat: float          # Always stored ex-VAT
    price_inc_vat: float         # For display — what provider sees on their price list
    description: str | None = None
    confidence: str              # “high” | “medium” | “low”
    keywords: str | None = None  # Comma-separated aliases for AI matching
    category: str | None = None  # Optional category hint (mobile sends this per-service)


class ScanPriceListResponse(BaseModel):
    services: list[ExtractedService]
    services_found: int
    raw_text: str                # What GPT-4o read â€” useful for debugging
    note: str | None = None      # Any warning or info message


class CreateProviderRequest(BaseModel):
    name: str
    phone: str | None = None
    city: str | None = None
    instagram_username: str | None = None
    instagram_user_id: str | None = None
    bio: str | None = None
    # New fields added for richer onboarding
    business_type: str | None = None           # "owner" | "freelancer" | "chair_renter"
    service_categories: list[str] | None = None  # e.g. ["hair", "nails"]
    parent_provider_id: str | None = None      # chair renters link to parent salon
    # Work location â€” critical for booking flow
    home_service: bool = False                 # Provider does home visits
    location_salon: str | None = None          # Salon / studio address
    amenity_keys: list[str] | None = None      # Amenities selected during onboarding
    # Services extracted from price list scan - created immediately on provider creation
    scanned_services: list[ExtractedService | dict] | None = None
    booking_policy: str | None = None
    cancellation_policy: str | None = None
    # IG bot connection — set when provider used the advanced token flow during onboarding
    ig_access_token: str | None = None   # Long-lived IG access token for DM bot
    ig_user_id: str | None = None        # IG user ID from InstagramPrefillResponse


class CreateProviderResponse(BaseModel):
    provider_id: str
    name: str
    slug: str | None = None
    message: str


class OnboardingStatusResponse(BaseModel):
    has_provider: bool
    has_services: bool
    has_working_hours: bool
    is_complete: bool
    provider_id: str | None = None


# â”€â”€ Helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# Keyword → category slug mapping: infer category from service name at creation time
_CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("hair",      ["hair", "haircut", "cut", "color", "colour", "balayage", "highlights",
                   "blowout", "blowdry", "blow dry", "styling", "extensions", "keratin",
                   "perm", "toning", "gloss", "frisyr", "frisör", "hår"]),
    ("barber",    ["barber", "beard", "shave", "fade", "trim"]),
    ("nails",     ["nail", "nagel", "manicure", "pedicure", "gel", "acrylic", "shellac",
                   "nail art", "sns", "dip powder"]),
    ("lashes",    ["lash", "fransar", "eyelash", "extension", "lift", "brow", "eyebrow",
                   "microblading", "lamination", "henna brow"]),
    ("skincare",  ["facial", "peel", "microneedling", "dermaplaning", "hydra", "skin",
                   "acne", "anti-age", "botox", "filler", "ipl", "laser", "chemical peel",
                   "ansikts", "hud"]),
    ("makeup",    ["makeup", "make-up", "make up", "bridal makeup", "smink"]),
    ("massage",   ["massage", "deep tissue", "hot stone", "sports massage",
                   "trigger point", "thai", "relaxation", "body massage"]),
    ("spa",       ["spa", "wrap", "body wrap", "scrub", "hydrotherapy", "flotation",
                   "sauna", "steam", "wellness treatment"]),
    ("tattoo",    ["tattoo", "tatuering", "piercing", "permanent makeup"]),
    ("fitness",   ["personal training", "pt session", "yoga", "pilates", "crossfit",
                   "workout", "coaching", "träning"]),
]


def _infer_category(service_name: str) -> str | None:
    """Return a category slug inferred from the service name, or None if no match."""
    lower = service_name.lower()
    for slug, keywords in _CATEGORY_KEYWORDS:
        if any(kw in lower for kw in keywords):
            return slug
    return None


def _strip_vat(price_inc_vat: float, vat_rate: float = 0.25) -> float:
    """Convert an inc-VAT price to ex-VAT (Swedish standard: 25%)."""
    return round(price_inc_vat / (1 + vat_rate), 2)


def _normalize_scanned_services(items: list[ExtractedService | dict] | None) -> list[ExtractedService]:
    normalized: list[ExtractedService] = []
    if not items:
        return normalized

    for raw in items:
        if isinstance(raw, ExtractedService):
            normalized.append(raw)
            continue
        if not isinstance(raw, dict):
            continue

        try:
            name = str(raw.get("name", "")).strip()
            if not name:
                continue

            duration = int(raw.get("duration_minutes") or raw.get("duration") or 60)
            duration = max(5, min(duration, 480))

            price_ex = raw.get("price_ex_vat")
            price_inc = raw.get("price_inc_vat", raw.get("price"))
            if price_ex is None and price_inc is None:
                price_ex_vat = 0.0
                price_inc_vat = 0.0
            elif price_ex is None:
                price_inc_vat = float(price_inc)
                price_ex_vat = _strip_vat(price_inc_vat)
            elif price_inc is None:
                price_ex_vat = float(price_ex)
                price_inc_vat = round(price_ex_vat * 1.25, 2)
            else:
                price_ex_vat = float(price_ex)
                price_inc_vat = float(price_inc)

            confidence = str(raw.get("confidence", "medium")).lower()
            if confidence not in {"high", "medium", "low"}:
                confidence = "medium"

            normalized.append(
                ExtractedService(
                    name=name,
                    duration_minutes=duration,
                    price_ex_vat=price_ex_vat,
                    price_inc_vat=price_inc_vat,
                    description=raw.get("description") or None,
                    confidence=confidence,
                    keywords=raw.get("keywords") or None,
                    category=str(raw["category"]).strip() if raw.get("category") else None,
                )
            )
        except Exception as exc:
            logger.warning("Skipping malformed scanned service payload: %s", exc)

    return normalized


def _parse_vision_response(raw_text: str) -> list[ExtractedService]:
    """
    Extract the JSON block from GPT-4o's response.

    GPT-4o is prompted to return a JSON array. This function finds and parses it
    robustly even if GPT adds prose around it.
    """
    # Try to find a JSON array in the response
    json_match = re.search(r'\[\s*\{.*?\}\s*\]', raw_text, re.DOTALL)
    if not json_match:
        logger.warning("No JSON array found in vision response: %s", raw_text[:200])
        return []

    try:
        items = json.loads(json_match.group(0))
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse vision JSON: %s | raw: %s", e, raw_text[:200])
        return []

    services = []
    for item in items:
        try:
            # GPT returns price_inc_vat (what's on the price list)
            price_inc = float(item.get("price", item.get("price_inc_vat", 0)))
            price_ex = _strip_vat(price_inc)
            duration = int(item.get("duration_minutes", 60))

            services.append(ExtractedService(
                name=str(item.get("name", "Unknown Service")).strip(),
                duration_minutes=max(5, min(duration, 480)),  # Clamp 5minâ€“8hr
                price_ex_vat=price_ex,
                price_inc_vat=price_inc,
                description=item.get("description") or None,
                confidence=str(item.get("confidence", "medium")).lower(),
                keywords=item.get("keywords") or None,
            ))
        except (ValueError, TypeError, KeyError) as e:
            logger.warning("Skipping malformed service item %s: %s", item, e)
            continue

    return services


# â”€â”€ Routes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post(
    "/scan-price-list",
    response_model=ScanPriceListResponse,
    summary="Extract services from a price list photo using AI vision",
)
async def scan_price_list(
    file: UploadFile = File(..., description="Photo of price list (JPG, PNG, WEBP, HEIC)"),
    categories: str = Form(default="", description="JSON array of category slugs, e.g. '[\"hair\",\"nails\"]'"),
    user_id: str = Depends(get_current_user_id),
):
    """
    Upload a photo of a price list menu and get back a structured list of services.

    The AI (GPT-4o vision) reads the image and extracts:
    - Service name
    - Duration in minutes
    - Price (inc VAT, as shown on the price list)
    - Confidence score per item

    Prices are stored ex-VAT internally (Swedish standard: divide by 1.25).
    The response includes both inc-VAT and ex-VAT so the frontend can show
    the familiar inc-VAT price to providers.

    This endpoint requires a valid JWT but does NOT require an existing
    Provider record â€” it is called during onboarding before the provider is created.
    """
    # â”€â”€ Validate file â”€â”€
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image type: {file.content_type}. Use JPG, PNG, WEBP, or HEIC.",
        )

    image_bytes = await file.read()
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image too large. Maximum size is 10 MB.",
        )

    # â”€â”€ Encode image for OpenAI â”€â”€
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    # Map content types to OpenAI's expected format
    mime = file.content_type
    if mime in ("image/heic", "image/heif"):
        mime = "image/jpeg"  # OpenAI doesn't support HEIC natively â€” treat as JPEG

    # â”€â”€ Build the vision prompt â”€â”€
    system_prompt = (
        "You are a data extraction assistant specializing in beauty salon and wellness "
        "service menus. Your job is to read price lists and extract structured service data.\n\n"
        "IMPORTANT RULES:\n"
        "1. Extract EVERY service listed on the image.\n"
        "2. Return ONLY a valid JSON array â€” no prose, no markdown, no code fences.\n"
        "3. If prices include VAT, return the price as shown. If ex-VAT, return as-is.\n"
        "4. If duration is not listed, estimate based on service type "
        "(e.g., haircut â‰ˆ 45 min, color â‰ˆ 90 min, manicure â‰ˆ 60 min).\n"
        "5. Set confidence to 'high' if you can clearly read name+price, "
        "'medium' if one field is estimated, 'low' if you're unsure.\n"
        "6. For 'keywords': add 3-6 common alternative names or phrases a customer might use "
        "when asking for this service in a chat (e.g. for 'Wash & Set': 'wash set, shampoo and set, wash and style, set'). "
        "These help an AI booking bot match customer requests to the right service.\n\n"
        "Return this exact JSON format:\n"
        "[\n"
        "  {\n"
        '    "name": "Wash & Set",\n'
        '    "duration_minutes": 45,\n'
        '    "price": 500,\n'
        '    "description": null,\n'
        '    "confidence": "high",\n'
        '    "keywords": "wash set, shampoo and set, wash and style, set"\n'
        "  }\n"
        "]"
    )

    user_prompt = (
        "Please extract all services from this price list. "
        "Return only the JSON array, nothing else."
    )

    # â”€â”€ Build category-aware context â”€â”€
    category_context = ""
    try:
        parsed_cats = json.loads(categories) if categories.strip() else []
    except json.JSONDecodeError:
        parsed_cats = []

    # Human-readable category names for the prompt
    CATEGORY_LABELS = {
        "hair": "hair salon (haircuts, coloring, styling, extensions, treatments)",
        "barber": "barbershop (haircuts, beard trims, shaves, fades)",
        "nails": "nail salon (manicures, pedicures, gel nails, nail art)",
        "spa": "spa (body treatments, facials, hydrotherapy, wellness)",
        "massage": "massage therapy (Swedish, deep tissue, hot stone, sports)",
        "fitness": "fitness & personal training (training sessions, classes, yoga, pilates)",
        "makeup": "makeup artist (everyday, bridal, event makeup)",
        "skincare": "aesthetics & skincare (facials, peels, dermaplaning, injectables)",
        "lashes": "lash & brow specialist (extensions, lifts, microblading)",
        "tattoo": "tattoo & piercing studio",
        "other": "specialist services",
    }
    if parsed_cats:
        category_descriptions = [CATEGORY_LABELS.get(c, c) for c in parsed_cats]
        category_context = (
            f"\n\nCONTEXT: This price list is from a {' / '.join(category_descriptions)}. "
            f"Focus on extracting services relevant to these categories. "
            f"Use typical durations for this industry if not stated (e.g. haircut=45min, color=90min, manicure=60min, massage=60min)."
        )

    logger.info("Scanning price list for user %s (%.1f KB, categories: %s)", user_id, len(image_bytes) / 1024, parsed_cats)

    # â”€â”€ Call GPT-4o Vision â”€â”€
    try:
        response = client.chat.completions.create(
            model="gpt-4o",   # gpt-4o has the best vision quality; gpt-4o-mini works too
            max_tokens=2000,
            messages=[
                {"role": "system", "content": system_prompt + category_context},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{image_b64}",
                                "detail": "high",  # High detail for reading small text
                            },
                        },
                        {"type": "text", "text": user_prompt},
                    ],
                },
            ],
        )
    except Exception as e:
        logger.exception("OpenAI vision API error for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service temporarily unavailable. Please try again in a moment.",
        )

    raw_text = response.choices[0].message.content or ""
    logger.info("Vision response for user %s: %s...", user_id, raw_text[:100])

    # â”€â”€ Parse the response â”€â”€
    services = _parse_vision_response(raw_text)

    note = None
    if not services:
        note = (
            "We couldn't extract services from this image. "
            "Try a well-lit, straight-on photo. You can also add services manually."
        )
    elif any(s.confidence == "low" for s in services):
        note = "Some services were hard to read clearly. Please review and correct any errors."

    return ScanPriceListResponse(
        services=services,
        services_found=len(services),
        raw_text=raw_text,
        note=note,
    )


@router.post(
    "/provider",
    response_model=CreateProviderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new provider profile during onboarding",
)
def create_provider_onboarding(
    body: CreateProviderRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Create a Provider record linked to the authenticated user.

    This is Step 3 of onboarding â€” after auth, before services.
    Only one provider per user is allowed.

    If the user already has a provider (e.g., they refreshed mid-onboarding),
    this returns the existing provider instead of creating a duplicate.
    """
    # Idempotent: return existing provider if already created
    existing = db.query(Provider).filter(Provider.user_id == user_id).first()
    if existing:
        logger.info("Provider already exists for user %s: %s", user_id, existing.provider_id)
        return CreateProviderResponse(
            provider_id=existing.provider_id,
            name=existing.name,
            message="Provider profile already exists.",
        )

    # Validate business_type if provided
    valid_business_types = {"owner", "freelancer", "chair_renter"}
    if body.business_type and body.business_type not in valid_business_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid business_type. Must be one of: {', '.join(valid_business_types)}",
        )

    # Validate parent_provider_id if chair renter
    if body.parent_provider_id:
        parent = db.query(Provider).filter(Provider.provider_id == body.parent_provider_id).first()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent salon not found. It may not be on FixmeApp yet.",
            )

    # Generate a unique URL-friendly slug from name + city
    def _make_slug(name: str, city: str | None, db) -> str:
        import re
        base = f"{name} {city or ''}".lower().strip()
        base = re.sub(r"[^a-z0-9\s-]", "", base)
        base = re.sub(r"\s+", "-", base).strip("-")
        base = base[:80] or "provider"
        slug = base
        counter = 1
        while db.query(Provider).filter(Provider.slug == slug).first():
            slug = f"{base}-{counter}"
            counter += 1
        return slug

    home_service_enabled = bool(
        body.home_service or ("home_visits" in (body.amenity_keys or []))
    )
    scanned_services = _normalize_scanned_services(body.scanned_services)

    provider = Provider(
        provider_id=str(uuid.uuid4()),
        user_id=user_id,
        name=body.name,
        phone=body.phone,
        city=body.city,
        instagram_username=body.instagram_username,
        bio=body.bio,
        business_type=body.business_type,
        slug=_make_slug(body.name, body.city, db),
        # Store categories as JSON string
        service_categories=json.dumps(body.service_categories) if body.service_categories else None,
        parent_provider_id=body.parent_provider_id or None,
        # Work location
        home_service=home_service_enabled,
        location_salon=body.location_salon,
        booking_policy=body.booking_policy,
        cancellation_policy=body.cancellation_policy,
        # Defaults â€” provider can update in settings later
        vat_percent=25.0,
    )

    try:
        db.add(provider)
        db.commit()
        db.refresh(provider)
    except Exception as exc:
        db.rollback()
        logger.exception("Provider creation failed for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not create provider profile: {exc}",
        ) from exc

    logger.info("Created provider %s for user %s during onboarding", provider.provider_id, user_id)

    # -- Create services from scanned price list ------------------------------
    if scanned_services:
        for svc in scanned_services:
            try:
                # Derive category: per-service hint wins, then explicit selection, then AI inference
                cats = body.service_categories or []
                category = svc.category or (cats[0] if cats else _infer_category(svc.name))

                service = Service(
                    service_id=str(uuid.uuid4()),
                    provider_id=provider.provider_id,
                    name=svc.name,
                    description=svc.description,
                    category=category,
                    duration_minutes=svc.duration_minutes,
                    price_ex_vat=svc.price_ex_vat,
                    vat_percent=25.0,
                    keywords=svc.keywords or None,
                    is_active=True,
                    home_service_available=home_service_enabled,
                )
                db.add(service)
            except Exception as e:
                logger.warning("Skipping scanned service '%s': %s", svc.name, e)
        try:
            db.commit()
            logger.info(
                "Created %d services from scan for provider %s",
                len(scanned_services), provider.provider_id,
            )
        except Exception:
            logger.exception("Failed to commit scanned services for provider %s", provider.provider_id)
            db.rollback()

    # -- Save amenities selected during onboarding -----------------------------
    if body.amenity_keys:
        for key in set(body.amenity_keys):
            try:
                db.add(
                    ProviderAmenity(
                        provider_id=provider.provider_id,
                        amenity_key=key,
                        is_active=True,
                    )
                )
            except Exception as e:
                logger.warning("Skipping onboarding amenity '%s': %s", key, e)
        try:
            db.commit()
            logger.info(
                "Saved %d onboarding amenity key(s) for provider %s",
                len(set(body.amenity_keys)),
                provider.provider_id,
            )
        except Exception:
            logger.exception("Failed to commit onboarding amenities for provider %s", provider.provider_id)
            db.rollback()

    # -- Wire IG bot: save ProviderInstagramPage if token was provided -----------
    if body.ig_user_id:
        try:
            existing_page = (
                db.query(ProviderInstagramPage)
                .filter(ProviderInstagramPage.instagram_page_id == body.ig_user_id)
                .first()
            )
            if not existing_page:
                db.add(
                    ProviderInstagramPage(
                        provider_id=provider.provider_id,
                        instagram_page_id=body.ig_user_id,
                        page_name=body.instagram_username or provider.instagram_username or body.name or "",
                        access_token=encrypt_token(body.ig_access_token) if body.ig_access_token else None,
                        is_platform_page=False,
                    )
                )
            else:
                # Token refresh — update access_token and bind to this provider
                existing_page.provider_id = provider.provider_id
                if body.ig_access_token:
                    existing_page.access_token = encrypt_token(body.ig_access_token)
            db.commit()
            logger.info("Saved ProviderInstagramPage for provider %s (ig_user_id=%s)", provider.provider_id, body.ig_user_id)
        except Exception:
            logger.exception("Failed to save ProviderInstagramPage for provider %s", provider.provider_id)
            db.rollback()

    return CreateProviderResponse(
        provider_id=provider.provider_id,
        name=provider.name,
        slug=provider.slug,
        message="Provider profile created successfully. Continue to add your services.",
    )


@router.get(
    "/status",
    response_model=OnboardingStatusResponse,
    summary="Check how far through onboarding this provider is",
)
def get_onboarding_status(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Returns which onboarding steps are complete.

    The frontend uses this on app startup to resume mid-onboarding
    or skip onboarding entirely for returning providers.
    """
    provider = db.query(Provider).filter(Provider.user_id == user_id).first()

    if not provider:
        return OnboardingStatusResponse(
            has_provider=False,
            has_services=False,
            has_working_hours=False,
            is_complete=False,
        )

    has_services = db.query(Service).filter(
        Service.provider_id == provider.provider_id
    ).count() > 0

    # Working hours live in the WorkingHours model â€” check if any rows exist
    try:
        from app.models.working_hours import WorkingHours
        has_hours = db.query(WorkingHours).filter(
            WorkingHours.provider_id == provider.provider_id
        ).count() > 0
    except Exception:
        has_hours = False

    is_complete = has_services and has_hours

    return OnboardingStatusResponse(
        has_provider=True,
        has_services=has_services,
        has_working_hours=has_hours,
        is_complete=is_complete,
        provider_id=provider.provider_id,
    )


class ProviderSearchResult(BaseModel):
    provider_id: str
    name: str
    city: str | None
    business_type: str | None


@router.get(
    "/search-providers",
    response_model=list[ProviderSearchResult],
    summary="Search providers by name (for chair renters to find their salon)",
)
def search_providers_for_linking(
    q: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Lightweight provider name search used during onboarding.
    Chair renters use this to find and link to the salon they work at.
    Returns max 10 results, filtered to owners only.
    """
    if len(q.strip()) < 2:
        return []

    results = (
        db.query(Provider)
        .filter(
            Provider.name.ilike(f"%{q.strip()}%"),
            Provider.business_type == "owner",
        )
        .limit(10)
        .all()
    )

    return [
        ProviderSearchResult(
            provider_id=p.provider_id,
            name=p.name,
            city=p.city,
            business_type=p.business_type,
        )
        for p in results
    ]


# -- Instagram prefill -------------------------------------------------------

class InstagramPrefillRequest(BaseModel):
    access_token: str  # Long-lived IG access token obtained from OAuth in the frontend


class InstagramMediaItem(BaseModel):
    id: str
    media_type: str
    media_url: str | None = None
    thumbnail_url: str | None = None
    caption: str | None = None
    permalink: str | None = None
    timestamp: str | None = None


class InstagramPrefillResponse(BaseModel):
    ig_user_id: str
    username: str
    name: str | None = None
    biography: str | None = None
    website: str | None = None
    followers_count: int
    following_count: int
    media_count: int
    profile_picture_url: str | None = None
    recent_media: list[InstagramMediaItem] = []
    # Whether we persisted stats to an existing Provider record
    stats_synced: bool = False


@router.post(
    "/instagram/prefill",
    response_model=InstagramPrefillResponse,
    summary="Fetch Instagram profile data to pre-fill the provider onboarding form",
)
def instagram_prefill(
    body: InstagramPrefillRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Use a long-lived Instagram access token to fetch the provider's IG profile.

    Returns bio, follower count, profile picture, and recent posts so the
    onboarding frontend can auto-fill name, bio, and instagram_username fields.

    If a Provider record already exists for this user, the IG stats columns
    (ig_followers_count, ig_following_count, ig_profile_picture_url,
    ig_stats_synced_at) are updated atomically — safe to call on re-login.

    Called by:  personas/provider/onboarding/InstagramStep.jsx
    """
    try:
        profile = fetch_provider_profile(body.access_token)
    except InstagramGraphError as exc:
        logger.warning("IG prefill failed for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not fetch Instagram profile. The access token may have expired.",
        )
    except Exception:
        logger.exception("Unexpected error during IG prefill for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Instagram service temporarily unavailable.",
        )

    # Fetch a small preview of recent media (non-fatal if it fails)
    media_items: list[InstagramMediaItem] = []
    try:
        raw_media = fetch_recent_media(body.access_token, limit=6)
        media_items = [
            InstagramMediaItem(
                id=m.get("id", ""),
                media_type=m.get("media_type", "IMAGE"),
                media_url=m.get("media_url"),
                thumbnail_url=m.get("thumbnail_url"),
                caption=m.get("caption"),
                permalink=m.get("permalink"),
                timestamp=m.get("timestamp"),
            )
            for m in raw_media
        ]
    except Exception:
        logger.warning("IG media fetch failed for user %s (non-fatal)", user_id)

    followers = int(profile.get("followers_count") or 0)
    following = int(profile.get("follows_count") or 0)
    media_count = int(profile.get("media_count") or 0)
    pic_url = profile.get("profile_picture_url")

    # Persist stats to Provider if the record already exists
    stats_synced = False
    provider = db.query(Provider).filter(Provider.user_id == user_id).first()
    if provider:
        provider.ig_followers_count = followers
        provider.ig_following_count = following
        provider.ig_profile_picture_url = pic_url
        provider.ig_stats_synced_at = datetime.now(timezone.utc)
        if not provider.instagram_username and profile.get("username"):
            provider.instagram_username = profile["username"]
        db.commit()
        stats_synced = True
        logger.info(
            "Synced IG stats for provider %s: %d followers",
            provider.provider_id, followers,
        )

    logger.info(
        "IG prefill for user %s: @%s, %d followers",
        user_id, profile.get("username"), followers,
    )

    return InstagramPrefillResponse(
        ig_user_id=profile.get("id", ""),
        username=profile.get("username", ""),
        name=profile.get("name"),
        biography=profile.get("biography"),
        website=profile.get("website"),
        followers_count=followers,
        following_count=following,
        media_count=media_count,
        profile_picture_url=pic_url,
        recent_media=media_items,
        stats_synced=stats_synced,
    )


# -- Business verification ---------------------------------------------------

_SUPPORTED_COUNTRIES = {"SE", "US", "IN"}


class BusinessVerifyRequest(BaseModel):
    country: str                  # "SE" | "US" | "IN"
    org_number: str | None = None # Org number / EIN / GSTIN
    name: str | None = None       # Business name (fallback)


class BusinessVerifyResponse(BaseModel):
    success: bool
    country: str
    source: str
    confidence: str               # "high" | "medium" | "low" | "none"
    # Profile fields (only present when success=True)
    legal_name: str | None = None
    trade_name: str | None = None
    business_type: str | None = None
    status: str | None = None
    address_line1: str | None = None
    city: str | None = None
    region: str | None = None
    postal_code: str | None = None
    registered_date: str | None = None
    source_url: str | None = None
    # Error message (only present when success=False)
    error: str | None = None
    # Whether we stamped is_verified on the Provider record
    provider_verified: bool = False


@router.post(
    "/business/verify",
    response_model=BusinessVerifyResponse,
    summary="Verify a business registration and stamp is_verified on the provider",
)
def verify_provider_business(
    body: BusinessVerifyRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Verify a business registration number or name against an official registry.

    Supported countries: SE (Bolagsverket), US (OpenCorporates), IN (GSTIN).

    On success, the authenticated provider's is_verified, verified_at,
    verified_country, and verification_source fields are updated.

    Called by: personas/provider/onboarding/BusinessVerifyStep.jsx
    """
    country = (body.country or "").upper().strip()
    if country not in _SUPPORTED_COUNTRIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported country '{country}'. Supported: {', '.join(sorted(_SUPPORTED_COUNTRIES))}.",
        )

    result = verify_business(
        country=country,
        org_number=body.org_number,
        name=body.name,
    )

    provider_verified = False
    if result.success:
        # Stamp the provider record if it exists
        provider = db.query(Provider).filter(Provider.user_id == user_id).first()
        if provider:
            provider.is_verified = True
            provider.verified_at = datetime.now(timezone.utc)
            provider.verified_country = country
            provider.verification_source = result.source
            # Auto-set currency from country (provider can change later)
            provider.currency = currency_for_country(country)
            db.commit()
            provider_verified = True
            logger.info(
                "Provider %s verified: %s / %s (confidence=%s)",
                provider.provider_id, country, result.source, result.confidence,
            )

    p = result.profile
    return BusinessVerifyResponse(
        success=result.success,
        country=result.country,
        source=result.source,
        confidence=result.confidence,
        legal_name=p.legal_name if p else None,
        trade_name=p.trade_name if p else None,
        business_type=p.business_type if p else None,
        status=p.status if p else None,
        address_line1=p.address_line1 if p else None,
        city=p.city if p else None,
        region=p.region if p else None,
        postal_code=p.postal_code if p else None,
        registered_date=p.registered_date if p else None,
        source_url=p.source_url if p else None,
        error=result.error,
        provider_verified=provider_verified,
    )
