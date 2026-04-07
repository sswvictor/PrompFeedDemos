"""Provider Finance & Insights API.

Endpoints:
    GET  /provider/insights                            - period-based booking metrics
    GET  /provider/finance/recent                      - recent bookings with payment status
    POST /provider/finance/bookings/{booking_id}/mark-paid
    GET  /provider/finance/summary?start_date=&end_date= - date-range tax summary
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_provider
from app.db.session import get_db
from app.models.booking import Booking
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.services.invoice_service import InvoiceService
from app.services.reporting_service import _period_range

router = APIRouter(prefix="/provider", tags=["finance"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_date_utc(s: str) -> datetime:
    """Parse YYYY-MM-DD and return UTC-aware datetime at midnight."""
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _top_services(bookings: list[Booking], n: int = 5) -> list[dict]:
    counter: Counter = Counter()
    for b in bookings:
        for item in (b.line_items or []):
            if item.service_type:
                counter[item.service_type] += 1
    return [{"name": name, "count": count} for name, count in counter.most_common(n)]


# ── Schemas ───────────────────────────────────────────────────────────────────

class InsightsOut(BaseModel):
    period: str
    total_bookings: int
    completed: int
    cancelled: int
    revenue_this_period: float
    revenue_prev_period: float
    top_services: list[dict]


class RecentBookingOut(BaseModel):
    booking_id: str
    booking_number: int
    status: str
    scheduled_start: str
    service_name: str | None
    customer_name: str | None
    amount_inc_vat: float
    payment_status: str   # "paid" | "draft" | "sent" | "no_invoice"
    invoice_id: str | None


class FinanceSummaryOut(BaseModel):
    start_date: str
    end_date: str
    total_bookings: int
    completed_bookings: int
    revenue_ex_vat: float
    vat_collected: float
    revenue_inc_vat: float
    top_services: list[dict]
    unpaid_count: int
    unpaid_amount: float


# ── Insights (period-based) ───────────────────────────────────────────────────

@router.get("/insights", response_model=InsightsOut)
def get_provider_insights(
    period: str = Query("this_month"),
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
) -> InsightsOut:
    try:
        start, end = _period_range(period)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown period: {period}")

    bookings = (
        db.query(Booking)
        .filter(
            Booking.provider_id == provider_id,
            Booking.scheduled_start >= start,
            Booking.scheduled_start < end,
        )
        .all()
    )

    completed = [b for b in bookings if b.status == "completed"]
    cancelled = [b for b in bookings if b.status == "cancelled"]
    revenue = sum(b.total_amount_inc_vat for b in completed)

    # Previous period — same length window
    period_len = end - start
    prev_start = start - period_len
    prev_bookings = (
        db.query(Booking)
        .filter(
            Booking.provider_id == provider_id,
            Booking.scheduled_start >= prev_start,
            Booking.scheduled_start < start,
            Booking.status == "completed",
        )
        .all()
    )
    revenue_prev = sum(b.total_amount_inc_vat for b in prev_bookings)

    return InsightsOut(
        period=period,
        total_bookings=len(bookings),
        completed=len(completed),
        cancelled=len(cancelled),
        revenue_this_period=round(revenue, 2),
        revenue_prev_period=round(revenue_prev, 2),
        top_services=_top_services(bookings),
    )


# ── Recent bookings with payment status ──────────────────────────────────────

@router.get("/finance/recent", response_model=list[RecentBookingOut])
def get_finance_recent(
    limit: int = Query(20, ge=1, le=100),
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
) -> list[RecentBookingOut]:
    bookings = (
        db.query(Booking)
        .filter(Booking.provider_id == provider_id)
        .order_by(Booking.scheduled_start.desc())
        .limit(limit)
        .all()
    )

    result = []
    for b in bookings:
        service_name = b.line_items[0].service_type if b.line_items else None
        customer = db.query(Customer).filter(Customer.customer_id == b.customer_id).first()
        customer_name = getattr(customer, "display_name", None)

        invoice = b.invoice
        if invoice:
            payment_status = invoice.status
            invoice_id = invoice.invoice_id
        else:
            payment_status = "no_invoice"
            invoice_id = None

        result.append(
            RecentBookingOut(
                booking_id=b.booking_id,
                booking_number=b.booking_number,
                status=b.status,
                scheduled_start=b.scheduled_start.isoformat(),
                service_name=service_name,
                customer_name=customer_name,
                amount_inc_vat=round(b.total_amount_inc_vat, 2),
                payment_status=payment_status,
                invoice_id=invoice_id,
            )
        )

    return result


# ── Mark booking as paid ──────────────────────────────────────────────────────

@router.post("/finance/bookings/{booking_id}/mark-paid")
def mark_booking_paid(
    booking_id: str,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
) -> dict:
    booking = (
        db.query(Booking)
        .filter(
            Booking.booking_id == booking_id,
            Booking.provider_id == provider_id,
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    invoice = db.query(Invoice).filter(Invoice.booking_id == booking_id).first()
    if not invoice:
        try:
            invoice = InvoiceService.create_invoice_from_booking(db, booking_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    invoice = InvoiceService.update_status(db, invoice.invoice_id, "paid")
    return {"ok": True, "invoice_id": invoice.invoice_id, "status": invoice.status}


# ── Finance summary (date-range, for tax export) ──────────────────────────────

@router.get("/finance/summary", response_model=FinanceSummaryOut)
def get_finance_summary(
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
) -> FinanceSummaryOut:
    try:
        start = _parse_date_utc(start_date)
        end = _parse_date_utc(end_date) + timedelta(days=1)  # inclusive
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid date. Use YYYY-MM-DD format."
        )

    if start >= end:
        raise HTTPException(
            status_code=400, detail="start_date must be before end_date"
        )

    bookings = (
        db.query(Booking)
        .filter(
            Booking.provider_id == provider_id,
            Booking.scheduled_start >= start,
            Booking.scheduled_start < end,
        )
        .all()
    )

    completed = [b for b in bookings if b.status == "completed"]
    rev_ex = sum(b.total_amount_ex_vat for b in completed)
    vat = sum(b.total_vat_amount for b in completed)
    rev_inc = sum(b.total_amount_inc_vat for b in completed)

    # Unpaid = completed bookings without a paid invoice
    unpaid = [
        b for b in completed
        if not b.invoice or b.invoice.status != "paid"
    ]

    return FinanceSummaryOut(
        start_date=start_date,
        end_date=end_date,
        total_bookings=len(bookings),
        completed_bookings=len(completed),
        revenue_ex_vat=round(rev_ex, 2),
        vat_collected=round(vat, 2),
        revenue_inc_vat=round(rev_inc, 2),
        top_services=_top_services(bookings),
        unpaid_count=len(unpaid),
        unpaid_amount=round(sum(b.total_amount_inc_vat for b in unpaid), 2),
    )
