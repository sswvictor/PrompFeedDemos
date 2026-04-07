"""
SubscriptionService — manages provider plans and Stripe billing.

Responsibilities:
  - Create/fetch subscriptions
  - Plan gate: is_pro() used by API routes and the orchestrator
  - Stripe checkout + portal session creation
  - Process inbound Stripe webhook events (subscription lifecycle)

Graceful downgrade policy:
  When a subscription lapses (status → "cancelled" / "past_due"),
  the bot continues running with platform defaults. The provider's
  custom bot settings row is preserved so they re-activate on renewal.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models.plan import Plan
from app.models.subscription import Subscription

logger = logging.getLogger(__name__)


class SubscriptionService:

    # ── Plan helpers ─────────────────────────────────────────

    @staticmethod
    def get_plans(db: Session) -> list[Plan]:
        return db.query(Plan).filter(Plan.is_active == True).order_by(Plan.price_sek).all()  # noqa: E712

    @staticmethod
    def get_plan(db: Session, plan_id: str) -> Plan | None:
        return db.query(Plan).filter(Plan.plan_id == plan_id).first()

    # ── Subscription CRUD ────────────────────────────────────

    @staticmethod
    def get_subscription(db: Session, provider_id: str) -> Subscription | None:
        return db.query(Subscription).filter(
            Subscription.provider_id == provider_id
        ).first()

    @staticmethod
    def get_or_create_free(db: Session, provider_id: str) -> Subscription:
        """Ensure every provider has at least a free subscription row."""
        sub = SubscriptionService.get_subscription(db, provider_id)
        if not sub:
            sub = Subscription(provider_id=provider_id, plan_id="free", status="active")
            db.add(sub)
            db.commit()
            db.refresh(sub)
        return sub

    @staticmethod
    def is_pro(db: Session, provider_id: str) -> bool:
        """True when the provider has an active Pro subscription."""
        sub = SubscriptionService.get_subscription(db, provider_id)
        return sub is not None and sub.is_pro

    # ── Stripe session helpers ────────────────────────────────

    @staticmethod
    def create_checkout_session(
        db: Session,
        provider_id: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """Create a Stripe Checkout session and return the session URL.

        If the provider already has a Stripe customer ID (from a previous
        subscription), it is reused so billing history is preserved.
        """
        if not settings.STRIPE_SECRET_KEY:
            raise ValueError("STRIPE_SECRET_KEY is not configured")
        if not settings.STRIPE_PRO_PRICE_ID:
            raise ValueError("STRIPE_PRO_PRICE_ID is not configured")

        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY

        sub = SubscriptionService.get_or_create_free(db, provider_id)

        session_params: dict = {
            "mode": "subscription",
            "line_items": [{"price": settings.STRIPE_PRO_PRICE_ID, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": {"provider_id": provider_id},
            "subscription_data": {"metadata": {"provider_id": provider_id}},
        }

        # Reuse existing Stripe customer if we have one
        if sub.stripe_customer_id:
            session_params["customer"] = sub.stripe_customer_id
        else:
            session_params["customer_creation"] = "always"

        checkout_session = stripe.checkout.Session.create(**session_params)
        return checkout_session.url

    @staticmethod
    def create_portal_session(
        db: Session,
        provider_id: str,
        return_url: str,
    ) -> str:
        """Create a Stripe Customer Portal session so providers can manage billing."""
        if not settings.STRIPE_SECRET_KEY:
            raise ValueError("STRIPE_SECRET_KEY is not configured")

        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY

        sub = SubscriptionService.get_subscription(db, provider_id)
        if not sub or not sub.stripe_customer_id:
            raise ValueError("No Stripe customer found — provider has never subscribed")

        portal = stripe.billing_portal.Session.create(
            customer=sub.stripe_customer_id,
            return_url=return_url,
        )
        return portal.url

    # ── Stripe webhook event processor ───────────────────────

    @staticmethod
    def handle_stripe_event(db: Session, event: dict) -> None:
        """Process a verified Stripe webhook event and update subscription state."""
        event_type = event.get("type", "")
        data = event.get("data", {}).get("object", {})

        logger.info("Stripe event: %s", event_type)

        if event_type in (
            "customer.subscription.created",
            "customer.subscription.updated",
        ):
            SubscriptionService._sync_stripe_subscription(db, data)

        elif event_type == "customer.subscription.deleted":
            SubscriptionService._cancel_subscription(db, data)

        elif event_type == "invoice.payment_failed":
            stripe_sub_id = data.get("subscription")
            if stripe_sub_id:
                sub = db.query(Subscription).filter(
                    Subscription.stripe_subscription_id == stripe_sub_id
                ).first()
                if sub:
                    sub.status = "past_due"
                    sub.updated_at = datetime.now(timezone.utc)
                    db.commit()
                    logger.info("Marked subscription past_due for provider %s", sub.provider_id)

        elif event_type == "invoice.payment_succeeded":
            stripe_sub_id = data.get("subscription")
            if stripe_sub_id:
                sub = db.query(Subscription).filter(
                    Subscription.stripe_subscription_id == stripe_sub_id
                ).first()
                if sub and sub.status == "past_due":
                    sub.status = "active"
                    sub.updated_at = datetime.now(timezone.utc)
                    db.commit()
                    logger.info("Reinstated subscription for provider %s", sub.provider_id)

    @staticmethod
    def _sync_stripe_subscription(db: Session, stripe_sub: dict) -> None:
        """Upsert our Subscription row from a Stripe subscription object."""
        stripe_sub_id = stripe_sub.get("id")
        stripe_customer_id = stripe_sub.get("customer")
        provider_id = (stripe_sub.get("metadata") or {}).get("provider_id")
        status = stripe_sub.get("status", "active")

        if not provider_id:
            logger.warning("Stripe subscription %s missing provider_id metadata", stripe_sub_id)
            return

        period_start = stripe_sub.get("current_period_start")
        period_end = stripe_sub.get("current_period_end")

        sub = SubscriptionService.get_or_create_free(db, provider_id)
        sub.plan_id = "pro"
        sub.status = status
        sub.stripe_customer_id = stripe_customer_id
        sub.stripe_subscription_id = stripe_sub_id
        if period_start:
            sub.current_period_start = datetime.fromtimestamp(period_start, tz=timezone.utc)
        if period_end:
            sub.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)
        sub.updated_at = datetime.now(timezone.utc)

        db.commit()
        logger.info("Synced Pro subscription for provider %s (status=%s)", provider_id, status)

    @staticmethod
    def _cancel_subscription(db: Session, stripe_sub: dict) -> None:
        """Graceful downgrade: status → cancelled, plan stays pro (shows what they had)."""
        stripe_sub_id = stripe_sub.get("id")
        sub = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub_id
        ).first()

        if sub:
            sub.status = "cancelled"
            sub.cancelled_at = datetime.now(timezone.utc)
            sub.updated_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(
                "Subscription cancelled for provider %s — graceful downgrade applied",
                sub.provider_id,
            )
