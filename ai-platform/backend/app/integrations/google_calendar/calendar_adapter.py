"""
Google Calendar sync adapter.

Create/update/delete calendar events from bookings.
Ported from fixmeapp-instagram-bot/app/calendar_client.py.

Uses Google Calendar API v3 with a service account.
"""
import logging
from datetime import datetime

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]

_service = None


def _get_service():
    """Build and cache the Google Calendar API service (service account)."""
    global _service
    if _service is None:
        creds = ServiceAccountCredentials.from_service_account_file(
            settings.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        _service = build("calendar", "v3", credentials=creds)
        logger.info("Google Calendar service initialized (service account)")
    return _service


def _get_service_for_token(
    access_token: str, refresh_token: str | None
) -> tuple:
    """Build a per-provider Google Calendar service from OAuth tokens.

    Returns (service, creds). Automatically refreshes an expired token
    when a refresh_token is available.
    """
    creds = OAuthCredentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
    return build("calendar", "v3", credentials=creds), creds


def create_event(
    calendar_id: str,
    summary: str,
    start: datetime,
    end: datetime,
    description: str | None = None,
    timezone: str | None = None,
) -> str | None:
    """Create a Google Calendar event.

    Returns the external event ID (Google event ID) or None on failure.
    """
    tz = timezone or settings.DEFAULT_TIMEZONE
    try:
        cal = _get_service()
        event_body = {
            "summary": summary,
            "start": {"dateTime": start.isoformat(), "timeZone": tz},
            "end": {"dateTime": end.isoformat(), "timeZone": tz},
        }
        if description:
            event_body["description"] = description

        result = cal.events().insert(
            calendarId=calendar_id, body=event_body
        ).execute()
        event_id = result.get("id")
        logger.info("Created calendar event: %s", event_id)
        return event_id
    except HttpError as e:
        logger.error("Failed to create calendar event: %s", e)
        return None


def update_event(
    calendar_id: str,
    event_id: str,
    summary: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    description: str | None = None,
    timezone: str | None = None,
) -> bool:
    """Update an existing Google Calendar event. Returns True on success."""
    tz = timezone or settings.DEFAULT_TIMEZONE
    try:
        cal = _get_service()
        patch_body: dict = {}
        if summary:
            patch_body["summary"] = summary
        if start:
            patch_body["start"] = {"dateTime": start.isoformat(), "timeZone": tz}
        if end:
            patch_body["end"] = {"dateTime": end.isoformat(), "timeZone": tz}
        if description:
            patch_body["description"] = description

        cal.events().patch(
            calendarId=calendar_id, eventId=event_id, body=patch_body
        ).execute()
        logger.info("Updated calendar event: %s", event_id)
        return True
    except HttpError as e:
        logger.error("Failed to update calendar event %s: %s", event_id, e)
        return False


def delete_event(
    calendar_id: str,
    event_id: str,
) -> bool:
    """Delete a Google Calendar event. Returns True on success."""
    try:
        cal = _get_service()
        cal.events().delete(
            calendarId=calendar_id, eventId=event_id
        ).execute()
        logger.info("Deleted calendar event: %s", event_id)
        return True
    except HttpError as e:
        logger.error("Failed to delete calendar event %s: %s", event_id, e)
        return False


def get_freebusy(
    calendar_id: str,
    time_min: datetime,
    time_max: datetime,
    timezone: str | None = None,
) -> list[tuple[datetime, datetime]]:
    """Query Google Calendar freebusy for busy periods.

    Returns list of (start, end) tuples representing busy times.
    Used by availability service for external calendar conflict detection.
    """
    tz = timezone or settings.DEFAULT_TIMEZONE
    try:
        cal = _get_service()
        body = {
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "timeZone": tz,
            "items": [{"id": calendar_id}],
        }
        result = cal.freebusy().query(body=body).execute()
        busy_periods = result.get("calendars", {}).get(calendar_id, {}).get("busy", [])

        ranges = []
        for period in busy_periods:
            busy_start = datetime.fromisoformat(period["start"])
            busy_end = datetime.fromisoformat(period["end"])
            ranges.append((busy_start, busy_end))
        return ranges
    except HttpError as e:
        logger.error("Google Calendar freebusy error: %s", e)
        return []


def find_events_by_query(
    calendar_id: str,
    query: str,
    time_min: datetime | None = None,
    max_results: int = 10,
) -> list[dict]:
    """Search upcoming calendar events by text query.

    Useful for finding a customer's appointments by their IG user ID
    (stored in event description).

    Returns list of dicts: {event_id, summary, start, end, description}
    """
    try:
        cal = _get_service()
        params: dict = {
            "calendarId": calendar_id,
            "q": query,
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if time_min:
            params["timeMin"] = time_min.isoformat()

        result = cal.events().list(**params).execute()

        events = []
        for item in result.get("items", []):
            events.append({
                "event_id": item["id"],
                "summary": item.get("summary", ""),
                "start": item["start"].get("dateTime", item["start"].get("date", "")),
                "end": item["end"].get("dateTime", item["end"].get("date", "")),
                "description": item.get("description", ""),
            })
        return events
    except HttpError as e:
        logger.error("Failed to search calendar events: %s", e)
        return []


# ── Per-provider OAuth token variants ────────────────────────────────────────
# These are used by CalendarSyncService when the provider has connected their
# own Google Calendar via the OAuth flow (access_token + refresh_token stored
# in ProviderCalendarConnection). Each function returns a tuple of
# (result, new_access_token_or_None) so the caller can persist a refreshed token.

def create_event_with_token(
    access_token: str,
    refresh_token: str | None,
    calendar_id: str,
    summary: str,
    start: datetime,
    end: datetime,
    description: str | None = None,
    timezone: str | None = None,
) -> tuple[str | None, str | None]:
    """Create a calendar event using the provider's OAuth tokens.

    Returns (google_event_id, new_access_token).
    new_access_token is non-None only when a token refresh happened.
    """
    tz = timezone or settings.DEFAULT_TIMEZONE
    try:
        cal, creds = _get_service_for_token(access_token, refresh_token)
        body = {
            "summary": summary,
            "start": {"dateTime": start.isoformat(), "timeZone": tz},
            "end": {"dateTime": end.isoformat(), "timeZone": tz},
        }
        if description:
            body["description"] = description
        result = cal.events().insert(calendarId=calendar_id, body=body).execute()
        event_id = result.get("id")
        logger.info("Created calendar event (OAuth): %s", event_id)
        new_token = creds.token if creds.token != access_token else None
        return event_id, new_token
    except HttpError as e:
        logger.error("create_event_with_token failed: %s", e)
        return None, None
    except Exception as e:
        logger.error("create_event_with_token unexpected error: %s", e)
        return None, None


def update_event_with_token(
    access_token: str,
    refresh_token: str | None,
    calendar_id: str,
    event_id: str,
    summary: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    description: str | None = None,
    timezone: str | None = None,
) -> tuple[bool, str | None]:
    """Update a calendar event using the provider's OAuth tokens.

    Returns (success, new_access_token).
    """
    tz = timezone or settings.DEFAULT_TIMEZONE
    try:
        cal, creds = _get_service_for_token(access_token, refresh_token)
        patch_body: dict = {}
        if summary:
            patch_body["summary"] = summary
        if start:
            patch_body["start"] = {"dateTime": start.isoformat(), "timeZone": tz}
        if end:
            patch_body["end"] = {"dateTime": end.isoformat(), "timeZone": tz}
        if description:
            patch_body["description"] = description
        cal.events().patch(calendarId=calendar_id, eventId=event_id, body=patch_body).execute()
        logger.info("Updated calendar event (OAuth): %s", event_id)
        new_token = creds.token if creds.token != access_token else None
        return True, new_token
    except HttpError as e:
        logger.error("update_event_with_token failed: %s", e)
        return False, None
    except Exception as e:
        logger.error("update_event_with_token unexpected error: %s", e)
        return False, None


def delete_event_with_token(
    access_token: str,
    refresh_token: str | None,
    calendar_id: str,
    event_id: str,
) -> tuple[bool, str | None]:
    """Delete a calendar event using the provider's OAuth tokens.

    Returns (success, new_access_token).
    """
    try:
        cal, creds = _get_service_for_token(access_token, refresh_token)
        cal.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        logger.info("Deleted calendar event (OAuth): %s", event_id)
        new_token = creds.token if creds.token != access_token else None
        return True, new_token
    except HttpError as e:
        logger.error("delete_event_with_token failed: %s", e)
        return False, None
    except Exception as e:
        logger.error("delete_event_with_token unexpected error: %s", e)
        return False, None
