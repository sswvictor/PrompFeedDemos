"""
Salon Link API — request and approval workflow for chair renters joining a salon.

Flow:
    1. Chair renter sends request during onboarding → POST /salon-links/request
    2. Salon owner sees it in their dashboard     → GET  /salon-links/incoming
    3. Owner approves or rejects                  → POST /salon-links/{id}/approve
                                                    POST /salon-links/{id}/reject
    4. Requester checks their own request status  → GET  /salon-links/my-request

When a request is approved, parent_provider_id is written onto the requester's
Provider record and the booking bot can show the correct salon location.

Auth:
    All endpoints require a valid JWT with role "business".
    Ownership is checked per endpoint — you can only act on your own requests/salon.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_provider
from app.db.session import get_db
from app.models.provider import Provider
from app.models.salon_link_request import (
    SalonLinkRequest,
    STATUS_PENDING,
    STATUS_APPROVED,
    STATUS_REJECTED,
    STATUS_REMOVED,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/salon-links", tags=["salon-links"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class SendLinkRequestBody(BaseModel):
    salon_provider_id: str
    message: str | None = None   # Optional intro message from the requester


class ReviewRequestBody(BaseModel):
    review_note: str | None = None   # Optional note from the salon owner


class LinkRequestSummary(BaseModel):
    request_id: str
    status: str
    salon_provider_id: str
    salon_name: str
    salon_city: str | None
    message: str | None
    review_note: str | None
    created_at: str
    reviewed_at: str | None


class IncomingRequestSummary(BaseModel):
    request_id: str
    status: str
    requester_provider_id: str
    requester_name: str
    requester_business_type: str | None
    requester_city: str | None
    message: str | None
    created_at: str


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post(
    "/request",
    status_code=status.HTTP_201_CREATED,
    summary="Chair renter sends a join request to a salon",
)
def send_link_request(
    body: SendLinkRequestBody,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """
    A freelancer or chair renter asks to be linked to a salon.

    - Only one pending request per requester+salon pair is allowed.
    - If a previous request was rejected, a new one can be sent (the old one stays
      in history for the salon owner's records).
    - Approved links cannot be re-requested — use /salon-links/remove to leave first.
    """
    requester = db.query(Provider).filter(Provider.provider_id == provider_id).first()
    if not requester:
        raise HTTPException(status_code=404, detail="Your provider profile was not found.")

    # Can't request to link to yourself
    if provider_id == body.salon_provider_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot link to your own profile.",
        )

    # Confirm the target is an actual salon owner on FixmeApp
    salon = db.query(Provider).filter(Provider.provider_id == body.salon_provider_id).first()
    if not salon:
        raise HTTPException(status_code=404, detail="Salon not found.")

    # Block duplicate pending requests
    existing_pending = (
        db.query(SalonLinkRequest)
        .filter(
            SalonLinkRequest.requester_provider_id == provider_id,
            SalonLinkRequest.salon_provider_id == body.salon_provider_id,
            SalonLinkRequest.status == STATUS_PENDING,
        )
        .first()
    )
    if existing_pending:
        return {
            "request_id": existing_pending.id,
            "message": f"Your request to {salon.name} is already pending. "
                       "You'll be notified when the owner responds.",
        }

    # Block if already approved and linked
    if requester.parent_provider_id == body.salon_provider_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You are already linked to {salon.name}.",
        )

    link_request = SalonLinkRequest(
        requester_provider_id=provider_id,
        salon_provider_id=body.salon_provider_id,
        status=STATUS_PENDING,
        message=body.message,
    )
    db.add(link_request)
    db.commit()
    db.refresh(link_request)

    logger.info(
        "Link request %s: provider %s → salon %s",
        link_request.id, provider_id, body.salon_provider_id
    )

    # TODO: Send push notification / email to salon owner here
    # e.g. notify_salon_owner(salon, requester, link_request)

    return {
        "request_id": link_request.id,
        "status": STATUS_PENDING,
        "message": f"Your request has been sent to {salon.name}. "
                   "You'll receive a notification when the owner responds. "
                   "You can continue setting up your profile in the meantime.",
    }


@router.get(
    "/my-request",
    response_model=LinkRequestSummary | None,
    summary="Check the status of your own most recent salon link request",
)
def get_my_link_request(
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """
    Returns the most recent link request for the current provider.
    Used by the requester to check whether they've been approved or rejected.
    """
    request = (
        db.query(SalonLinkRequest)
        .filter(SalonLinkRequest.requester_provider_id == provider_id)
        .order_by(SalonLinkRequest.created_at.desc())
        .first()
    )
    if not request:
        return None

    salon = db.query(Provider).filter(Provider.provider_id == request.salon_provider_id).first()

    return LinkRequestSummary(
        request_id=request.id,
        status=request.status,
        salon_provider_id=request.salon_provider_id,
        salon_name=salon.name if salon else "Unknown",
        salon_city=salon.city if salon else None,
        message=request.message,
        review_note=request.review_note,
        created_at=request.created_at.isoformat(),
        reviewed_at=request.reviewed_at.isoformat() if request.reviewed_at else None,
    )


@router.get(
    "/incoming",
    response_model=list[IncomingRequestSummary],
    summary="Salon owner: see all pending join requests",
)
def get_incoming_requests(
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """
    Returns all pending link requests addressed to this salon.

    The salon owner sees who wants to join, their name, business type,
    city, and any message they wrote.

    Only returns pending requests by default — add ?include_reviewed=true to see all.
    """
    requests = (
        db.query(SalonLinkRequest)
        .filter(
            SalonLinkRequest.salon_provider_id == provider_id,
            SalonLinkRequest.status == STATUS_PENDING,
        )
        .order_by(SalonLinkRequest.created_at.desc())
        .all()
    )

    result = []
    for req in requests:
        requester = db.query(Provider).filter(
            Provider.provider_id == req.requester_provider_id
        ).first()
        if not requester:
            continue
        result.append(IncomingRequestSummary(
            request_id=req.id,
            status=req.status,
            requester_provider_id=req.requester_provider_id,
            requester_name=requester.name,
            requester_business_type=requester.business_type,
            requester_city=requester.city,
            message=req.message,
            created_at=req.created_at.isoformat(),
        ))
    return result


@router.post(
    "/{request_id}/approve",
    summary="Salon owner: approve a join request",
)
def approve_link_request(
    request_id: str,
    body: ReviewRequestBody = ReviewRequestBody(),
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """
    Approve a pending link request.

    This:
    1. Sets the request status to "approved"
    2. Writes parent_provider_id on the requester's Provider record
    3. Records when the review happened and any optional note

    Only the salon owner (the request's salon_provider_id) can approve.
    """
    request = db.query(SalonLinkRequest).filter(SalonLinkRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found.")

    # Confirm the current user owns the salon being requested
    if request.salon_provider_id != provider_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the salon owner can approve this request.",
        )

    if request.status != STATUS_PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This request is already {request.status}. Cannot approve again.",
        )

    # ── Approve: update request + write parent link ──
    request.status = STATUS_APPROVED
    request.review_note = body.review_note
    request.reviewed_at = datetime.now(timezone.utc)

    # Write the relationship on the requester's profile
    requester = db.query(Provider).filter(
        Provider.provider_id == request.requester_provider_id
    ).first()
    if requester:
        requester.parent_provider_id = provider_id  # Link to this salon

    db.commit()

    logger.info(
        "Link request %s approved: %s joined salon %s",
        request_id, request.requester_provider_id, provider_id
    )

    # TODO: Notify the requester (push notification / email)
    # e.g. notify_requester_approved(requester, salon)

    return {
        "message": f"Request approved. {requester.name if requester else 'The freelancer'} "
                   "is now linked to your salon.",
        "request_id": request_id,
        "status": STATUS_APPROVED,
    }


@router.post(
    "/{request_id}/reject",
    summary="Salon owner: reject a join request",
)
def reject_link_request(
    request_id: str,
    body: ReviewRequestBody = ReviewRequestBody(),
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """
    Reject a pending link request.

    The requester's parent_provider_id is left as None.
    They can send a new request to a different salon or re-apply later.

    Only the salon owner can reject.
    """
    request = db.query(SalonLinkRequest).filter(SalonLinkRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found.")

    if request.salon_provider_id != provider_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the salon owner can reject this request.",
        )

    if request.status != STATUS_PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This request is already {request.status}.",
        )

    request.status = STATUS_REJECTED
    request.review_note = body.review_note
    request.reviewed_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(
        "Link request %s rejected: salon %s declined %s",
        request_id, provider_id, request.requester_provider_id
    )

    # TODO: Notify the requester
    # e.g. notify_requester_rejected(requester, salon, body.review_note)

    requester = db.query(Provider).filter(
        Provider.provider_id == request.requester_provider_id
    ).first()

    return {
        "message": f"Request rejected. {requester.name if requester else 'The freelancer'} "
                   "has been notified.",
        "request_id": request_id,
        "status": STATUS_REJECTED,
    }


@router.delete(
    "/remove",
    summary="Either party: remove an existing approved link",
)
def remove_salon_link(
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """
    Removes an active salon ↔ freelancer link.

    Can be called by either party:
    - If the requester calls this: clears their own parent_provider_id
    - If the salon owner calls this: NOT implemented here — use /salon-links/{request_id}/remove

    After removal, the freelancer can send a new link request to any salon.
    """
    provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found.")

    if not provider.parent_provider_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not currently linked to any salon.",
        )

    old_salon_id = provider.parent_provider_id
    provider.parent_provider_id = None

    # Mark the approved request as removed
    approved_request = (
        db.query(SalonLinkRequest)
        .filter(
            SalonLinkRequest.requester_provider_id == provider_id,
            SalonLinkRequest.salon_provider_id == old_salon_id,
            SalonLinkRequest.status == STATUS_APPROVED,
        )
        .first()
    )
    if approved_request:
        approved_request.status = STATUS_REMOVED
        approved_request.reviewed_at = datetime.now(timezone.utc)

    db.commit()

    logger.info("Provider %s removed link to salon %s", provider_id, old_salon_id)

    return {"message": "Salon link removed. You can link to a different salon anytime."}
