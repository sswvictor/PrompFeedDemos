"""
Provider follow/unfollow API endpoints.

Routes:
    POST   /providers/{provider_id}/follow          — follow a provider
    DELETE /providers/{provider_id}/follow          — unfollow a provider
    GET    /providers/{provider_id}/followers/count — get follower count

The customer identity is resolved from the JWT token (fixme_token).
The provider's denormalised fixmeapp_followers_count is kept in sync here.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone

from app.db.session import get_db
from app.models.provider_follow import ProviderFollow
from app.models.provider import Provider
from app.models.customer import Customer
from app.api.customer_dashboard import get_current_customer_user_id
from app.services.loyalty_service import LoyaltyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/providers", tags=["Provider Follow"])


def _get_provider_or_404(db: Session, provider_id: str) -> Provider:
    provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


def _resolve_customer_id(db: Session, user_id: str) -> str:
    """Return the primary customer_id for a logged-in user.

    A user may have several Customer rows (one per booking before sign-up).
    merge_status='primary' marks the canonical record after merging.
    """
    customer = (
        db.query(Customer)
        .filter(Customer.user_id == user_id, Customer.merge_status == "primary")
        .first()
    )
    if not customer:
        # Fallback: any linked customer (handles edge cases where merge hasn't run)
        customer = db.query(Customer).filter(Customer.user_id == user_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer profile not found")
    return customer.customer_id


@router.post("/{provider_id}/follow", status_code=201)
def follow_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_customer_user_id),
):
    """Follow a provider. Idempotent — following twice returns 201 without error."""
    customer_id = _resolve_customer_id(db, user_id)
    _get_provider_or_404(db, provider_id)

    existing = db.query(ProviderFollow).filter(
        ProviderFollow.customer_id == customer_id,
        ProviderFollow.provider_id == provider_id,
    ).first()

    if existing:
        return {"status": "already_following", "provider_id": provider_id}

    follow = ProviderFollow(customer_id=customer_id, provider_id=provider_id)
    db.add(follow)

    try:
        db.flush()
        # Increment denormalised counter atomically
        db.query(Provider).filter(Provider.provider_id == provider_id).update(
            {"fixmeapp_followers_count": Provider.fixmeapp_followers_count + 1}
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        # Race condition — another request already created the follow
        return {"status": "already_following", "provider_id": provider_id}

    logger.info("Customer %s followed provider %s", customer_id, provider_id)

    try:
        LoyaltyService.track_follow_provider(
            db,
            customer_user_id=user_id,
            provider_id=provider_id,
        )
    except Exception:
        logger.exception("Loyalty follow tracking failed user=%s provider=%s", user_id, provider_id)

    return {"status": "following", "provider_id": provider_id}


@router.delete("/{provider_id}/follow", status_code=200)
def unfollow_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_customer_user_id),
):
    """Unfollow a provider. Idempotent — unfollowing when not following returns 200."""
    customer_id = _resolve_customer_id(db, user_id)
    _get_provider_or_404(db, provider_id)

    follow = db.query(ProviderFollow).filter(
        ProviderFollow.customer_id == customer_id,
        ProviderFollow.provider_id == provider_id,
    ).first()

    if not follow:
        return {"status": "not_following", "provider_id": provider_id}

    db.delete(follow)
    # Decrement counter, floor at 0
    db.query(Provider).filter(Provider.provider_id == provider_id).update(
        {
            "fixmeapp_followers_count": Provider.fixmeapp_followers_count - 1
            if Provider.fixmeapp_followers_count > 0
            else 0
        }
    )
    db.commit()

    logger.info("Customer %s unfollowed provider %s", customer_id, provider_id)
    return {"status": "unfollowed", "provider_id": provider_id}


@router.get("/{provider_id}/followers/count")
def get_follower_count(
    provider_id: str,
    db: Session = Depends(get_db),
):
    """Get the native Fixmeapp follower count for a provider. Public endpoint."""
    provider = _get_provider_or_404(db, provider_id)
    return {
        "provider_id": provider_id,
        "fixmeapp_followers_count": provider.fixmeapp_followers_count,
        "ig_followers_count": provider.ig_followers_count,
    }


@router.get("/{provider_id}/follow/status")
def get_follow_status(
    provider_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_customer_user_id),
):
    """Check if the current customer follows this provider."""
    customer_id = _resolve_customer_id(db, user_id)
    follow = db.query(ProviderFollow).filter(
        ProviderFollow.customer_id == customer_id,
        ProviderFollow.provider_id == provider_id,
    ).first()
    return {"is_following": follow is not None, "provider_id": provider_id}
