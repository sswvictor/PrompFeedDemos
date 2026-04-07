"""
Calendar API for Fixmeapp Booking Logic.

Endpoints:
  GET  /calendar/bookings        → bookings for a date range with customer names
  POST /calendar/manual-booking  → create a manual / walk-in booking

COPY THIS ROUTER REGISTRATION TO main.py:
    from app.api.calendar import router as calendar_router
    app.include_router(calendar_router, prefix="/api/v1")
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.api.auth import get_current_provider
from app.db.session import get_db
from app.models.booking import Booking
from app.models.customer import Customer
from app.services.booking_service import BookingService, SlotUnavailableError

router = APIRouter(prefix="/calendar", tags=["calendar"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_customer_name(customer: Customer | None) -> str:
    """Resolve the best display name for a customer."""
    if not customer:
        return "Guest"
    return (
        customer.display_name
        or customer.instagram_username_snapshot
        or customer.customer_email
        or f"Customer #{customer.customer_number}"
    )


# ── Schemas ───────────────────────────────────────────────────────────────────

class CalendarBookingOut(BaseModel):
    booking_id: str
    booking_number: int
    status: str                    # pending | confirmed | completed | cancelled
    scheduled_start: str           # ISO 8601 datetime
    scheduled_end: str             # ISO 8601 datetime
    customer_name: str
    service_name: str              # First line item (+ N more if multiple)
    customer_notes: str | None = None
    provider_notes: str | None = None
    is_walkin: bool = False
    total_amount_inc_vat: float


class ManualBookingIn(BaseModel):
    customer_name: str
    service_name: str
    scheduled_start: datetime      # Full ISO datetime with timezone
    duration_minutes: int          # e.g. 60
    price_inc_vat: float = 0.0    # Total price the customer pays (inc VAT)
    provider_notes: str | None = None
    customer_notes: str | None = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/bookings", response_model=list[CalendarBookingOut])
def get_calendar_bookings(
    from_date: datetime = Query(..., description="Range start (inclusive), ISO datetime"),
    to_date: datetime = Query(..., description="Range end (exclusive), ISO datetime"),
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """
    Returns all non-cancelled bookings for the authenticated provider
    within [from_date, to_date), enriched with customer display names.

    Used by the mobile CalendarScreen to populate the time grid.

    Example:
        GET /api/v1/calendar/bookings?from_date=2024-01-15T00:00:00Z&to_date=2024-01-22T00:00:00Z
    """
    bookings = (
        db.query(Booking)
        .options(joinedload(Booking.customer), joinedload(Booking.line_items))
        .filter(
            Booking.provider_id == provider_id,
            Booking.scheduled_start >= from_date,
            Booking.scheduled_start < to_date,
            Booking.status != "cancelled",
        )
        .order_by(Booking.scheduled_start.asc())
        .all()
    )

    result: list[CalendarBookingOut] = []
    for b in bookings:
        if b.line_items:
            service_name = b.line_items[0].service_type
            if len(b.line_items) > 1:
                service_name += f" +{len(b.line_items) - 1}"
        else:
            service_name = "Appointment"

        result.append(CalendarBookingOut(
            booking_id=b.booking_id,
            booking_number=b.booking_number,
            status=b.status,
            scheduled_start=b.scheduled_start.isoformat(),
            scheduled_end=b.scheduled_end.isoformat(),
            customer_name=_resolve_customer_name(b.customer),
            service_name=service_name,
            customer_notes=b.customer_notes,
            provider_notes=b.provider_notes,
            is_walkin=bool(b.is_walkin),
            total_amount_inc_vat=b.total_amount_inc_vat,
        ))

    return result


@router.post("/manual-booking", response_model=CalendarBookingOut, status_code=201)
def create_manual_booking(
    payload: ManualBookingIn,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """
    Create a manual booking (walk-in, phone call, in-person scheduling).
    No customer account is required — just a name.

    A temporary Customer record is auto-created with source_channel='walkin'.
    The booking appears immediately in the calendar.
    """
    from app.models.provider import Provider

    provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    scheduled_end = payload.scheduled_start + timedelta(minutes=payload.duration_minutes)

    # Back-calculate ex-VAT price from inc-VAT using provider default rate
    vat_pct = provider.vat_percent or 0.0
    if vat_pct > 0 and payload.price_inc_vat > 0:
        price_ex = round(payload.price_inc_vat / (1 + vat_pct / 100), 2)
    else:
        price_ex = payload.price_inc_vat

    try:
        booking = BookingService.create_booking(
            db=db,
            provider_id=provider_id,
            customer_id=None,                          # walk-in: auto-create customer
            scheduled_start=payload.scheduled_start,
            scheduled_end=scheduled_end,
            line_items=[{
                "service_type": payload.service_name,
                "quantity": 1,
                "unit_price_ex_vat": price_ex,
            }],
            customer_notes=payload.customer_notes,
            provider_notes=payload.provider_notes,
            is_walkin=True,
            walkin_customer_name=payload.customer_name,
        )
    except SlotUnavailableError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Reload to get computed totals + relationships
    db.refresh(booking)

    service_name = (
        booking.line_items[0].service_type if booking.line_items else payload.service_name
    )

    return CalendarBookingOut(
        booking_id=booking.booking_id,
        booking_number=booking.booking_number,
        status=booking.status,
        scheduled_start=booking.scheduled_start.isoformat(),
        scheduled_end=booking.scheduled_end.isoformat(),
        customer_name=payload.customer_name,
        service_name=service_name,
        customer_notes=booking.customer_notes,
        provider_notes=booking.provider_notes,
        is_walkin=True,
        total_amount_inc_vat=booking.total_amount_inc_vat,
    )
