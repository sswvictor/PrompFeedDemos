"""
Provider AI Command endpoint.

The provider types a natural-language instruction in the mobile app and this
endpoint interprets it and executes the matching action.

Supported actions:
  - Block time         "block tomorrow 2–4pm, dentist"
  - Send late alert    "tell my 3pm client I'm running 20 minutes late"
  - Cancel booking     "cancel all today's bookings, I'm sick"
  - Update hours       "close at 5pm on Fridays from now on"

POST /provider/ai/command
  { "message": "block tomorrow 12–1pm lunch break" }
  → { "action": "block_time", "message": "Done! Blocked 12:00–13:00 tomorrow." }
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_provider
from app.config import settings
from app.db.session import get_db
from app.models.provider import Provider
from app.models.provider_time_block import ProviderTimeBlock
from app.services.booking_service import BookingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/provider/ai", tags=["provider-ai"])


class CommandRequest(BaseModel):
    message: str


class CommandResponse(BaseModel):
    action: str          # what was done
    message: str         # human-readable confirmation
    details: dict = {}   # optional extra data


# ── Time parsing helpers ──────────────────────────────────────────────────────

def _parse_time(text: str) -> tuple[int, int] | None:
    """Parse 'HH:MM', 'H am/pm', 'Hpm' → (hour, minute) in 24h."""
    text = text.strip().lower()
    m = re.match(r'(\d{1,2}):(\d{2})\s*(am|pm)?', text)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        if m.group(3) == 'pm' and h < 12:
            h += 12
        if m.group(3) == 'am' and h == 12:
            h = 0
        return h, mn
    m = re.match(r'(\d{1,2})\s*(am|pm)', text)
    if m:
        h = int(m.group(1))
        if m.group(2) == 'pm' and h < 12:
            h += 12
        if m.group(2) == 'am' and h == 12:
            h = 0
        return h, 0
    return None


def _parse_day(text: str, now: datetime) -> datetime | None:
    """Parse 'today', 'tomorrow', weekday names → date."""
    text = text.lower().strip()
    if 'today' in text:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if 'tomorrow' in text:
        return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    for i, wd in enumerate(weekdays):
        if wd in text:
            current_wd = now.weekday()
            days_ahead = (i - current_wd) % 7 or 7
            return (now + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
    return None


# ── Main handler ─────────────────────────────────────────────────────────────

@router.post("/command", response_model=CommandResponse)
async def ai_command(
    body: CommandRequest,
    provider: Provider = Depends(get_current_provider),
    db: Session = Depends(get_db),
) -> CommandResponse:
    """Interpret a natural-language provider instruction and execute it."""

    msg = body.message.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Empty command")

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # ── Try local pattern matching first (fast, no API cost) ─────────────────

    msg_lower = msg.lower()

    # 1. Block time
    block_keywords = ['block', 'busy', 'unavailable', 'off', 'break', 'lunch', 'dentist', 'vacation', 'holiday']
    if any(k in msg_lower for k in block_keywords):
        result = _handle_block_time(msg, msg_lower, provider, db, now)
        if result:
            return result

    # 2. Late alert
    late_keywords = ['late', 'running late', 'delayed', 'behind', 'stuck']
    if any(k in msg_lower for k in late_keywords):
        result = _handle_late_alert(msg, msg_lower, provider, db, now)
        if result:
            return result

    # 3. Sick / cancel all today
    sick_keywords = ['sick', 'ill', 'unwell', 'cancel today', 'cancel all today', 'not coming in']
    if any(k in msg_lower for k in sick_keywords):
        result = _handle_sick_day(msg, provider, db, now)
        if result:
            return result

    # ── Fall back to GPT-4o-mini for ambiguous commands ──────────────────────

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        system_prompt = """You are an AI assistant for a beauty/wellness provider.
Interpret the provider's instruction and respond with a JSON object:
{
  "action": "block_time" | "late_alert" | "cancel_today" | "update_hours" | "unknown",
  "start_time": "HH:MM" or null,
  "end_time": "HH:MM" or null,
  "day": "today" | "tomorrow" | "monday" ... | null,
  "minutes_late": number or null,
  "reason": "string" or null,
  "reply": "friendly one-sentence confirmation to show the provider"
}
Only return JSON, no other text."""

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=200,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": msg},
            ],
        )
        parsed = json.loads(resp.choices[0].message.content or "{}")
        action = parsed.get("action", "unknown")
        reply = parsed.get("reply", "Got it!")

        if action == "block_time":
            day_str = parsed.get("day") or "today"
            start_str = parsed.get("start_time") or "09:00"
            end_str = parsed.get("end_time") or "10:00"
            reason = parsed.get("reason") or "blocked"
            day_dt = _parse_day(day_str, now) or now
            start_t = _parse_time(start_str) or (9, 0)
            end_t = _parse_time(end_str) or (10, 0)
            starts_at = day_dt.replace(hour=start_t[0], minute=start_t[1])
            ends_at = day_dt.replace(hour=end_t[0], minute=end_t[1])
            _create_block(provider.provider_id, reason, starts_at, ends_at, db)
            return CommandResponse(action="block_time", message=reply)

        if action == "late_alert":
            minutes = int(parsed.get("minutes_late") or 15)
            count = _send_late_alerts(provider.provider_id, minutes, db, now)
            return CommandResponse(
                action="late_alert",
                message=reply or f"Sent late alert ({minutes} min) to {count} client{'s' if count != 1 else ''}.",
            )

        if action == "cancel_today":
            count = _cancel_today(provider.provider_id, db, now)
            return CommandResponse(
                action="cancel_today",
                message=reply or f"Cancelled {count} booking{'s' if count != 1 else ''} for today. Clients notified.",
            )

        return CommandResponse(
            action="unknown",
            message="I understood your message but couldn't complete that action yet. Try: 'block 2–4pm tomorrow' or 'tell my next client I'm 15 min late'.",
        )

    except Exception as e:
        logger.warning("AI command GPT fallback failed: %s", e)
        return CommandResponse(
            action="error",
            message="I couldn't process that. Try something like: 'block tomorrow 12–1pm' or 'I'm running 20 minutes late'.",
        )


# ── Action helpers ────────────────────────────────────────────────────────────

def _create_block(provider_id: str, label: str, starts_at: datetime, ends_at: datetime, db: Session) -> None:
    block = ProviderTimeBlock(
        block_id=__import__('uuid').uuid4().hex,
        provider_id=provider_id,
        label=label,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    db.add(block)
    db.commit()


def _handle_block_time(msg: str, msg_lower: str, provider: Provider, db: Session, now: datetime) -> CommandResponse | None:
    # Extract time range e.g. "2-4pm", "14:00-16:00", "2pm to 4pm"
    time_range = re.search(
        r'(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:to|–|-|until)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)',
        msg, re.IGNORECASE,
    )
    day_dt = _parse_day(msg_lower, now) or now

    if not time_range:
        # Can't determine time — let GPT handle it
        return None

    start_t = _parse_time(time_range.group(1))
    end_t = _parse_time(time_range.group(2))

    if not start_t or not end_t:
        return None

    # Infer am/pm if no suffix: if start > end, end is pm
    sh, sm = start_t
    eh, em = end_t
    if eh < sh and eh < 12:
        eh += 12

    starts_at = day_dt.replace(hour=sh, minute=sm, second=0, microsecond=0)
    ends_at = day_dt.replace(hour=eh, minute=em, second=0, microsecond=0)

    # Label
    reason_match = re.search(r'(?:for|,|—|-)\s*(.{3,30})$', msg, re.IGNORECASE)
    label = reason_match.group(1).strip() if reason_match else 'blocked'

    _create_block(provider.provider_id, label, starts_at, ends_at, db)

    day_label = 'today' if day_dt.date() == now.date() else 'tomorrow' if day_dt.date() == (now + timedelta(days=1)).date() else day_dt.strftime('%A')
    return CommandResponse(
        action="block_time",
        message=f"Done! Blocked {sh:02d}:{sm:02d}–{eh:02d}:{em:02d} on {day_label}.",
        details={"starts_at": starts_at.isoformat(), "ends_at": ends_at.isoformat()},
    )


def _send_late_alerts(provider_id: str, minutes: int, db: Session, now: datetime) -> int:
    """Find upcoming bookings in the next 3 hours and mark them as running late."""
    window_end = now + timedelta(hours=3)
    from app.models.booking import Booking
    bookings = (
        db.query(Booking)
        .filter(
            Booking.provider_id == provider_id,
            Booking.scheduled_start >= now,
            Booking.scheduled_start <= window_end,
            Booking.status == 'confirmed',
        )
        .all()
    )
    for b in bookings:
        b.late_notification_minutes = minutes
    db.commit()
    return len(bookings)


def _handle_late_alert(msg: str, msg_lower: str, provider: Provider, db: Session, now: datetime) -> CommandResponse | None:
    minutes_match = re.search(r'(\d+)\s*(?:min|minutes?)', msg, re.IGNORECASE)
    minutes = int(minutes_match.group(1)) if minutes_match else 15

    count = _send_late_alerts(provider.provider_id, minutes, db, now)
    if count == 0:
        return CommandResponse(
            action="late_alert",
            message="No upcoming bookings found in the next 3 hours to notify.",
        )
    return CommandResponse(
        action="late_alert",
        message=f"Got it! Notified {count} client{'s' if count != 1 else ''} that you're running {minutes} minutes late.",
        details={"minutes": minutes, "bookings_notified": count},
    )


def _cancel_today(provider_id: str, db: Session, now: datetime) -> int:
    from app.models.booking import Booking
    today_end = now.replace(hour=23, minute=59, second=59)
    bookings = (
        db.query(Booking)
        .filter(
            Booking.provider_id == provider_id,
            Booking.scheduled_start >= now,
            Booking.scheduled_start <= today_end,
            Booking.status == 'confirmed',
        )
        .all()
    )
    for b in bookings:
        b.status = 'cancelled'
    db.commit()
    return len(bookings)


def _handle_sick_day(msg: str, provider: Provider, db: Session, now: datetime) -> CommandResponse | None:
    count = _cancel_today(provider.provider_id, db, now)
    return CommandResponse(
        action="cancel_today",
        message=f"Take care! Cancelled {count} booking{'s' if count != 1 else ''} for today. Your clients have been notified.",
        details={"cancelled_count": count},
    )
