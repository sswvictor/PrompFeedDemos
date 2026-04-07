from __future__ import annotations

import logging
from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.booking import Booking
from app.models.referral_payout import ReferralPayout
from app.models.subscription import Subscription

logger = logging.getLogger(__name__)

PAID_STATUSES = ("paid", "credited")
PENDING_STATUSES = ("pending", "processing")


@dataclass
class ReferralSummary:
    total_completed_referrals: int
    completed_referrals_this_month: int
    credit_rate_sek: float
    earned_total_sek: float
    earned_this_month_sek: float
    paid_total_sek: float
    pending_payout_sek: float
    available_balance_sek: float
    last_paid_at_iso: str | None


class ReferralService:
    @staticmethod
    def _month_window(year: int, month: int) -> tuple[datetime, datetime]:
        start = datetime(year, month, 1)
        _, days = monthrange(year, month)
        end = datetime(year, month, days, 23, 59, 59, 999999)
        return start, end

    @staticmethod
    def _current_month_window(now: datetime | None = None) -> tuple[datetime, datetime]:
        now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        return ReferralService._month_window(now.year, now.month)

    @staticmethod
    def previous_month(now: datetime | None = None) -> tuple[int, int]:
        now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        year = now.year
        month = now.month - 1
        if month == 0:
            month = 12
            year -= 1
        return year, month

    @staticmethod
    def _sum_payout_amount(db: Session, provider_id: str, statuses: tuple[str, ...]) -> float:
        if not statuses:
            return 0.0
        total = (
            db.query(func.coalesce(func.sum(ReferralPayout.amount_sek), 0.0))
            .filter(
                ReferralPayout.provider_id == provider_id,
                ReferralPayout.status.in_(statuses),
            )
            .scalar()
        )
        return float(total or 0.0)

    @staticmethod
    def _target_period_exists(db: Session, year: int, month: int) -> bool:
        period_start, period_end = ReferralService._month_window(year, month)
        count = (
            db.query(func.count(ReferralPayout.payout_id))
            .filter(
                ReferralPayout.period_start == period_start,
                ReferralPayout.period_end == period_end,
            )
            .scalar()
        )
        return int(count or 0) > 0

    @staticmethod
    def get_provider_summary(db: Session, provider_id: str) -> ReferralSummary:
        credit_rate = float(settings.REFERRAL_CREDIT_SEK)

        total_completed = (
            db.query(func.count(Booking.booking_id))
            .filter(
                Booking.provider_id == provider_id,
                Booking.status == "completed",
                Booking.referral_source == "provider_link",
            )
            .scalar()
        ) or 0

        month_start, month_end = ReferralService._current_month_window()
        month_count = (
            db.query(func.count(Booking.booking_id))
            .filter(
                Booking.provider_id == provider_id,
                Booking.status == "completed",
                Booking.referral_source == "provider_link",
                Booking.scheduled_start >= month_start,
                Booking.scheduled_start <= month_end,
            )
            .scalar()
        ) or 0

        earned_total = round(float(total_completed) * credit_rate, 2)
        earned_month = round(float(month_count) * credit_rate, 2)

        paid_total = round(ReferralService._sum_payout_amount(db, provider_id, PAID_STATUSES), 2)
        pending_total = round(ReferralService._sum_payout_amount(db, provider_id, PENDING_STATUSES), 2)
        available = round(max(earned_total - paid_total - pending_total, 0.0), 2)

        last_paid = (
            db.query(func.max(ReferralPayout.processed_at))
            .filter(
                ReferralPayout.provider_id == provider_id,
                ReferralPayout.status.in_(PAID_STATUSES),
            )
            .scalar()
        )

        return ReferralSummary(
            total_completed_referrals=int(total_completed),
            completed_referrals_this_month=int(month_count),
            credit_rate_sek=credit_rate,
            earned_total_sek=earned_total,
            earned_this_month_sek=earned_month,
            paid_total_sek=paid_total,
            pending_payout_sek=pending_total,
            available_balance_sek=available,
            last_paid_at_iso=last_paid.isoformat() if last_paid else None,
        )

    @staticmethod
    def run_scheduled_monthly_payouts_if_due(
        db: Session,
        now: datetime | None = None,
    ) -> tuple[int, int, list[ReferralPayout]] | None:
        if not bool(settings.REFERRAL_AUTO_PAYOUT_ENABLED):
            return None

        now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        payout_day = int(settings.REFERRAL_PAYOUT_DAY or 1)
        payout_day = max(1, min(28, payout_day))
        if now.day < payout_day:
            return None

        year, month = ReferralService.previous_month(now)
        if ReferralService._target_period_exists(db, year, month):
            return year, month, []

        payouts = ReferralService.process_monthly_payouts(
            db=db,
            year=year,
            month=month,
            auto_mark_paid=bool(settings.REFERRAL_AUTO_MARK_PAID),
            dry_run=False,
        )
        return year, month, payouts

    @staticmethod
    def process_monthly_payouts(
        db: Session,
        year: int,
        month: int,
        auto_mark_paid: bool = False,
        dry_run: bool = False,
    ) -> list[ReferralPayout]:
        """Create one payout row per provider for completed referral bookings in a month.

        Idempotent by unique(provider_id, period_start, period_end).
        """
        period_start, period_end = ReferralService._month_window(year, month)
        credit_rate = float(settings.REFERRAL_CREDIT_SEK)

        grouped = (
            db.query(Booking.provider_id, func.count(Booking.booking_id).label("cnt"))
            .filter(
                Booking.status == "completed",
                Booking.referral_source == "provider_link",
                Booking.scheduled_start >= period_start,
                Booking.scheduled_start <= period_end,
            )
            .group_by(Booking.provider_id)
            .all()
        )

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        created: list[ReferralPayout] = []

        for row in grouped:
            provider_id = str(row.provider_id)
            credits_count = int(row.cnt or 0)
            if credits_count <= 0:
                continue

            exists = (
                db.query(ReferralPayout)
                .filter(
                    ReferralPayout.provider_id == provider_id,
                    ReferralPayout.period_start == period_start,
                    ReferralPayout.period_end == period_end,
                )
                .first()
            )
            if exists:
                continue

            amount = round(credits_count * credit_rate, 2)
            payout = ReferralPayout(
                provider_id=provider_id,
                period_start=period_start,
                period_end=period_end,
                credits_count=credits_count,
                amount_sek=amount,
                currency="SEK",
                status="paid" if auto_mark_paid else "pending",
                auto_processed=True,
                processed_at=now_utc if auto_mark_paid else None,
                notes="Automated monthly referral payout",
            )
            created.append(payout)
            db.add(payout)

        if dry_run:
            db.rollback()
            return created

        try:
            db.commit()
        except IntegrityError:
            # Multiple replicas may run startup jobs concurrently. Unique constraint keeps writes safe.
            db.rollback()
            return (
                db.query(ReferralPayout)
                .filter(
                    ReferralPayout.period_start == period_start,
                    ReferralPayout.period_end == period_end,
                )
                .all()
            )

        for payout in created:
            db.refresh(payout)
        return created

    @staticmethod
    def apply_pending_subscription_credits(
        db: Session,
        year: int,
        month: int,
    ) -> list[ReferralPayout]:
        """Apply pending payouts for a month as Stripe customer credits for subscription billing."""
        if not bool(settings.REFERRAL_AUTO_APPLY_TO_SUBSCRIPTION):
            return []
        if not settings.STRIPE_SECRET_KEY:
            logger.info("Referral credits: Stripe not configured, leaving payouts pending")
            return []

        import stripe

        stripe.api_key = settings.STRIPE_SECRET_KEY
        period_start, period_end = ReferralService._month_window(year, month)

        pending = (
            db.query(ReferralPayout)
            .filter(
                ReferralPayout.period_start == period_start,
                ReferralPayout.period_end == period_end,
                ReferralPayout.status.in_(PENDING_STATUSES),
            )
            .all()
        )

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        applied: list[ReferralPayout] = []

        for payout in pending:
            sub = (
                db.query(Subscription)
                .filter(Subscription.provider_id == payout.provider_id)
                .first()
            )
            if not sub or not sub.stripe_customer_id:
                continue

            amount_minor = int(round(float(payout.amount_sek or 0.0) * 100))
            if amount_minor <= 0:
                continue

            try:
                tx = stripe.CustomerBalanceTransaction.create(
                    customer=sub.stripe_customer_id,
                    amount=-amount_minor,
                    currency=(payout.currency or "SEK").lower(),
                    description=f"Fixmeapp referral credit {year}-{month:02d}",
                    metadata={
                        "provider_id": str(payout.provider_id),
                        "payout_id": str(payout.payout_id),
                        "period": f"{year}-{month:02d}",
                    },
                )
            except Exception:
                logger.exception(
                    "Referral credit Stripe apply failed provider=%s payout=%s",
                    payout.provider_id,
                    payout.payout_id,
                )
                continue

            payout.status = "credited"
            payout.processed_at = now_utc
            payout.external_transfer_id = tx.get("id") if isinstance(tx, dict) else getattr(tx, "id", None)
            payout.notes = "Applied to Stripe subscription credit balance"
            applied.append(payout)

        if applied:
            db.commit()
            for payout in applied:
                db.refresh(payout)

        return applied
