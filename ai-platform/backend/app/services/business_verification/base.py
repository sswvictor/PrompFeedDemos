"""
Business verification orchestrator.

Usage:
    from app.services.business_verification import verify_business

    result = verify_business(
        country="SE",
        org_number="556000-1111",   # optional
        name="Scissors & Co",       # optional
    )
    if result.success:
        print(result.profile.legal_name)

Architecture
------------
Each country maps to one adapter module under adapters/.
The adapter is called with (org_number, name) and returns VerificationResult.
To add a new country: create adapters/<country_code>.py and register it below.

This module never raises — callers always get a VerificationResult.
"""

import logging
from typing import Callable

from app.services.business_verification.models import VerificationResult, BusinessProfile

logger = logging.getLogger(__name__)

# -- Adapter registry ---------------------------------------------------------
# Maps ISO 3166-1 alpha-2 country code -> callable(org_number, name) -> VerificationResult

_ADAPTER_MAP: dict[str, Callable] = {}


def _load_adapters() -> None:
    """Lazy-load adapters so import errors in one country don't break others."""
    global _ADAPTER_MAP
    if _ADAPTER_MAP:
        return  # Already loaded

    from app.services.business_verification.adapters.sweden import verify as se_verify
    from app.services.business_verification.adapters.usa import verify as us_verify
    from app.services.business_verification.adapters.india import verify as in_verify

    _ADAPTER_MAP = {
        "SE": se_verify,
        "US": us_verify,
        "IN": in_verify,
    }


def supported_countries() -> list[str]:
    """Return list of supported ISO country codes."""
    _load_adapters()
    return list(_ADAPTER_MAP.keys())


def verify_business(
    country: str,
    org_number: str | None = None,
    name: str | None = None,
) -> VerificationResult:
    """
    Verify a business in the given country.

    Args:
        country:    ISO 3166-1 alpha-2 country code (e.g. "SE", "US", "IN").
        org_number: Registration / tax number (preferred — gives high confidence).
        name:       Business name (fallback — gives medium confidence).

    Returns:
        VerificationResult. Never raises.

    Raises:
        Nothing — all adapter errors are caught and returned as failed results.
    """
    country = country.upper().strip()
    _load_adapters()

    adapter = _ADAPTER_MAP.get(country)
    if adapter is None:
        logger.warning("No business verification adapter for country %s", country)
        return VerificationResult(
            success=False,
            country=country,
            source="none",
            error=f"Business verification is not yet available for {country}.",
        )

    try:
        result = adapter(org_number=org_number, name=name)
        if result.success:
            logger.info(
                "Business verified: %s | %s | confidence=%s",
                country, result.profile.legal_name or org_number, result.confidence,
            )
        else:
            logger.info(
                "Business not verified: %s | %s | error=%s",
                country, org_number or name, result.error,
            )
        return result
    except Exception:
        logger.exception(
            "Unexpected error in business verification adapter for %s", country
        )
        return VerificationResult(
            success=False,
            country=country,
            source=country.lower(),
            error="Verification service temporarily unavailable.",
        )
