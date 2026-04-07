"""
Customer GDPR / Data Rights API

GDPR Articles implemented:
  Art. 15 — Right of access        → GET /customer/me/gdpr/requests
  Art. 17 — Right to erasure        → POST /customer/me/gdpr/request (type=deletion)
  Art. 20 — Right to portability    → POST /customer/me/gdpr/request (type=export)

Requests are queued for manual processing by our ops team.
Response SLA: 30 days (GDPR Art. 12).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.gdpr_request import GDPRRequest
from app.models.user import User
from app.utils.jwt_token import decode_access_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/customer/me/gdpr", tags=["customer-gdpr"])
security = HTTPBearer()

ALLOWED_TYPES = {"export", "deletion"}
ACTIVE_STATUSES = {"pending", "in_progress"}


def _get_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    try:
        payload = decode_access_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing user ID")
    roles = payload.get("role", [])
    if "customer" not in roles:
        raise HTTPException(status_code=403, detail="Customer access required")
    return user_id


# ── Schemas ───────────────────────────────────────────────────────────────────

class GDPRRequestIn(BaseModel):
    request_type: Literal["export", "deletion"]
    notes: str | None = Field(None, max_length=1000)


class GDPRRequestOut(BaseModel):
    request_id: str
    request_type: str
    status: str
    notes: str | None = None
    requested_at: str
    updated_at: str | None = None
    completed_at: str | None = None

    class Config:
        from_attributes = True


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/request", response_model=GDPRRequestOut, status_code=201)
def submit_gdpr_request(
    payload: GDPRRequestIn,
    user_id: str = Depends(_get_user_id),
    db: Session = Depends(get_db),
):
    """
    Submit a GDPR data rights request.

    - type=export   → Art. 15 (access) + Art. 20 (portability): we send you all your data
    - type=deletion → Art. 17 (erasure): we delete your account and all personal data

    Duplicate pending/in-progress requests of the same type are rejected to prevent spam.
    Our ops team will action the request within 30 days (GDPR Art. 12 SLA).
    """
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent duplicate active requests of the same type
    existing = (
        db.query(GDPRRequest)
        .filter(
            GDPRRequest.user_id == user_id,
            GDPRRequest.request_type == payload.request_type,
            GDPRRequest.status.in_(list(ACTIVE_STATUSES)),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"You already have a pending {payload.request_type} request "
                f"(submitted {existing.requested_at.strftime('%Y-%m-%d')}). "
                "Please wait for it to be processed."
            ),
        )

    req = GDPRRequest(
        user_id=user_id,
        request_type=payload.request_type,
        status="pending",
        notes=payload.notes,
        requested_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    logger.info(
        "GDPR %s request submitted by user %s (request_id=%s)",
        payload.request_type,
        user_id,
        req.request_id,
    )

    return GDPRRequestOut(
        request_id=req.request_id,
        request_type=req.request_type,
        status=req.status,
        notes=req.notes,
        requested_at=req.requested_at.isoformat(),
        updated_at=None,
        completed_at=None,
    )


@router.get("/requests", response_model=list[GDPRRequestOut])
def list_my_gdpr_requests(
    user_id: str = Depends(_get_user_id),
    db: Session = Depends(get_db),
):
    """Return all GDPR requests submitted by the authenticated user (newest first)."""
    rows = (
        db.query(GDPRRequest)
        .filter(GDPRRequest.user_id == user_id)
        .order_by(GDPRRequest.requested_at.desc())
        .all()
    )

    return [
        GDPRRequestOut(
            request_id=r.request_id,
            request_type=r.request_type,
            status=r.status,
            notes=r.notes,
            requested_at=r.requested_at.isoformat(),
            updated_at=r.updated_at.isoformat() if r.updated_at else None,
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
        )
        for r in rows
    ]
