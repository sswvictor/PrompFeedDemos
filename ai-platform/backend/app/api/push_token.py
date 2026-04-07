"""
Provider push token endpoints.

POST   /api/v1/provider/push-token   — register Expo push token (called on login)
DELETE /api/v1/provider/push-token   — unregister token (called on logout)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_provider
from app.db.session import get_db
from app.models.provider import Provider

logger = logging.getLogger(__name__)
router = APIRouter(tags=["push-token"])


class PushTokenIn(BaseModel):
    push_token: str


@router.post("/provider/push-token", status_code=200)
def register_push_token(
    body: PushTokenIn,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Save the device's Expo push token so we can send push notifications."""
    if not body.push_token.startswith("ExponentPushToken"):
        raise HTTPException(
            status_code=422,
            detail="Invalid push token format — expected ExponentPushToken[...]",
        )

    provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    provider.push_token = body.push_token
    db.commit()
    logger.info("Push token registered for provider %s", provider_id)
    return {"ok": True}


@router.delete("/provider/push-token", status_code=200)
def unregister_push_token(
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Remove the stored push token (called when provider logs out)."""
    provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    provider.push_token = None
    db.commit()
    logger.info("Push token unregistered for provider %s", provider_id)
    return {"ok": True}
