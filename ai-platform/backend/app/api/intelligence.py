"""
Intelligence API — provider vibe profile analysis and confirmation.

Routes:
    POST /intelligence/analyze     — Run the intelligence pipeline (website + IG)
    GET  /intelligence/profile     — Get AI-derived intelligence profile
    POST /intelligence/confirm     — Provider confirms/adjusts vibe tags
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_provider
from app.db.session import get_db
from app.models.provider_intelligence import VIBE_DIMENSIONS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/intelligence", tags=["intelligence"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    scan_data: Optional[dict] = None     # Output from /setup/scan-website
    ig_access_token: Optional[str] = None


class VibeTag(BaseModel):
    tag: str
    score: float
    dimension: str


class IntelligenceProfileResponse(BaseModel):
    provider_id: str
    status: str                          # pending | analyzed | confirmed

    # Contextual layer
    specialties: list[str] = []
    price_tier: Optional[str] = None
    target_audience: Optional[str] = None
    unique_value: Optional[str] = None
    social_proof: list[str] = []

    # Vibe layer
    ai_vibe_tags: list[VibeTag] = []
    confirmed_vibe_tags: list[str] = []
    vibe_summary: Optional[str] = None

    # Source info
    source_url: Optional[str] = None
    ig_posts_analyzed: int = 0

    # Taxonomy for the UI
    vibe_dimensions: dict[str, list[str]] = {}


class ConfirmVibesRequest(BaseModel):
    confirmed_tags: list[str]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tag_to_dimension(tag: str) -> str:
    """Find which dimension a tag belongs to."""
    for dim, tags in VIBE_DIMENSIONS.items():
        if tag in tags:
            return dim
    return "unknown"


def _intel_to_response(intel, provider_id: str) -> IntelligenceProfileResponse:
    """Convert a ProviderIntelligence record to an API response."""
    # Parse JSON fields
    specialties = []
    if intel.specialties:
        try:
            specialties = json.loads(intel.specialties)
        except Exception:
            pass

    social_proof = []
    if intel.social_proof:
        try:
            social_proof = json.loads(intel.social_proof)
        except Exception:
            pass

    ai_tags = []
    if intel.ai_vibe_tags:
        try:
            tag_list = json.loads(intel.ai_vibe_tags)
            scores = json.loads(intel.vibe_scores) if intel.vibe_scores else {}
            ai_tags = [
                VibeTag(tag=t, score=scores.get(t, 0.5), dimension=_tag_to_dimension(t))
                for t in tag_list
            ]
        except Exception:
            pass

    confirmed = []
    if intel.confirmed_vibe_tags:
        try:
            confirmed = json.loads(intel.confirmed_vibe_tags)
        except Exception:
            pass

    return IntelligenceProfileResponse(
        provider_id=provider_id,
        status=intel.status,
        specialties=specialties,
        price_tier=intel.price_tier,
        target_audience=intel.target_audience,
        unique_value=intel.unique_value,
        social_proof=social_proof,
        ai_vibe_tags=ai_tags,
        confirmed_vibe_tags=confirmed,
        vibe_summary=intel.vibe_summary,
        source_url=intel.source_url,
        ig_posts_analyzed=intel.ig_posts_analyzed,
        vibe_dimensions=VIBE_DIMENSIONS,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=IntelligenceProfileResponse)
async def analyze_provider_intelligence(
    body: AnalyzeRequest,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """
    Run the intelligence pipeline for the authenticated provider.

    Accepts website scan data and/or Instagram access token.
    Extracts contextual profile + AI-suggested vibe tags.
    """
    from app.services.intelligence_pipeline import analyze_provider

    intel = analyze_provider(
        db=db,
        provider_id=provider_id,
        scan_data=body.scan_data,
        ig_access_token=body.ig_access_token,
    )

    return _intel_to_response(intel, provider_id)


@router.get("/profile", response_model=IntelligenceProfileResponse)
async def get_intelligence_profile(
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """
    Get the current intelligence profile for the authenticated provider.
    Returns 404 if no analysis has been run yet.
    """
    from app.services.intelligence_pipeline import get_intelligence

    intel = get_intelligence(db, provider_id)
    if not intel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No intelligence profile found. Run analysis first.",
        )

    return _intel_to_response(intel, provider_id)


@router.post("/confirm", response_model=IntelligenceProfileResponse)
async def confirm_vibe_tags(
    body: ConfirmVibesRequest,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """
    Provider confirms or adjusts their AI-suggested vibe tags.
    This becomes the canonical vibe profile for the discovery engine.
    """
    from app.services.intelligence_pipeline import confirm_vibes

    try:
        intel = confirm_vibes(db, provider_id, body.confirmed_tags)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return _intel_to_response(intel, provider_id)
