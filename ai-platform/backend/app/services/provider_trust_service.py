from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math

from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.provider import Provider
from app.services.revisit_service import RevisitRateService


class ProviderTrustService:
    """Fair provider trust score that goes beyond ratings.

    Score dimensions (0-100):
    - experience: Bayesian-smoothed rating quality
    - reliability: punctuality and lateness behavior
    - retention: real revisit behavior from completed bookings
    """

    BASE_EXPERIENCE = 70.0
    BASE_RELIABILITY = 70.0
    BASE_RETENTION = 65.0

    @staticmethod
    def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
        return max(lo, min(hi, value))

    @staticmethod
    def _confidence(volume: int, target: int) -> float:
        if target <= 0:
            return 1.0
        # Smoothly approaches 1.0 as volume grows.
        return ProviderTrustService._clamp(math.log1p(max(volume, 0)) / math.log1p(target), 0.0, 1.0)

    @staticmethod
    def _bayesian_rating(observed_rating: float, observed_count: int, prior_mean: float = 4.2, prior_count: int = 12) -> float:
        r = observed_rating if observed_rating > 0 else prior_mean
        n = max(observed_count, 0)
        return ((n * r) + (prior_count * prior_mean)) / (n + prior_count)

    @staticmethod
    def _booking_late_minutes(booking: Booking) -> float | None:
        if booking.actual_start_time and booking.scheduled_start:
            delta = (booking.actual_start_time - booking.scheduled_start).total_seconds() / 60.0
            return max(0.0, delta)
        if booking.late_notification_minutes is not None:
            return max(0.0, float(booking.late_notification_minutes))
        return None

    @staticmethod
    def calculate_provider_trust(db: Session, provider_id: str, window_days: int = 90) -> dict:
        provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
        if not provider:
            raise ValueError(f"Provider {provider_id} not found")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        window_start = now - timedelta(days=window_days)

        # --- Experience (ratings) ---
        review_count = int(provider.review_count or 0)
        rating = float(provider.rating or 0.0)
        bayesian = ProviderTrustService._bayesian_rating(rating, review_count)
        experience_raw = ProviderTrustService._clamp((bayesian / 5.0) * 100.0)
        experience_conf = ProviderTrustService._confidence(review_count, target=80)
        experience_score = (experience_raw * experience_conf) + (ProviderTrustService.BASE_EXPERIENCE * (1 - experience_conf))

        # --- Retention (revisit) ---
        revisit = RevisitRateService.calculate_revisit_rate(db, provider_id)
        revisit_rate = float(revisit.get("revisit_rate", 0.0))
        returning_customers = int(revisit.get("returning_customers", 0))
        total_customers = int(revisit.get("total_customers", 0))
        total_completed = int(revisit.get("total_completed", 0))

        retention_raw = ProviderTrustService._clamp(revisit_rate * 100.0)
        retention_conf = ProviderTrustService._confidence(total_customers, target=60)
        retention_score = (retention_raw * retention_conf) + (ProviderTrustService.BASE_RETENTION * (1 - retention_conf))

        # --- Reliability (punctuality) ---
        reliability_bookings = (
            db.query(Booking)
            .filter(
                Booking.provider_id == provider_id,
                Booking.scheduled_start >= window_start,
                Booking.status.in_(["confirmed", "completed"]),
            )
            .all()
        )

        late_values: list[float] = []
        for booking in reliability_bookings:
            late = ProviderTrustService._booking_late_minutes(booking)
            if late is not None:
                late_values.append(late)

        punctual_events = len(late_values)
        on_time_events = sum(1 for mins in late_values if mins <= 5.0)
        on_time_rate = (on_time_events / punctual_events) if punctual_events > 0 else 0.75
        avg_late_minutes = (sum(late_values) / punctual_events) if punctual_events > 0 else 0.0

        lateness_penalty = min(40.0, avg_late_minutes * 1.8)
        reliability_raw = ProviderTrustService._clamp((on_time_rate * 100.0) - lateness_penalty + 10.0)
        reliability_conf = ProviderTrustService._confidence(punctual_events, target=40)
        reliability_score = (reliability_raw * reliability_conf) + (ProviderTrustService.BASE_RELIABILITY * (1 - reliability_conf))

        # --- Composite ---
        trust_score = (
            (0.30 * experience_score)
            + (0.35 * reliability_score)
            + (0.35 * retention_score)
        )
        trust_score = round(ProviderTrustService._clamp(trust_score), 1)

        if trust_score >= 85:
            trust_tier = "elite"
        elif trust_score >= 70:
            trust_tier = "strong"
        elif trust_score >= 55:
            trust_tier = "developing"
        else:
            trust_tier = "needs_attention"

        recommendations: list[str] = []
        if reliability_score < 70:
            recommendations.append("Improve punctuality and reduce late starts")
        if retention_score < 65:
            recommendations.append("Increase repeat visits with follow-up offers")
        if experience_score < 70:
            recommendations.append("Collect more verified reviews from completed visits")

        confidence = round((experience_conf + reliability_conf + retention_conf) / 3.0, 3)

        return {
            "provider_id": provider_id,
            "window_days": window_days,
            "trust_score": trust_score,
            "trust_tier": trust_tier,
            "confidence": confidence,
            "breakdown": {
                "experience": round(experience_score, 1),
                "reliability": round(reliability_score, 1),
                "retention": round(retention_score, 1),
            },
            "signals": {
                "rating": round(rating, 2),
                "review_count": review_count,
                "bayesian_rating": round(bayesian, 3),
                "revisit_rate": round(revisit_rate, 3),
                "returning_customers": returning_customers,
                "total_customers": total_customers,
                "total_completed_bookings": total_completed,
                "on_time_rate": round(on_time_rate, 3),
                "avg_late_minutes": round(avg_late_minutes, 2),
                "punctuality_events": punctual_events,
            },
            "recommendations": recommendations,
        }
