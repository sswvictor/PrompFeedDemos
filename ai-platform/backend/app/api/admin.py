"""Internal admin API endpoints for operations tooling."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.admin_audit_log import AdminAuditLog
from app.models.booking import Booking
from app.models.business_verification import BusinessVerification
from app.models.customer import Customer
from app.models.gdpr_request import GDPRRequest
from app.models.loyalty_event import LoyaltyEvent
from app.models.provider import Provider
from app.models.user import User
from app.services.booking_service import BookingService, SlotUnavailableError
from app.services.customer_service import CustomerService
from app.services.loyalty_service import LoyaltyService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

SUPER_ADMIN_EMAILS = {
    email.strip().lower()
    for email in os.environ.get("ADMIN_SUPER_ADMINS", "johanna@fixmeapp.ai").split(",")
    if email.strip()
}


def verify_admin_token(x_admin_token: str = Header(..., alias="X-Admin-Token")) -> None:
    expected = os.environ.get("ADMIN_SECRET_TOKEN", "")
    if not expected or x_admin_token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing admin token")


def _now_utc_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _admin_email(actor_header: str | None) -> str:
    return (actor_header or "ops@fixmeapp.ai").strip().lower() or "ops@fixmeapp.ai"


def _admin_role(admin_email: str) -> str:
    if admin_email in SUPER_ADMIN_EMAILS:
        return "super_admin"
    return "ops_admin"


def _admin_actor(actor_header: str | None) -> str:
    return _admin_email(actor_header)


def require_super_admin(
    x_admin_actor: str = Header(..., alias="X-Admin-Actor"),
    _: None = Depends(verify_admin_token),
) -> str:
    admin_email = _admin_email(x_admin_actor)
    if _admin_role(admin_email) != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    return admin_email


def _safe_json(data: Any) -> str:
    return json.dumps(data or {}, default=str, ensure_ascii=False)


def _user_snapshot(user: User) -> dict[str, Any]:
    return {
        "user_id": user.user_id,
        "email": user.email,
        "display_name": user.display_name,
        "status": user.status,
        "is_customer": bool(user.is_customer),
        "is_provider": bool(user.is_provider),
        "is_profile_public": bool(user.is_profile_public),
    }


def _provider_snapshot(provider: Provider) -> dict[str, Any]:
    return {
        "provider_id": provider.provider_id,
        "user_id": provider.user_id,
        "name": provider.name,
        "city": provider.city,
        "location_salon": provider.location_salon,
        "phone": provider.phone,
        "is_verified": bool(provider.is_verified),
    }


def _booking_snapshot(booking: Booking) -> dict[str, Any]:
    return {
        "booking_id": booking.booking_id,
        "provider_id": booking.provider_id,
        "customer_id": booking.customer_id,
        "status": booking.status,
        "scheduled_start": booking.scheduled_start.isoformat() if booking.scheduled_start else None,
        "scheduled_end": booking.scheduled_end.isoformat() if booking.scheduled_end else None,
        "customer_notes": booking.customer_notes,
        "provider_notes": booking.provider_notes,
        "total_amount_inc_vat": booking.total_amount_inc_vat,
    }


def _log_admin_action(
    db: Session,
    *,
    admin_actor: str,
    action: str,
    entity_type: str,
    entity_id: str | None,
    reason: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        AdminAuditLog(
            admin_actor=admin_actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            reason=reason,
            before_json=_safe_json(before),
            after_json=_safe_json(after),
            metadata_json=_safe_json(metadata),
        )
    )


@router.get("/me")
def admin_me(
    x_admin_actor: str = Header(..., alias="X-Admin-Actor"),
    _: None = Depends(verify_admin_token),
):
    admin_email = _admin_email(x_admin_actor)
    role = _admin_role(admin_email)
    return {
        "admin_email": admin_email,
        "role": role,
        "is_super_admin": role == "super_admin",
    }


class VerificationItem(BaseModel):
    id: str
    provider_id: str
    provider_name: str
    provider_email: str
    country: str
    us_state: Optional[str]
    license_type: Optional[str]
    license_number: Optional[str]
    org_number: Optional[str]
    document_filename: Optional[str]
    status: str
    submitted_at: datetime
    reviewed_at: Optional[datetime]
    reviewer_notes: Optional[str]

    class Config:
        from_attributes = True


class RejectBody(BaseModel):
    reason: Optional[str] = None


@router.get("/verifications", response_model=list[VerificationItem])
def list_verifications(
    status: str = "pending",
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
):
    rows = (
        db.query(BusinessVerification)
        .filter(BusinessVerification.status == status)
        .order_by(BusinessVerification.submitted_at.asc())
        .all()
    )

    result = []
    for v in rows:
        provider = db.query(Provider).filter(Provider.provider_id == v.provider_id).first()
        provider_name = (provider.name if provider else None) or "Unknown"
        provider_email = ""
        if provider and provider.user:
            provider_email = getattr(provider.user, "email", "") or ""

        result.append(
            VerificationItem(
                id=v.id,
                provider_id=v.provider_id,
                provider_name=provider_name,
                provider_email=provider_email,
                country=v.country,
                us_state=v.us_state,
                license_type=v.license_type,
                license_number=v.license_number,
                org_number=v.org_number,
                document_filename=v.document_filename,
                status=v.status,
                submitted_at=v.submitted_at,
                reviewed_at=v.reviewed_at,
                reviewer_notes=v.reviewer_notes,
            )
        )
    return result


@router.post("/verifications/{verification_id}/approve")
def approve_verification(
    verification_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
    x_admin_actor: str | None = Header(None, alias="X-Admin-Actor"),
):
    v = db.query(BusinessVerification).filter(BusinessVerification.id == verification_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Verification not found")
    if v.status != "pending":
        raise HTTPException(status_code=400, detail=f"Verification is already {v.status}")

    before = {"status": v.status, "provider_id": v.provider_id}
    provider = db.query(Provider).filter(Provider.provider_id == v.provider_id).first()
    if provider:
        provider.is_verified = True
        provider.verified_at = _now_utc_naive()
        provider.verified_country = v.country
        provider.verification_source = "manual_review"

    v.status = "approved"
    v.reviewed_at = _now_utc_naive()
    v.license_number = None
    v.org_number = None

    _log_admin_action(
        db,
        admin_actor=_admin_actor(x_admin_actor),
        action="verification.approve",
        entity_type="business_verification",
        entity_id=v.id,
        before=before,
        after={"status": v.status, "provider_verified": bool(provider and provider.is_verified)},
    )
    db.commit()
    return {"ok": True, "provider_id": v.provider_id}


@router.post("/verifications/{verification_id}/reject")
def reject_verification(
    verification_id: str,
    body: RejectBody = RejectBody(),
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
    x_admin_actor: str | None = Header(None, alias="X-Admin-Actor"),
):
    v = db.query(BusinessVerification).filter(BusinessVerification.id == verification_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Verification not found")

    before = {"status": v.status}
    v.status = "rejected"
    v.reviewed_at = _now_utc_naive()
    v.reviewer_notes = body.reason
    v.license_number = None
    v.org_number = None

    _log_admin_action(
        db,
        admin_actor=_admin_actor(x_admin_actor),
        action="verification.reject",
        entity_type="business_verification",
        entity_id=v.id,
        reason=body.reason,
        before=before,
        after={"status": v.status, "reviewer_notes": v.reviewer_notes},
    )
    db.commit()
    return {"ok": True}


@router.get("/verifications/stats")
def verification_stats(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
):
    rows = (
        db.query(BusinessVerification.status, func.count(BusinessVerification.id))
        .group_by(BusinessVerification.status)
        .all()
    )
    return {status: count for status, count in rows}

class GDPRRequestAdminOut(BaseModel):
    request_id: str
    user_id: str
    user_email: str
    user_display_name: Optional[str]
    request_type: str
    status: str
    notes: Optional[str]
    admin_notes: Optional[str]
    requested_at: datetime
    updated_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class GDPRStatusUpdateIn(BaseModel):
    status: str
    admin_notes: Optional[str] = None


VALID_GDPR_STATUSES = {"pending", "in_progress", "completed", "rejected"}
VALID_USER_STATUSES = {"active", "paused", "cancelled", "blocked"}
VALID_ACCOUNT_TYPES = {"customer", "provider", "salon"}


@router.get("/gdpr-requests", response_model=list[GDPRRequestAdminOut])
def list_gdpr_requests(
    status: Optional[str] = None,
    request_type: Optional[str] = None,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
):
    q = db.query(GDPRRequest)
    if status:
        q = q.filter(GDPRRequest.status == status)
    if request_type:
        q = q.filter(GDPRRequest.request_type == request_type)
    rows = q.order_by(GDPRRequest.requested_at.desc()).limit(500).all()

    result = []
    for r in rows:
        user = db.query(User).filter(User.user_id == r.user_id).first()
        result.append(
            GDPRRequestAdminOut(
                request_id=r.request_id,
                user_id=r.user_id,
                user_email=getattr(user, "email", "") or "",
                user_display_name=getattr(user, "display_name", None),
                request_type=r.request_type,
                status=r.status,
                notes=r.notes,
                admin_notes=r.admin_notes,
                requested_at=r.requested_at,
                updated_at=r.updated_at,
                completed_at=r.completed_at,
            )
        )
    return result


@router.patch("/gdpr-requests/{request_id}")
def update_gdpr_request(
    request_id: str,
    body: GDPRStatusUpdateIn,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
    x_admin_actor: str | None = Header(None, alias="X-Admin-Actor"),
):
    if body.status not in VALID_GDPR_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(sorted(VALID_GDPR_STATUSES))}",
        )
    req = db.query(GDPRRequest).filter(GDPRRequest.request_id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="GDPR request not found")

    before = {"status": req.status, "admin_notes": req.admin_notes}
    now = _now_utc_naive()
    req.status = body.status
    req.updated_at = now
    if body.admin_notes is not None:
        req.admin_notes = body.admin_notes
    if body.status == "completed" and not req.completed_at:
        req.completed_at = now

    _log_admin_action(
        db,
        admin_actor=_admin_actor(x_admin_actor),
        action="gdpr.update",
        entity_type="gdpr_request",
        entity_id=req.request_id,
        before=before,
        after={
            "status": req.status,
            "admin_notes": req.admin_notes,
            "completed_at": req.completed_at.isoformat() if req.completed_at else None,
        },
    )
    db.commit()
    return {"ok": True, "request_id": request_id, "status": body.status}


@router.get("/gdpr-requests/stats")
def gdpr_request_stats(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
):
    by_status = (
        db.query(GDPRRequest.status, func.count(GDPRRequest.request_id))
        .group_by(GDPRRequest.status)
        .all()
    )
    by_type = (
        db.query(GDPRRequest.request_type, func.count(GDPRRequest.request_id))
        .group_by(GDPRRequest.request_type)
        .all()
    )
    pending_count = sum(c for s, c in by_status if s in ("pending", "in_progress"))
    return {
        "by_status": {s: c for s, c in by_status},
        "by_type": {t: c for t, c in by_type},
        "pending_attention": pending_count,
    }


class AdminSearchEntity(BaseModel):
    id: str
    label: str
    subtitle: Optional[str] = None
    status: Optional[str] = None


class AdminSearchOut(BaseModel):
    providers: list[AdminSearchEntity]
    users: list[AdminSearchEntity]
    bookings: list[AdminSearchEntity]


@router.get("/search", response_model=AdminSearchOut)
def admin_search(
    q: str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
):
    needle = f"%{q.strip()}%"

    provider_rows = (
        db.query(Provider, User)
        .outerjoin(User, Provider.user_id == User.user_id)
        .filter(
            or_(
                Provider.provider_id.like(needle),
                Provider.name.ilike(needle),
                Provider.slug.ilike(needle),
                Provider.instagram_username.ilike(needle),
                User.email.ilike(needle),
            )
        )
        .order_by(Provider.created_at.desc())
        .limit(limit)
        .all()
    )

    user_rows = (
        db.query(User)
        .filter(
            or_(
                User.user_id.like(needle),
                User.email.ilike(needle),
                User.display_name.ilike(needle),
            )
        )
        .order_by(User.created_at.desc())
        .limit(limit)
        .all()
    )

    booking_rows = (
        db.query(Booking)
        .filter(or_(Booking.booking_id.like(needle), Booking.status.ilike(needle)))
        .order_by(Booking.created_at.desc())
        .limit(limit)
        .all()
    )

    provider_items = [
        AdminSearchEntity(
            id=row.Provider.provider_id,
            label=row.Provider.name,
            subtitle=(row.User.email if row.User else None) or row.Provider.slug,
            status=("verified" if row.Provider.is_verified else "unverified"),
        )
        for row in provider_rows
    ]

    user_items = [
        AdminSearchEntity(
            id=u.user_id,
            label=u.display_name or u.email,
            subtitle=u.email,
            status=u.status,
        )
        for u in user_rows
    ]

    booking_items = [
        AdminSearchEntity(
            id=b.booking_id,
            label=f"Booking {b.booking_number}",
            subtitle=f"provider={b.provider_id} customer={b.customer_id}",
            status=b.status,
        )
        for b in booking_rows
    ]

    return AdminSearchOut(providers=provider_items, users=user_items, bookings=booking_items)


@router.get("/users/{user_id}")
def admin_get_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    customer_ids = [
        row.customer_id
        for row in db.query(Customer.customer_id).filter(Customer.user_id == user.user_id).all()
    ]
    bookings_count = 0
    if customer_ids:
        bookings_count = (
            db.query(func.count(Booking.booking_id))
            .filter(Booking.customer_id.in_(customer_ids))
            .scalar()
            or 0
        )

    linked_provider = db.query(Provider).filter(Provider.user_id == user.user_id).first()
    snapshot = LoyaltyService.get_actor_snapshot(db, actor_type="customer", actor_id=user.user_id)

    return {
        **_user_snapshot(user),
        "customer_records": len(customer_ids),
        "bookings_count": int(bookings_count),
        "linked_provider_id": linked_provider.provider_id if linked_provider else None,
        "loyalty": {
            "score": snapshot.score,
            "tier": snapshot.tier,
            "level_badge": snapshot.level_badge,
        },
    }


class AdminUserPatchIn(BaseModel):
    status: Optional[str] = None
    display_name: Optional[str] = None
    is_profile_public: Optional[bool] = None
    is_customer: Optional[bool] = None
    is_provider: Optional[bool] = None
    reason: Optional[str] = None


@router.patch("/users/{user_id}")
def admin_patch_user(
    user_id: str,
    payload: AdminUserPatchIn,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
    x_admin_actor: str | None = Header(None, alias="X-Admin-Actor"),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    before = _user_snapshot(user)
    if payload.status is not None:
        status = payload.status.strip().lower()
        if status not in VALID_USER_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid user status")
        user.status = status
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip() or None
    if payload.is_profile_public is not None:
        user.is_profile_public = bool(payload.is_profile_public)
    if payload.is_customer is not None:
        user.is_customer = bool(payload.is_customer)
    if payload.is_provider is not None:
        user.is_provider = bool(payload.is_provider)

    after = _user_snapshot(user)
    _log_admin_action(
        db,
        admin_actor=_admin_actor(x_admin_actor),
        action="user.update",
        entity_type="user",
        entity_id=user.user_id,
        reason=payload.reason,
        before=before,
        after=after,
    )
    db.commit()
    return {"ok": True, "user": after}


@router.get("/providers/{provider_id}")
def admin_get_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
):
    provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    bookings_count = (
        db.query(func.count(Booking.booking_id))
        .filter(Booking.provider_id == provider.provider_id)
        .scalar()
        or 0
    )
    snapshot = LoyaltyService.get_actor_snapshot(db, actor_type="provider", actor_id=provider.provider_id)

    user_email = None
    user_status = None
    if provider.user_id:
        user = db.query(User).filter(User.user_id == provider.user_id).first()
        if user:
            user_email = user.email
            user_status = user.status

    return {
        **_provider_snapshot(provider),
        "bookings_count": int(bookings_count),
        "user_email": user_email,
        "user_status": user_status,
        "loyalty": {
            "score": snapshot.score,
            "tier": snapshot.tier,
            "level_badge": snapshot.level_badge,
        },
    }


class AdminProviderPatchIn(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    location_salon: Optional[str] = None
    is_verified: Optional[bool] = None
    linked_user_status: Optional[str] = None
    reason: Optional[str] = None


@router.patch("/providers/{provider_id}")
def admin_patch_provider(
    provider_id: str,
    payload: AdminProviderPatchIn,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
    x_admin_actor: str | None = Header(None, alias="X-Admin-Actor"),
):
    provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    before = _provider_snapshot(provider)
    if payload.name is not None:
        provider.name = payload.name.strip() or provider.name
    if payload.phone is not None:
        provider.phone = payload.phone.strip() or None
    if payload.city is not None:
        provider.city = payload.city.strip() or None
    if payload.location_salon is not None:
        provider.location_salon = payload.location_salon.strip() or None
    if payload.is_verified is not None:
        provider.is_verified = bool(payload.is_verified)
        provider.verified_at = _now_utc_naive() if provider.is_verified else None
    if payload.linked_user_status is not None and provider.user_id:
        status = payload.linked_user_status.strip().lower()
        if status not in VALID_USER_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid linked user status")
        user = db.query(User).filter(User.user_id == provider.user_id).first()
        if user:
            user.status = status

    after = _provider_snapshot(provider)
    _log_admin_action(
        db,
        admin_actor=_admin_actor(x_admin_actor),
        action="provider.update",
        entity_type="provider",
        entity_id=provider.provider_id,
        reason=payload.reason,
        before=before,
        after=after,
    )
    db.commit()
    return {"ok": True, "provider": after}


def _serialize_bookings(db: Session, bookings: list[Booking]) -> list[dict[str, Any]]:
    if not bookings:
        return []

    provider_ids = {b.provider_id for b in bookings}
    customer_ids = {b.customer_id for b in bookings}

    providers = (
        db.query(Provider.provider_id, Provider.name)
        .filter(Provider.provider_id.in_(list(provider_ids)))
        .all()
    )
    provider_map = {row.provider_id: row.name for row in providers}

    customers = (
        db.query(Customer.customer_id, Customer.customer_email, Customer.display_name, Customer.user_id)
        .filter(Customer.customer_id.in_(list(customer_ids)))
        .all()
    )
    customer_map = {row.customer_id: row for row in customers}

    user_ids = {row.user_id for row in customers if row.user_id}
    users = (
        db.query(User.user_id, User.email)
        .filter(User.user_id.in_(list(user_ids)))
        .all()
        if user_ids
        else []
    )
    user_map = {row.user_id: row.email for row in users}

    out: list[dict[str, Any]] = []
    for booking in bookings:
        c = customer_map.get(booking.customer_id)
        email = ""
        if c:
            email = c.customer_email or (user_map.get(c.user_id) if c.user_id else "") or ""

        out.append(
            {
                "booking_id": booking.booking_id,
                "status": booking.status,
                "provider_id": booking.provider_id,
                "provider_name": provider_map.get(booking.provider_id, "Unknown"),
                "customer_id": booking.customer_id,
                "customer_name": (c.display_name if c else None) or "Customer",
                "customer_email": email,
                "scheduled_start": booking.scheduled_start,
                "scheduled_end": booking.scheduled_end,
                "total_amount_inc_vat": booking.total_amount_inc_vat,
                "created_at": booking.created_at,
            }
        )
    return out


@router.get("/bookings")
def admin_list_bookings(
    provider_id: str | None = None,
    user_id: str | None = None,
    status: str | None = None,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
):
    q = db.query(Booking)

    if provider_id:
        q = q.filter(Booking.provider_id == provider_id)
    if status:
        q = q.filter(Booking.status == status)
    if from_at:
        q = q.filter(Booking.scheduled_start >= from_at)
    if to_at:
        q = q.filter(Booking.scheduled_start <= to_at)
    if user_id:
        customer_ids = [
            row.customer_id
            for row in db.query(Customer.customer_id).filter(Customer.user_id == user_id).all()
        ]
        if not customer_ids:
            return []
        q = q.filter(Booking.customer_id.in_(customer_ids))

    rows = q.order_by(Booking.scheduled_start.desc()).limit(limit).all()
    return _serialize_bookings(db, rows)


class AdminBookingPatchIn(BaseModel):
    status: Optional[str] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    customer_notes: Optional[str] = None
    provider_notes: Optional[str] = None
    reason: Optional[str] = None


@router.patch("/bookings/{booking_id}")
def admin_patch_booking(
    booking_id: str,
    payload: AdminBookingPatchIn,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
    x_admin_actor: str | None = Header(None, alias="X-Admin-Actor"),
):
    booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    before = _booking_snapshot(booking)

    changes: dict[str, Any] = {}
    if payload.status is not None:
        changes["status"] = payload.status
    if payload.scheduled_start is not None:
        changes["scheduled_start"] = payload.scheduled_start
    if payload.scheduled_end is not None:
        changes["scheduled_end"] = payload.scheduled_end
    if payload.customer_notes is not None:
        changes["customer_notes"] = payload.customer_notes
    if payload.provider_notes is not None:
        changes["provider_notes"] = payload.provider_notes

    if not changes:
        raise HTTPException(status_code=400, detail="No changes provided")

    try:
        booking = BookingService.update_booking(db, booking_id, **changes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _log_admin_action(
        db,
        admin_actor=_admin_actor(x_admin_actor),
        action="booking.update",
        entity_type="booking",
        entity_id=booking_id,
        reason=payload.reason,
        before=before,
        after=_booking_snapshot(booking),
    )
    db.commit()

    return {"ok": True, "booking": _booking_snapshot(booking)}


class AdminManualAccountIn(BaseModel):
    account_type: str = Field(description="customer | provider | salon")
    email: str
    display_name: Optional[str] = None
    provider_name: Optional[str] = None
    reason: Optional[str] = None


@router.post("/accounts/manual")
def admin_create_manual_account(
    payload: AdminManualAccountIn,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
    super_admin_email: str = Depends(require_super_admin),
    x_admin_actor: str | None = Header(None, alias="X-Admin-Actor"),
):
    account_type = payload.account_type.strip().lower()
    if account_type not in VALID_ACCOUNT_TYPES:
        raise HTTPException(status_code=400, detail="Invalid account_type")

    email = payload.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email")

    user = db.query(User).filter(User.email == email).first()
    created_user = False
    if not user:
        user = User(
            email=email,
            display_name=payload.display_name,
            is_customer=(account_type == "customer"),
            is_provider=(account_type in {"provider", "salon"}),
            status="active",
        )
        db.add(user)
        db.flush()
        created_user = True
    else:
        if payload.display_name and not user.display_name:
            user.display_name = payload.display_name
        if account_type == "customer":
            user.is_customer = True
        if account_type in {"provider", "salon"}:
            user.is_provider = True

    provider = None
    created_provider = False
    if account_type in {"provider", "salon"}:
        provider = db.query(Provider).filter(Provider.user_id == user.user_id).first()
        if not provider:
            provider_name = (
                payload.provider_name
                or payload.display_name
                or email.split("@")[0].replace(".", " ").title()
            )
            provider = Provider(
                user_id=user.user_id,
                name=provider_name,
                business_type="owner" if account_type == "salon" else "freelancer",
            )
            db.add(provider)
            db.flush()
            created_provider = True

    _log_admin_action(
        db,
        admin_actor=_admin_actor(x_admin_actor),
        action="account.create_manual",
        entity_type="user",
        entity_id=user.user_id,
        reason=payload.reason,
        before=None,
        after={
            "user": _user_snapshot(user),
            "provider_id": provider.provider_id if provider else None,
            "account_type": account_type,
            "created_user": created_user,
            "created_provider": created_provider,
        },
    )
    db.commit()

    return {
        "ok": True,
        "account_type": account_type,
        "user_id": user.user_id,
        "provider_id": provider.provider_id if provider else None,
        "created_user": created_user,
        "created_provider": created_provider,
    }


class AdminManualBookingIn(BaseModel):
    provider_id: str
    customer_email: str
    customer_name: Optional[str] = None
    scheduled_start: datetime
    scheduled_end: datetime
    service_name: str
    unit_price_ex_vat: float = 0.0
    quantity: int = 1
    status: str = "confirmed"
    customer_notes: Optional[str] = None
    provider_notes: Optional[str] = None
    referral_source: Optional[str] = None
    reason: Optional[str] = None


@router.post("/bookings/manual")
def admin_create_booking_manual(
    payload: AdminManualBookingIn,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
    super_admin_email: str = Depends(require_super_admin),
    x_admin_actor: str | None = Header(None, alias="X-Admin-Actor"),
):
    provider = db.query(Provider).filter(Provider.provider_id == payload.provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    email = payload.customer_email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid customer email")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            display_name=payload.customer_name,
            is_customer=True,
            is_provider=False,
            status="active",
        )
        db.add(user)
        db.flush()

    customer = CustomerService.find_by_email_and_provider(db, provider.provider_id, email)
    if not customer:
        customer = CustomerService.create_customer(
            db=db,
            provider_id=provider.provider_id,
            customer_email=email,
            user_id=user.user_id,
            display_name=payload.customer_name,
            source_channel="admin_manual",
        )

    try:
        booking = BookingService.create_booking(
            db=db,
            provider_id=provider.provider_id,
            customer_id=customer.customer_id,
            scheduled_start=payload.scheduled_start,
            scheduled_end=payload.scheduled_end,
            line_items=[
                {
                    "service_type": payload.service_name,
                    "quantity": payload.quantity,
                    "unit_price_ex_vat": payload.unit_price_ex_vat,
                }
            ],
            customer_notes=payload.customer_notes,
            provider_notes=payload.provider_notes,
            referral_source=payload.referral_source,
            status=payload.status,
        )
    except SlotUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _log_admin_action(
        db,
        admin_actor=_admin_actor(x_admin_actor),
        action="booking.create_manual",
        entity_type="booking",
        entity_id=booking.booking_id,
        reason=payload.reason,
        before=None,
        after=_booking_snapshot(booking),
        metadata={"provider_id": provider.provider_id, "customer_id": customer.customer_id},
    )
    db.commit()

    return {
        "ok": True,
        "booking_id": booking.booking_id,
        "provider_id": booking.provider_id,
        "customer_id": booking.customer_id,
    }

@router.get("/level/{actor_type}/{actor_id}")
def admin_level_inspector(
    actor_type: str,
    actor_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
):
    if actor_type not in {"customer", "provider"}:
        raise HTTPException(status_code=400, detail="actor_type must be customer or provider")

    snapshot = LoyaltyService.get_actor_snapshot(db, actor_type=actor_type, actor_id=actor_id)
    events = (
        db.query(LoyaltyEvent)
        .filter(LoyaltyEvent.actor_type == actor_type, LoyaltyEvent.actor_id == actor_id)
        .order_by(LoyaltyEvent.occurred_at.desc())
        .limit(50)
        .all()
    )

    return {
        "snapshot": {
            "actor_type": snapshot.actor_type,
            "actor_id": snapshot.actor_id,
            "score": snapshot.score,
            "tier": snapshot.tier,
            "level_badge": snapshot.level_badge,
            "completed_bookings": snapshot.completed_bookings,
            "completed_referrals": snapshot.completed_referrals,
        },
        "events": [
            {
                "event_id": e.event_id,
                "event_type": e.event_type,
                "points": e.points,
                "source": e.source,
                "occurred_at": e.occurred_at,
                "unique_event_key": e.unique_event_key,
            }
            for e in events
        ],
    }


@router.get("/audit-logs")
def admin_audit_logs(
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    admin_actor: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
):
    q = db.query(AdminAuditLog)
    if entity_type:
        q = q.filter(AdminAuditLog.entity_type == entity_type)
    if entity_id:
        q = q.filter(AdminAuditLog.entity_id == entity_id)
    if action:
        q = q.filter(AdminAuditLog.action == action)
    if admin_actor:
        q = q.filter(AdminAuditLog.admin_actor.ilike(f"%{admin_actor}%"))

    rows = q.order_by(AdminAuditLog.created_at.desc()).limit(limit).all()
    return [
        {
            "log_id": row.log_id,
            "admin_actor": row.admin_actor,
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "reason": row.reason,
            "before": json.loads(row.before_json or "{}"),
            "after": json.loads(row.after_json or "{}"),
            "metadata": json.loads(row.metadata_json or "{}"),
            "created_at": row.created_at,
        }
        for row in rows
    ]





