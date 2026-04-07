from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.customer import Customer
from app.models.loyalty_event import LoyaltyEvent
from app.models.subscription import Subscription

logger = logging.getLogger(__name__)


EVENT_POINTS: dict[str, int] = {
    "booking_completed": 40,
    "referral_booking_completed": 60,
    "provider_active_month": 35,
    "meaningful_search": 2,
    "follow_provider": 1,
    "add_favorite_provider": 2,
    "invite_friend": 5,
}

# Daily cap is applied by event type and actor.
DAILY_POINTS_CAP: dict[str, int] = {
    "meaningful_search": 10,
    "follow_provider": 10,
    "add_favorite_provider": 10,
    "invite_friend": 20,
}

TIER_THRESHOLDS = {
    "silver": {"score": 120, "completed_bookings": 2},
    "gold": {"score": 450, "completed_bookings": 8},
    "vip": {"score": 1200, "completed_bookings": 25},
}


@dataclass
class LoyaltySnapshot:
    actor_type: str
    actor_id: str
    score: int
    tier: str
    level_badge: str
    completed_bookings: int
    completed_referrals: int


class LoyaltyService:
    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _event_points(event_type: str) -> int:
        return int(EVENT_POINTS.get(event_type, 0))

    @staticmethod
    def _day_window(now: datetime) -> tuple[datetime, datetime]:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return start, end

    @staticmethod
    def _daily_points_for_event(
        db: Session,
        *,
        actor_type: str,
        actor_id: str,
        event_type: str,
        now: datetime,
    ) -> int:
        start, end = LoyaltyService._day_window(now)
        total = (
            db.query(func.coalesce(func.sum(LoyaltyEvent.points), 0))
            .filter(
                LoyaltyEvent.actor_type == actor_type,
                LoyaltyEvent.actor_id == actor_id,
                LoyaltyEvent.event_type == event_type,
                LoyaltyEvent.occurred_at >= start,
                LoyaltyEvent.occurred_at < end,
            )
            .scalar()
        )
        return int(total or 0)

    @staticmethod
    def record_event(
        db: Session,
        *,
        actor_type: str,
        actor_id: str,
        event_type: str,
        source: str | None = None,
        metadata: dict | None = None,
        unique_event_key: str | None = None,
        occurred_at: datetime | None = None,
    ) -> bool:
        if actor_type not in {"customer", "provider"}:
            return False
        if not actor_id:
            return False

        points = LoyaltyService._event_points(event_type)
        if points <= 0:
            return False

        now = occurred_at or LoyaltyService._utcnow()

        # Idempotency guard before insert.
        if unique_event_key:
            existing = (
                db.query(LoyaltyEvent.event_id)
                .filter(LoyaltyEvent.unique_event_key == unique_event_key)
                .first()
            )
            if existing:
                return False

        # Anti-gaming daily caps for low-weight engagement events.
        cap = DAILY_POINTS_CAP.get(event_type)
        if cap is not None:
            already = LoyaltyService._daily_points_for_event(
                db,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type=event_type,
                now=now,
            )
            if already >= cap:
                return False
            remaining = max(cap - already, 0)
            points = min(points, remaining)
            if points <= 0:
                return False

        event = LoyaltyEvent(
            actor_type=actor_type,
            actor_id=actor_id,
            event_type=event_type,
            points=points,
            source=source,
            metadata_json=json.dumps(metadata or {}),
            unique_event_key=unique_event_key,
            occurred_at=now,
        )
        db.add(event)

        try:
            db.commit()
            return True
        except IntegrityError:
            db.rollback()
            return False
        except Exception:
            db.rollback()
            logger.exception(
                "loyalty.record_event failed actor_type=%s actor_id=%s event_type=%s",
                actor_type,
                actor_id,
                event_type,
            )
            return False

    @staticmethod
    def _customer_completed_bookings(db: Session, user_id: str) -> int:
        customer_ids = (
            db.query(Customer.customer_id)
            .filter(Customer.user_id == user_id)
            .all()
        )
        ids = [c.customer_id for c in customer_ids]
        if not ids:
            return 0
        total = (
            db.query(func.count(Booking.booking_id))
            .filter(
                Booking.customer_id.in_(ids),
                Booking.status == "completed",
            )
            .scalar()
        )
        return int(total or 0)

    @staticmethod
    def _customer_completed_referrals(db: Session, user_id: str) -> int:
        customer_ids = (
            db.query(Customer.customer_id)
            .filter(Customer.user_id == user_id)
            .all()
        )
        ids = [c.customer_id for c in customer_ids]
        if not ids:
            return 0
        total = (
            db.query(func.count(Booking.booking_id))
            .filter(
                Booking.customer_id.in_(ids),
                Booking.status == "completed",
                Booking.referral_source == "provider_link",
            )
            .scalar()
        )
        return int(total or 0)

    @staticmethod
    def _provider_completed_bookings(db: Session, provider_id: str) -> int:
        total = (
            db.query(func.count(Booking.booking_id))
            .filter(
                Booking.provider_id == provider_id,
                Booking.status == "completed",
            )
            .scalar()
        )
        return int(total or 0)

    @staticmethod
    def _provider_completed_referrals(db: Session, provider_id: str) -> int:
        total = (
            db.query(func.count(Booking.booking_id))
            .filter(
                Booking.provider_id == provider_id,
                Booking.status == "completed",
                Booking.referral_source == "provider_link",
            )
            .scalar()
        )
        return int(total or 0)

    @staticmethod
    def _resolve_tier(score: int, completed_bookings: int) -> str:
        if (
            score >= TIER_THRESHOLDS["vip"]["score"]
            and completed_bookings >= TIER_THRESHOLDS["vip"]["completed_bookings"]
        ):
            return "vip"
        if (
            score >= TIER_THRESHOLDS["gold"]["score"]
            and completed_bookings >= TIER_THRESHOLDS["gold"]["completed_bookings"]
        ):
            return "gold"
        if (
            score >= TIER_THRESHOLDS["silver"]["score"]
            and completed_bookings >= TIER_THRESHOLDS["silver"]["completed_bookings"]
        ):
            return "silver"
        return "member"

    @staticmethod
    def _tier_badge(tier: str) -> str:
        lookup = {
            "member": "Member",
            "silver": "Silver",
            "gold": "Gold",
            "vip": "VIP",
        }
        return lookup.get((tier or "member").lower(), "Member")

    @staticmethod
    def get_actor_snapshot(db: Session, *, actor_type: str, actor_id: str) -> LoyaltySnapshot:
        if actor_type not in {"customer", "provider"} or not actor_id:
            return LoyaltySnapshot(
                actor_type=actor_type,
                actor_id=actor_id,
                score=0,
                tier="member",
                level_badge="Member",
                completed_bookings=0,
                completed_referrals=0,
            )

        window_start = LoyaltyService._utcnow() - timedelta(days=365)
        score_total = (
            db.query(func.coalesce(func.sum(LoyaltyEvent.points), 0))
            .filter(
                LoyaltyEvent.actor_type == actor_type,
                LoyaltyEvent.actor_id == actor_id,
                LoyaltyEvent.occurred_at >= window_start,
            )
            .scalar()
        )
        score = int(score_total or 0)

        if actor_type == "provider":
            completed_bookings = LoyaltyService._provider_completed_bookings(db, actor_id)
            completed_referrals = LoyaltyService._provider_completed_referrals(db, actor_id)
        else:
            completed_bookings = LoyaltyService._customer_completed_bookings(db, actor_id)
            completed_referrals = LoyaltyService._customer_completed_referrals(db, actor_id)

        tier = LoyaltyService._resolve_tier(score, completed_bookings)
        return LoyaltySnapshot(
            actor_type=actor_type,
            actor_id=actor_id,
            score=score,
            tier=tier,
            level_badge=LoyaltyService._tier_badge(tier),
            completed_bookings=completed_bookings,
            completed_referrals=completed_referrals,
        )

    @staticmethod
    def track_completed_booking(db: Session, booking: Booking) -> None:
        # Provider completion event
        LoyaltyService.record_event(
            db,
            actor_type="provider",
            actor_id=booking.provider_id,
            event_type="booking_completed",
            source="booking_status",
            metadata={"booking_id": booking.booking_id},
            unique_event_key=f"booking_completed:provider:{booking.booking_id}",
        )

        # Extra provider reward for referred booking completion
        if (booking.referral_source or "").strip().lower() == "provider_link":
            LoyaltyService.record_event(
                db,
                actor_type="provider",
                actor_id=booking.provider_id,
                event_type="referral_booking_completed",
                source="referral",
                metadata={"booking_id": booking.booking_id},
                unique_event_key=f"referral_booking_completed:provider:{booking.booking_id}",
            )

        # Customer completion event (if account-linked)
        customer = (
            db.query(Customer)
            .filter(Customer.customer_id == booking.customer_id)
            .first()
        )
        if customer and customer.user_id:
            LoyaltyService.record_event(
                db,
                actor_type="customer",
                actor_id=customer.user_id,
                event_type="booking_completed",
                source="booking_status",
                metadata={"booking_id": booking.booking_id},
                unique_event_key=f"booking_completed:customer:{booking.booking_id}",
            )

    @staticmethod
    def track_follow_provider(db: Session, *, customer_user_id: str, provider_id: str) -> None:
        LoyaltyService.record_event(
            db,
            actor_type="customer",
            actor_id=customer_user_id,
            event_type="follow_provider",
            source="provider_profile",
            metadata={"provider_id": provider_id},
        )

    @staticmethod
    def track_favorite_provider_additions(
        db: Session,
        *,
        customer_user_id: str,
        provider_ids: list[str],
    ) -> None:
        if not provider_ids:
            return
        for provider_id in provider_ids:
            LoyaltyService.record_event(
                db,
                actor_type="customer",
                actor_id=customer_user_id,
                event_type="add_favorite_provider",
                source="customer_settings",
                metadata={"provider_id": provider_id},
                unique_event_key=f"favorite_provider_added:{customer_user_id}:{provider_id}",
            )

    @staticmethod
    def track_meaningful_search(
        db: Session,
        *,
        customer_user_id: str,
        prompt: str,
        result_count: int,
    ) -> None:
        text = (prompt or "").strip()
        if len(text) < 8 or result_count <= 0:
            return

        day_key = LoyaltyService._utcnow().strftime("%Y%m%d")
        query_hash = hashlib.sha1(text.lower().encode("utf-8")).hexdigest()[:10]
        unique_key = f"meaningful_search:{customer_user_id}:{day_key}:{query_hash}"
        LoyaltyService.record_event(
            db,
            actor_type="customer",
            actor_id=customer_user_id,
            event_type="meaningful_search",
            source="search_feed",
            metadata={"query_len": len(text), "result_count": int(result_count)},
            unique_event_key=unique_key,
        )

    @staticmethod
    def award_provider_active_month_if_eligible(db: Session, provider_id: str) -> None:
        now = LoyaltyService._utcnow()
        sub = (
            db.query(Subscription)
            .filter(Subscription.provider_id == provider_id)
            .first()
        )
        if not sub:
            return
        if sub.status not in {"active", "trialing"}:
            return
        if sub.current_period_end and sub.current_period_end < now:
            return

        month_key = now.strftime("%Y-%m")
        LoyaltyService.record_event(
            db,
            actor_type="provider",
            actor_id=provider_id,
            event_type="provider_active_month",
            source="subscription",
            metadata={"month": month_key, "plan_id": sub.plan_id},
            unique_event_key=f"provider_active_month:{provider_id}:{month_key}",
        )
