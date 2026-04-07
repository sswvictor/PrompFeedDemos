from datetime import datetime, timezone
import re

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.api.auth import get_current_provider
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.config import settings
from app.api.schemas import (
    BookingCreateIn, BookingUpdateIn, BookingOut,
    InvoiceOut,
    CustomerCreateIn, CustomerOut,
    InstagramResolveIn, InstagramIdentityOut,
    ServiceCreateIn, ServiceOut,
    ProviderOut,
    WorkingHoursIn, WorkingHoursOut,
    OverrideIn, OverrideOut,
    SlotOut,
    ConversationCreateIn, ConversationOut,
    MessageIn, MessageOut,
    SlotHoldIn, SlotHoldOut,
)
from app.services.booking_service import BookingService, SlotUnavailableError
from app.services.invoice_service import InvoiceService
from app.services.customer_service import CustomerService
from app.services.customer_reliability_service import CustomerReliabilityService
from app.services.instagram_service import InstagramMappingService
from app.services.reporting_service import ReportingService
from app.services.provider_service import ProviderService
from app.services.availability_service import AvailabilityService
from app.services.conversation_service import ConversationService
from app.services.webhook_service import WebhookService
from app.services.token_crypto import decrypt_token, encrypt_token
from app.integrations.instagram.webhook_parser import (
    verify_webhook_signature,
    parse_webhook_challenge,
    parse_messaging_events,
)
from app.integrations.instagram.messenger import send_message
from app.services.chat_runtime import ChatRuntimeService

import logging
logger = logging.getLogger(__name__)

router = APIRouter()


# â”€â”€ Bookings â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post("/booking/create", response_model=BookingOut)
def create_booking(payload: BookingCreateIn, db: Session = Depends(get_db)):
    try:
        booking = BookingService.create_booking(
            db=db,
            provider_id=payload.provider_id,
            customer_id=payload.customer_id,
            scheduled_start=payload.scheduled_start,
            scheduled_end=payload.scheduled_end,
            line_items=[li.model_dump() for li in payload.line_items],
            customer_notes=payload.customer_notes,
            provider_notes=payload.provider_notes,
            is_walkin=payload.is_walkin,
            walkin_customer_name=payload.walkin_customer_name,
            walkin_customer_email=payload.walkin_customer_email,
            session_preferences=payload.session_preferences,
            referral_source=payload.referral_source,
            status=payload.status or "pending",
        )
        return booking
    except SlotUnavailableError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/bookings", response_model=list[BookingOut])
def list_bookings(
    provider_id: str | None = Query(None),
    customer_id: str | None = Query(None),
    status: str | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    db: Session = Depends(get_db),
):
    return BookingService.list_bookings(
        db=db,
        provider_id=provider_id,
        customer_id=customer_id,
        status=status,
        from_date=from_date,
        to_date=to_date,
    )


@router.get("/bookings/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: str, db: Session = Depends(get_db)):
    booking = BookingService.get_booking(db, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.patch("/bookings/{booking_id}", response_model=BookingOut)
def update_booking(booking_id: str, payload: BookingUpdateIn, db: Session = Depends(get_db)):
    """Update booking fields (status, notes, schedule). Used by the provider dashboard."""
    try:
        booking = BookingService.update_booking(
            db, booking_id, **payload.model_dump(exclude_none=True)
        )
        return booking
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bookings/{booking_id}/reschedule", response_model=BookingOut)
def reschedule_booking(
    booking_id: str,
    new_start: datetime = Query(...),
    new_end: datetime = Query(...),
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Reschedule a booking to a new time slot."""
    try:
        booking = BookingService.reschedule_booking(db, booking_id, new_start, new_end, provider_id=provider_id)
        return booking
    except SlotUnavailableError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# â”€â”€ Invoices â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class ProviderLateAlertIn(BaseModel):
    minutes: int


class CustomerReliabilityReportIn(BaseModel):
    category: str
    booking_id: str | None = None
    severity: int = 1
    details: str | None = None

@router.post("/bookings/{booking_id}/provider-running-late", status_code=200)
def provider_running_late(
    booking_id: str,
    payload: ProviderLateAlertIn,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Provider marks themselves as running late for an upcoming booking.

    Sets the same late_notification_minutes field that customers use,
    so the orange banner shows/updates on the provider home card.
    """
    booking = (
        db.query(Booking)
        .filter(Booking.booking_id == booking_id, Booking.provider_id == provider_id)
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status not in ("pending", "confirmed"):
        raise HTTPException(status_code=400, detail="Booking is not upcoming")
    booking.late_notification_minutes = payload.minutes
    booking.late_notification_sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return {"booking_id": booking_id, "late_minutes": payload.minutes}


@router.post("/invoice/create/{booking_id}", response_model=InvoiceOut)
def create_invoice(booking_id: str, db: Session = Depends(get_db)):
    try:
        return InvoiceService.create_invoice_from_booking(db, booking_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# â”€â”€ Customers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post("/customer/create", response_model=CustomerOut)
def create_customer(payload: CustomerCreateIn, db: Session = Depends(get_db)):
    return CustomerService.create_customer(
        db=db,
        provider_id=payload.provider_id,
        customer_email=payload.customer_email,
        user_id=payload.user_id,
        instagram_username_snapshot=payload.instagram_username_snapshot,
        display_name=payload.display_name,
        phone=payload.phone,
        source_channel=payload.source_channel,
    )


@router.get("/customers", response_model=list[CustomerOut])
def list_customers(provider_id: str = Query(...), db: Session = Depends(get_db)):
    return CustomerService.get_customers_by_provider(db, provider_id)


@router.get("/customer/{customer_id}/profile")
def get_customer_profile(
    customer_id: str,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Dynamic customer profile â€” only accessible by authenticated providers.
    The reliability score block is stripped unless the provider has a booking
    or waitlist relationship with this customer.
    """
    profile = CustomerService.get_customer_profile(db, customer_id, provider_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Customer not found")
    return profile


@router.post("/customer/{customer_id}/reliability-report", status_code=201)
def create_customer_reliability_report(
    customer_id: str,
    payload: CustomerReliabilityReportIn,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Provider submits an anonymous structured reliability report on a customer."""
    try:
        report = CustomerReliabilityService.submit_provider_report(
            db,
            provider_id=provider_id,
            customer_id=customer_id,
            category=payload.category,
            booking_id=payload.booking_id,
            severity=payload.severity,
            details=payload.details,
        )
        reliability = CustomerReliabilityService.calculate_for_customer(db, customer_id)
        return {
            "report_id": report.report_id,
            "customer_id": customer_id,
            "category": report.category,
            "severity": report.severity,
            "created_at": report.created_at.isoformat() if report.created_at else None,
            "reliability_score": reliability.get("reliability_score", 0.0),
            "reliability_tier": reliability.get("reliability_tier", "new"),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/customer/{customer_id}/reliability-score")
def get_customer_reliability_score(
    customer_id: str,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Provider reads customer reliability score for booking-risk decisions."""
    customer = CustomerService.get_customer(db, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if customer.provider_id != provider_id:
        raise HTTPException(status_code=403, detail="Customer is not linked to this provider")

    can_view = CustomerService.provider_can_view_customer_rating(
        db,
        provider_id=provider_id,
        customer_id=customer_id,
    )
    if not can_view:
        raise HTTPException(status_code=403, detail="Customer rating is visible only while an active booking exists")

    try:
        return CustomerReliabilityService.calculate_for_customer(db, customer_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# â”€â”€ Customer Preferences â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

from app.api.schemas import PreferenceCreateIn, PreferenceOut, MergeProposalOut
from app.services.customer_preference_service import CustomerPreferenceService
from app.services.customer_matching_service import CustomerMatchingService


@router.post("/preferences", response_model=PreferenceOut)
def add_preference(payload: PreferenceCreateIn, db: Session = Depends(get_db)):
    return CustomerPreferenceService.add_preference(
        db=db,
        customer_id=payload.customer_id,
        provider_id=payload.provider_id,
        category=payload.category,
        key=payload.key,
        value=payload.value,
        source=payload.source,
    )


@router.get("/preferences", response_model=list[PreferenceOut])
def get_preferences(customer_id: str = Query(...), provider_id: str = Query(...), db: Session = Depends(get_db)):
    """Get approved preferences visible to the provider."""
    return CustomerPreferenceService.get_provider_visible_preferences(db, customer_id, provider_id)


@router.get("/preferences/all")
def get_all_preferences(customer_id: str = Query(...), provider_id: str = Query(...), db: Session = Depends(get_db)):
    """Get ALL preferences grouped by status â€” for the customer's 'My Data' view."""
    grouped = CustomerPreferenceService.get_all_preferences(db, customer_id, provider_id)
    # Convert to serializable format
    return {
        status: [PreferenceOut.model_validate(p).model_dump() for p in prefs]
        for status, prefs in grouped.items()
    }


@router.patch("/preferences/{preference_id}/approve", response_model=PreferenceOut)
def approve_preference(preference_id: str, db: Session = Depends(get_db)):
    try:
        return CustomerPreferenceService.approve_preference(db, preference_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/preferences/{preference_id}/deny", response_model=PreferenceOut)
def deny_preference(preference_id: str, db: Session = Depends(get_db)):
    try:
        return CustomerPreferenceService.deny_preference(db, preference_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# â”€â”€ Merge Proposals â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.get("/merge-proposals", response_model=list[MergeProposalOut])
def get_merge_proposals(provider_id: str = Query(...), db: Session = Depends(get_db)):
    return CustomerMatchingService.get_pending_proposals(db, provider_id)


@router.patch("/merge-proposals/{proposal_id}/approve", response_model=MergeProposalOut)
def approve_merge(proposal_id: str, db: Session = Depends(get_db)):
    try:
        return CustomerMatchingService.approve_merge(db, proposal_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/merge-proposals/{proposal_id}/deny", response_model=MergeProposalOut)
def deny_merge(proposal_id: str, db: Session = Depends(get_db)):
    try:
        return CustomerMatchingService.deny_merge(db, proposal_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# â”€â”€ Instagram â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post("/instagram/resolve", response_model=InstagramIdentityOut)
def resolve_instagram(payload: InstagramResolveIn, db: Session = Depends(get_db)):
    return InstagramMappingService.resolve_or_create_customer(
        db=db,
        provider_id=payload.provider_id,
        instagram_user_id=payload.instagram_user_id,
        instagram_username=payload.instagram_username,
    )


# â”€â”€ Trust Signals (Revisit Rate) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

from app.services.revisit_service import RevisitRateService
from app.services.provider_trust_service import ProviderTrustService


@router.post("/provider/{provider_id}/recalculate-stats")
def recalculate_provider_stats(provider_id: str, db: Session = Depends(get_db)):
    """Recalculate revisit + trust stats for a provider."""
    try:
        provider = RevisitRateService.update_provider_stats(db, provider_id)
        trust = ProviderTrustService.calculate_provider_trust(db, provider_id)
        return {
            "provider_id": provider.provider_id,
            "revisit_rate": provider.revisit_rate,
            "total_completed_bookings": provider.total_completed_bookings,
            "trust_score": trust["trust_score"],
            "trust_tier": trust["trust_tier"],
            "trust_confidence": trust["confidence"],
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
@router.get("/provider/{provider_id}/trust-signals")
def get_trust_signals(provider_id: str, db: Session = Depends(get_db)):
    """Get revisit, rating and fair trust score signals for a provider."""
    provider = ProviderService.get_provider(db, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    revisit = RevisitRateService.calculate_revisit_rate(db, provider_id)
    trust = ProviderTrustService.calculate_provider_trust(db, provider_id)

    return {
        **revisit,
        "rating": provider.rating,
        "review_count": provider.review_count,
        "trust_score": trust["trust_score"],
        "trust_tier": trust["trust_tier"],
        "trust_confidence": trust["confidence"],
        "trust_breakdown": trust["breakdown"],
        "trust_recommendations": trust["recommendations"],
    }


@router.get("/provider/{provider_id}/trust-score")
def get_provider_trust_score(provider_id: str, db: Session = Depends(get_db)):
    """Get full trust score payload with component-level transparency."""
    try:
        return ProviderTrustService.calculate_provider_trust(db, provider_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
# â”€â”€ Reports â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/reports/summary")
def get_report_summary(
    provider_id: str = Query(...),
    period: str = Query("this_month"),
    db: Session = Depends(get_db),
):
    try:
        booking_summary = ReportingService.get_booking_summary(db, provider_id, period)
        invoice_summary = ReportingService.get_invoice_summary(db, provider_id, period)
        return {"bookings": booking_summary, "invoices": invoice_summary}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# â”€â”€ Provider Search â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/providers/search", response_model=list[ProviderOut])
def search_providers(
    location: str | None = Query(None),
    service_category: str | None = Query(None),
    service_name: str | None = Query(None),
    home_service: bool | None = Query(None),
    db: Session = Depends(get_db),
):
    return ProviderService.search_providers(
        db=db,
        location=location,
        service_category=service_category,
        service_name=service_name,
        home_service=home_service,
    )


@router.get("/providers/{provider_id}", response_model=ProviderOut)
def get_provider(provider_id: str, db: Session = Depends(get_db)):
    provider = ProviderService.get_provider(db, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


# â”€â”€ Service Catalog â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post("/service/create", response_model=ServiceOut)
def create_service(payload: ServiceCreateIn, db: Session = Depends(get_db)):
    return ProviderService.create_service(
        db=db,
        provider_id=payload.provider_id,
        name=payload.name,
        category=payload.category,
        description=payload.description,
        duration_minutes=payload.duration_minutes,
        price_ex_vat=payload.price_ex_vat,
        vat_percent=payload.vat_percent,
        home_service_available=payload.home_service_available,
    )


@router.get("/services", response_model=list[ServiceOut])
def list_services(
    provider_id: str = Query(...),
    category: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return ProviderService.get_provider_services(db, provider_id, category)


# ── Provider-authenticated service CRUD (used by mobile settings) ─

class ProviderServiceUpdateIn(BaseModel):
    name: str | None = None
    category: str | None = None
    description: str | None = None
    duration_minutes: int | None = None
    price_ex_vat: float | None = None
    vat_percent: float | None = None
    is_active: bool | None = None
    home_service_available: bool | None = None


class ProviderServiceCreateIn(BaseModel):
    name: str
    category: str | None = None
    description: str | None = None
    duration_minutes: int
    price_ex_vat: float
    vat_percent: float | None = None
    home_service_available: bool = False


@router.get("/provider/services", response_model=list[ServiceOut])
def provider_list_services(
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Return ALL services for the authenticated provider (active + inactive)."""
    return ProviderService.get_provider_services(db, provider_id, active_only=False)


@router.post("/provider/services", response_model=ServiceOut, status_code=201)
def provider_create_service(
    payload: ProviderServiceCreateIn,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    return ProviderService.create_service(
        db=db,
        provider_id=provider_id,
        name=payload.name,
        category=payload.category,
        description=payload.description,
        duration_minutes=payload.duration_minutes,
        price_ex_vat=payload.price_ex_vat,
        vat_percent=payload.vat_percent,
        home_service_available=payload.home_service_available,
    )


@router.patch("/provider/services/{service_id}", response_model=ServiceOut)
def provider_update_service(
    service_id: str,
    payload: ProviderServiceUpdateIn,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    from app.models.service import Service as ServiceModel
    svc = db.query(ServiceModel).filter(
        ServiceModel.service_id == service_id,
        ServiceModel.provider_id == provider_id,
    ).first()
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    return ProviderService.update_service(db, service_id, **payload.model_dump(exclude_none=True))


@router.delete("/provider/services/{service_id}", status_code=204)
def provider_delete_service(
    service_id: str,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    try:
        ProviderService.delete_service(db, service_id, provider_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Service not found")


# â”€â”€ Availability â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post("/availability/hours", response_model=WorkingHoursOut)
def set_working_hours(payload: WorkingHoursIn, db: Session = Depends(get_db)):
    try:
        return AvailabilityService.set_working_hours(
            db=db,
            provider_id=payload.provider_id,
            day_of_week=payload.day_of_week,
            start_minutes=payload.start_minutes,
            end_minutes=payload.end_minutes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/availability/hours", response_model=list[WorkingHoursOut])
def get_working_hours(provider_id: str = Query(...), db: Session = Depends(get_db)):
    return AvailabilityService.get_working_hours(db, provider_id)


@router.post("/availability/override", response_model=OverrideOut)
def add_override(payload: OverrideIn, db: Session = Depends(get_db)):
    return AvailabilityService.add_override(
        db=db,
        provider_id=payload.provider_id,
        date=payload.date,
        is_closed=payload.is_closed,
        start_minutes=payload.start_minutes,
        end_minutes=payload.end_minutes,
        reason=payload.reason,
    )


@router.get("/availability/slots", response_model=list[SlotOut])
def get_available_slots(
    provider_id: str = Query(...),
    date: datetime = Query(...),
    duration_minutes: int = Query(...),
    slot_interval: int = Query(15),
    db: Session = Depends(get_db),
):
    return AvailabilityService.get_available_slots(
        db=db,
        provider_id=provider_id,
        date=date,
        duration_minutes=duration_minutes,
        slot_interval=slot_interval,
    )


# â”€â”€ Conversations â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post("/conversation/create", response_model=ConversationOut)
def create_conversation(payload: ConversationCreateIn, db: Session = Depends(get_db)):
    return ConversationService.get_or_create_conversation(
        db=db,
        provider_id=payload.provider_id,
        channel=payload.channel,
        external_thread_id=payload.external_thread_id,
        customer_id=payload.customer_id,
    )


@router.post("/conversation/message", response_model=MessageOut)
def log_message(payload: MessageIn, db: Session = Depends(get_db)):
    return ConversationService.log_message(
        db=db,
        conversation_id=payload.conversation_id,
        direction=payload.direction,
        text=payload.text,
        raw_payload_json=payload.raw_payload_json,
        idempotency_key=payload.idempotency_key,
    )


@router.get("/conversation/{conversation_id}/history", response_model=list[MessageOut])
def get_conversation_history(
    conversation_id: str,
    limit: int = Query(50),
    db: Session = Depends(get_db),
):
    return ConversationService.get_conversation_history(db, conversation_id, limit)


# â”€â”€ Slot Holds â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post("/availability/hold", response_model=SlotHoldOut)
def hold_slot(payload: SlotHoldIn, db: Session = Depends(get_db)):
    return AvailabilityService.hold_slot(
        db=db,
        provider_id=payload.provider_id,
        start=payload.start,
        end=payload.end,
        conversation_id=payload.conversation_id,
        hold_minutes=payload.hold_minutes,
    )


# â”€â”€ Provider Instagram Page Mapping â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

from app.models.provider_instagram_page import ProviderInstagramPage as PIPage


@router.post("/platform/instagram-page")
def register_platform_instagram_page(
    instagram_page_id: str = Query(...),
    page_name: str | None = Query(None),
    access_token: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Register @fixmeapp's own Instagram page as the platform discovery account.

    Messages to this page route to the platform orchestrator (cross-provider search)
    instead of any single provider's bot.
    """
    existing = db.query(PIPage).filter(PIPage.instagram_page_id == instagram_page_id).first()
    if existing:
        existing.provider_id = None
        existing.is_platform_page = True
        if page_name:
            existing.page_name = page_name
        if access_token:
            existing.access_token = encrypt_token(access_token)
        db.commit()
        return {"status": "updated", "instagram_page_id": instagram_page_id, "is_platform_page": True}

    page = PIPage(
        provider_id=None,
        instagram_page_id=instagram_page_id,
        page_name=page_name or "fixmeapp",
        access_token=encrypt_token(access_token),
        is_platform_page=True,
    )
    db.add(page)
    db.commit()
    return {"status": "registered", "instagram_page_id": instagram_page_id, "is_platform_page": True}


@router.post("/provider/{provider_id}/instagram-page")
def register_instagram_page(
    provider_id: str,
    instagram_page_id: str = Query(...),
    page_name: str | None = Query(None),
    access_token: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Register an Instagram page ID for webhook auto-resolution."""
    existing = db.query(PIPage).filter(PIPage.instagram_page_id == instagram_page_id).first()
    if existing:
        existing.provider_id = provider_id
        if page_name:
            existing.page_name = page_name
        if access_token:
            existing.access_token = encrypt_token(access_token)
        db.commit()
        db.refresh(existing)
        return {"id": existing.id, "provider_id": existing.provider_id, "instagram_page_id": existing.instagram_page_id}

    page = PIPage(
        provider_id=provider_id,
        instagram_page_id=instagram_page_id,
        page_name=page_name,
        access_token=encrypt_token(access_token),
    )
    db.add(page)
    db.commit()
    db.refresh(page)
    return {"id": page.id, "provider_id": page.provider_id, "instagram_page_id": page.instagram_page_id}


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# â”€â”€ Instagram Webhook (full AI pipeline) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@router.get("/webhooks/instagram")
async def instagram_webhook_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Meta webhook verification handshake (GET).

    Meta sends this when you register your webhook URL.
    We validate the token and echo back the challenge.
    """
    challenge = parse_webhook_challenge(
        hub_mode, hub_verify_token, hub_challenge, settings.INSTAGRAM_VERIFY_TOKEN,
    )
    if challenge:
        return PlainTextResponse(content=challenge)
    return PlainTextResponse(content="Forbidden", status_code=403)


@router.post("/webhooks/instagram")
async def instagram_webhook(request: Request, db: Session = Depends(get_db)):
    """Full Instagram DM pipeline:

    1. Verify HMAC signature
    2. Parse messaging events
    3. For each message:
       a. Idempotency check (WebhookService)
       b. Resolve IG user â†’ Customer (InstagramMappingService)
       c. Get/create conversation (ConversationService)
       d. Log inbound message
       e. Run AI orchestrator â†’ get reply
       f. Log outbound reply
       g. Send reply via Instagram Graph API
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    # Verify signature (skip if no app secret configured â€” local dev)
    if settings.INSTAGRAM_APP_SECRET:
        if not verify_webhook_signature(raw_body, signature, settings.INSTAGRAM_APP_SECRET):
            logger.warning("Invalid webhook signature")
            return JSONResponse(content={"error": "invalid signature"}, status_code=403)

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(content={"error": "invalid json"}, status_code=400)

    messages = parse_messaging_events(payload)

    for msg in messages:
        sender_id = msg["sender_id"]
        recipient_id = msg.get("recipient_id", "")
        text = msg["text"]
        message_id = msg.get("message_id", "")

        # Auto-resolve provider from IG page ID (ProviderInstagramPage table)
        # Falls back to X-Provider-Id header for backward compatibility
        provider_id = ""
        is_platform_page = False
        mapping = None  # ProviderInstagramPage row - carries per-provider access_token
        if recipient_id:
            from app.models.provider_instagram_page import ProviderInstagramPage
            mapping = db.query(ProviderInstagramPage).filter(
                ProviderInstagramPage.instagram_page_id == recipient_id
            ).first()
            if mapping:
                provider_id = mapping.provider_id or ""
                is_platform_page = mapping.is_platform_page or False

        if not provider_id and not is_platform_page:
            provider_id = request.headers.get("X-Provider-Id", "")

        if not provider_id and not is_platform_page:
            logger.warning("Cannot resolve provider for recipient=%s, skipping message from %s", recipient_id, sender_id)
            continue

        # Idempotency â€” platform pages skip WebhookEvent tracking because
        # WebhookEvent.provider_id is a non-nullable FK to providers.
        # provider_id="" for platform pages would cause an IntegrityError.
        platform_event_id = message_id or f"{sender_id}_{msg.get('timestamp', '')}"
        event = None
        if not is_platform_page:
            if WebhookService.is_duplicate(db, provider_id, "instagram", platform_event_id):
                continue
            event = WebhookService.record_event(db, provider_id, "instagram", platform_event_id)

        # Resolve token before handle_message: on DB errors the session is rolled back and
        # ORM rows like `mapping` must not be lazy-loaded in the except block.
        reply_send_token = (
            (decrypt_token(mapping.access_token) if mapping and mapping.access_token else None)
            or settings.INSTAGRAM_PAGE_ACCESS_TOKEN
        )

        try:
            mode = "platform" if is_platform_page else "provider"
            if is_platform_page:
                logger.info("platform.message sender=%s", sender_id)

            runtime_result = await ChatRuntimeService.handle_message(
                db=db,
                mode=mode,
                channel="instagram_dm",
                thread_id=sender_id,
                text=text,
                provider_id=provider_id or None,
                sender_id=sender_id,
                inbound_idempotency_key=platform_event_id,
            )
            reply_text = runtime_result.reply

            if reply_send_token:
                await send_message(reply_send_token, sender_id, reply_text)

            if event:
                WebhookService.mark_processed(db, event.event_id)

        except Exception as e:
            logger.exception("Error processing message from %s", sender_id)
            db.rollback()
            if event:
                WebhookService.mark_processed(db, event.event_id, error_detail=str(e))

            if reply_send_token:
                try:
                    await send_message(
                        reply_send_token,
                        sender_id,
                        "Sorry, I'm having a small technical issue. Please try again in a moment!",
                    )
                except Exception:
                    pass

    return JSONResponse(content={"status": "ok"})


# â”€â”€ Test endpoint (local dev â€” bypasses Instagram) â”€â”€â”€â”€â”€â”€â”€â”€

from datetime import timedelta, timezone as tz_mod
from sqlalchemy import func as sa_func, or_ as sa_or
from app.models.conversation import Conversation, Message
from app.models.booking import Booking
from app.models.customer import Customer


# â”€â”€ Dashboard API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/dashboard/{provider_id}")
def get_dashboard_data(
    provider_id: str,
    db: Session = Depends(get_db),
):
    """Single endpoint returning all data the provider dashboard needs."""
    now = datetime.now(tz_mod.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    provider = ProviderService.get_provider(db, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    # --- Bookings today / this week ---
    bookings_today = db.query(Booking).filter(
        Booking.provider_id == provider_id,
        Booking.scheduled_start >= today_start,
        Booking.scheduled_start < today_start + timedelta(days=1),
        Booking.status.in_(["pending", "confirmed"]),
    ).order_by(Booking.scheduled_start).all()

    week_end = week_start + timedelta(days=7)
    bookings_week = db.query(Booking).filter(
        Booking.provider_id == provider_id,
        Booking.scheduled_start >= today_start,
        Booking.scheduled_start < week_end,
        Booking.status.in_(["pending", "confirmed"]),
    ).order_by(Booking.scheduled_start).all()

    def booking_to_dict(b):
        items = ", ".join(li.service_type for li in b.line_items)
        cust = db.query(Customer).filter(Customer.customer_id == b.customer_id).first()
        cust_name = cust.instagram_username_snapshot or cust.customer_email or f"Customer #{cust.customer_number}" if cust else "Unknown"
        return {
            "booking_id": b.booking_id,
            "booking_number": b.booking_number,
            "customer_id": b.customer_id,
            "customer_name": cust_name,
            "services": items,
            "scheduled_start": b.scheduled_start.isoformat(),
            "scheduled_end": b.scheduled_end.isoformat(),
            "status": b.status,
            "total_inc_vat": b.total_amount_inc_vat,
            "customer_notes": b.customer_notes or "",
            "provider_notes": b.provider_notes or "",
            "is_walkin": b.is_walkin or False,
        }

    # --- Stats ---
    total_bookings_month = db.query(Booking).filter(
        Booking.provider_id == provider_id,
        Booking.created_at >= month_start,
    ).count()

    revenue_month = db.query(sa_func.coalesce(sa_func.sum(Booking.total_amount_inc_vat), 0.0)).filter(
        Booking.provider_id == provider_id,
        Booking.scheduled_start >= month_start,
        Booking.status.in_(["pending", "confirmed", "completed"]),
    ).scalar()

    total_customers = db.query(Customer).filter(Customer.provider_id == provider_id, Customer.merge_status == "primary").count()

    total_conversations = db.query(Conversation).filter(
        Conversation.provider_id == provider_id
    ).count()

    # --- AI bot stats: messages that led to a booking ---
    # Conversations that have at least one booking (customer has bookings)
    conversations_with_bookings = (
        db.query(Conversation)
        .join(Customer, Customer.customer_id == Conversation.customer_id)
        .join(Booking, Booking.customer_id == Customer.customer_id)
        .filter(Conversation.provider_id == provider_id)
        .distinct()
        .count()
    )

    # --- 5 Recent conversations with last message ---
    recent_convs = (
        db.query(Conversation)
        .filter(Conversation.provider_id == provider_id)
        .order_by(Conversation.last_message_at.desc().nullslast())
        .limit(5)
        .all()
    )
    conversations_out = []
    for conv in recent_convs:
        cust = db.query(Customer).filter(Customer.customer_id == conv.customer_id).first() if conv.customer_id else None
        cust_name = (cust.instagram_username_snapshot or cust.customer_email or f"Customer #{cust.customer_number}") if cust else "Unknown"
        # Get last 2 messages
        msgs = db.query(Message).filter(
            Message.conversation_id == conv.conversation_id
        ).order_by(Message.timestamp.desc()).limit(2).all()
        msg_list = [{"direction": m.direction, "text": (m.text or "")[:120], "timestamp": m.timestamp.isoformat()} for m in reversed(msgs)]
        conversations_out.append({
            "conversation_id": conv.conversation_id,
            "customer_name": cust_name,
            "channel": conv.channel,
            "status": conv.status,
            "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
            "messages": msg_list,
        })

    # --- Booking history: only PAST bookings (completed/cancelled or scheduled before today) ---
    recent_bookings = db.query(Booking).filter(
        Booking.provider_id == provider_id,
        sa_or(
            Booking.status.in_(["completed", "cancelled"]),
            Booking.scheduled_start < today_start,
        ),
    ).order_by(Booking.scheduled_start.desc()).limit(10).all()

    return {
        "provider": {
            "provider_id": provider.provider_id,
            "name": provider.name,
            "location": provider.location_salon,
            "city": provider.city,
            "bio": provider.bio,
            "image_url": provider.image_url,
            "revisit_rate": provider.revisit_rate,
            "rating": provider.rating,
            "review_count": provider.review_count,
        },
        "stats": {
            "bookings_today": len(bookings_today),
            "bookings_this_week": len(bookings_week),
            "bookings_this_month": total_bookings_month,
            "revenue_this_month": round(revenue_month, 2),
            "total_customers": total_customers,
            "total_conversations": total_conversations,
            "ai_converted_conversations": conversations_with_bookings,
            "revisit_rate": provider.revisit_rate,
            "total_completed_bookings": provider.total_completed_bookings,
        },
        "bookings_today": [booking_to_dict(b) for b in bookings_today],
        "bookings_week": [booking_to_dict(b) for b in bookings_week],
        "recent_conversations": conversations_out,
        "booking_history": [booking_to_dict(b) for b in recent_bookings],
    }



_EMAIL_PATTERN = re.compile(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
_NAME_PATTERN = re.compile(r"\bmy name is\s+([^\n\.,!\?]+)", re.IGNORECASE)


def _extract_email(text: str) -> str | None:
    match = _EMAIL_PATTERN.search(text or "")
    if not match:
        return None
    return match.group(1).strip().lower()


def _extract_name(text: str) -> str | None:
    match = _NAME_PATTERN.search(text or "")
    if not match:
        return None
    return match.group(1).strip()
class TestMessage(BaseModel):
    message: str
    user_id: str = "test_user_123"
    provider_id: str


@router.post("/test/chat")
async def test_chat(payload: TestMessage, db: Session = Depends(get_db)):
    """Test the AI bot directly without Instagram.

    Send: {"message": "What services do you offer?", "provider_id": "..."}
    """
    # Resolve or create a test customer
    identity = InstagramMappingService.resolve_or_create_customer(
        db=db,
        provider_id=payload.provider_id,
        instagram_user_id=payload.user_id,
        instagram_username="test_user",
    )

    # Persist email/name if the test message contains them so customer auth can
    # resolve the same profile on /customer/me/dashboard.
    customer = db.query(Customer).filter(Customer.customer_id == identity.customer_id).first()
    if customer:
        extracted_email = _extract_email(payload.message)
        extracted_name = _extract_name(payload.message)
        changed = False

        if extracted_email and ((customer.customer_email or "").strip().lower() != extracted_email):
            customer.customer_email = extracted_email
            changed = True

        if extracted_name and not (customer.display_name or "").strip():
            customer.display_name = extracted_name
            changed = True

        if changed:
            db.commit()

    runtime_result = await ChatRuntimeService.handle_message(
        db=db,
        mode="provider",
        channel="test",
        thread_id=payload.user_id,
        text=payload.message,
        provider_id=payload.provider_id,
        sender_id=payload.user_id,
        customer_id=identity.customer_id,
    )

    return {
        "reply": runtime_result.reply,
        "conversation_id": runtime_result.conversation_id,
        "customer_id": identity.customer_id,
    }
