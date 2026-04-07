import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.booking import Booking, BookingLineItem
from app.models.provider import Provider
from app.models.customer import Customer
from app.models.timeslot_hold import TimeSlotHold
from app.services.email_service import EmailService
from app.services.loyalty_service import LoyaltyService

logger = logging.getLogger(__name__)


class SlotUnavailableError(Exception):
    """Raised when a requested time slot is no longer available."""
    pass


class BookingService:

    @staticmethod
    def _track_completed_loyalty(db: Session, booking: Booking) -> None:
        """Best-effort loyalty event tracking when a booking is completed."""
        try:
            LoyaltyService.track_completed_booking(db, booking)
        except Exception:
            logger.exception("Loyalty tracking failed for completed booking %s", booking.booking_id)

    @staticmethod
    def _get_next_booking_number(db: Session, provider_id: str) -> int:
        max_num = db.query(func.max(Booking.booking_number)).filter(
            Booking.provider_id == provider_id
        ).scalar()
        return (max_num or 0) + 1

    @staticmethod
    def _calculate_line_item(item: dict, default_vat: float) -> dict:
        """Calculate totals for a single line item."""
        quantity = item.get("quantity", 1)
        unit_price = item["unit_price_ex_vat"]
        vat_pct = item.get("vat_percent") or default_vat

        total_ex = round(quantity * unit_price, 2)
        total_vat = round(total_ex * vat_pct / 100, 2)
        total_inc = round(total_ex + total_vat, 2)

        return {
            "service_type": item["service_type"],
            "quantity": quantity,
            "unit_price_ex_vat": unit_price,
            "vat_percent": vat_pct,
            "total_line_ex_vat": total_ex,
            "total_line_vat": total_vat,
            "total_line_inc_vat": total_inc,
        }

    @staticmethod
    def create_booking(
        db: Session,
        provider_id: str,
        customer_id: str | None,
        scheduled_start: datetime,
        scheduled_end: datetime,
        line_items: list[dict[str, Any]],
        customer_notes: str | None = None,
        provider_notes: str | None = None,
        is_walkin: bool = False,
        walkin_customer_name: str | None = None,
        walkin_customer_email: str | None = None,
        session_preferences: list[str] | None = None,
        referral_source: str | None = None,
        status: str = "pending",
    ) -> Booking:
        # Get provider default VAT
        provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
        if not provider:
            raise ValueError(f"Provider {provider_id} not found")

        # ── Double-booking guard ──────────────────────────────────────────
        # SELECT FOR UPDATE locks overlapping rows so concurrent transactions
        # cannot both pass this check. Works across all channels (web, DM, admin).
        overlapping = (
            db.query(Booking)
            .filter(
                Booking.provider_id == provider_id,
                Booking.status.in_(["pending", "confirmed"]),
                Booking.scheduled_start < scheduled_end,
                Booking.scheduled_end > scheduled_start,
            )
            .with_for_update()
            .first()
        )
        if overlapping:
            raise SlotUnavailableError(
                "This time slot is no longer available. Please choose another time."
            )

        # Also reject if a non-expired hold exists from another conversation
        active_hold = (
            db.query(TimeSlotHold)
            .filter(
                TimeSlotHold.provider_id == provider_id,
                TimeSlotHold.expires_at > datetime.now(timezone.utc),
                TimeSlotHold.start < scheduled_end,
                TimeSlotHold.end > scheduled_start,
            )
            .with_for_update()
            .first()
        )
        if active_hold:
            raise SlotUnavailableError(
                "This time slot is currently being held by another customer. Please choose another time."
            )

        # Walk-in: auto-create a customer record if no customer_id provided
        if not customer_id and is_walkin:
            from app.services.customer_service import CustomerService
            walkin_cust = CustomerService.create_customer(
                db=db,
                provider_id=provider_id,
                customer_email=walkin_customer_email,
                instagram_username_snapshot=walkin_customer_name or "Walk-in",
                display_name=walkin_customer_name,
                source_channel="walkin",
            )
            customer_id = walkin_cust.customer_id
        elif not customer_id:
            raise ValueError("customer_id is required for non-walk-in bookings")

        # Blocked customer guard
        if customer_id:
            customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
            if customer and getattr(customer, "is_blocked", False):
                raise ValueError("This customer has been blocked from the platform.")

        default_vat = provider.vat_percent
        booking_number = BookingService._get_next_booking_number(db, provider_id)

        # Calculate line items and totals
        calculated_items = [BookingService._calculate_line_item(li, default_vat) for li in line_items]

        total_ex = round(sum(i["total_line_ex_vat"] for i in calculated_items), 2)
        total_vat = round(sum(i["total_line_vat"] for i in calculated_items), 2)
        total_inc = round(sum(i["total_line_inc_vat"] for i in calculated_items), 2)

        booking = Booking(
            provider_id=provider_id,
            customer_id=customer_id,
            booking_number=booking_number,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            total_amount_ex_vat=total_ex,
            total_vat_amount=total_vat,
            total_amount_inc_vat=total_inc,
            customer_notes=customer_notes,
            provider_notes=provider_notes,
            is_walkin=is_walkin,
            session_preferences=json.dumps(session_preferences) if session_preferences else None,
            referral_source=referral_source,
            status=status,
        )
        db.add(booking)
        db.flush()  # Get booking_id before creating line items

        for item_data in calculated_items:
            line_item = BookingLineItem(booking_id=booking.booking_id, **item_data)
            db.add(line_item)

        db.commit()
        db.refresh(booking)

        BookingService._queue_calendar_sync(db, booking, "created")

        # Best-effort emails — never block booking creation.
        try:
            customer_for_email = db.query(Customer).filter(
                Customer.customer_id == booking.customer_id
            ).first()
            customer_email = (
                (customer_for_email.customer_email or "").strip()
                if customer_for_email else ""
            )
            customer_display = (
                (customer_for_email.display_name or customer_for_email.instagram_username_snapshot or "Customer")
                if customer_for_email else "Customer"
            )
            primary_service = (
                calculated_items[0]["service_type"]
                if calculated_items else "Appointment"
            )
            slot_date = booking.scheduled_start.strftime("%Y-%m-%d")
            slot_time = booking.scheduled_start.strftime("%H:%M")

            # Customer confirmation — send when booking is confirmed at creation
            if booking.status == "confirmed" and customer_email:
                EmailService.send_booking_confirmed(
                    to=customer_email,
                    provider_name=provider.name,
                    booking_number=booking.booking_number,
                    service_name=primary_service,
                    slot_date=slot_date,
                    slot_time=slot_time,
                )

            # Provider new-booking notification — always send when provider has an email
            provider_email = (provider.email or "").strip()
            if provider_email:
                EmailService.send_provider_new_booking(
                    to=provider_email,
                    customer_name=customer_display,
                    booking_number=booking.booking_number,
                    service_name=primary_service,
                    slot_date=slot_date,
                    slot_time=slot_time,
                    customer_notes=customer_notes,
                )
        except Exception:
            logger.warning("Booking creation emails failed (non-blocking)", exc_info=True)

        # Best-effort push notification — never block booking creation.
        try:
            from app.services.push_notification_service import PushNotificationService
            _push_customer = db.query(Customer).filter(
                Customer.customer_id == booking.customer_id
            ).first()
            _push_name = (
                (_push_customer.display_name or _push_customer.instagram_username_snapshot or "A client")
                if _push_customer else "A client"
            )
            _push_service = (
                calculated_items[0]["service_type"] if calculated_items else "Appointment"
            )
            PushNotificationService.notify_new_booking(
                db=db,
                provider_id=provider_id,
                customer_name=_push_name,
                service=_push_service,
                time=booking.scheduled_start.strftime("%H:%M"),
            )
        except Exception:
            logger.warning("Push notification failed (non-blocking)", exc_info=True)

        return booking

    @staticmethod
    def get_booking(db: Session, booking_id: str) -> Booking | None:
        return db.query(Booking).filter(Booking.booking_id == booking_id).first()

    @staticmethod
    def list_bookings(
        db: Session,
        provider_id: str | None = None,
        customer_id: str | None = None,
        status: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[Booking]:
        q = db.query(Booking)
        if provider_id:
            q = q.filter(Booking.provider_id == provider_id)
        if customer_id:
            q = q.filter(Booking.customer_id == customer_id)
        if status:
            q = q.filter(Booking.status == status)
        if from_date:
            q = q.filter(Booking.scheduled_start >= from_date)
        if to_date:
            q = q.filter(Booking.scheduled_start <= to_date)
        return q.order_by(Booking.scheduled_start.desc()).all()

    @staticmethod
    def _notify_waitlist_slot_freed(db: Session, provider_id: str, start: datetime, end: datetime):
        """Non-blocking: check waitlist when a slot is freed."""
        try:
            from app.services.waitlist_service import WaitlistService
            WaitlistService.on_slot_freed(db, provider_id, start, end)
        except Exception:
            logger.exception("Waitlist notification failed (non-blocking)")

    @staticmethod
    def _queue_calendar_sync(db: Session, booking: Booking, reason: str) -> None:
        """Queue calendar sync jobs for all active provider calendar connections."""
        try:
            from app.models.provider_calendar_connection import ProviderCalendarConnection
            from app.services.calendar_sync_service import CalendarSyncService

            active_connections = (
                db.query(ProviderCalendarConnection)
                .filter(
                    ProviderCalendarConnection.provider_id == booking.provider_id,
                    ProviderCalendarConnection.sync_enabled.is_(True),
                    ProviderCalendarConnection.connector.in_(["google", "microsoft"]),
                )
                .all()
            )
            if not active_connections:
                return

            job_type = "push_update"
            if reason == "created":
                job_type = "push_create"
            elif reason == "cancelled":
                job_type = "push_delete"

            ts = int(datetime.now(timezone.utc).timestamp())
            for conn in active_connections:
                CalendarSyncService.queue_sync_job(
                    db=db,
                    provider_id=booking.provider_id,
                    connection_id=conn.connection_id,
                    booking_id=booking.booking_id,
                    job_type=job_type,
                    payload={
                        "booking_id": booking.booking_id,
                        "reason": reason,
                    },
                    idempotency_key=f"{job_type}:{conn.connection_id}:{booking.booking_id}:{ts}",
                )
        except Exception:
            logger.exception("Calendar sync queue failed for booking %s", booking.booking_id)

    @staticmethod
    def _send_status_emails(db: Session, booking: Booking, new_status: str, old_status: str) -> None:
        """Best-effort: send relevant emails when a booking status changes."""
        try:
            customer = db.query(Customer).filter(Customer.customer_id == booking.customer_id).first()
            provider = db.query(Provider).filter(Provider.provider_id == booking.provider_id).first()
            if not customer or not provider:
                return

            customer_email = (customer.customer_email or "").strip()
            service_name = "Appointment"
            if booking.line_items:
                service_name = booking.line_items[0].service_type or "Appointment"
            slot_date = booking.scheduled_start.strftime("%Y-%m-%d")
            slot_time = booking.scheduled_start.strftime("%H:%M")

            # Pending → Confirmed: send customer confirmation
            if new_status == "confirmed" and old_status != "confirmed" and customer_email:
                EmailService.send_booking_confirmed(
                    to=customer_email,
                    provider_name=provider.name,
                    booking_number=booking.booking_number,
                    service_name=service_name,
                    slot_date=slot_date,
                    slot_time=slot_time,
                )

            # Cancelled: notify customer
            if new_status == "cancelled" and customer_email:
                EmailService.send_booking_cancelled(
                    to=customer_email,
                    provider_name=provider.name,
                    booking_number=booking.booking_number,
                    service_name=service_name,
                    slot_date=slot_date,
                    slot_time=slot_time,
                )
        except Exception:
            logger.warning("Status-change emails failed for booking %s (non-blocking)", booking.booking_id, exc_info=True)

        # Best-effort push notifications for status changes
        try:
            from app.services.push_notification_service import PushNotificationService
            _customer = db.query(Customer).filter(Customer.customer_id == booking.customer_id).first()
            _cname = (
                (_customer.display_name or _customer.instagram_username_snapshot or "A client")
                if _customer else "A client"
            )
            _svc = booking.line_items[0].service_type if booking.line_items else "Appointment"
            _time = booking.scheduled_start.strftime("%H:%M")

            if new_status == "cancelled":
                PushNotificationService.notify_booking_cancelled(
                    db=db,
                    provider_id=booking.provider_id,
                    customer_name=_cname,
                    time=_time,
                )
            elif new_status == "confirmed" and old_status != "confirmed":
                PushNotificationService.notify_booking_confirmed(
                    db=db,
                    provider_id=booking.provider_id,
                    customer_name=_cname,
                    service=_svc,
                    time=_time,
                )
        except Exception:
            logger.warning("Status-change push notification failed for booking %s (non-blocking)", booking.booking_id, exc_info=True)

    @staticmethod
    def update_status(db: Session, booking_id: str, new_status: str) -> Booking:
        booking = BookingService.get_booking(db, booking_id)
        if not booking:
            raise ValueError(f"Booking {booking_id} not found")
        valid = {"pending", "confirmed", "completed", "cancelled"}
        if new_status not in valid:
            raise ValueError(f"Invalid status: {new_status}")
        old_status = booking.status
        booking.status = new_status
        db.commit()
        db.refresh(booking)

        # Slot freed - notify waitlist
        if new_status == "cancelled":
            BookingService._notify_waitlist_slot_freed(
                db, booking.provider_id, booking.scheduled_start, booking.scheduled_end
            )

        BookingService._queue_calendar_sync(db, booking, "cancelled" if new_status == "cancelled" else "status_update")

        if new_status == "completed":
            BookingService._track_completed_loyalty(db, booking)

        BookingService._send_status_emails(db, booking, new_status, old_status)

        return booking

    @staticmethod
    def update_booking(
        db: Session,
        booking_id: str,
        **kwargs,
    ) -> Booking:
        """Update booking fields. Used by dashboard for notes, status, reschedule."""
        booking = BookingService.get_booking(db, booking_id)
        if not booking:
            raise ValueError(f"Booking {booking_id} not found")

        old_status_before_change = booking.status  # capture BEFORE any setattr

        allowed = {
            "scheduled_start", "scheduled_end", "status",
            "customer_notes", "provider_notes",
        }
        for key, val in kwargs.items():
            if key in allowed and val is not None:
                if key == "status":
                    valid = {"pending", "confirmed", "completed", "cancelled"}
                    if val not in valid:
                        raise ValueError(f"Invalid status: {val}")
                setattr(booking, key, val)

        new_status = kwargs.get("status")
        db.commit()
        db.refresh(booking)

        if new_status == "cancelled":
            BookingService._notify_waitlist_slot_freed(
                db, booking.provider_id, booking.scheduled_start, booking.scheduled_end
            )

        BookingService._queue_calendar_sync(db, booking, "cancelled" if new_status == "cancelled" else "booking_update")

        if new_status == "completed":
            BookingService._track_completed_loyalty(db, booking)

        if new_status:
            BookingService._send_status_emails(db, booking, new_status, old_status_before_change)

        return booking

    @staticmethod
    def reschedule_booking(
        db: Session,
        booking_id: str,
        new_start: datetime,
        new_end: datetime,
        provider_id: str | None = None,
    ) -> Booking:
        """Reschedule a booking to a new time. Keeps same service/customer/line items."""
        booking = BookingService.get_booking(db, booking_id)
        if not booking:
            raise ValueError(f"Booking {booking_id} not found")
        if provider_id and booking.provider_id != provider_id:
            raise ValueError("You cannot reschedule another provider's booking")
        if booking.status == "cancelled":
            raise ValueError("Cannot reschedule a cancelled booking")
        if booking.status == "completed":
            raise ValueError("Cannot reschedule a completed booking")

        # ── Double-booking guard for new slot ─────────────────────────────
        overlapping = (
            db.query(Booking)
            .filter(
                Booking.provider_id == booking.provider_id,
                Booking.booking_id != booking_id,  # exclude self
                Booking.status.in_(["pending", "confirmed"]),
                Booking.scheduled_start < new_end,
                Booking.scheduled_end > new_start,
            )
            .with_for_update()
            .first()
        )
        if overlapping:
            raise SlotUnavailableError(
                "The new time slot is no longer available. Please choose another time."
            )

        # Capture old slot before overwriting
        old_start = booking.scheduled_start
        old_end = booking.scheduled_end

        booking.scheduled_start = new_start
        booking.scheduled_end = new_end
        db.commit()
        db.refresh(booking)

        # Old slot is now free - notify waitlist
        BookingService._notify_waitlist_slot_freed(db, booking.provider_id, old_start, old_end)
        BookingService._queue_calendar_sync(db, booking, "rescheduled")

        try:
            customer = db.query(Customer).filter(Customer.customer_id == booking.customer_id).first()
            provider = db.query(Provider).filter(Provider.provider_id == booking.provider_id).first()
            customer_email = (customer.customer_email or "").strip() if customer else ""
            service_name = booking.line_items[0].service_type if booking.line_items else "Appointment"

            if customer_email and provider:
                EmailService.send_booking_rescheduled(
                    to=customer_email,
                    provider_name=provider.name,
                    booking_number=booking.booking_number,
                    service_name=service_name,
                    old_slot_date=old_start.strftime("%Y-%m-%d"),
                    old_slot_time=old_start.strftime("%H:%M"),
                    new_slot_date=booking.scheduled_start.strftime("%Y-%m-%d"),
                    new_slot_time=booking.scheduled_start.strftime("%H:%M"),
                )
        except Exception:
            logger.warning("Reschedule email failed for booking %s (non-blocking)", booking.booking_id, exc_info=True)

        return booking

