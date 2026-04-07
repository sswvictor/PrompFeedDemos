import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.provider import Provider
from app.models.service import Service
from app.models.user import User
from app.models.waitlist import WaitlistEntry, WaitlistOffer
from app.services.customer_service import CustomerService
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

OFFER_EXPIRY_MINUTES = 10


class WaitlistService:

    # -- Join waitlist (with identity stitching) --------------------

    @staticmethod
    def join_waitlist(
        db: Session,
        provider_id: str,
        email: str,
        name: str,
        service_id: str | None = None,
        preferred_days: list[int] | None = None,
        earliest_hour: int = 8,
        latest_hour: int = 18,
    ) -> WaitlistEntry:
        """Add a customer to the waitlist, stitching identity to User/Customer."""
        email_lower = email.strip().lower()

        # 1. Check if email belongs to an existing User
        user = db.query(User).filter(
            func.lower(User.email) == email_lower
        ).first()
        user_id = user.user_id if user else None

        # 2. Check if a Customer record already exists for this provider + email
        customer = CustomerService.find_by_email_and_provider(db, provider_id, email_lower)

        if not customer:
            # Create customer — triggers existing _run_matching for auto-merge
            customer = CustomerService.create_customer(
                db=db,
                provider_id=provider_id,
                customer_email=email_lower,
                user_id=user_id,
                display_name=name,
                source_channel="waitlist",
            )
        elif user_id and not customer.user_id:
            # Stitch: existing customer didn't have a user_id, but we found one
            customer.user_id = user_id
            db.commit()

        # 3. Check for existing active waitlist entry (prevent duplicates)
        #    DB-level partial unique index enforces this on PostgreSQL;
        #    this app-level check still provides a friendly update path and race-safe behavior.
        existing = db.query(WaitlistEntry).filter(
            WaitlistEntry.provider_id == provider_id,
            WaitlistEntry.customer_email == email_lower,
            WaitlistEntry.status == "active",
        ).first()
        if existing:
            # Update preferences instead of creating duplicate
            existing.preferred_days = json.dumps(preferred_days or [0, 1, 2, 3, 4])
            existing.preferred_earliest_hour = earliest_hour
            existing.preferred_latest_hour = latest_hour
            existing.customer_name = name
            if service_id:
                existing.service_id = service_id
            db.commit()
            db.refresh(existing)
            logger.info(
                "waitlist.join_updated provider_id=%s entry_id=%s email=%s",
                provider_id, existing.entry_id, email_lower,
            )
            return existing

        # 4. Create new waitlist entry
        entry = WaitlistEntry(
            provider_id=provider_id,
            user_id=user_id,
            customer_id=customer.customer_id,
            customer_email=email_lower,
            customer_name=name,
            service_id=service_id,
            preferred_days=json.dumps(preferred_days or [0, 1, 2, 3, 4]),
            preferred_earliest_hour=earliest_hour,
            preferred_latest_hour=latest_hour,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        logger.info(
            "waitlist.joined provider_id=%s entry_id=%s email=%s "
            "days=%s hours=%d-%d",
            provider_id, entry.entry_id, email_lower,
            preferred_days, earliest_hour, latest_hour,
        )
        return entry

    # -- Slot freed trigger -----------------------------------------

    @staticmethod
    def on_slot_freed(
        db: Session,
        provider_id: str,
        slot_start: datetime,
        slot_end: datetime,
    ) -> WaitlistOffer | None:
        """Called when a booking is cancelled/rescheduled. Find matching waitlist
        entry and send an offer. Returns the offer if one was created."""
        try:
            return WaitlistService._try_offer_slot(db, provider_id, slot_start, slot_end)
        except Exception:
            logger.exception(
                "waitlist.on_slot_freed_error provider_id=%s slot_start=%s",
                provider_id, slot_start,
            )
            return None

    @staticmethod
    def _try_offer_slot(
        db: Session,
        provider_id: str,
        slot_start: datetime,
        slot_end: datetime,
    ) -> WaitlistOffer | None:
        # Handle both naive and aware datetimes
        start_naive = slot_start.replace(tzinfo=None) if slot_start.tzinfo else slot_start
        day_of_week = start_naive.weekday()  # 0=Mon, 6=Sun
        slot_hour = start_naive.hour

        # -- Fix #5: Idempotency — check for existing pending offer on this slot
        now = datetime.now(timezone.utc)
        existing_slot_offer = db.query(WaitlistOffer).filter(
            WaitlistOffer.provider_id == provider_id,
            WaitlistOffer.slot_start == slot_start,
            WaitlistOffer.slot_end == slot_end,
            WaitlistOffer.status == "pending",
            WaitlistOffer.expires_at > now,
        ).first()
        if existing_slot_offer:
            logger.info(
                "waitlist.slot_offer_exists provider_id=%s offer_id=%s "
                "slot_start=%s — skipping duplicate",
                provider_id, existing_slot_offer.offer_id, slot_start,
            )
            return None

        # -- Fix #6: DB-level preferred_days filtering with LIKE
        # Days are single digits 0-6, so LIKE '%N%' is safe (no false matches)
        day_filter = f"%{day_of_week}%"

        entries = db.query(WaitlistEntry).filter(
            WaitlistEntry.provider_id == provider_id,
            WaitlistEntry.status == "active",
            WaitlistEntry.preferred_earliest_hour <= slot_hour,
            WaitlistEntry.preferred_latest_hour >= slot_hour,
            WaitlistEntry.preferred_days.like(day_filter),
        ).order_by(WaitlistEntry.created_at.asc()).all()

        for entry in entries:
            # Skip if this entry already has a pending (non-expired) offer
            pending_offer = db.query(WaitlistOffer).filter(
                WaitlistOffer.entry_id == entry.entry_id,
                WaitlistOffer.status == "pending",
                WaitlistOffer.expires_at > now,
            ).first()
            if pending_offer:
                continue

            # Create the offer
            offer = WaitlistOffer(
                entry_id=entry.entry_id,
                provider_id=provider_id,
                slot_start=slot_start,
                slot_end=slot_end,
                expires_at=now + timedelta(minutes=OFFER_EXPIRY_MINUTES),
            )
            db.add(offer)
            db.commit()
            db.refresh(offer)

            # Send email
            provider = db.query(Provider).filter(
                Provider.provider_id == provider_id
            ).first()
            provider_name = provider.name if provider else "Your provider"

            slot_date_str = start_naive.strftime("%A %B %d")
            slot_time_str = start_naive.strftime("%H:%M")

            email_ok = EmailService.send_waitlist_offer(
                to=entry.customer_email,
                provider_name=provider_name,
                slot_date=slot_date_str,
                slot_time=slot_time_str,
                offer_id=offer.offer_id,
                offer_secret=offer.offer_secret,
            )

            logger.info(
                "waitlist.offer_created offer_id=%s entry_id=%s provider_id=%s "
                "slot_start=%s email_sent=%s",
                offer.offer_id, entry.entry_id, provider_id, slot_start, email_ok,
            )
            return offer

        return None  # No matching entry found

    # -- Accept offer -----------------------------------------------

    @staticmethod
    def accept_offer(db: Session, offer_id: str, offer_secret: str) -> dict:
        """Accept a waitlist offer — creates a real booking.

        Validates:
        1. offer_secret matches (security)
        2. offer is pending and not expired
        3. slot is still available (revalidation)
        """
        from app.services.availability_service import AvailabilityService
        from app.services.booking_service import BookingService, SlotUnavailableError

        offer = db.query(WaitlistOffer).filter(
            WaitlistOffer.offer_id == offer_id
        ).first()
        if not offer:
            raise ValueError("Offer not found")

        # -- Fix #3: Validate offer_secret
        if offer.offer_secret != offer_secret:
            logger.warning(
                "waitlist.accept_invalid_secret offer_id=%s provider_id=%s",
                offer_id, offer.provider_id,
            )
            raise ValueError("Invalid offer link")

        if offer.status != "pending":
            raise ValueError(f"Offer is already {offer.status}")

        now = datetime.now(timezone.utc)
        if offer.expires_at <= now:
            offer.status = "expired"
            db.commit()
            logger.info(
                "waitlist.accept_expired offer_id=%s entry_id=%s provider_id=%s",
                offer_id, offer.entry_id, offer.provider_id,
            )
            raise ValueError("Offer has expired")

        # -- Fix #4: Slot revalidation — check the slot is still free
        still_free = AvailabilityService.check_slot_available(
            db, offer.provider_id, offer.slot_start, offer.slot_end
        )
        if not still_free:
            offer.status = "expired"
            db.commit()
            logger.warning(
                "waitlist.accept_slot_taken offer_id=%s entry_id=%s provider_id=%s "
                "slot_start=%s — slot no longer available",
                offer_id, offer.entry_id, offer.provider_id, offer.slot_start,
            )
            raise ValueError(
                "Sorry, this slot was just booked by someone else. "
                "You're still on the waitlist — we'll notify you for the next opening."
            )

        entry = db.query(WaitlistEntry).filter(
            WaitlistEntry.entry_id == offer.entry_id
        ).first()
        if not entry:
            raise ValueError("Waitlist entry not found")

        # Build line items from the service (if specified)
        line_items = []
        service = None
        if entry.service_id:
            service = db.query(Service).filter(
                Service.service_id == entry.service_id
            ).first()

        if service:
            line_items = [{
                "service_type": service.name,
                "quantity": 1,
                "unit_price_ex_vat": service.price_ex_vat,
                "vat_percent": service.vat_percent,
            }]
        else:
            line_items = [{
                "service_type": "Waitlist booking",
                "quantity": 1,
                "unit_price_ex_vat": 0,
            }]

        # Create the real booking — slot may have been taken since the offer was made
        try:
            booking = BookingService.create_booking(
                db=db,
                provider_id=offer.provider_id,
                customer_id=entry.customer_id,
                scheduled_start=offer.slot_start,
                scheduled_end=offer.slot_end,
                line_items=line_items,
                customer_notes=f"Booked via waitlist (entry {entry.entry_id[:8]})",
                referral_source="waitlist",
            )
        except SlotUnavailableError:
            offer.status = "expired"
            db.commit()
            raise ValueError("This slot was taken before you could accept. We'll notify you when another opens up.")

        # Mark offer accepted, entry fulfilled
        offer.status = "accepted"
        entry.status = "fulfilled"
        entry.updated_at = now
        db.commit()

        # Send confirmation email
        provider = db.query(Provider).filter(
            Provider.provider_id == offer.provider_id
        ).first()
        provider_name = provider.name if provider else "Your provider"
        start_naive = offer.slot_start.replace(tzinfo=None) if offer.slot_start.tzinfo else offer.slot_start

        email_ok = EmailService.send_waitlist_confirmed(
            to=entry.customer_email,
            provider_name=provider_name,
            booking_number=booking.booking_number,
            slot_date=start_naive.strftime("%A %B %d"),
            slot_time=start_naive.strftime("%H:%M"),
        )

        logger.info(
            "waitlist.offer_accepted offer_id=%s entry_id=%s provider_id=%s "
            "booking_id=%s booking_number=%s email_sent=%s",
            offer.offer_id, entry.entry_id, offer.provider_id,
            booking.booking_id, booking.booking_number, email_ok,
        )

        return {
            "booking_id": booking.booking_id,
            "booking_number": booking.booking_number,
            "scheduled_start": booking.scheduled_start.isoformat(),
            "scheduled_end": booking.scheduled_end.isoformat(),
        }

    # -- Decline offer ----------------------------------------------

    @staticmethod
    def decline_offer(db: Session, offer_id: str, offer_secret: str) -> None:
        """Decline an offer — advances to next person in queue."""
        offer = db.query(WaitlistOffer).filter(
            WaitlistOffer.offer_id == offer_id
        ).first()
        if not offer:
            raise ValueError("Offer not found")

        # -- Fix #3: Validate offer_secret
        if offer.offer_secret != offer_secret:
            logger.warning(
                "waitlist.decline_invalid_secret offer_id=%s provider_id=%s",
                offer_id, offer.provider_id,
            )
            raise ValueError("Invalid offer link")

        if offer.status != "pending":
            raise ValueError(f"Offer is already {offer.status}")

        offer.status = "declined"
        db.commit()

        logger.info(
            "waitlist.offer_declined offer_id=%s entry_id=%s provider_id=%s",
            offer.offer_id, offer.entry_id, offer.provider_id,
        )

        # Try next person in queue for this slot
        WaitlistService.on_slot_freed(
            db, offer.provider_id, offer.slot_start, offer.slot_end
        )

    # -- Expire stale offers ----------------------------------------

    @staticmethod
    def expire_stale_offers(db: Session) -> int:
        """Mark expired offers and cascade to next in queue. Run via cron/startup."""
        from app.services.availability_service import AvailabilityService

        now = datetime.now(timezone.utc)
        stale = db.query(WaitlistOffer).filter(
            WaitlistOffer.status == "pending",
            WaitlistOffer.expires_at <= now,
        ).all()

        count = 0
        for offer in stale:
            offer.status = "expired"
            db.commit()
            count += 1

            logger.info(
                "waitlist.offer_expired offer_id=%s entry_id=%s provider_id=%s "
                "slot_start=%s",
                offer.offer_id, offer.entry_id, offer.provider_id,
                offer.slot_start,
            )

            # Check if the slot is still free before offering to next person
            still_free = AvailabilityService.check_slot_available(
                db, offer.provider_id, offer.slot_start, offer.slot_end
            )
            if still_free:
                WaitlistService.on_slot_freed(
                    db, offer.provider_id, offer.slot_start, offer.slot_end
                )

        return count

    # -- Provider view ----------------------------------------------

    @staticmethod
    def get_entries_for_provider(
        db: Session, provider_id: str, status: str | None = "active"
    ) -> list[dict]:
        q = db.query(WaitlistEntry).filter(
            WaitlistEntry.provider_id == provider_id
        )
        if status:
            q = q.filter(WaitlistEntry.status == status)
        entries = q.order_by(WaitlistEntry.created_at.asc()).all()

        result = []
        for e in entries:
            try:
                days = json.loads(e.preferred_days)
            except (json.JSONDecodeError, TypeError):
                days = []
            result.append({
                "entry_id": e.entry_id,
                "customer_name": e.customer_name,
                "customer_email": e.customer_email,
                "service_id": e.service_id,
                "preferred_days": days,
                "preferred_earliest_hour": e.preferred_earliest_hour,
                "preferred_latest_hour": e.preferred_latest_hour,
                "status": e.status,
                "created_at": e.created_at.isoformat(),
            })
        return result

    # -- Customer actions -------------------------------------------

    @staticmethod
    def get_entry_status(db: Session, entry_id: str) -> dict | None:
        entry = db.query(WaitlistEntry).filter(
            WaitlistEntry.entry_id == entry_id
        ).first()
        if not entry:
            return None

        # Calculate queue position
        position = db.query(WaitlistEntry).filter(
            WaitlistEntry.provider_id == entry.provider_id,
            WaitlistEntry.status == "active",
            WaitlistEntry.created_at <= entry.created_at,
        ).count()

        # Check for pending offer
        now = datetime.now(timezone.utc)
        pending_offer = db.query(WaitlistOffer).filter(
            WaitlistOffer.entry_id == entry_id,
            WaitlistOffer.status == "pending",
            WaitlistOffer.expires_at > now,
        ).first()

        return {
            "entry_id": entry.entry_id,
            "status": entry.status,
            "position": position,
            "preferred_days": json.loads(entry.preferred_days) if entry.preferred_days else [],
            "preferred_earliest_hour": entry.preferred_earliest_hour,
            "preferred_latest_hour": entry.preferred_latest_hour,
            "created_at": entry.created_at.isoformat(),
            "pending_offer": {
                "offer_id": pending_offer.offer_id,
                "slot_start": pending_offer.slot_start.isoformat(),
                "slot_end": pending_offer.slot_end.isoformat(),
                "expires_at": pending_offer.expires_at.isoformat(),
            } if pending_offer else None,
        }

    @staticmethod
    def cancel_entry(db: Session, entry_id: str) -> None:
        entry = db.query(WaitlistEntry).filter(
            WaitlistEntry.entry_id == entry_id
        ).first()
        if not entry:
            raise ValueError("Waitlist entry not found")
        if entry.status != "active":
            raise ValueError(f"Entry is already {entry.status}")
        entry.status = "cancelled"
        entry.updated_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "waitlist.entry_cancelled entry_id=%s provider_id=%s email=%s",
            entry.entry_id, entry.provider_id, entry.customer_email,
        )

    # -- Get offer details (for accept page) ------------------------

    @staticmethod
    def get_offer(db: Session, offer_id: str, offer_secret: str) -> dict | None:
        """Get offer details. Validates offer_secret for security."""
        offer = db.query(WaitlistOffer).filter(
            WaitlistOffer.offer_id == offer_id
        ).first()
        if not offer:
            return None

        # -- Fix #3: Validate offer_secret
        if offer.offer_secret != offer_secret:
            logger.warning(
                "waitlist.get_offer_invalid_secret offer_id=%s provider_id=%s",
                offer_id, offer.provider_id,
            )
            return None  # Return None (same as not found) to not leak existence

        entry = db.query(WaitlistEntry).filter(
            WaitlistEntry.entry_id == offer.entry_id
        ).first()

        provider = db.query(Provider).filter(
            Provider.provider_id == offer.provider_id
        ).first()

        now = datetime.now(timezone.utc)
        is_expired = offer.expires_at <= now and offer.status == "pending"
        if is_expired:
            offer.status = "expired"
            db.commit()

        return {
            "offer_id": offer.offer_id,
            "status": "expired" if is_expired else offer.status,
            "slot_start": offer.slot_start.isoformat(),
            "slot_end": offer.slot_end.isoformat(),
            "expires_at": offer.expires_at.isoformat(),
            "provider_name": provider.name if provider else None,
            "provider_slug": provider.slug if provider else None,
            "customer_name": entry.customer_name if entry else None,
            "service_id": entry.service_id if entry else None,
        }

    # -- Provider manual offer ---------------------------------------

    @staticmethod
    def create_manual_offer(
        db: Session,
        entry_id: str,
        provider_id: str,
        slot_start: datetime,
        slot_end: datetime,
    ) -> WaitlistOffer:
        """Provider manually sends an offer to a specific waitlist entry."""
        entry = db.query(WaitlistEntry).filter(
            WaitlistEntry.entry_id == entry_id,
            WaitlistEntry.provider_id == provider_id,
        ).first()
        if not entry:
            raise ValueError("Waitlist entry not found")
        if entry.status != "active":
            raise ValueError(f"Entry is already {entry.status}")

        # Check for existing pending offer on this entry
        now = datetime.now(timezone.utc)
        pending = db.query(WaitlistOffer).filter(
            WaitlistOffer.entry_id == entry_id,
            WaitlistOffer.status == "pending",
            WaitlistOffer.expires_at > now,
        ).first()
        if pending:
            raise ValueError("This customer already has a pending offer")

        # Create the offer
        offer = WaitlistOffer(
            entry_id=entry_id,
            provider_id=provider_id,
            slot_start=slot_start,
            slot_end=slot_end,
            expires_at=now + timedelta(minutes=OFFER_EXPIRY_MINUTES),
        )
        db.add(offer)
        db.commit()
        db.refresh(offer)

        # Send email notification
        provider = db.query(Provider).filter(
            Provider.provider_id == provider_id
        ).first()
        provider_name = provider.name if provider else "Your provider"

        start_naive = slot_start.replace(tzinfo=None) if slot_start.tzinfo else slot_start
        slot_date_str = start_naive.strftime("%A %B %d")
        slot_time_str = start_naive.strftime("%H:%M")

        email_ok = EmailService.send_waitlist_offer(
            to=entry.customer_email,
            provider_name=provider_name,
            slot_date=slot_date_str,
            slot_time=slot_time_str,
            offer_id=offer.offer_id,
            offer_secret=offer.offer_secret,
        )

        logger.info(
            "waitlist.manual_offer_created offer_id=%s entry_id=%s provider_id=%s "
            "slot_start=%s email_sent=%s",
            offer.offer_id, entry_id, provider_id, slot_start, email_ok,
        )
        return offer

    # -- Provider remove entry ---------------------------------------

    @staticmethod
    def provider_remove_entry(db: Session, entry_id: str, provider_id: str) -> None:
        """Provider removes a customer from the waitlist."""
        entry = db.query(WaitlistEntry).filter(
            WaitlistEntry.entry_id == entry_id,
            WaitlistEntry.provider_id == provider_id,
        ).first()
        if not entry:
            raise ValueError("Waitlist entry not found")
        if entry.status != "active":
            raise ValueError(f"Entry is already {entry.status}")
        entry.status = "cancelled"
        entry.updated_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "waitlist.provider_removed entry_id=%s provider_id=%s email=%s",
            entry_id, provider_id, entry.customer_email,
        )

