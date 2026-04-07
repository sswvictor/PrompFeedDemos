"""
RevisitRateService — Calculates provider trust signals from real booking data.

Revisit rate = percentage of customers who booked more than once.
This is THE key trust signal: can't be faked, calculated from actual behavior.

Called periodically (cron) or after each completed booking to update the provider.
"""
import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.provider import Provider

logger = logging.getLogger(__name__)


class RevisitRateService:

    @staticmethod
    def calculate_revisit_rate(db: Session, provider_id: str) -> dict:
        """
        Calculate revisit rate for a provider.

        Returns: {
            "revisit_rate": 0.72,         # 72% of customers came back
            "total_customers": 50,
            "returning_customers": 36,
            "total_completed": 120,
        }
        """
        # Count completed bookings per customer
        customer_booking_counts = (
            db.query(
                Booking.customer_id,
                func.count(Booking.booking_id).label("booking_count"),
            )
            .filter(
                Booking.provider_id == provider_id,
                Booking.status == "completed",
            )
            .group_by(Booking.customer_id)
            .all()
        )

        total_customers = len(customer_booking_counts)
        returning = sum(1 for _, count in customer_booking_counts if count >= 2)
        total_completed = sum(count for _, count in customer_booking_counts)

        rate = returning / total_customers if total_customers > 0 else 0.0

        return {
            "revisit_rate": round(rate, 2),
            "total_customers": total_customers,
            "returning_customers": returning,
            "total_completed": total_completed,
        }

    @staticmethod
    def update_provider_stats(db: Session, provider_id: str) -> Provider:
        """Calculate and persist revisit rate + total completed bookings on the provider."""
        provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
        if not provider:
            raise ValueError(f"Provider {provider_id} not found")

        stats = RevisitRateService.calculate_revisit_rate(db, provider_id)
        provider.revisit_rate = stats["revisit_rate"]
        provider.total_completed_bookings = stats["total_completed"]
        db.commit()
        db.refresh(provider)

        logger.info(
            "Updated stats for %s: revisit=%.0f%% (%d/%d customers), %d completed",
            provider.name, stats["revisit_rate"] * 100,
            stats["returning_customers"], stats["total_customers"],
            stats["total_completed"],
        )
        return provider

    @staticmethod
    def update_all_providers(db: Session):
        """Recalculate stats for all providers. Run as periodic job."""
        providers = db.query(Provider).all()
        for p in providers:
            try:
                RevisitRateService.update_provider_stats(db, p.provider_id)
            except Exception:
                logger.exception("Failed to update stats for provider %s", p.provider_id)
