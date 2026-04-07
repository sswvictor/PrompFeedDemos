"""Ensure the official Fixmeapp Instagram relay Page is registered in the DB.

Meta webhooks always send recipient_id = the Facebook Page that received the DM.
For the platform relay account, that row must exist with is_platform_page=True.

Set PLATFORM_INSTAGRAM_PAGE_ID in the environment so every fresh DB / deploy
gets the mapping without a manual POST to /platform/instagram-page.
"""

from __future__ import annotations

import logging

from app.config import settings
from app.db.session import SessionLocal
from app.models.provider_instagram_page import ProviderInstagramPage
from app.services.token_crypto import encrypt_token

logger = logging.getLogger(__name__)


def ensure_platform_instagram_page_from_env() -> None:
    page_id = (settings.PLATFORM_INSTAGRAM_PAGE_ID or "").strip()
    if not page_id:
        return

    token_src = (
        (settings.PLATFORM_INSTAGRAM_PAGE_ACCESS_TOKEN or "").strip()
        or (settings.INSTAGRAM_PAGE_ACCESS_TOKEN or "").strip()
    )
    page_name = (settings.PLATFORM_INSTAGRAM_PAGE_NAME or "").strip() or "fixmeapp"
    enc = encrypt_token(token_src) if token_src else None

    db = SessionLocal()
    try:
        existing = (
            db.query(ProviderInstagramPage)
            .filter(ProviderInstagramPage.instagram_page_id == page_id)
            .first()
        )
        if existing:
            existing.provider_id = None
            existing.is_platform_page = True
            existing.page_name = page_name
            if enc:
                existing.access_token = enc
            db.commit()
            logger.info(
                "Platform Instagram page sync: updated instagram_page_id=%s",
                page_id,
            )
            return

        row = ProviderInstagramPage(
            provider_id=None,
            instagram_page_id=page_id,
            page_name=page_name,
            access_token=enc,
            is_platform_page=True,
        )
        db.add(row)
        db.commit()
        logger.info(
            "Platform Instagram page sync: inserted instagram_page_id=%s",
            page_id,
        )
    except Exception:
        db.rollback()
        logger.exception("Platform Instagram page sync failed (startup continues)")
    finally:
        db.close()
