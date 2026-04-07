import logging
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.user import User
from app.services.customer_reliability_service import CustomerReliabilityService

logger = logging.getLogger(__name__)


class CustomerService:

    @staticmethod
    def get_next_customer_number(db: Session, provider_id: str) -> int:
        max_num = db.query(func.max(Customer.customer_number)).filter(
            Customer.provider_id == provider_id
        ).scalar()
        return (max_num or 0) + 1

    @staticmethod
    def create_customer(
        db: Session,
        provider_id: str,
        customer_email: str | None = None,
        user_id: str | None = None,
        instagram_username_snapshot: str | None = None,
        display_name: str | None = None,
        phone: str | None = None,
        source_channel: str | None = None,
    ) -> Customer:
        customer_number = CustomerService.get_next_customer_number(db, provider_id)
        customer = Customer(
            provider_id=provider_id,
            user_id=user_id,
            customer_email=customer_email,
            instagram_username_snapshot=instagram_username_snapshot,
            display_name=display_name,
            phone=phone,
            source_channel=source_channel,
            customer_number=customer_number,
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

        # If a name was provided and the customer has a linked User, sync name to User
        if display_name and customer_email:
            CustomerService._sync_name_to_user(db, customer_email, display_name)

        # Run identity matching against existing customers
        CustomerService._run_matching(db, provider_id, customer)

        return customer

    @staticmethod
    def _sync_name_to_user(db: Session, email: str, display_name: str) -> None:
        """Copy display_name to the User record if the User has no name yet."""
        try:
            user = db.query(User).filter(User.email == email.lower()).first()
            if user and not user.display_name:
                user.display_name = display_name
                db.commit()
                logger.info("Synced display_name '%s' to user %s", display_name, user.user_id)
        except Exception:
            logger.exception("Failed to sync display_name to user (non-fatal)")

    @staticmethod
    def _run_matching(db: Session, provider_id: str, customer: Customer):
        """Run identity matching after creating a customer. Silent failures — never blocks creation."""
        try:
            from app.services.customer_matching_service import CustomerMatchingService
            matches = CustomerMatchingService.find_matches(db, provider_id, customer)
            if matches:
                CustomerMatchingService.process_matches(db, provider_id, customer, matches)
        except Exception:
            logger.exception("Identity matching failed for customer %s (non-blocking)", customer.customer_id)

    @staticmethod
    def get_customer(db: Session, customer_id: str) -> Customer | None:
        return db.query(Customer).filter(Customer.customer_id == customer_id).first()

    @staticmethod
    def get_customers_by_provider(db: Session, provider_id: str) -> list[Customer]:
        """Returns only primary (non-merged) customers."""
        return db.query(Customer).filter(
            Customer.provider_id == provider_id,
            Customer.merge_status == "primary",
        ).all()

    @staticmethod
    def find_by_email_and_provider(db: Session, provider_id: str, email: str) -> Customer | None:
        return db.query(Customer).filter(
            Customer.provider_id == provider_id,
            Customer.customer_email == email,
        ).first()

    @staticmethod
    def provider_can_view_customer_rating(db: Session, provider_id: str, customer_id: str) -> bool:
        """Privacy rule: customer rating is only visible to providers that have or had
        a real booking relationship with the customer, or have them on their waitlist.

        Allowed if ANY of:
          1. Active / upcoming booking (pending, confirmed, reschedule_requested)
          2. Any past completed booking with this provider
          3. Customer has an active waitlist entry at this provider
        """
        from app.models.booking import Booking
        from app.models.waitlist import WaitlistEntry

        # 1. Active / upcoming booking
        booked = (
            db.query(Booking.booking_id)
            .filter(
                Booking.provider_id == provider_id,
                Booking.customer_id == customer_id,
                Booking.status.in_(("pending", "confirmed", "reschedule_requested", "completed")),
            )
            .first()
        )
        if booked:
            return True

        # 2. Waitlist entry (active)
        on_waitlist = (
            db.query(WaitlistEntry.id)
            .filter(
                WaitlistEntry.provider_id == provider_id,
                WaitlistEntry.customer_id == customer_id,
                WaitlistEntry.status == "active",
            )
            .first()
        )
        return on_waitlist is not None



    @staticmethod
    def get_customer_profile(db: Session, customer_id: str, provider_id: str) -> dict | None:
        """
        Dynamic customer profile — returns rich or minimal data depending on what exists.
        This is the 'dynamic UI' data source.
        """
        customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
        if not customer:
            return None

        # Follow merge chain if needed
        if customer.merge_status == "merged" and customer.merged_into_id:
            customer = db.query(Customer).filter(Customer.customer_id == customer.merged_into_id).first()
            if not customer:
                return None

        from app.models.booking import Booking
        from app.services.customer_preference_service import CustomerPreferenceService

        # Booking stats
        bookings = db.query(Booking).filter(Booking.customer_id == customer.customer_id).all()
        completed = [b for b in bookings if b.status == "completed"]
        total_spend = sum(b.total_amount_inc_vat for b in completed)

        # Preferences (approved only for provider view)
        pref_summary = CustomerPreferenceService.get_preferences_summary(db, customer.customer_id, provider_id)

        # Channels this customer has used
        channels = set()
        if customer.source_channel:
            channels.add(customer.source_channel)
        for b in bookings:
            if b.is_walkin:
                channels.add("walkin")

        from app.models.instagram_identity import InstagramIdentity
        ig_count = db.query(InstagramIdentity).filter(
            InstagramIdentity.customer_id == customer.customer_id,
        ).count()
        if ig_count > 0:
            channels.add("instagram_dm")
        can_view_reliability = CustomerService.provider_can_view_customer_rating(
            db,
            provider_id=provider_id,
            customer_id=customer.customer_id,
        )

        reliability_payload = None
        if can_view_reliability:
            reliability = CustomerReliabilityService.calculate_for_customer(db, customer.customer_id, window_days=180)
            reliability_payload = {
                "score": float(reliability.get("reliability_score", 0.0)),
                "tier": str(reliability.get("reliability_tier", "new")),
                "confidence": float(reliability.get("confidence", 0.0)),
                "breakdown": reliability.get("breakdown", {}),
                "anonymous_reports_count": int(reliability.get("signals", {}).get("anonymous_reports_count", 0)),
            }

        return {
            "customer_id": customer.customer_id,
            "display_name": customer.display_name or customer.instagram_username_snapshot or customer.customer_email or f"Customer #{customer.customer_number}",
            "email": customer.customer_email,
            "phone": customer.phone,
            "instagram": customer.instagram_username_snapshot,
            "source_channel": customer.source_channel,
            "channels": sorted(channels),
            "customer_number": customer.customer_number,
            "created_at": customer.created_at.isoformat(),
            "stats": {
                "total_bookings": len(bookings),
                "completed_bookings": len(completed),
                "total_spend": round(total_spend, 2),
                "last_visit": max((b.scheduled_start for b in completed), default=None),
            },
            "preferences": pref_summary,
            "reliability": reliability_payload,
        }
