"""
Intelligence Pipeline — extracts vibe & contextual profile from provider data.

Orchestrates:
  1. Website scan data → contextual fields + initial vibe extraction
  2. Instagram media → GPT-4o Vision vibe analysis (images + captions)
  3. Merges signals → produces AI-suggested vibe tags + summary

Called during onboarding after website scan completes. The resulting
vibe profile is presented to the provider for confirmation in StepVibeConfirm.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.provider_intelligence import ProviderIntelligence, VIBE_DIMENSIONS
from openai import OpenAI

logger = logging.getLogger(__name__)
client = OpenAI(api_key=settings.OPENAI_API_KEY)


# ── Vibe extraction prompts ──────────────────────────────────────────────────

_VIBE_FROM_TEXT_PROMPT = """\
You are an AI aesthetic analyst for a beauty & wellness discovery platform.
Analyze the provider's website content, bio, services, and any other text to
determine their aesthetic vibe and brand identity.

Choose tags from EXACTLY these dimensions (pick 1-3 per dimension that fits):

AESTHETIC: minimalist, maximalist, editorial, boho, classic, avant-garde, natural, glamorous, industrial, vintage
ENERGY: calm, energetic, luxurious, cozy, edgy, playful, sophisticated, zen, bold, intimate
STYLE ERA: modern, retro, timeless, trendsetting, traditional
BRAND PERSONALITY: artistic, clinical, boutique, eco-conscious, tech-forward, family-friendly, exclusive, community-driven

Also provide:
- vibe_summary: 1-2 sentences describing their overall vibe/aesthetic in a warm, human way (max 150 chars)
- confidence: object mapping each chosen tag to a confidence score 0.0-1.0

Return ONLY valid JSON:
{
  "tags": ["tag1", "tag2", ...],
  "confidence": {"tag1": 0.85, "tag2": 0.72, ...},
  "vibe_summary": "..."
}
"""

_VIBE_FROM_IMAGES_PROMPT = """\
You are an AI aesthetic analyst for a beauty & wellness discovery platform.
Analyze these Instagram images from a beauty/wellness provider to determine
their visual aesthetic, vibe, and brand identity.

Look at: color palettes, composition style, lighting, workspace aesthetics,
client results, brand consistency, and overall visual storytelling.

Choose tags from EXACTLY these dimensions (pick 1-3 per dimension):

AESTHETIC: minimalist, maximalist, editorial, boho, classic, avant-garde, natural, glamorous, industrial, vintage
ENERGY: calm, energetic, luxurious, cozy, edgy, playful, sophisticated, zen, bold, intimate
STYLE ERA: modern, retro, timeless, trendsetting, traditional
BRAND PERSONALITY: artistic, clinical, boutique, eco-conscious, tech-forward, family-friendly, exclusive, community-driven

Return ONLY valid JSON:
{
  "tags": ["tag1", "tag2", ...],
  "confidence": {"tag1": 0.85, "tag2": 0.72, ...},
  "visual_notes": "Brief note on what the images convey (max 100 chars)"
}
"""


def _extract_vibe_from_text(text_context: str) -> dict:
    """Extract vibe tags from website/bio text using GPT-4o-mini."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _VIBE_FROM_TEXT_PROMPT},
                {"role": "user", "content": text_context},
            ],
            temperature=0.3,
            max_tokens=500,
        )
        raw = response.choices[0].message.content.strip()
        return json.loads(raw)
    except Exception as exc:
        logger.error("Vibe text extraction failed: %s", exc)
        return {"tags": [], "confidence": {}, "vibe_summary": ""}


def _extract_vibe_from_images(image_urls: list[str], captions: list[str]) -> dict:
    """Extract vibe tags from Instagram images using GPT-4o Vision."""
    if not image_urls:
        return {"tags": [], "confidence": {}, "visual_notes": ""}

    # Build vision content — up to 6 images to stay within token budget
    content_parts = [{"type": "text", "text": _VIBE_FROM_IMAGES_PROMPT}]

    for i, url in enumerate(image_urls[:6]):
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": url, "detail": "low"},
        })
        if i < len(captions) and captions[i]:
            content_parts.append({
                "type": "text",
                "text": f"Caption {i+1}: {captions[i][:200]}",
            })

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content_parts}],
            temperature=0.3,
            max_tokens=500,
        )
        raw = response.choices[0].message.content.strip()
        return json.loads(raw)
    except Exception as exc:
        logger.error("Vibe image extraction failed: %s", exc)
        return {"tags": [], "confidence": {}, "visual_notes": ""}


def _merge_vibe_signals(text_vibe: dict, image_vibe: dict) -> tuple[list[str], dict, str]:
    """
    Merge vibe signals from text and image analysis.
    Image analysis gets slightly higher weight for visual aesthetics.
    Returns (merged_tags, merged_scores, summary).
    """
    all_scores = {}

    # Text signals (weight 0.4)
    for tag, score in text_vibe.get("confidence", {}).items():
        all_scores[tag] = all_scores.get(tag, 0) + score * 0.4

    # Image signals (weight 0.6 — visual is king in beauty)
    for tag, score in image_vibe.get("confidence", {}).items():
        all_scores[tag] = all_scores.get(tag, 0) + score * 0.6

    # Validate tags against taxonomy
    valid_tags = set()
    for tags in VIBE_DIMENSIONS.values():
        valid_tags.update(tags)

    filtered = {k: v for k, v in all_scores.items() if k in valid_tags}

    # Take top tags (at least 3, up to 8) sorted by score
    sorted_tags = sorted(filtered.keys(), key=lambda t: filtered[t], reverse=True)
    top_tags = sorted_tags[:8] if len(sorted_tags) > 3 else sorted_tags

    # Build score dict for top tags only
    scores = {tag: round(filtered[tag], 2) for tag in top_tags}

    # Summary: prefer text vibe summary, append visual notes
    summary = text_vibe.get("vibe_summary", "")
    visual = image_vibe.get("visual_notes", "")
    if visual and summary:
        summary = f"{summary} {visual}"
    elif visual:
        summary = visual

    return top_tags, scores, summary


def analyze_provider(
    db: Session,
    provider_id: str,
    scan_data: Optional[dict] = None,
    ig_access_token: Optional[str] = None,
) -> ProviderIntelligence:
    """
    Run the full intelligence pipeline for a provider.

    Args:
        db: Database session
        provider_id: Provider UUID
        scan_data: Output from /setup/scan-website (ScanWebsiteResponse dict)
        ig_access_token: Instagram access token for media analysis

    Returns:
        ProviderIntelligence record with AI-suggested vibe tags
    """
    # Get or create intelligence record
    intel = db.query(ProviderIntelligence).filter(
        ProviderIntelligence.provider_id == provider_id
    ).first()

    if not intel:
        intel = ProviderIntelligence(provider_id=provider_id)
        db.add(intel)

    data_sources = []

    # ── Step 1: Process website scan data ─────────────────────────────────────
    text_context_parts = []

    if scan_data:
        # Store contextual fields
        intel.specialties = json.dumps(scan_data.get("specialties", []))
        intel.price_tier = scan_data.get("price_tier")
        intel.target_audience = scan_data.get("target_audience")
        intel.unique_value = scan_data.get("unique_value")
        intel.social_proof = json.dumps(scan_data.get("social_proof", []))
        intel.source_url = scan_data.get("source_url")

        # Build text context for vibe extraction
        if scan_data.get("name"):
            text_context_parts.append(f"Business name: {scan_data['name']}")
        if scan_data.get("bio"):
            text_context_parts.append(f"Bio: {scan_data['bio']}")
        if scan_data.get("specialties"):
            text_context_parts.append(f"Specialties: {', '.join(scan_data['specialties'])}")
        if scan_data.get("services"):
            svc_names = [s.get("name", "") for s in scan_data["services"] if isinstance(s, dict)]
            text_context_parts.append(f"Services: {', '.join(svc_names[:15])}")
        if scan_data.get("price_tier"):
            text_context_parts.append(f"Price tier: {scan_data['price_tier']}")
        if scan_data.get("target_audience"):
            text_context_parts.append(f"Target audience: {scan_data['target_audience']}")
        if scan_data.get("unique_value"):
            text_context_parts.append(f"Unique value: {scan_data['unique_value']}")
        if scan_data.get("social_proof"):
            text_context_parts.append(f"Reviews: {' | '.join(scan_data['social_proof'][:3])}")

        data_sources.append({
            "type": "website",
            "url": scan_data.get("source_url", ""),
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        })

    # ── Step 2: Analyze Instagram media ───────────────────────────────────────
    image_urls = []
    captions = []

    if ig_access_token:
        try:
            from app.integrations.instagram.graph_client import fetch_recent_media
            media_items = fetch_recent_media(ig_access_token, limit=12)
            for item in media_items:
                if item.get("media_type") in ("IMAGE", "CAROUSEL_ALBUM"):
                    url = item.get("media_url") or item.get("thumbnail_url")
                    if url:
                        image_urls.append(url)
                        captions.append(item.get("caption", ""))
                        # Add captions to text context too
                        if item.get("caption"):
                            text_context_parts.append(f"IG post: {item['caption'][:200]}")

            intel.ig_posts_analyzed = len(image_urls)
            data_sources.append({
                "type": "instagram",
                "posts_analyzed": len(image_urls),
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as exc:
            logger.warning("Instagram media fetch failed for pipeline: %s", exc)

    # ── Step 3: Extract vibes ─────────────────────────────────────────────────
    text_vibe = {}
    image_vibe = {}

    if text_context_parts:
        text_vibe = _extract_vibe_from_text("\n".join(text_context_parts))

    if image_urls:
        image_vibe = _extract_vibe_from_images(image_urls, captions)

    # ── Step 4: Merge and store ───────────────────────────────────────────────
    tags, scores, summary = _merge_vibe_signals(text_vibe, image_vibe)

    intel.ai_vibe_tags = json.dumps(tags)
    intel.vibe_scores = json.dumps(scores)
    intel.vibe_summary = summary
    intel.data_sources = json.dumps(data_sources)
    intel.status = "analyzed"
    intel.analyzed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(intel)

    logger.info(
        "Intelligence pipeline complete: provider=%s tags=%s sources=%d",
        provider_id, tags, len(data_sources),
    )
    return intel


def confirm_vibes(
    db: Session,
    provider_id: str,
    confirmed_tags: list[str],
) -> ProviderIntelligence:
    """
    Provider confirms or adjusts their AI-suggested vibe tags.
    This becomes the canonical profile used by the discovery engine.
    """
    intel = db.query(ProviderIntelligence).filter(
        ProviderIntelligence.provider_id == provider_id
    ).first()

    if not intel:
        raise ValueError(f"No intelligence record for provider {provider_id}")

    # Validate tags against taxonomy
    valid_tags = set()
    for tags in VIBE_DIMENSIONS.values():
        valid_tags.update(tags)

    validated = [t for t in confirmed_tags if t in valid_tags]

    intel.confirmed_vibe_tags = json.dumps(validated)
    intel.status = "confirmed"
    intel.confirmed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(intel)

    logger.info("Vibes confirmed: provider=%s tags=%s", provider_id, validated)
    return intel


def get_intelligence(db: Session, provider_id: str) -> Optional[ProviderIntelligence]:
    """Retrieve intelligence record for a provider."""
    return db.query(ProviderIntelligence).filter(
        ProviderIntelligence.provider_id == provider_id
    ).first()
