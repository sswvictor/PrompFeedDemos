from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.api.auth import get_current_provider
from app.db.session import get_db
from app.services.waitlist_service import WaitlistService

router = APIRouter(prefix="/waitlist", tags=["waitlist"])


# ── Schemas ────────────────────────────────────────────────────────

class WaitlistJoinIn(BaseModel):
    provider_id: str
    email: EmailStr
    name: str
    service_id: str | None = None
    preferred_days: list[int] | None = None  # [0,1,2,3,4] Mon=0, Sun=6
    earliest_hour: int = 8
    latest_hour: int = 18


class ManualOfferIn(BaseModel):
    slot_start: datetime
    slot_end: datetime


# ── Public endpoints ──────────────────────────────────────────────

@router.post("/join")
def join_waitlist(payload: WaitlistJoinIn, db: Session = Depends(get_db)):
    """Customer joins the waitlist for a provider."""
    entry = WaitlistService.join_waitlist(
        db=db,
        provider_id=payload.provider_id,
        email=payload.email,
        name=payload.name,
        service_id=payload.service_id,
        preferred_days=payload.preferred_days,
        earliest_hour=payload.earliest_hour,
        latest_hour=payload.latest_hour,
    )
    return {
        "entry_id": entry.entry_id,
        "status": entry.status,
        "message": "You're on the waitlist! We'll email you when a slot opens.",
    }


@router.get("/status/{entry_id}")
def waitlist_status(entry_id: str, db: Session = Depends(get_db)):
    """Check waitlist position and status."""
    result = WaitlistService.get_entry_status(db, entry_id)
    if not result:
        raise HTTPException(status_code=404, detail="Waitlist entry not found")
    return result


@router.get("/offer/{offer_id}")
def get_offer(
    offer_id: str,
    secret: str = Query(..., min_length=1, description="Offer secret token from email link"),
    db: Session = Depends(get_db),
):
    """Get offer details (for the accept/decline page). Requires secret token."""
    result = WaitlistService.get_offer(db, offer_id, offer_secret=secret)
    if not result:
        raise HTTPException(status_code=404, detail="Offer not found")
    return result


@router.post("/offer/{offer_id}/accept")
def accept_offer(
    offer_id: str,
    secret: str = Query(..., min_length=1, description="Offer secret token from email link"),
    db: Session = Depends(get_db),
):
    """Accept an offer — creates a real booking. Requires secret token."""
    try:
        result = WaitlistService.accept_offer(db, offer_id, offer_secret=secret)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/offer/{offer_id}/decline")
def decline_offer(
    offer_id: str,
    secret: str = Query(..., min_length=1, description="Offer secret token from email link"),
    db: Session = Depends(get_db),
):
    """Decline an offer — slot goes to next person in queue. Requires secret token."""
    try:
        WaitlistService.decline_offer(db, offer_id, offer_secret=secret)
        return {"status": "declined", "message": "Offer declined. You're still on the waitlist."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/public/{provider_id}/entries")
def provider_waitlist_public(
    provider_id: str,
    status: str | None = "active",
    db: Session = Depends(get_db),
):
    """Public/debug view of a provider's waitlist entries."""
    return WaitlistService.get_entries_for_provider(db, provider_id, status)


@router.post("/{entry_id}/cancel")
def cancel_entry(entry_id: str, db: Session = Depends(get_db)):
    """Customer removes themselves from the waitlist."""
    try:
        WaitlistService.cancel_entry(db, entry_id)
        return {"status": "cancelled"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/expire-stale")
def expire_stale(db: Session = Depends(get_db)):
    """Maintenance: expire stale offers and cascade to next in queue.
    Call from cron job or admin endpoint."""
    count = WaitlistService.expire_stale_offers(db)
    return {"expired_count": count}


# ── Provider-authenticated endpoints ──────────────────────────────

@router.get("/provider/entries")
def provider_waitlist_auth(
    status: str | None = "active",
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Authenticated: provider views their own waitlist entries."""
    return WaitlistService.get_entries_for_provider(db, provider_id, status)


@router.get("/provider/count")
def provider_waitlist_count(
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Authenticated: get the active waitlist count for dashboard badge."""
    entries = WaitlistService.get_entries_for_provider(db, provider_id, "active")
    return {"count": len(entries)}


@router.post("/provider/entries/{entry_id}/offer")
def provider_manual_offer(
    entry_id: str,
    payload: ManualOfferIn,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Provider manually sends an offer to a specific waitlist entry.

    Used from the dashboard when the provider wants to hand-pick a
    customer and offer them a specific time slot."""
    try:
        offer = WaitlistService.create_manual_offer(
            db=db,
            entry_id=entry_id,
            provider_id=provider_id,
            slot_start=payload.slot_start,
            slot_end=payload.slot_end,
        )
        return {
            "offer_id": offer.offer_id,
            "status": offer.status,
            "expires_at": offer.expires_at.isoformat(),
            "message": "Offer sent! The customer has 10 minutes to accept.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/provider/entries/{entry_id}")
def provider_remove_entry(
    entry_id: str,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Provider removes a waitlist entry."""
    try:
        WaitlistService.provider_remove_entry(db, entry_id, provider_id)
        return {"status": "removed"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


