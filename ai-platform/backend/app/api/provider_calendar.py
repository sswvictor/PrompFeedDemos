import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.api.auth import get_current_provider
from app.config import settings
from app.db.session import get_db
from app.models.booking import Booking
from app.models.provider_calendar_connection import ProviderCalendarConnection
from app.models.provider_time_block import ProviderTimeBlock
from app.services.availability_service import AvailabilityService
from app.services.calendar_sync_service import CalendarSyncService

router = APIRouter(prefix="/provider/calendar", tags=["provider-calendar"])


class CalendarConnectionOut(BaseModel):
    connection_id: str
    connector: str
    external_account_id: str | None = None
    external_calendar_id: str
    display_name: str | None = None
    sync_enabled: bool
    sync_direction: str
    last_synced_at: datetime | None = None
    last_error: str | None = None


class ConnectUrlOut(BaseModel):
    connector: str
    auth_url: str
    state: str


class QueueSyncOut(BaseModel):
    job_id: str
    status: str
    message: str


class OAuthCallbackIn(BaseModel):
    code: str
    state: str
    external_calendar_id: str = "primary"


class IcsLinkOut(BaseModel):
    connected: bool
    feed_url: str | None = None


class TimeBlockCreateIn(BaseModel):
    start_at: datetime
    end_at: datetime
    kind: str = "private"
    reason: str | None = None


class TimeBlockOut(BaseModel):
    block_id: str
    provider_id: str
    start_at: datetime
    end_at: datetime
    kind: str
    reason: str | None = None



def _to_connection_out(row: ProviderCalendarConnection) -> CalendarConnectionOut:
    return CalendarConnectionOut(
        connection_id=row.connection_id,
        connector=row.connector,
        external_account_id=row.external_account_id,
        external_calendar_id=row.external_calendar_id,
        display_name=row.display_name,
        sync_enabled=row.sync_enabled,
        sync_direction=row.sync_direction,
        last_synced_at=row.last_synced_at,
        last_error=row.last_error,
    )



def _to_time_block_out(row: ProviderTimeBlock) -> TimeBlockOut:
    return TimeBlockOut(
        block_id=row.block_id,
        provider_id=row.provider_id,
        start_at=row.start_at,
        end_at=row.end_at,
        kind=row.kind,
        reason=row.reason,
    )



def _build_ics_url(request: Request, provider_id: str, token: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/v1/provider/calendar/ics/{provider_id}/{token}.ics"


@router.get("/connections", response_model=list[CalendarConnectionOut])
def list_connections(
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    rows = CalendarSyncService.list_connections(db, provider_id)
    return [_to_connection_out(r) for r in rows if r.connector in ("google", "microsoft")]


@router.post("/google/connect-url", response_model=ConnectUrlOut)
def google_connect_url(provider_id: str = Depends(get_current_provider)):
    state = f"g_{provider_id[:8]}_{uuid.uuid4().hex[:12]}"
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar",
        "access_type": "offline",
        "prompt": "consent",   # always returns refresh_token
        "state": state,
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return ConnectUrlOut(connector="google", auth_url=auth_url, state=state)


@router.post("/microsoft/connect-url", response_model=ConnectUrlOut)
def microsoft_connect_url(provider_id: str = Depends(get_current_provider)):
    state = f"ms_{provider_id[:8]}_{uuid.uuid4().hex[:12]}"
    return ConnectUrlOut(
        connector="microsoft",
        auth_url=f"/api/v1/provider/calendar/microsoft/callback?state={state}&code=TODO",
        state=state,
    )


@router.post("/google/callback", response_model=CalendarConnectionOut)
def google_callback(
    payload: OAuthCallbackIn,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    # Exchange authorisation code for access + refresh tokens
    token_response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": payload.code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
    )
    if not token_response.is_success:
        raise HTTPException(
            status_code=400,
            detail=f"Google token exchange failed: {token_response.text}",
        )

    token_data = token_response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")   # only present with prompt=consent
    expires_in = token_data.get("expires_in", 3600)

    if not access_token:
        raise HTTPException(status_code=400, detail="No access_token in Google response")

    # Resolve the calendar summary and real calendar_id
    calendar_id = payload.external_calendar_id or "primary"
    display_name = "Google Calendar"
    try:
        cal_res = httpx.get(
            f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if cal_res.is_success:
            cal_data = cal_res.json()
            calendar_id = cal_data.get("id", calendar_id)
            display_name = cal_data.get("summary", display_name)
    except Exception:
        pass   # non-fatal — fall back to defaults

    # Get the provider's Google account email as external_account_id
    external_account_id = f"google-{provider_id[:8]}"
    try:
        userinfo = httpx.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo.is_success:
            external_account_id = userinfo.json().get("email", external_account_id)
    except Exception:
        pass

    token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    row = CalendarSyncService.upsert_connection(
        db=db,
        provider_id=provider_id,
        connector="google",
        external_account_id=external_account_id,
        external_calendar_id=calendar_id,
        display_name=display_name,
        access_token=access_token,
        refresh_token=refresh_token,
        token_expires_at=token_expires_at,
    )
    return _to_connection_out(row)


@router.post("/microsoft/callback", response_model=CalendarConnectionOut)
def microsoft_callback(
    payload: OAuthCallbackIn,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    row = CalendarSyncService.upsert_connection(
        db=db,
        provider_id=provider_id,
        connector="microsoft",
        external_account_id=payload.external_account_id,
        external_calendar_id=payload.external_calendar_id,
        display_name=payload.display_name,
    )
    return _to_connection_out(row)


@router.post("/connections/{connection_id}/disconnect", response_model=CalendarConnectionOut)
def disconnect_connection(
    connection_id: str,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    row = CalendarSyncService.disable_connection(db, provider_id, connection_id)
    if not row:
        raise HTTPException(status_code=404, detail="Connection not found")
    return _to_connection_out(row)


@router.post("/connections/{connection_id}/sync-now", response_model=QueueSyncOut)
def sync_now(
    connection_id: str,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    row = (
        db.query(ProviderCalendarConnection)
        .filter(
            ProviderCalendarConnection.connection_id == connection_id,
            ProviderCalendarConnection.provider_id == provider_id,
            ProviderCalendarConnection.sync_enabled.is_(True),
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Connection not found")

    job = CalendarSyncService.queue_sync_job(
        db=db,
        provider_id=provider_id,
        connection_id=connection_id,
        job_type="reconcile",
        payload={"connector": row.connector, "external_calendar_id": row.external_calendar_id},
        idempotency_key=f"manual-reconcile:{connection_id}:{uuid.uuid4().hex[:8]}",
    )

    if row.connector == "google":
        stats = CalendarSyncService.sync_google_connection(db, row)
        msg = (
            f"Google sync complete. Created {stats['created']}, updated {stats['updated']}, "
            f"deleted {stats['deleted']}, failed {stats['failed']}."
        )
    else:
        msg = "Sync job queued. Connector execution is being rolled out for this provider type."

    return QueueSyncOut(job_id=job.job_id, status=job.status, message=msg)


@router.get("/ics/link", response_model=IcsLinkOut)
def get_ics_link(
    request: Request,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    token = CalendarSyncService.get_ics_token(db, provider_id)
    if not token:
        return IcsLinkOut(connected=False, feed_url=None)
    return IcsLinkOut(connected=True, feed_url=_build_ics_url(request, provider_id, token))


@router.post("/ics/rotate-token", response_model=IcsLinkOut)
def rotate_ics_token(
    request: Request,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    _, token = CalendarSyncService.rotate_ics_token(db, provider_id)
    return IcsLinkOut(connected=True, feed_url=_build_ics_url(request, provider_id, token))


@router.get("/blocks", response_model=list[TimeBlockOut])
def list_time_blocks(
    from_at: datetime | None = Query(None),
    to_at: datetime | None = Query(None),
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    rows = AvailabilityService.list_time_blocks(
        db=db,
        provider_id=provider_id,
        from_at=from_at,
        to_at=to_at,
    )
    return [_to_time_block_out(row) for row in rows]


@router.post("/blocks", response_model=TimeBlockOut)
def create_time_block(
    payload: TimeBlockCreateIn,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    try:
        row = AvailabilityService.create_time_block(
            db=db,
            provider_id=provider_id,
            start_at=payload.start_at,
            end_at=payload.end_at,
            kind=payload.kind,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_time_block_out(row)


@router.delete("/blocks/{block_id}", status_code=204)
def delete_time_block(
    block_id: str,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    deleted = AvailabilityService.delete_time_block(db, provider_id, block_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Block not found")
    return Response(status_code=204)


def _ics_escape(value: str) -> str:
    return (
        (value or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )



def _ics_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y%m%dT%H%M%SZ")


@router.get("/ics/{provider_id}/{token}.ics", response_class=PlainTextResponse)
def ics_feed(provider_id: str, token: str, db: Session = Depends(get_db)):
    if not CalendarSyncService.verify_ics_token(db, provider_id, token):
        raise HTTPException(status_code=404, detail="Feed not found")

    bookings = (
        db.query(Booking)
        .options(joinedload(Booking.customer), joinedload(Booking.line_items), joinedload(Booking.provider))
        .filter(
            Booking.provider_id == provider_id,
            Booking.status.in_(["pending", "confirmed"]),
        )
        .order_by(Booking.scheduled_start.asc())
        .all()
    )

    provider_name = bookings[0].provider.name if bookings and bookings[0].provider else "Fixmeapp"
    now_utc = datetime.now(timezone.utc)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Fixmeapp//Booking Calendar//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{_ics_escape(provider_name)} - Fixmeapp",
        "METHOD:PUBLISH",
    ]

    for b in bookings:
        service_name = b.line_items[0].service_type if b.line_items else "Appointment"
        customer_name = (
            (b.customer.display_name if b.customer else None)
            or (b.customer.instagram_username_snapshot if b.customer else None)
            or "Customer"
        )
        summary = f"{service_name} - {customer_name}"
        description = f"Fixmeapp booking #{b.booking_number}\\nBooking ID: {b.booking_id}"

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:booking-{b.booking_id}@fixmeapp.ai",
            f"DTSTAMP:{_ics_dt(now_utc)}",
            f"DTSTART:{_ics_dt(b.scheduled_start)}",
            f"DTEND:{_ics_dt(b.scheduled_end)}",
            f"SUMMARY:{_ics_escape(summary)}",
            f"DESCRIPTION:{_ics_escape(description)}",
            "STATUS:CONFIRMED",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")

    return PlainTextResponse(
        content="\r\n".join(lines),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": "inline; filename=fixmeapp-calendar.ics"},
    )
