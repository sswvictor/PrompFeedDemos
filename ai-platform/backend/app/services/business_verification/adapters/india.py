"""
India business verification adapter.

Source: GSTIN verification via the public GST portal search API.
        The MasterGST / GST Suvidha Provider APIs are paid services.
        We use the publicly accessible sandboxed GSTIN lookup endpoint
        that does not require an API key for basic lookups.

GSTIN format: 15 alphanumeric characters
  - Digits 1-2:  State code (01–37)
  - Digits 3-12: PAN of taxpayer
  - Digit 13:    Entity number of PAN
  - Digit 14:    'Z' by default
  - Digit 15:    Check digit

Fallback endpoint: https://sheet.gst.gov.in/gst/search (GET, no auth).

Note: If the GST portal is unavailable (common during maintenance windows),
we return a graceful failure rather than raising an exception.
"""

import logging
import re

import requests

from app.services.business_verification.models import BusinessProfile, VerificationResult

logger = logging.getLogger(__name__)

_SOURCE = "gstin"
_COUNTRY = "IN"
_GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_TIMEOUT = 12

# Public GSTIN search — no auth required, best-effort availability
_GST_SEARCH_URL = "https://services.gst.gov.in/services/searchtp"


def _validate_gstin(gstin: str) -> bool:
    """Return True if the GSTIN string matches the expected 15-char format."""
    cleaned = gstin.upper().strip().replace(" ", "").replace("-", "")
    return bool(_GSTIN_PATTERN.match(cleaned))


def _parse_profile(data: dict, gstin: str) -> BusinessProfile:
    """Map GST portal response to BusinessProfile."""
    # The GST portal returns different shapes depending on the endpoint used.
    # We handle the most common structure here.
    pradr = data.get("pradr", {}).get("addr", {}) or {}
    legal_name = data.get("lgnm") or data.get("tradeNam") or data.get("tradeName")
    trade_name = data.get("tradeName") or data.get("tradeNam")

    return BusinessProfile(
        org_number=gstin,
        legal_name=legal_name,
        trade_name=trade_name if trade_name != legal_name else None,
        business_type=data.get("ctb"),          # Constitution of Business
        status="active" if data.get("sts", "").lower() in ("active",) else "inactive",
        address_line1=pradr.get("bnm") or pradr.get("st"),
        city=pradr.get("dst"),
        region=pradr.get("stcd"),
        postal_code=str(pradr.get("pncd", "")) or None,
        country=_COUNTRY,
        registered_date=data.get("rgdt"),       # Registration date
        industry_code=data.get("nba", [""])[0] if isinstance(data.get("nba"), list) else None,
        source_url=f"https://www.gst.gov.in/",
        raw=data,
    )


def _lookup_gstin(gstin: str) -> VerificationResult:
    """Look up a GSTIN via the GST portal search endpoint."""
    try:
        resp = requests.get(
            _GST_SEARCH_URL,
            params={"gstin": gstin},
            headers={
                "Accept": "application/json",
                "User-Agent": "Fixmeapp-BusinessVerification/1.0",
            },
            timeout=_TIMEOUT,
        )
    except requests.RequestException as exc:
        return VerificationResult(
            success=False,
            country=_COUNTRY,
            source=_SOURCE,
            error=f"Network error contacting GST portal: {exc}",
        )

    if resp.status_code == 404:
        return VerificationResult(
            success=False,
            country=_COUNTRY,
            source=_SOURCE,
            error=f"GSTIN {gstin} not found in GST registry.",
        )

    if not resp.ok:
        logger.warning("GST portal returned %s for GSTIN %s", resp.status_code, gstin)
        return VerificationResult(
            success=False,
            country=_COUNTRY,
            source=_SOURCE,
            error=f"GST portal error ({resp.status_code}). Try again shortly.",
        )

    try:
        body = resp.json()
    except Exception:
        return VerificationResult(
            success=False,
            country=_COUNTRY,
            source=_SOURCE,
            error="GST portal returned an unexpected response format.",
        )

    # Check for error codes in the body (GST portal wraps errors as 200 responses)
    if body.get("errorCode") or not body.get("lgnm"):
        err_msg = body.get("message") or body.get("errorCode") or "GSTIN not found."
        return VerificationResult(
            success=False,
            country=_COUNTRY,
            source=_SOURCE,
            error=str(err_msg),
        )

    profile = _parse_profile(body, gstin)
    return VerificationResult(
        success=True,
        country=_COUNTRY,
        source=_SOURCE,
        profile=profile,
        confidence="high",  # Direct GSTIN match
    )


def verify(
    org_number: str | None = None,  # GSTIN (15-char)
    name: str | None = None,
) -> VerificationResult:
    """
    India adapter entry point.

    GSTIN (org_number) is required — the GST portal does not support
    name-only lookups in the public API.
    """
    if not org_number:
        return VerificationResult(
            success=False,
            country=_COUNTRY,
            source=_SOURCE,
            error=(
                "A GSTIN (GST Identification Number) is required to verify an Indian business. "
                "It is a 15-character alphanumeric code found on your GST certificate."
            ),
        )

    gstin = org_number.upper().strip().replace(" ", "").replace("-", "")

    if not _validate_gstin(gstin):
        return VerificationResult(
            success=False,
            country=_COUNTRY,
            source=_SOURCE,
            error=(
                f"'{org_number}' does not look like a valid GSTIN. "
                "A GSTIN has 15 characters: two state digits + PAN + 3 suffix characters."
            ),
        )

    return _lookup_gstin(gstin)
