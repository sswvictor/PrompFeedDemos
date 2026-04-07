"""
Instagram Graph API client.

Responsibility: fetch provider profile data and media from the Instagram
Graph API using a long-lived access token obtained during OAuth.

This module is ONLY for Graph API calls (profile data, media).
Do NOT add DM/webhook logic here — that lives in messenger.py and webhook_parser.py.

Adapted from backend-main/services/instagram/instagram_client.py.
"""

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.instagram.com"

# Fields fetched for provider profile auto-fill during onboarding.
_PROFILE_FIELDS = (
    "id,username,account_type,media_count,"
    "profile_picture_url,followers_count,follows_count,"
    "name,biography,website"
)

# Fields fetched per media item for pricelist OCR and portfolio gallery.
_MEDIA_FIELDS = (
    "id,caption,media_type,media_url,thumbnail_url,"
    "timestamp,permalink,like_count,comments_count"
)


class InstagramGraphError(Exception):
    """Raised when the Graph API returns a non-200 response."""
    pass


def fetch_provider_profile(access_token: str) -> dict:
    """
    Fetch provider profile data from the Instagram Graph API.

    Returns a dict with keys:
        id, username, account_type, media_count,
        profile_picture_url, followers_count, follows_count,
        name, biography, website

    Raises InstagramGraphError on HTTP errors.
    """
    resp = requests.get(
        f"{GRAPH_API}/me",
        params={"fields": _PROFILE_FIELDS, "access_token": access_token},
        timeout=15,
    )
    if not resp.ok:
        logger.error("IG profile fetch failed: %s %s", resp.status_code, resp.text)
        raise InstagramGraphError(f"Instagram API error {resp.status_code}: {resp.text}")
    return resp.json()


def fetch_recent_media(access_token: str, limit: int = 20) -> list[dict]:
    """
    Fetch the provider's most recent Instagram posts.

    Used for:
    - Pricelist OCR: pass images to the screenshot/OCR service
    - Portfolio gallery: display on provider public profile

    Returns a list of media item dicts. Each item contains:
        id, caption, media_type, media_url, thumbnail_url,
        timestamp, permalink, like_count, comments_count

    Handles pagination internally up to `limit` items.
    Returns empty list on error (non-fatal for onboarding).
    """
    url = f"{GRAPH_API}/me/media"
    params = {
        "fields": _MEDIA_FIELDS,
        "limit": min(limit, 20),  # IG max per page is 20
        "access_token": access_token,
    }

    items = []
    try:
        while url and len(items) < limit:
            resp = requests.get(url, params=params, timeout=15)
            if not resp.ok:
                logger.warning("IG media fetch failed: %s %s", resp.status_code, resp.text)
                break
            data = resp.json()
            items.extend(data.get("data", []))

            # Follow pagination cursor if we need more items
            next_url = data.get("paging", {}).get("next")
            url = next_url if next_url and len(items) < limit else None
            params = {}  # next URL already contains all params
    except Exception:
        logger.exception("Unexpected error fetching IG media")

    return items[:limit]


def refresh_media_url(ig_media_id: str, access_token: str) -> Optional[dict]:
    """
    Refresh an expiring Instagram media URL.

    Returns a dict with updated media_url, thumbnail_url, media_type, permalink,
    or None if the refresh fails (expired token, permission issue, etc.).

    Callers should treat None as a soft failure and skip the update.
    """
    try:
        resp = requests.get(
            f"{GRAPH_API}/{ig_media_id}",
            params={
                "fields": "id,media_type,media_url,thumbnail_url,permalink",
                "access_token": access_token,
            },
            timeout=10,
        )
        if not resp.ok:
            logger.warning("IG media URL refresh failed for %s: %s", ig_media_id, resp.status_code)
            return None
        data = resp.json()
        return {
            "media_url": data.get("media_url"),
            "thumbnail_url": data.get("thumbnail_url"),
            "media_type": data.get("media_type"),
            "permalink": data.get("permalink"),
        }
    except Exception:
        logger.exception("Unexpected error refreshing IG media URL for %s", ig_media_id)
        return None
