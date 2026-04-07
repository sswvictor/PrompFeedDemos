"""
Shared data models for the business verification service.

These dataclasses are passed between adapters and API endpoints.
They are intentionally plain Python — no SQLAlchemy, no FastAPI.
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class BusinessProfile:
    """
    Normalised business profile returned by every adapter.

    All fields are optional — adapters fill what the data source provides.
    The API layer decides what to persist and what to surface in the UI.
    """
    # Core identity
    org_number: str | None = None         # Registration number as returned by the source
    legal_name: str | None = None         # Official registered name
    trade_name: str | None = None         # Trading name / DBA if different
    business_type: str | None = None      # e.g. "AB", "LLC", "Sole Trader"
    status: str | None = None             # "active" | "inactive" | "unknown"

    # Address
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    region: str | None = None
    postal_code: str | None = None
    country: str | None = None            # ISO 3166-1 alpha-2

    # Registration
    registered_date: str | None = None    # ISO 8601 date string
    industry_code: str | None = None      # SNI / NAICS / NIC code

    # Contact
    phone: str | None = None
    email: str | None = None
    website: str | None = None

    # Source metadata
    source_url: str | None = None         # URL of the data source page
    raw: dict = field(default_factory=dict)  # Full raw response for debugging


@dataclass
class VerificationResult:
    """
    Result of a single verification attempt.

    success=True means we found a matching active business.
    The `profile` is None only when success=False.
    """
    success: bool
    country: str                          # ISO 3166-1 alpha-2
    source: str                           # Adapter identifier, e.g. "bolagsverket"
    profile: BusinessProfile | None = None
    error: str | None = None              # Human-readable error message on failure

    # Confidence: "high" if org_number matched, "medium" if name-matched
    confidence: Literal["high", "medium", "low", "none"] = "none"
