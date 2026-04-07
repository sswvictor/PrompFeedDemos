"""
Subscription & Bot Settings API

Routes:
    GET    /api/v1/plans                       — list available plans
    GET    /api/v1/subscription                — provider's current subscription
    POST   /api/v1/subscription/checkout       — create Stripe checkout session
    POST   /api/v1/subscription/portal         — create Stripe customer portal session
    POST   /api/v1/webhooks/stripe             — Stripe webhook handler

    GET    /api/v1/bot-settings                — get bot settings (with defaults)
    PUT    /api/v1/bot-settings                — update bot settings (Pro only)
    DELETE /api/v1/bot-settings                — reset to platform defaults (Pro only)
"""
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.services.subscription_service import SubscriptionService
from app.services.bot_settings_service import BotSettingsService

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic schemas ─────────────────────────────────────────

class PlanOut(BaseModel):
    plan_id: str
    name: str
    price_sek: int
    stripe_price_id: str | None
    features: list[str]
    is_active: bool

    model_config = {"from_attributes": True}


class SubscriptionOut(BaseModel):
    subscription_id: str
    provider_id: str
    plan_id: str
    status: str
    is_pro: bool
    stripe_customer_id: str | None = None
    current_period_end: str | None = None   # ISO string

    model_config = {"from_attributes": True}


class CheckoutIn(BaseModel):
    provider_id: str
    success_url: str
    cancel_url: str


class PortalIn(BaseModel):
    provider_id: str
    return_url: str


class CheckoutOut(BaseModel):
    checkout_url: str


class BotSettingsIn(BaseModel):
    bot_name: str | None = None
    tone: str | None = None                          # friendly | formal | casual
    language: str | None = None                      # auto | sv | en
    custom_welcome_message: str | None = None
    auto_confirm_bookings: bool | None = None
    out_of_hours_behavior: str | None = None         # show_hours | send_link
    max_advance_booking_days: int | None = None


class BotSettingsOut(BaseModel):
    provider_id: str
    bot_name: str | None
    tone: str
    language: str
    custom_welcome_message: str | None
    auto_confirm_bookings: bool
    out_of_hours_behavior: str
    max_advance_booking_days: int | None
    is_pro: bool           # whether the provider currently has Pro
    updated_at: str | None = None


# ── Plan routes ──────────────────────────────────────────────

@router.get("/plans", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db)):
    """List all active subscription plans."""
    plans = SubscriptionService.get_plans(db)
    return [
        PlanOut(
            plan_id=p.plan_id,
            name=p.name,
            price_sek=p.price_sek,
            stripe_price_id=p.stripe_price_id,
            features=p.features,
            is_active=p.is_active,
        )
        for p in plans
    ]


# ── Subscription routes ──────────────────────────────────────

@router.get("/subscription", response_model=SubscriptionOut)
def get_subscription(provider_id: str, db: Session = Depends(get_db)):
    """Get the provider's current subscription (creates free tier if none exists)."""
    sub = SubscriptionService.get_or_create_free(db, provider_id)
    return SubscriptionOut(
        subscription_id=sub.subscription_id,
        provider_id=sub.provider_id,
        plan_id=sub.plan_id,
        status=sub.status,
        is_pro=sub.is_pro,
        stripe_customer_id=sub.stripe_customer_id,
        current_period_end=(
            sub.current_period_end.isoformat() if sub.current_period_end else None
        ),
    )


@router.post("/subscription/checkout", response_model=CheckoutOut)
def create_checkout(payload: CheckoutIn, db: Session = Depends(get_db)):
    """Create a Stripe Checkout session for upgrading to Pro."""
    if SubscriptionService.is_pro(db, payload.provider_id):
        raise HTTPException(status_code=400, detail="Provider is already on Pro plan")

    try:
        url = SubscriptionService.create_checkout_session(
            db=db,
            provider_id=payload.provider_id,
            success_url=payload.success_url,
            cancel_url=payload.cancel_url,
        )
        return CheckoutOut(checkout_url=url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/subscription/portal", response_model=CheckoutOut)
def create_portal(payload: PortalIn, db: Session = Depends(get_db)):
    """Create a Stripe Customer Portal session to manage billing."""
    try:
        url = SubscriptionService.create_portal_session(
            db=db,
            provider_id=payload.provider_id,
            return_url=payload.return_url,
        )
        return CheckoutOut(checkout_url=url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Stripe webhook ────────────────────────────────────────────

@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_db),
):
    """Receive and process Stripe webhook events.

    Verifies the signature using STRIPE_WEBHOOK_SECRET, then delegates
    to SubscriptionService.handle_stripe_event().
    """
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    raw_body = await request.body()

    # Verify signature (skip if no webhook secret — local dev)
    if settings.STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(
                raw_body, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
            )
        except stripe.error.SignatureVerificationError:
            logger.warning("Invalid Stripe webhook signature")
            raise HTTPException(status_code=400, detail="Invalid signature")
    else:
        import json
        event = json.loads(raw_body)

    try:
        SubscriptionService.handle_stripe_event(db, event)
    except Exception as e:
        logger.exception("Error handling Stripe event %s", event.get("type"))
        raise HTTPException(status_code=500, detail=str(e))

    return {"received": True}


# ── Bot settings routes ───────────────────────────────────────

def _require_pro(db: Session, provider_id: str) -> None:
    """Raise 403 with upgrade prompt if provider is not on Pro."""
    if not SubscriptionService.is_pro(db, provider_id):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Bot personalisation is a Pro feature.",
                "requires_plan": "pro",
            },
        )


@router.get("/bot-settings", response_model=BotSettingsOut)
def get_bot_settings(provider_id: str, db: Session = Depends(get_db)):
    """Get bot settings. Returns platform defaults for non-Pro providers."""
    s = BotSettingsService.get_settings_dict(db, provider_id)
    is_pro = SubscriptionService.is_pro(db, provider_id)
    return BotSettingsOut(
        provider_id=provider_id,
        bot_name=s["bot_name"],
        tone=s["tone"],
        language=s["language"],
        custom_welcome_message=s["custom_welcome_message"],
        auto_confirm_bookings=s["auto_confirm_bookings"],
        out_of_hours_behavior=s["out_of_hours_behavior"],
        max_advance_booking_days=s["max_advance_booking_days"],
        is_pro=is_pro,
        updated_at=s.get("updated_at").isoformat() if s.get("updated_at") else None,
    )


@router.put("/bot-settings", response_model=BotSettingsOut)
def update_bot_settings(
    provider_id: str,
    payload: BotSettingsIn,
    db: Session = Depends(get_db),
):
    """Update bot settings. Requires active Pro subscription."""
    _require_pro(db, provider_id)

    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    try:
        row = BotSettingsService.update_settings(db, provider_id, updates)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return BotSettingsOut(
        provider_id=row.provider_id,
        bot_name=row.bot_name,
        tone=row.tone,
        language=row.language,
        custom_welcome_message=row.custom_welcome_message,
        auto_confirm_bookings=row.auto_confirm_bookings,
        out_of_hours_behavior=row.out_of_hours_behavior,
        max_advance_booking_days=row.max_advance_booking_days,
        is_pro=True,
        updated_at=row.updated_at.isoformat(),
    )


@router.delete("/bot-settings", status_code=204)
def reset_bot_settings(provider_id: str, db: Session = Depends(get_db)):
    """Reset bot settings to platform defaults. Requires active Pro subscription."""
    _require_pro(db, provider_id)
    BotSettingsService.reset_to_defaults(db, provider_id)
