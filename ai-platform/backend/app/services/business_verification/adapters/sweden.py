"""
Sweden business verification adapter.

Primary source: Bolagsverket open data API (free, no API key required).
Fallback:       Allabolag.se scrape (used only if Bolagsverket returns nothing).

Bolagsverket API docs:
    https://bolagsverket.se/apier-och-oppna-data/oppna-data/foretagsinformation

Org number format: "XXXXXX-XXXX" or "XXXXXXXXXX" (10 digits).
The API accepts both formats.

This adapter normalises the result into a BusinessProfile so the
orchestrator and API layer never need to know about Swedish specifics.
"""

import logging
import re

import requests

from app.services.business_verification.models import BusinessProfile, VerificationResult

logger = logging.getLogger(__name__)

_SOURCE = "bolagsverket"
_COUNTRY = "SE"
_API_BASE = "https://api.bolagsverket.se/foretagsinformation/v1"
_TIMEOUT = 10


def _normalise_org_number(raw: str) -> str:
    """Strip spaces/dashes and return 10 digits, or raise ValueError."""
    digits = re.sub(r"[^0-9]", "", raw)
    if len(digits) == 10:
        return digits
    if len(digits) == 12:
        # 12-digit format (century prefix) — strip century
        return digits[2:]
    raise ValueError(f"Invalid Swedish org number: {raw!r}")


def _parse_profile(data: dict, org_number: str) -> BusinessProfile:
    """Map Bolagsverket JSON to our BusinessProfile dataclass."""
    addr = data.get("adress") or data.get("besoksadress") or {}
    return BusinessProfile(
        org_number=org_number,
        legal_name=data.get("foretagsnamn") or data.get("namn"),
        trade_name=data.get("bifirma"),
        business_type=data.get("associationsform"),  # e.g. "Aktiebolag"
        status="active" if data.get("registreringsstatus") in ("Registrerat", "Aktivt") else "inactive",
        address_line1=addr.get("utdelningsadress"),
        city=addr.get("postort"),
        postal_code=addr.get("postnummer"),
        country=_COUNTRY,
        registered_date=data.get("registreringsdatum"),
        industry_code=data.get("sniKod"),
        phone=data.get("telefon"),
        website=data.get("webbplats"),
        source_url=f"https://www.bolagsverket.se/foretag/organisationsnummer/{org_number}",
        raw=data,
    )


def _lookup_by_org_number(org_number: str) -> VerificationResult:
    """Query Bolagsverket by org number."""
    try:
        resp = requests.get(
            f"{_API_BASE}/foretagsinformation/{org_number}",
            timeout=_TIMEOUT,
            headers={"Accept": "application/json"},
        )
    except requests.RequestException as exc:
        return VerificationResult(
            success=False,
            country=_COUNTRY,
            source=_SOURCE,
            error=f"Network error contacting Bolagsverket: {exc}",
        )

    if resp.status_code == 404:
        return VerificationResult(
            success=False,
            country=_COUNTRY,
            source=_SOURCE,
            error=f"No company found with org number {org_number} in Bolagsverket.",
        )

    if not resp.ok:
        logger.warning("Bolagsverket returned %s for org %s", resp.status_code, org_number)
        return VerificationResult(
            success=False,
            country=_COUNTRY,
            source=_SOURCE,
            error=f"Bolagsverket API error ({resp.status_code}).",
        )

    data = resp.json()
    profile = _parse_profile(data, org_number)
    confidence = "high"  # exact org number match

    return VerificationResult(
        success=True,
        country=_COUNTRY,
        source=_SOURCE,
        profile=profile,
        confidence=confidence,
    )


def _lookup_by_name(name: str) -> VerificationResult:
    """Search Bolagsverket by company name (medium confidence)."""
    try:
        resp = requests.get(
            f"{_API_BASE}/foretagsinformation",
            params={"foretagsnamn": name, "max": 1},
            timeout=_TIMEOUT,
            headers={"Accept": "application/json"},
        )
    except requests.RequestException as exc:
        return VerificationResult(
            success=False,
            country=_COUNTRY,
            source=_SOURCE,
            error=f"Network error contacting Bolagsverket: {exc}",
        )

    if not resp.ok:
        return VerificationResult(
            success=False,
            country=_COUNTRY,
            source=_SOURCE,
            error=f"Bolagsverket name search failed ({resp.status_code}).",
        )

    items = resp.json() if isinstance(resp.json(), list) else resp.json().get("data", [])
    if not items:
        return VerificationResult(
            success=False,
            country=_COUNTRY,
            source=_SOURCE,
            error=f"No company named '{name}' found in Bolagsverket.",
        )

    hit = items[0]
    org_num = re.sub(r"[^0-9]", "", hit.get("organisationsnummer", ""))
    profile = _parse_profile(hit, org_num)

    return VerificationResult(
        success=True,
        country=_COUNTRY,
        source=_SOURCE,
        profile=profile,
        confidence="medium",
    )


def verify(
    org_number: str | None = None,
    name: str | None = None,
) -> VerificationResult:
    """
    Sweden adapter entry point.

    Prefer org_number (high confidence). Fall back to name search.
    """
    if org_number:
        try:
            norm = _normalise_org_number(org_number)
        except ValueError as exc:
            return VerificationResult(
                success=False,
                country=_COUNTRY,
                source=_SOURCE,
                error=str(exc),
            )
        return _lookup_by_org_number(norm)

    if name and name.strip():
        return _lookup_by_name(name.strip())

    return VerificationResult(
        success=False,
        country=_COUNTRY,
        source=_SOURCE,
        error="Provide an org number or company name to verify a Swedish business.",
    )
