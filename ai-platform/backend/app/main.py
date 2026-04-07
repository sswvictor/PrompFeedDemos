import asyncio
import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.amenities import router as amenities_router
from app.api.calendar import router as calendar_router
from app.api.chat import router as chat_router
from app.api.customer_auth import router as customer_auth_router
from app.api.customer_dashboard import router as customer_dashboard_router
from app.api.customer_gdpr import router as customer_gdpr_router
from app.api.demo_provider import router as demo_provider_router
from app.api.feed import router as feed_router
from app.api.home_dashboard import router as home_router, providers_router as home_providers_router
from app.api.onboarding import router as onboarding_router
from app.api.provider_auth import router as provider_auth_router
from app.api.provider_follow import router as provider_follow_router
from app.api.provider_links import router as provider_links_router
from app.api.provider_settings import router as provider_settings_router
from app.api.provider_calendar import router as provider_calendar_router
from app.api.routes import router
from app.api.salon_links import router as salon_links_router
from app.api.setup import router as setup_router
from app.api.inbox import router as inbox_router
from app.api.instagram_connect import router as instagram_connect_router
from app.api.intelligence import router as intelligence_router
from app.api.admin import router as admin_router
from app.api.admin_reports import router as admin_reports_router
from app.api.subscription import router as subscription_router
from app.api.waitlist import router as waitlist_router
from app.api.loyalty import router as loyalty_router
from app.api.push_token import router as push_token_router
from app.api.finance import router as finance_router
from app.api.provider_ai_command import router as provider_ai_command_router
from app.db.bootstrap import main as db_bootstrap
from app.db.session import SessionLocal
from app.services.platform_instagram_bootstrap import ensure_platform_instagram_page_from_env
from app.services.referral_service import ReferralService

logger = logging.getLogger(__name__)

app = FastAPI(title="Fixmeapp Booking Logic", version="1.0.0")
app.include_router(router, prefix="/api/v1")
app.include_router(onboarding_router, prefix="/api/v1")
app.include_router(salon_links_router, prefix="/api/v1")
app.include_router(home_router, prefix="/api/v1")
app.include_router(home_providers_router, prefix="/api/v1")
app.include_router(feed_router, prefix="/api/v1")
app.include_router(subscription_router, prefix="/api/v1")
app.include_router(calendar_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(customer_auth_router, prefix="/api/v1")
app.include_router(provider_auth_router, prefix="/api/v1")
app.include_router(amenities_router, prefix="/api/v1")
app.include_router(provider_links_router, prefix="/api/v1")
app.include_router(provider_settings_router, prefix="/api/v1")
app.include_router(provider_calendar_router, prefix="/api/v1")
app.include_router(customer_dashboard_router, prefix="/api/v1")
app.include_router(customer_gdpr_router, prefix="/api/v1")
app.include_router(waitlist_router, prefix="/api/v1")
app.include_router(demo_provider_router, prefix="/api/v1")
app.include_router(provider_follow_router, prefix="/api/v1")
app.include_router(setup_router, prefix="/api/v1")
app.include_router(inbox_router, prefix="/api/v1")
app.include_router(instagram_connect_router, prefix="/api/v1")
app.include_router(intelligence_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(admin_reports_router, prefix="/api/v1")
app.include_router(loyalty_router, prefix="/api/v1")
app.include_router(push_token_router, prefix="/api/v1")
app.include_router(finance_router, prefix="/api/v1")
app.include_router(provider_ai_command_router, prefix="/api/v1")

STATIC_DIR = Path(__file__).parent.parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

WAITLIST_EXPIRE_INTERVAL = 60
CALENDAR_SYNC_INTERVAL = 60  # seconds between sync worker runs
REMINDER_CHECK_INTERVAL = 15 * 60  # 15 minutes â€” tight enough to catch each window once
WEB_BOOKING_BASE_URL = os.getenv("WEB_BOOKING_BASE_URL", "http://127.0.0.1:5174").rstrip("/")
waitlist_expiry_task: asyncio.Task | None = None
calendar_sync_task: asyncio.Task | None = None
reminder_task: asyncio.Task | None = None


def _startup_bootstrap_enabled() -> bool:
    return os.getenv("FIXMEAPP_SKIP_STARTUP_BOOTSTRAP", "0").lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }


async def _waitlist_expiry_loop() -> None:
    """Background loop that expires stale waitlist offers."""
    from app.services.waitlist_service import WaitlistService

    while True:
        await asyncio.sleep(WAITLIST_EXPIRE_INTERVAL)
        db = SessionLocal()
        try:
            expired = WaitlistService.expire_stale_offers(db)
            if expired:
                logger.info("Waitlist expiry: expired %d stale offer(s)", expired)
        except Exception:
            logger.exception("Waitlist expiry loop error (will retry)")
        finally:
            db.close()


async def _calendar_sync_loop() -> None:
    """Background loop that processes queued Google Calendar sync jobs."""
    from datetime import datetime as _dt
    from app.integrations.google_calendar import calendar_adapter  # noqa: F401 â€” ensure adapter is importable
    from app.models.provider_calendar_connection import ProviderCalendarConnection
    from app.models.sync_job import SyncJob
    from app.services.calendar_sync_service import CalendarSyncService

    while True:
        await asyncio.sleep(CALENDAR_SYNC_INTERVAL)
        db = SessionLocal()
        try:
            now = _dt.utcnow()
            connections = (
                db.query(ProviderCalendarConnection)
                .filter(
                    ProviderCalendarConnection.connector == "google",
                    ProviderCalendarConnection.sync_enabled.is_(True),
                )
                .all()
            )
            for conn in connections:
                has_work = (
                    db.query(SyncJob)
                    .filter(
                        SyncJob.connection_id == conn.connection_id,
                        SyncJob.status == "queued",
                        SyncJob.next_run_at <= now,
                    )
                    .first()
                )
                if not has_work:
                    continue
                try:
                    stats = CalendarSyncService.sync_google_connection(db, conn)
                    # Mark all queued jobs for this connection as done
                    db.query(SyncJob).filter(
                        SyncJob.connection_id == conn.connection_id,
                        SyncJob.status == "queued",
                    ).update({"status": "done"})
                    db.commit()
                    logger.info(
                        "Calendar sync: conn=%s created=%d updated=%d deleted=%d failed=%d",
                        conn.connection_id,
                        stats["created"],
                        stats["updated"],
                        stats["deleted"],
                        stats["failed"],
                    )
                except Exception:
                    logger.exception("Calendar sync error for connection %s", conn.connection_id)
        except Exception:
            logger.exception("Calendar sync loop error (will retry)")
        finally:
            db.close()


async def _booking_reminder_loop() -> None:
    """Background loop that sends 24h and 2h appointment reminder emails.

    Runs every 15 minutes. Uses a Â±5-minute window around each target horizon
    so each booking is caught by at most one run â€” no extra model/column needed.

    Windows:
      - 24h reminder: scheduled_start âˆˆ [now+23h55m, now+24h05m]
      -  2h reminder: scheduled_start âˆˆ [now+1h55m,  now+2h05m]
    """
    from datetime import timedelta, datetime as _dt
    from app.models.booking import Booking
    from app.models.customer import Customer
    from app.models.provider import Provider
    from app.services.email_service import EmailService

    while True:
        await asyncio.sleep(REMINDER_CHECK_INTERVAL)
        db = SessionLocal()
        try:
            now = _dt.utcnow()
            sent_24h = 0
            sent_2h = 0

            for horizon_hours, label in ((24, "24h"), (2, "2h")):
                window_center = now + timedelta(hours=horizon_hours)
                window_start = window_center - timedelta(minutes=5)
                window_end = window_center + timedelta(minutes=5)

                upcoming = (
                    db.query(Booking)
                    .filter(
                        Booking.scheduled_start >= window_start,
                        Booking.scheduled_start <= window_end,
                        Booking.status.in_(["pending", "confirmed"]),
                    )
                    .all()
                )

                for booking in upcoming:
                    try:
                        customer = db.query(Customer).filter(
                            Customer.customer_id == booking.customer_id
                        ).first()
                        provider = db.query(Provider).filter(
                            Provider.provider_id == booking.provider_id
                        ).first()
                        if not customer or not provider:
                            continue
                        email = (customer.customer_email or "").strip()
                        if not email:
                            continue
                        service_name = "Appointment"
                        if booking.line_items:
                            service_name = booking.line_items[0].service_type or "Appointment"
                        EmailService.send_booking_reminder(
                            to=email,
                            provider_name=provider.name,
                            booking_number=booking.booking_number,
                            service_name=service_name,
                            slot_date=booking.scheduled_start.strftime("%Y-%m-%d"),
                            slot_time=booking.scheduled_start.strftime("%H:%M"),
                            hours_until=horizon_hours,
                        )
                        if horizon_hours == 24:
                            sent_24h += 1
                        else:
                            sent_2h += 1
                    except Exception:
                        logger.exception("Reminder email failed for booking %s", booking.booking_id)

            if sent_24h or sent_2h:
                logger.info("Booking reminders: sent 24h=%d 2h=%d", sent_24h, sent_2h)
        except Exception:
            logger.exception("Booking reminder loop error (will retry)")
        finally:
            db.close()


def _run_referral_payout_startup_job() -> None:
    db = SessionLocal()
    try:
        result = ReferralService.run_scheduled_monthly_payouts_if_due(db)
        if result is None:
            logger.info("Referral payout scheduler: not due or disabled")
            return

        year, month, payouts = result
        if payouts:
            logger.info(
                "Referral payout scheduler: created %d payout row(s) for %d-%02d",
                len(payouts),
                year,
                month,
            )
        else:
            logger.info("Referral payout scheduler: already processed for %d-%02d", year, month)

        applied = ReferralService.apply_pending_subscription_credits(db, year, month)
        if applied:
            logger.info(
                "Referral payout scheduler: applied %d Stripe subscription credit(s) for %d-%02d",
                len(applied),
                year,
                month,
            )
    except Exception:
        logger.exception("Referral payout scheduler failed (startup continues)")
    finally:
        db.close()


@app.on_event("startup")
async def on_startup() -> None:
    if _startup_bootstrap_enabled():
        try:
            db_bootstrap()  # run migrations for local/dev startup paths that skip container bootstrap
            logger.info("DB bootstrap completed successfully.")
        except Exception as exc:
            logger.error("DB bootstrap failed: %s", exc, exc_info=True)
            strict_startup = os.getenv("STRICT_STARTUP_MIGRATIONS", "1").lower() not in {
                "0",
                "false",
                "no",
                "off",
            }
            if strict_startup:
                raise
    else:
        logger.info("Skipping startup DB bootstrap; container bootstrap already ran.")
    ensure_platform_instagram_page_from_env()
    _run_referral_payout_startup_job()
    global waitlist_expiry_task, calendar_sync_task, reminder_task
    waitlist_expiry_task = asyncio.create_task(_waitlist_expiry_loop())
    calendar_sync_task = asyncio.create_task(_calendar_sync_loop())
    reminder_task = asyncio.create_task(_booking_reminder_loop())
    logger.info("Calendar sync loop started (interval=%ds)", CALENDAR_SYNC_INTERVAL)
    logger.info("Booking reminder loop started (interval=%ds)", REMINDER_CHECK_INTERVAL)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    global waitlist_expiry_task, calendar_sync_task, reminder_task
    for task in (waitlist_expiry_task, calendar_sync_task, reminder_task):
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@app.get("/health")
@app.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/dashboard")
def legacy_dashboard_redirect():
    """Deprecated legacy dashboard endpoint: redirect to React provider home."""
    return RedirectResponse(url=f"{WEB_BOOKING_BASE_URL}/provider/home", status_code=307)


@app.get("/feed-explorer")
def serve_feed_explorer():
    return FileResponse(STATIC_DIR / "feed-explorer.html")
