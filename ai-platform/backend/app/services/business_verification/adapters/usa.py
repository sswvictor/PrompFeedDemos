"""
USA business verification adapter.

Source: OpenCorporates public API (free tier, no key required for basic lookups).
        https://api.opencorporates.com/documentation/API-Reference

Lookup strategy:
1. If EIN (Employer Identification Number, 9 digits) is provided:
   - OpenCorporates doesn't index by EIN — we search by name + jurisdiction.
   - We treat the EIN as additional evidence; confidence stays "medium".
2. If name is provided: search OpenCorporates by name, jurisdiction=us.
3. Returns the top-ranked active result.

Note: OpenCorporates free tier may rate-limit at ~50 req/day.
To remove the limit: set OPENCORPORATES_API_TOKEN in env vars.
"""

import logging
import os

import requests

from app.services.business_verification.models import BusinessProfile, VerificationResult

logger = logging.getLogger(__name__)

_SOURCE = "opencorporates"
_COUNTRY = "US"
_API_BASE = "https://api.opencorporates.com/v0.4"
_TIMEOUT = 10

# Optional API token — increases rate limit substantially
_API_TOKEN = os.getenv("OPENCORPORATES_API_TOKEN")


def _headers() -> dict:
    h = {"Accept": "application/json"}
    if _API_TOKEN:
        h["Authorization"] = f"Bearer {_API_TOKEN}"
    return h


def _parse_profile(company: dict) -> BusinessProfile:
    """Map OpenCorporates company object to BusinessProfile."""
    reg_addr = company.get("registered_address") or {}
    return BusinessProfile(
        org_number=company.get("company_number"),
        legal_name=company.get("name"),
        business_type=company.get("company_type"),
        status="active" if company.get("current_status", "").lower() in ("active", "good standing") else "inactive",
        address_line1=reg_addr.get("street_address"),
        city=reg_addr.get("locality"),
        region=reg_addr.get("region"),
        postal_code=reg_addr.get("postal_code"),
        country=_COUNTRY,
        registered_date=company.get("incorporation_date"),
        source_url=company.get("opencorporates_url"),
        raw=company,
    )


def _search_by_name(name: str, jurisdiction: str = "us") -> VerificationResult:
    """Search OpenCorporates by company name within US jurisdictions."""
    try:
        resp = requests.get(
            f"{_API_BASE}/companies/search",
            params={
                "q": name,
                "jurisdiction_code": jurisdiction,
                "per_page": 1,
                "current_status": "Active",
            },
            headers=_headers(),
            timeout=_TIMEOUT,
        )
    except requests.RequestException as exc:
        return VerificationResult(
            success=False,
            country=_COUNTRY,
            source=_SOURCE,
            error=f"Network error contacting OpenCorporates: {exc}",
        )

    if resp.status_code == 429:
        return VerificationResult(
            success=False,
            country=_COUNTRY,
            source=_SOURCE,
            error="OpenCorporates rate limit reached. Try again later.",
        )

    if not resp.ok:
        return VerificationResult(
            success=False,
            country=_COUNTRY,
            source=_SOURCE,
            error=f"OpenCorporates API error ({resp.status_code}).",
        )

    try:
        companies = resp.json()["results"]["companies"]
    except (KeyError, TypeError):
        companies = []

    if not companies:
        return VerificationResult(
            success=False,
            country=_COUNTRY,
            source=_SOURCE,
            error=f"No active US company named '{name}' found in OpenCorporates.",
        )

    company = companies[0]["company"]
    profile = _parse_profile(company)

    return VerificationResult(
        success=True,
        country=_COUNTRY,
        source=_SOURCE,
        profile=profile,
        confidence="medium",  # name match only
    )


def verify(
    org_number: str | None = None,  # EIN or state registration number
    name: str | None = None,
) -> VerificationResult:
    """
    USA adapter entry point.

    OpenCorporates doesn't support EIN lookup — we always do a name search.
    If org_number (EIN) is provided alongside a name, we note it in the result
    but still rely on the name search.
    """
    if not name and not org_number:
        return VerificationResult(
            success=False,
            country=_COUNTRY,
            source=_SOURCE,
            error="Provide a business name to verify a US business.",
        )

    search_name = name or org_number or ""
    result = _search_by_name(search_name.strip())

    # If EIN was provided and name search succeeded, bump confidence slightly
    if result.success and org_number and name:
        result.confidence = "medium"  # Still medium — EIN not directly verified

    return result
