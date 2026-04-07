"""
AI Orchestration Layer.

Architecture:
    IG DM Ã¢â€ ' webhook_parser Ã¢â€ ' Orchestrator Ã¢â€ ' Service layer Ã¢â€ ' DB
    Orchestrator Ã¢â€ ' messenger (reply)

The orchestrator NEVER touches the DB directly.
It only calls service methods through the tools module.

Pro bot settings:
    When a provider has an active Pro subscription, their custom settings
    (tone, language, bot name, out-of-hours behaviour) are loaded and
    applied to the system prompt before the OpenAI call. Free providers
    always get platform defaults.
"""
import json
import logging
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.orchestrators.tools import TOOLS, execute_tool
from app.services.provider_service import ProviderService
from app.services.availability_service import AvailabilityService
from app.services.conversation_service import ConversationService
from app.services.conversation_state_service import ConversationStateService
from app.services.subscription_service import SubscriptionService
from app.services.bot_settings_service import BotSettingsService
from app.models.customer import Customer
from app.models.provider_intelligence import ProviderIntelligence

logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Tone Ã¢â€ ' system prompt phrasing
_TONE_INSTRUCTIONS = {
    "friendly": "Be warm, friendly, and approachable. Use a conversational tone.",
    "formal":   "Be professional and formal. Use polite, precise language.",
    "casual":   "Be relaxed and casual. Short sentences, feel free to use emojis.",
}

# Language Ã¢â€ ' instruction injected into system prompt
_LANGUAGE_INSTRUCTIONS = {
    "auto": "Detect the customer's language from their message and reply in the same language.",
    "sv":   "Always reply in Swedish, regardless of the language the customer writes in.",
    "en":   "Always reply in English, regardless of the language the customer writes in.",
}

# Human-readable labels for provider amenity keys
_AMENITY_LABELS: dict[str, str] = {
    "coffee":                "complimentary coffee",
    "wine":                  "complimentary wine",
    "eco_friendly":          "eco-friendly products",
    "wifi":                  "free WiFi",
    "parking":               "on-site parking",
    "dog_friendly":          "dog-friendly",
    "wheelchair_accessible": "wheelchair accessible",
}

_HUMAN_HINTS = (
    # English
    "talk to a human",
    "talk to human",
    "speak to a human",
    "speak to human",
    "real person",
    "talk to someone",
    "speak to someone",
    "connect me to",
    "want to talk to",
    "want to speak to",
    "talk to the owner",
    "speak to the owner",
    "talk to staff",
    "speak to staff",
    "human please",
    "person please",
    "not a bot",
    "stop bot",
    "actual person",
    # Swedish
    "prata med en mÃ¤nniska",
    "prata med en person",
    "pratar med en riktig",
    "riktig person",
    "mÃ¤nsklig support",
    "vill prata med",
    "prata med Ã¤garen",
    "prata med personalen",
    "inte en bot",
    "ingen bot",
    "koppla mig till",
)

_MANUAL_LINK_HINTS = (
    "confused",
    "don't understand",
    "do not understand",
    "not sure",
    "unsure",
    "show me",
    "look myself",
    "book myself",
    "manual",
    "link",
    "booking link",
    "browse",
    "jag fattar inte",
    "jag forstar inte",
    "forstar inte",
    "osaker",
    "jag ar osaker",
    "kan jag kolla sjalv",
    "kan jag boka sjalv",
    "kolla sjalv",
    "boka sjalv",
    "lank",
)


def _is_human_request(user_text: str) -> bool:
    text = (user_text or "").lower().strip()
    if not text:
        return False
    return any(hint in text for hint in _HUMAN_HINTS)


def _should_offer_manual_link(user_text: str) -> bool:
    text = (user_text or "").lower().strip()
    if not text:
        return False
    return any(hint in text for hint in _MANUAL_LINK_HINTS)


_CONFIRM_HINTS = (
    "yes",
    "y",
    "confirm",
    "book it",
    "go ahead",
    "do it",
    "ja",
    "boka",
    "kÃ¶r",
    "perfect",
    "perfekt",
    "sounds good",
    "that works",
    "works for me",
    "passar",
    "toppen",
    "yes please",
)

_CREATE_ACCOUNT_HINTS = (
    "create account now",
    "create now",
    "create account",
    "create",
    "skapa konto",
    "skapa",
)

_SEND_LINK_HINTS = (
    "send signup link",
    "signup link",
    "send link",
    "link",
    "skicka lÃ¤nk",
    "lÃ¤nk",
)

_EMAIL_PATTERN = re.compile(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
_TIME_ONLY_PATTERN = re.compile(r"^\s*(\d{1,2}:\d{2})\s*$")
_TIME_IN_TEXT_PATTERN = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_ISO_DATE_PATTERN = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_AVAILABILITY_ON_DATE_PATTERN = re.compile(
    r"available slots for\s+(?P<service>.+?)\s+on\s+(?P<date>\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
_PENDING_OFFER_PATTERNS = (
    re.compile(
        r"availability for\s+(?:a\s+)?(?P<service>.+?)\s+on\s+(?P<date>\d{4}-\d{2}-\d{2})\s+at\s+(?P<time>\d{1,2}:\d{2})",
        re.IGNORECASE,
    ),
    re.compile(
        r"availability for\s+(?:a\s+)?(?P<service>.+?)\s+tomorrow\s+at\s+(?P<time>\d{1,2}:\d{2})",
        re.IGNORECASE,
    ),
)
_CONTACT_PROMPT = "Great, thank you. What is your name and email and i will add to that booking?"

_SWEDISH_HINTS = (
    "jag",
    "hej",
    "idag",
    "imorgon",
    "tack",
    "boka",
    "tid",
    "frisor",
    "frisÃ¶r",
    "klippning",
    "balayage",
    "kan du",
    "vill",
)

_ENGLISH_HINTS = (
    "hi",
    "hello",
    "today",
    "tomorrow",
    "asap",
    "book",
    "booking",
    "please",
    "thanks",
    "need",
)

_TODAY_HINTS = ("idag", "i dag", "today", "asap", "nu")
_OTHER_DAY_HINTS = ("imorgon", "tomorrow", "annan dag", "another day")
_NO_TODAY_HINTS = ("inga tider idag", "no slots today", "no availability today")


def _is_confirmation_intent(user_text: str) -> bool:
    text = (user_text or "").strip().lower()
    if not text:
        return False
    return any(hint in text for hint in _CONFIRM_HINTS)


def _parse_account_action(user_text: str) -> str | None:
    text = (user_text or "").strip().lower()
    if not text:
        return None
    if any(h in text for h in _CREATE_ACCOUNT_HINTS):
        return "create_now"
    if any(h in text for h in _SEND_LINK_HINTS):
        return "send_link"
    return None


def _extract_email(text: str) -> str | None:
    match = _EMAIL_PATTERN.search(text or "")
    if not match:
        return None
    return match.group(1).strip().lower()


def _extract_name_from_contact_reply(text: str, email: str | None) -> str | None:
    source = (text or "").strip()
    if not source:
        return None

    lower = source.lower()
    if "my name is" in lower:
        start = lower.find("my name is") + len("my name is")
        candidate = source[start:].strip(" .,!?:;")
        if candidate:
            if email:
                candidate = candidate.replace(email, "").strip(" ,;:-")
            return candidate or None

    if ":" in source:
        parts = [p.strip() for p in source.splitlines() if p.strip()]
        for part in parts:
            if part.lower().startswith("name:"):
                candidate = part.split(":", 1)[1].strip()
                if email:
                    candidate = candidate.replace(email, "").strip(" ,;:-")
                if candidate:
                    return candidate

    candidate = source
    if email:
        candidate = candidate.replace(email, " ")
    candidate = re.sub(r"\b(email|mail|name|namn)\b", " ", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"[^A-Za-zÃ…Ã„Ã–Ã¥Ã¤Ã¶'\-\s]", " ", candidate)
    candidate = re.sub(r"\s+", " ", candidate).strip()
    if not candidate:
        return None

    words = candidate.split()
    if 1 <= len(words) <= 4:
        return " ".join(words)
    return None


def _last_assistant_text(conversation_history: list[dict]) -> str:
    for msg in reversed(conversation_history):
        if msg.get("role") == "assistant":
            return (msg.get("content") or "").strip()
    return ""


def _awaiting_contact_details(conversation_history: list[dict]) -> bool:
    last_assistant = _last_assistant_text(conversation_history).lower()
    return _CONTACT_PROMPT.lower() in last_assistant


def _extract_pending_offer(conversation_history: list[dict], tz: ZoneInfo) -> dict | None:
    """Find the most recent pending slot offer in conversation history.

    Only scans the last 3 assistant messages to prevent the 'ghost service' bug
    where a stale offer from an earlier topic (e.g. 'balayage' in a previous
    test session) is mistakenly treated as the current pending offer.
    """
    now = datetime.now(tz=tz)
    checked = 0
    for msg in reversed(conversation_history):
        if msg.get("role") != "assistant":
            continue
        checked += 1
        if checked > 3:
            break  # Never look more than 3 assistant turns back
        content = (msg.get("content") or "").strip()
        if not content:
            continue

        for pattern in _PENDING_OFFER_PATTERNS:
            match = pattern.search(content)
            if not match:
                continue
            service_name = (match.group("service") or "").strip(" .,!?:;")
            time_str = (match.group("time") or "").strip()
            date_str = (match.groupdict().get("date") or "").strip()
            if not date_str:
                date_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
            if service_name and time_str and date_str:
                return {
                    "service_name": service_name,
                    "date": date_str,
                    "time": time_str,
                }

    return None


def _extract_availability_context(conversation_history: list[dict]) -> dict | None:
    """Find the most recent availability check context from conversation history.

    Scans assistant messages first (AI paraphrase), then falls back to tool
    result messages which always contain the reliable machine-generated header
    'Available slots for {service} on {YYYY-MM-DD}:'.
    This prevents the balayage-style loop where a slightly different AI phrasing
    causes context extraction to fail and triggers another check_availability call.
    """
    # Primary: scan assistant messages (most recent first)
    for msg in reversed(conversation_history):
        if msg.get("role") != "assistant":
            continue
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        match = _AVAILABILITY_ON_DATE_PATTERN.search(content)
        if match:
            return {
                "service_name": (match.group("service") or "").strip(),
                "date": (match.group("date") or "").strip(),
            }

    # Fallback: scan tool result messages â€” these always have the exact header
    for msg in reversed(conversation_history):
        if msg.get("role") != "tool":
            continue
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        match = _AVAILABILITY_ON_DATE_PATTERN.search(content)
        if match:
            return {
                "service_name": (match.group("service") or "").strip(),
                "date": (match.group("date") or "").strip(),
            }

    return None


def _extract_time_only_choice(text: str) -> str | None:
    match = _TIME_ONLY_PATTERN.match(text or "")
    if not match:
        return None
    return match.group(1)




def _extract_time_choice(text: str) -> str | None:
    exact = _extract_time_only_choice(text)
    if exact:
        return exact
    match = _TIME_IN_TEXT_PATTERN.search(text or "")
    if not match:
        return None
    return f"{int(match.group(1)):02d}:{match.group(2)}"


def _extract_requested_date(text: str, tz: ZoneInfo) -> str | None:
    lowered = (text or "").lower()
    if not lowered:
        return None

    iso = _ISO_DATE_PATTERN.search(lowered)
    if iso:
        return iso.group(1)

    now = datetime.now(tz=tz)
    if any(h in lowered for h in ("idag", "i dag", "today", "asap", "nu")):
        return now.strftime("%Y-%m-%d")
    if any(h in lowered for h in ("imorgon", "tomorrow")):
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")
    return None


def _match_service_name_in_text(text: str, services: list) -> str | None:
    lowered = (text or "").lower()
    if not lowered:
        return None

    for svc in services:
        name = (svc.name or "").strip()
        if name and name.lower() in lowered:
            return name

    for svc in services:
        if not getattr(svc, "keywords", None):
            continue
        for kw in svc.keywords.split(","):
            keyword = kw.strip().lower()
            if keyword and keyword in lowered:
                return svc.name
    return None


def _last_service_from_history(conversation_history: list[dict], services: list) -> str | None:
    for msg in reversed(conversation_history):
        if msg.get("role") != "user":
            continue
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        matched = _match_service_name_in_text(content, services)
        if matched:
            return matched
    return None

def _last_requested_date_from_user_history(conversation_history: list[dict], tz: ZoneInfo) -> str | None:
    for msg in reversed(conversation_history):
        if msg.get("role") != "user":
            continue
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        date_hit = _extract_requested_date(content, tz)
        if date_hit:
            return date_hit
    return None


def _extract_contextual_choice(
    *,
    user_text: str,
    conversation_history: list[dict],
    services: list,
    tz: ZoneInfo,
) -> dict | None:
    time_choice = _extract_time_choice(user_text)
    if not time_choice:
        return None

    date_choice = _extract_requested_date(user_text, tz)
    service_choice = _match_service_name_in_text(user_text, services)

    availability_ctx = _extract_availability_context(conversation_history)
    if not service_choice and availability_ctx:
        service_choice = availability_ctx.get("service_name")
    if not date_choice and availability_ctx:
        date_choice = availability_ctx.get("date")

    if not service_choice:
        service_choice = _last_service_from_history(conversation_history, services)

    if not date_choice:
        date_choice = _last_requested_date_from_user_history(conversation_history, tz)

    if service_choice and date_choice and time_choice:
        return {
            "service_name": service_choice,
            "date": date_choice,
            "time": time_choice,
        }
    return None

def _text_contains_any(text: str, hints: tuple[str, ...]) -> bool:
    lowered = (text or "").lower()
    if not lowered:
        return False
    return any(h in lowered for h in hints)


def _prefer_swedish(user_text: str, conversation_history: list[dict]) -> bool:
    user_messages = [
        (m.get("content") or "")
        for m in conversation_history
        if m.get("role") == "user"
    ]

    first_user_message = ""
    for msg in user_messages:
        if (msg or "").strip():
            first_user_message = msg.strip().lower()
            break
    if not first_user_message:
        first_user_message = (user_text or "").strip().lower()

    if first_user_message:
        first_looks_swedish = any(h in first_user_message for h in _SWEDISH_HINTS)
        first_looks_english = any(h in first_user_message for h in _ENGLISH_HINTS)
        if first_looks_english and not first_looks_swedish:
            return False
        if first_looks_swedish and not first_looks_english:
            return True

    merged = "\n".join(user_messages + [user_text or ""]).lower()
    if not merged.strip():
        return False
    return any(h in merged for h in _SWEDISH_HINTS)


def _requested_today(user_text: str) -> bool:
    return _text_contains_any(user_text, _TODAY_HINTS)


def _mentions_other_day(text: str) -> bool:
    return _text_contains_any(text, _OTHER_DAY_HINTS)


def _states_no_today_availability(text: str) -> bool:
    return _text_contains_any(text, _NO_TODAY_HINTS)


def _localize(prefer_swedish: bool, sv_text: str, en_text: str) -> str:
    return sv_text if prefer_swedish else en_text

def _build_system_prompt(db: Session, provider_id: str) -> str:
    """Build a dynamic system prompt with provider-specific info.

    For Pro providers, applies their custom bot settings (tone, language,
    bot name, out-of-hours behaviour). Free providers use platform defaults.
    """
    provider = ProviderService.get_provider(db, provider_id)
    if not provider:
        return "You are a helpful booking assistant."

    # Load Pro settings if applicable
    is_pro = SubscriptionService.is_pro(db, provider_id)
    bot_cfg = BotSettingsService.get_settings_dict(db, provider_id) if is_pro else {}

    tone = bot_cfg.get("tone", "friendly")
    language = bot_cfg.get("language", "auto")
    bot_name = bot_cfg.get("bot_name")           # None Ã¢â€ ' unnamed assistant
    out_of_hours = bot_cfg.get("out_of_hours_behavior", "show_hours")
    max_days = bot_cfg.get("max_advance_booking_days")  # None Ã¢â€ ' unlimited

    # Bot identity line
    if bot_name:
        identity = (
            f"You are {bot_name}, the booking assistant for {provider.name}. "
            f"Always introduce yourself as {bot_name}."
        )
    else:
        identity = f"You are the booking assistant for {provider.name}."

    # Service catalog
    services = ProviderService.get_provider_services(db, provider_id)
    if services:
        svc_lines = []
        for s in services:
            line = f"- {s.name} ({s.duration_minutes} min, {s.price_ex_vat:.0f} SEK ex VAT)"
            if s.keywords:
                line += f" [also called: {s.keywords}]"
            svc_lines.append(line)
        services_text = "\n".join(svc_lines)
    else:
        services_text = "No services configured yet."

    # Working hours
    hours = AvailabilityService.get_working_hours(db, provider_id)
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    if hours:
        hours_lines = []
        for h in hours:
            sh, sm = divmod(h.start_minutes, 60)
            eh, em = divmod(h.end_minutes, 60)
            hours_lines.append(f"  {day_names[h.day_of_week]}: {sh:02d}:{sm:02d} - {eh:02d}:{em:02d}")
        hours_text = "\n".join(hours_lines)
    else:
        hours_text = "  Not configured"

    # Provider profile (location, bio, amenities)
    profile_section = ""
    profile_lines = []
    if provider.bio:
        profile_lines.append(f"  Bio: {provider.bio}")
    location_parts = [p for p in [getattr(provider, "city", None), getattr(provider, "location_salon", None)] if p]
    if location_parts:
        profile_lines.append(f"  Location: {', '.join(location_parts)}")
    try:
        active_amenities = [a.amenity_key for a in provider.amenities if a.is_active]
        if active_amenities:
            labels = [_AMENITY_LABELS.get(k, k.replace("_", " ")) for k in active_amenities]
            profile_lines.append(f"  Facilities: {', '.join(labels)}")
    except Exception:
        pass
    if profile_lines:
        profile_section = f"About {provider.name}:\n" + "\n".join(profile_lines) + "\n\n"

    # Brand identity from intelligence pipeline
    brand_section = ""
    intel = db.query(ProviderIntelligence).filter(
        ProviderIntelligence.provider_id == provider_id
    ).first()
    if intel:
        vibe_tags = json.loads(intel.confirmed_vibe_tags or intel.ai_vibe_tags or "[]")
        brand_lines = []
        if vibe_tags:
            brand_lines.append(f"  Vibe & aesthetic: {', '.join(vibe_tags)}")
        if intel.vibe_summary:
            brand_lines.append(f"  Brand summary: {intel.vibe_summary}")
        if intel.target_audience:
            brand_lines.append(f"  Typical clientele: {intel.target_audience}")
        if intel.unique_value:
            brand_lines.append(f"  What makes us special: {intel.unique_value}")
        if brand_lines:
            brand_section = "Brand identity:\n" + "\n".join(brand_lines) + "\n\n"

    tz = ZoneInfo(settings.DEFAULT_TIMEZONE)
    now = datetime.now(tz=tz)

    # Out-of-hours instruction
    if out_of_hours == "send_link":
        ooh_instruction = (
            "If the customer messages outside working hours, send them the booking link "
            "using send_booking_link so they can self-serve for a future slot."
        )
    else:
        ooh_instruction = (
            "If the customer messages outside working hours, tell them the opening hours "
            "and invite them to message back when you're open."
        )

    # Advance booking cap
    if max_days:
        booking_window = f"- Only accept bookings up to {max_days} days in advance."
    else:
        booking_window = ""

    return (
        f"{identity} "
        f"You help customers book, reschedule, and cancel appointments via Instagram DM.\n\n"
        f"Tone: {_TONE_INSTRUCTIONS.get(tone, _TONE_INSTRUCTIONS['friendly'])}\n"
        f"Language: {_LANGUAGE_INSTRUCTIONS.get(language, _LANGUAGE_INSTRUCTIONS['auto'])}\n\n"
        f"{profile_section}"
        f"{brand_section}"
        f"Available services:\n{services_text}\n\n"
        f"Working hours:\n{hours_text}\n"
        f"Timezone: {settings.DEFAULT_TIMEZONE}\n"
        f"Current date and time: {now.strftime('%A, %B %d, %Y')} at {now.strftime('%H:%M')}\n\n"
        f"Guidelines:\n"
        f"- Keep messages short and clear (Instagram DM)\n"
        f"- On first contact, greet briefly and offer booking help\n"
        f"- When a customer wants to book: ask for service, date, and time preferences\n"
        f"- If customer asks about a service, use list_services/check_availability before saying a service is unavailable\n"
        f"- Ask for customer name if missing. If booking is already completed, ask right after confirmation.\n"
        f"- Service matching: use the service name OR any alias in [also called: ...] to identify what the customer wants. If ambiguous, ask which service they mean.\n"
        f"- Once the customer has picked a service/date/time, keep that context until they explicitly change it\n"
        f"- Always check availability before confirming a booking\n"
        f"- Before finalizing for an unverified customer: ask for email and ask choice: create account now or send signup link\n"
        f"- If customer chooses create now: call book_appointment with account_action=create_now\n"
        f"- If customer chooses signup link: call book_appointment with account_action=send_link (or send_verification_link)\n"
        f"- After verification link is completed, continue and finalize the booking\n"
        f"- If the customer explicitly asks you to book now and has provided service + date + time, proceed directly with booking and then send confirmation details.\n- Otherwise confirm full details (service, date, time, price) before finalizing\n"
        f"- After booking is confirmed, ask exactly: Great, thank you. What is your name and email and i will add to that booking?\n"
        f"- For cancel/reschedule: use find_my_bookings first to get the booking ID\n"
        f"- If you don't understand, ask for clarification\n"
        f"- Format dates and times in a human-friendly way\n"
        f"- IMPORTANT: when listing available slots, always include the phrase 'available slots for [service] on [YYYY-MM-DD]' using the real ISO date. The booking engine needs this exact phrase to track context - surrounding text can be in any language.\n"
        f"- IMPORTANT: when offering or confirming a specific slot, always phrase it as 'availability for [service] on [YYYY-MM-DD] at [HH:MM]' using real ISO date and 24h time. The booking engine relies on this exact phrase to capture the offer.\n"
        f"- Never make up availability â€” always use check_availability tool\n"
        f"- When showing available times, present a few good options\n"
        f"- SCHEDULE INTELLIGENCE: check_availability marks some slots '\u2b50 RECOMMENDED'.\n"
        f"  These slots minimise empty gaps between the provider's appointments.\n"
        f"  Rule: if the customer has NOT specified an exact time, always lead with the RECOMMENDED slot(s).\n"
        f"  Phrase it naturally: 'I'd suggest [time] â€” that fits perfectly into the schedule!' or similar.\n"
        f"  If the customer says a specific time (e.g. 'only at 13:00'), always honour their constraint regardless.\n"
        f"- Use hold_slot to temporarily reserve a slot while confirming with customer\n"
        f"- {ooh_instruction}\n"
        f"- You can offer a direct booking link via send_booking_link. Use it when:\n"
        f"    * The customer asks to book online or prefers a link\n"
        f"    * They have already told you which service they want (pass it as service_name)\n"
        f"    * The conversation is getting long or the customer seems unsure/confused\n"
        f"  Wrap the returned URL naturally: 'Tap here to book: <url>'\n"
        + (f"- {booking_window}\n" if booking_window else "")
    )

def _flag_needs_human(db: Session, conversation_id: str) -> None:
    """Mark conversation as needing human attention so the bot stops looping."""
    from app.models.conversation import Conversation

    conv = db.query(Conversation).filter(
        Conversation.conversation_id == conversation_id
    ).first()
    if conv and not conv.needs_human:
        conv.needs_human = True
        db.commit()
    ConversationStateService.mark_handoff_requested(db, conversation_id)


def _get_conversation_messages(db: Session, conversation_id: str) -> list[dict]:
    """Load conversation history from DB and format for OpenAI."""
    history = ConversationService.get_conversation_history(db, conversation_id, limit=30)
    messages = []
    for msg in history:
        if msg.direction == "in":
            messages.append({"role": "user", "content": msg.text or ""})
        elif msg.direction == "out":
            messages.append({"role": "assistant", "content": msg.text or ""})
    return messages


async def process_message(
    *,
    db: Session,
    provider_id: str,
    customer_id: str | None,
    conversation_id: str,
    text: str,
) -> str:
    """Process an incoming message and return the bot's reply.

    1. Load conversation history from DB
    2. Build system prompt and deterministic step guards
    3. Run OpenAI function-calling loop (max 5 iterations)
    4. Execute tool calls through service layer
    5. Return the final text reply

    The reply is NOT saved to DB here - the caller (webhook route) logs it.
    """
    state = ConversationStateService.get_or_create_state(
        db,
        conversation_id,
        mode="provider",
        provider_id=provider_id,
    )

    # Check if customer is explicitly requesting a human before anything else.
    if _is_human_request(text):
        provider = ProviderService.get_provider(db, provider_id)
        provider_name = provider.name if provider else "the provider"
        _flag_needs_human(db, conversation_id)
        prefer_swedish_early = _prefer_swedish(text, [])
        return _localize(
            prefer_swedish_early,
            f"Självklart! Jag meddelar {provider_name} och de återkommer till dig så snart som möjligt.",
            f"Of course! I'll let {provider_name} know and they'll get back to you as soon as possible.",
        )

    if state.booking_status == "confirmed" and _is_confirmation_intent(text):
        prefer_swedish_early = _prefer_swedish(text, [])
        return _localize(
            prefer_swedish_early,
            "Bokningen är redan bekräftad. Om du vill ändra något kan jag hjälpa dig att boka om eller avboka.",
            "Your booking is already confirmed. If you want to change it, I can help you reschedule or cancel it.",
        )
    system_prompt = _build_system_prompt(db, provider_id)

    # Append customer preferences to system prompt if we have a known customer
    if customer_id:
        try:
            from app.models.user import User as UserModel
            customer_rec = db.query(Customer).filter(Customer.customer_id == customer_id).first()
            if customer_rec and customer_rec.user_id:
                user_rec = db.query(UserModel).filter(UserModel.user_id == customer_rec.user_id).first()
                if user_rec:
                    pref_lines = []
                    try:
                        si = json.loads(user_rec.service_interests or "[]")
                        if si:
                            pref_lines.append(f"Service interests: {', '.join(si)}")
                    except Exception:
                        pass
                    try:
                        lp = json.loads(user_rec.lifestyle_preferences or "[]")
                        if lp:
                            pref_lines.append(f"Lifestyle preferences: {', '.join(lp)}")
                    except Exception:
                        pass
                    try:
                        locs = json.loads(user_rec.preferred_locations or "[]")
                        if locs:
                            pref_lines.append(f"Preferred locations: {', '.join(locs)}")
                    except Exception:
                        pass
                    if pref_lines:
                        system_prompt += (
                            "\n\n--- CUSTOMER PREFERENCES ---\n"
                            + "\n".join(pref_lines)
                            + "\nUse these to personalise your responses and suggest relevant services."
                            + "\n--- END CUSTOMER PREFERENCES ---"
                        )
        except Exception:
            pass  # Never block a conversation over a preference lookup failure

    conversation_history = _get_conversation_messages(db, conversation_id)
    manual_booking_link = f"{settings.WEB_BOOKING_BASE_URL}/book?provider_id={provider_id}"
    should_offer_manual_link = _should_offer_manual_link(text)
    tz = ZoneInfo(settings.DEFAULT_TIMEZONE)
    prefer_swedish = _prefer_swedish(text, conversation_history)
    requested_today = _requested_today(text)
    today_date_str = datetime.now(tz=tz).strftime("%Y-%m-%d")
    provider_services = ProviderService.get_provider_services(db, provider_id)
    sticky_choice = _extract_contextual_choice(
        user_text=text,
        conversation_history=conversation_history,
        services=provider_services,
        tz=tz,
    )
    state_choice = None
    if state.selected_service_name and state.selected_date and state.selected_time:
        state_choice = {
            "service_name": state.selected_service_name,
            "date": state.selected_date,
            "time": state.selected_time,
        }
    elif sticky_choice:
        state_choice = sticky_choice
        ConversationStateService.update_selection(
            db,
            conversation_id,
            provider_id=provider_id,
            service_name=sticky_choice.get("service_name"),
            date=sticky_choice.get("date"),
            time=sticky_choice.get("time"),
            last_ai_action="selection_detected",
        )
        state = ConversationStateService.get_state(db, conversation_id) or state

    requested_service = _match_service_name_in_text(text, provider_services) or state.selected_service_name
    if not requested_service and state_choice:
        requested_service = state_choice.get("service_name")
    # Deterministic step: collect name + email after booking confirmation prompt.
    awaiting_contact = bool(state.contact_requested_at and not state.contact_received_at)
    if customer_id and (awaiting_contact or _awaiting_contact_details(conversation_history)):
        email = _extract_email(text)
        if not email:
            return _localize(prefer_swedish, "Skriv både ditt namn och din e-post så lägger jag till det på bokningen.", "Please share both your name and email so I can add them to your booking.")

        name = _extract_name_from_contact_reply(text, email)
        customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
        if customer:
            changed = False
            if (customer.customer_email or "").strip().lower() != email:
                customer.customer_email = email
                changed = True

            if name:
                normalized_existing = (customer.display_name or "").strip().lower()
                if normalized_existing != name.strip().lower():
                    customer.display_name = name.strip()
                    changed = True

            if changed:
                db.commit()

        ConversationStateService.set_contact_details(
            db,
            conversation_id,
            contact_name=name,
            contact_email=email,
        )

        if name:
            return _localize(
                prefer_swedish,
                f"Perfekt, {name}. Du kan skapa din profil och hantera bokningen genom att logga in med den här e-posten: {email}.",
                f"Perfect, {name}. You can create your own profile to manage this booking by logging in with that email: {email}.",
            )
        return _localize(
            prefer_swedish,
            f"Perfekt. Du kan skapa din profil och hantera bokningen genom att logga in med den här e-posten: {email}.",
            f"Perfect. You can create your own profile to manage this booking by logging in with that email: {email}.",
        )

    # Deterministic step: if customer confirms, finalize using the structured state first.
    pending_offer = None
    if state.selected_service_name and state.selected_date and state.selected_time:
        pending_offer = {
            "service_name": state.selected_service_name,
            "date": state.selected_date,
            "time": state.selected_time,
        }
    else:
        pending_offer = _extract_pending_offer(conversation_history, tz)
        if pending_offer:
            ConversationStateService.update_selection(
                db,
                conversation_id,
                provider_id=provider_id,
                service_name=pending_offer.get("service_name"),
                date=pending_offer.get("date"),
                time=pending_offer.get("time"),
                booking_status="pending",
                last_ai_action="pending_offer_detected",
            )
            state = ConversationStateService.get_state(db, conversation_id) or state

    account_action = _parse_account_action(text)
    if customer_id and state_choice and (_is_confirmation_intent(text) or account_action):
        direct_args = {
            "service_name": state_choice["service_name"],
            "date": state_choice["date"],
            "time": state_choice["time"],
        }
        if account_action:
            direct_args["account_action"] = account_action

        return await execute_tool(
            "book_appointment",
            direct_args,
            db=db,
            provider_id=provider_id,
            customer_id=customer_id,
            conversation_id=conversation_id,
        )
    if customer_id and pending_offer and (_is_confirmation_intent(text) or account_action):
        direct_args = {
            "service_name": pending_offer["service_name"],
            "date": pending_offer["date"],
            "time": pending_offer["time"],
        }
        if account_action:
            direct_args["account_action"] = account_action

        return await execute_tool(
            "book_appointment",
            direct_args,
            db=db,
            provider_id=provider_id,
            customer_id=customer_id,
            conversation_id=conversation_id,
        )
    messages = [{"role": "system", "content": system_prompt}]

    if prefer_swedish:
        messages.append(
            {
                "role": "system",
                "content": "Keep the whole conversation in Swedish. Do not switch to English.",
            }
        )

    if requested_today:
        messages.append(
            {
                "role": "system",
                "content": (
                    "The customer asked for a slot today. First check availability for "
                    f"{today_date_str}. "
                    "Only suggest another day if there are no slots today, and explicitly say that there are no slots today."
                ),
            }
        )

    if sticky_choice:
        messages.append(
            {
                "role": "system",
                "content": (
                    "Use this selected context unless the customer explicitly changes it: "
                    f"service={sticky_choice['service_name']}, date={sticky_choice['date']}, time={sticky_choice['time']}. "
                    "Do not switch to another service on your own."
                ),
            }
        )

    if requested_service:
        messages.append(
            {
                "role": "system",
                "content": (
                    f"Current requested service is: {requested_service}. "
                    "Do not switch service unless the customer explicitly asks for another one."
                ),
            }
        )
    # If user selected a bare time from the shown slot list, nudge model to progress.
    availability_context = _extract_availability_context(conversation_history)
    selected_time = _extract_time_choice(text)
    if availability_context and selected_time:
        messages.append(
            {
                "role": "system",
                "content": (
                    "The customer selected this exact time slot: "
                    f"{availability_context['date']} {selected_time} for {availability_context['service_name']}. "
                    "Acknowledge and move forward. Do not repeat full slot list unless user asks."
                ),
            }
        )

    messages.extend(conversation_history)
    if not conversation_history or conversation_history[-1].get("content") != text:
        messages.append({"role": "user", "content": text})

    max_iterations = 5
    tool_signature_counts: dict[str, int] = {}

    for _ in range(max_iterations):
        try:
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
            )
        except Exception:
            logger.exception("OpenAI API error")
            return _localize(prefer_swedish, "Jag har ett tillfÃ¤lligt tekniskt problem just nu. FÃ¶rsÃ¶k igen om en liten stund.", "I'm having a small technical issue right now. Please try again in a moment!")

        choice = response.choices[0]
        assistant_msg = choice.message

        if not assistant_msg.tool_calls:
            final_text = (assistant_msg.content or "").strip()
            last_assistant = _last_assistant_text(conversation_history).lower()

            # Loop guard across turns: do not send the exact same assistant response again.
            if final_text and last_assistant and final_text.lower() == last_assistant:
                return _localize(
                    prefer_swedish,
                    "Jag hÃ¶r dig. FÃ¶r att undvika loop: skriv en rad med tjÃ¤nst, datum (YYYY-MM-DD) och tid (HH:MM), sÃ¥ slutfÃ¶r jag direkt.",
                    "I hear you. Let's avoid a loop. Please send one line with service, date (YYYY-MM-DD), and time (HH:MM), and I will finalize directly.",
                )

            if requested_today and _mentions_other_day(final_text) and not _states_no_today_availability(final_text):
                return _localize(
                    prefer_swedish,
                    "Du bad om en tid idag. Jag kollar fÃ¶rst tider idag innan vi gÃ¥r vidare till andra dagar.",
                    "You asked for a slot today. I will check today first before we move to other days.",
                )

            if should_offer_manual_link and "book yourself:" not in final_text.lower() and "boka sjÃ¤lv:" not in final_text.lower():
                link_text = _localize(
                    prefer_swedish,
                    f"Om du vill boka sjÃ¤lv kan du gÃ¶ra det hÃ¤r: {manual_booking_link}",
                    f"If you prefer to book manually, here you can book yourself: {manual_booking_link}",
                )
                if final_text:
                    return f"{final_text}\n\n{link_text}"
                return link_text
            return final_text

        tool_calls_data = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in assistant_msg.tool_calls
        ]

        assistant_dict = {"role": "assistant", "tool_calls": tool_calls_data}
        if assistant_msg.content:
            assistant_dict["content"] = assistant_msg.content
        messages.append(assistant_dict)

        for tc in assistant_msg.tool_calls:
            tool_name = tc.function.name
            try:
                arguments = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                arguments = {}

            logger.info("Tool call: %s(%s) for provider %s", tool_name, json.dumps(arguments), provider_id)

            signature = f"{tool_name}:{json.dumps(arguments, sort_keys=True)}"
            tool_signature_counts[signature] = tool_signature_counts.get(signature, 0) + 1
            if tool_signature_counts[signature] > 1:
                result = (
                    "Loop guard: I already executed that exact step. "
                    "Continue to the next booking step without repeating the same question."
                )
            else:
                result = await execute_tool(
                    tool_name,
                    arguments,
                    db=db,
                    provider_id=provider_id,
                    customer_id=customer_id,
                    conversation_id=conversation_id,
                )

            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    # Max iterations exhausted â€” bot couldn't handle it. Flag for human and notify customer.
    _flag_needs_human(db, conversation_id)
    provider = ProviderService.get_provider(db, provider_id)
    provider_name = provider.name if provider else "the provider"

    if should_offer_manual_link:
        return _localize(
            prefer_swedish,
            f"Jag har svÃ¥rt att behandla fÃ¶rfrÃ¥gan just nu. Jag meddelar {provider_name} och de Ã¥terkommer till dig sÃ¥ snart som mÃ¶jligt.\n\nOm du vill boka sjÃ¤lv kan du gÃ¶ra det hÃ¤r: {manual_booking_link}",
            f"I'm having trouble with your request. I've notified {provider_name} and they'll get back to you as soon as possible.\n\nIf you prefer to book yourself in the meantime: {manual_booking_link}",
        )
    return _localize(
        prefer_swedish,
        f"Jag har svÃ¥rt att behandla fÃ¶rfrÃ¥gan just nu. Jag meddelar {provider_name} och de Ã¥terkommer till dig sÃ¥ snart som mÃ¶jligt.",
        f"I'm having trouble with your request. I've notified {provider_name} and they'll get back to you as soon as possible.",
    )
