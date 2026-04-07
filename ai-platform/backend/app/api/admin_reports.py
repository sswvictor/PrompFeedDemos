"""Admin handling for incident reports from provider and customer booking cards."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.admin_audit_log import AdminAuditLog
from app.models.booking import Booking
from app.models.customer import Customer
from app.models.customer_reliability_report import CustomerReliabilityReport
from app.models.provider import Provider
from app.models.provider_incident_report import ProviderIncidentReport
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin-reports"])


def verify_admin_token(x_admin_token: str = Header(..., alias="X-Admin-Token")) -> None:
    expected = os.environ.get("ADMIN_SECRET_TOKEN", "")
    if not expected or x_admin_token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing admin token")


def _now_utc_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _admin_actor(actor_header: str | None) -> str:
    return (actor_header or "ops@fixmeapp.ai").strip().lower() or "ops@fixmeapp.ai"


def _safe_json(data: Any) -> str:
    return json.dumps(data or {}, default=str, ensure_ascii=False)


def _log_admin_action(
    db: Session,
    *,
    admin_actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    reason: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
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
            metadata_json=_safe_json({"source": "admin-reports"}),
        )
    )


class AdminReportPatchIn(BaseModel):
    status: str | None = None
    action_taken: str | None = None
    admin_notes: str | None = None
    reason: str | None = None


VALID_STATUSES = {"open", "reviewing", "resolved", "dismissed"}
VALID_ACTIONS = {"none", "warned", "blocked", "dismissed"}


def _provider_name_map(db: Session, provider_ids: set[str]) -> dict[str, str]:
    if not provider_ids:
        return {}
    rows = (
        db.query(Provider.provider_id, Provider.name)
        .filter(Provider.provider_id.in_(list(provider_ids)))
        .all()
    )
    return {row.provider_id: row.name for row in rows}


def _customer_map(db: Session, customer_ids: set[str]) -> dict[str, Customer]:
    if not customer_ids:
        return {}
    rows = db.query(Customer).filter(Customer.customer_id.in_(list(customer_ids))).all()
    return {row.customer_id: row for row in rows}


def _booking_map(db: Session, booking_ids: set[str]) -> dict[str, Booking]:
    if not booking_ids:
        return {}
    rows = db.query(Booking).filter(Booking.booking_id.in_(list(booking_ids))).all()
    return {row.booking_id: row for row in rows}


def _serialize_provider_to_customer(
    row: CustomerReliabilityReport,
    provider_names: dict[str, str],
    customers: dict[str, Customer],
    bookings: dict[str, Booking],
) -> dict[str, Any]:
    customer = customers.get(row.customer_id)
    booking = bookings.get(row.booking_id) if row.booking_id else None
    return {
        "report_scope": "provider_to_customer",
        "report_id": row.report_id,
        "booking_id": row.booking_id,
        "provider_id": row.provider_id,
        "provider_name": provider_names.get(row.provider_id, "Unknown"),
        "customer_id": row.customer_id,
        "customer_name": (customer.display_name if customer else None) or "Customer",
        "customer_email": customer.customer_email if customer else None,
        "report_type": row.category,
        "severity": int(row.severity or 1),
        "details": row.details,
        "status": row.admin_status,
        "action_taken": row.admin_action_taken,
        "admin_notes": row.admin_notes,
        "created_at": row.created_at,
        "resolved_at": row.admin_resolved_at,
        "booking_start": booking.scheduled_start if booking else None,
    }


def _serialize_customer_to_provider(
    row: ProviderIncidentReport,
    provider_names: dict[str, str],
    customers: dict[str, Customer],
    bookings: dict[str, Booking],
) -> dict[str, Any]:
    customer = customers.get(row.customer_id)
    booking = bookings.get(row.booking_id)
    return {
        "report_scope": "customer_to_provider",
        "report_id": row.report_id,
        "booking_id": row.booking_id,
        "provider_id": row.provider_id,
        "provider_name": provider_names.get(row.provider_id, "Unknown"),
        "customer_id": row.customer_id,
        "customer_name": (customer.display_name if customer else None) or "Customer",
        "customer_email": customer.customer_email if customer else None,
        "report_type": row.report_type,
        "severity": int(row.severity or 1),
        "details": row.details,
        "status": row.status,
        "action_taken": row.action_taken,
        "admin_notes": row.admin_notes,
        "created_at": row.created_at,
        "resolved_at": row.resolved_at,
        "booking_start": booking.scheduled_start if booking else None,
    }


@router.get("/reports")
def admin_reports(
    scope: str = Query("all"),
    status: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
):
    scope = (scope or "all").strip().lower()
    if scope not in {"all", "provider_to_customer", "customer_to_provider"}:
        raise HTTPException(status_code=400, detail="Invalid scope")

    if status is not None:
        status = status.strip().lower()
        if status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")

    provider_rows: list[CustomerReliabilityReport] = []
    customer_rows: list[ProviderIncidentReport] = []

    if scope in {"all", "provider_to_customer"}:
        q = db.query(CustomerReliabilityReport)
        if status:
            q = q.filter(CustomerReliabilityReport.admin_status == status)
        provider_rows = q.order_by(CustomerReliabilityReport.created_at.desc()).limit(limit).all()

    if scope in {"all", "customer_to_provider"}:
        q = db.query(ProviderIncidentReport)
        if status:
            q = q.filter(ProviderIncidentReport.status == status)
        customer_rows = q.order_by(ProviderIncidentReport.created_at.desc()).limit(limit).all()

    provider_ids = {row.provider_id for row in provider_rows} | {row.provider_id for row in customer_rows}
    customer_ids = {row.customer_id for row in provider_rows} | {row.customer_id for row in customer_rows}
    booking_ids = {row.booking_id for row in customer_rows if row.booking_id} | {
        row.booking_id for row in provider_rows if row.booking_id
    }

    provider_names = _provider_name_map(db, provider_ids)
    customers = _customer_map(db, customer_ids)
    bookings = _booking_map(db, booking_ids)

    rows: list[dict[str, Any]] = []
    rows.extend(_serialize_provider_to_customer(row, provider_names, customers, bookings) for row in provider_rows)
    rows.extend(_serialize_customer_to_provider(row, provider_names, customers, bookings) for row in customer_rows)
    rows.sort(key=lambda r: r.get("created_at") or datetime.min, reverse=True)
    return rows[:limit]


@router.get("/reports/stats")
def admin_report_stats(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
):
    provider_open = (
        db.query(func.count(CustomerReliabilityReport.report_id))
        .filter(CustomerReliabilityReport.admin_status.in_(["open", "reviewing"]))
        .scalar()
        or 0
    )
    customer_open = (
        db.query(func.count(ProviderIncidentReport.report_id))
        .filter(ProviderIncidentReport.status.in_(["open", "reviewing"]))
        .scalar()
        or 0
    )
    return {
        "open_provider_to_customer": int(provider_open),
        "open_customer_to_provider": int(customer_open),
        "open_total": int(provider_open + customer_open),
    }


@router.patch("/reports/{report_scope}/{report_id}")
def admin_update_report(
    report_scope: str,
    report_id: str,
    payload: AdminReportPatchIn,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_token),
    x_admin_actor: str | None = Header(None, alias="X-Admin-Actor"),
):
    scope = (report_scope or "").strip().lower()
    if scope not in {"provider_to_customer", "customer_to_provider"}:
        raise HTTPException(status_code=400, detail="Invalid report scope")

    action_taken = (payload.action_taken or "").strip().lower() if payload.action_taken is not None else None
    if action_taken is not None and action_taken not in VALID_ACTIONS:
        raise HTTPException(status_code=400, detail="Invalid action_taken")

    requested_status = (payload.status or "").strip().lower() if payload.status is not None else None
    if requested_status is not None and requested_status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    admin_actor = _admin_actor(x_admin_actor)

    if scope == "provider_to_customer":
        report = db.query(CustomerReliabilityReport).filter(CustomerReliabilityReport.report_id == report_id).first()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        before = {
            "status": report.admin_status,
            "action_taken": report.admin_action_taken,
            "admin_notes": report.admin_notes,
        }

        if action_taken is not None:
            report.admin_action_taken = action_taken
        if payload.admin_notes is not None:
            report.admin_notes = payload.admin_notes

        if requested_status is not None:
            report.admin_status = requested_status

        if action_taken == "dismissed":
            report.admin_status = "dismissed"
        elif action_taken in {"warned", "blocked"} and report.admin_status in {"open", "reviewing"}:
            report.admin_status = "resolved"

        if action_taken == "blocked":
            customer = db.query(Customer).filter(Customer.customer_id == report.customer_id).first()
            if customer and customer.user_id:
                user = db.query(User).filter(User.user_id == customer.user_id).first()
                if user:
                    user.status = "blocked"

        if report.admin_status in {"resolved", "dismissed"}:
            report.admin_resolved_at = _now_utc_naive()
            report.admin_resolved_by = admin_actor
        else:
            report.admin_resolved_at = None
            report.admin_resolved_by = None

        _log_admin_action(
            db,
            admin_actor=admin_actor,
            action="report.update.provider_to_customer",
            entity_type="customer_reliability_report",
            entity_id=report.report_id,
            reason=payload.reason,
            before=before,
            after={
                "status": report.admin_status,
                "action_taken": report.admin_action_taken,
                "admin_notes": report.admin_notes,
            },
        )

        db.commit()
        return {
            "ok": True,
            "report_scope": scope,
            "report_id": report.report_id,
            "status": report.admin_status,
            "action_taken": report.admin_action_taken,
            "admin_notes": report.admin_notes,
        }

    report = db.query(ProviderIncidentReport).filter(ProviderIncidentReport.report_id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    before = {
        "status": report.status,
        "action_taken": report.action_taken,
        "admin_notes": report.admin_notes,
    }

    if action_taken is not None:
        report.action_taken = action_taken
    if payload.admin_notes is not None:
        report.admin_notes = payload.admin_notes
    if requested_status is not None:
        report.status = requested_status

    if action_taken == "dismissed":
        report.status = "dismissed"
    elif action_taken in {"warned", "blocked"} and report.status in {"open", "reviewing"}:
        report.status = "resolved"

    if action_taken == "blocked":
        provider = db.query(Provider).filter(Provider.provider_id == report.provider_id).first()
        if provider and provider.user_id:
            user = db.query(User).filter(User.user_id == provider.user_id).first()
            if user:
                user.status = "blocked"

    if report.status in {"resolved", "dismissed"}:
        report.resolved_at = _now_utc_naive()
        report.resolved_by = admin_actor
    else:
        report.resolved_at = None
        report.resolved_by = None

    _log_admin_action(
        db,
        admin_actor=admin_actor,
        action="report.update.customer_to_provider",
        entity_type="provider_incident_report",
        entity_id=report.report_id,
        reason=payload.reason,
        before=before,
        after={
            "status": report.status,
            "action_taken": report.action_taken,
            "admin_notes": report.admin_notes,
        },
    )

    db.commit()
    return {
        "ok": True,
        "report_scope": scope,
        "report_id": report.report_id,
        "status": report.status,
        "action_taken": report.action_taken,
        "admin_notes": report.admin_notes,
    }
