"""
AI Tool definitions + executor for the booking agent.

Each tool wraps a service-layer call ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the AI never touches the DB directly.
Ported from fixmeapp-instagram-bot/app/tools.py, upgraded to use our
multi-provider, multi-service service layer instead of a single JSON catalog.

Tool inventory:
    1. list_services       ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â show provider's service catalog
    2. check_availability  ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â get available slots for a date + service
    3. hold_slot           ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â temporarily reserve a slot while confirming
    4. book_appointment    ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â create a booking (with line items + VAT)
    5. find_my_bookings    ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â find customer's upcoming bookings
    6. cancel_booking      ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â cancel an existing booking
    7. reschedule_booking  ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â move a booking to a new slot
    8. get_provider_info   ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â get provider details (name, location, hours)
    9. send_booking_link   ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â generate a direct link to the web booking flow
    10. join_waitlist      ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â add customer to waitlist with day/time prefs
    11. check_nearby_availability ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â scan nearby days for open slots
"""
import json
import logging
from datetime import datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import settings
from app.services.provider_service import ProviderService
from app.services.availability_service import AvailabilityService
from app.services.booking_service import BookingService, SlotUnavailableError
from app.models.booking import Booking
from app.models.customer import Customer
from app.services.chat_auth_service import ChatAuthService
from app.services.conversation_state_service import ConversationStateService

logger = logging.getLogger(__name__)


# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Service resolver: 3-tier fuzzy + keyword + AI fallback ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

def _resolve_service(query: str, services: list) -> object | None:
    """Match a customer's service description to a provider's Service record.

    Tier 1: Case-insensitive substring match on service name.
    Tier 2: Match against keywords column (comma-separated aliases).
    Tier 3: GPT-4o-mini picks the best match from the full list.
    Returns None only if the service list is empty.
    """
    q = query.lower().strip()

    # Tier 1 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â name match
    for s in services:
        if q in s.name.lower() or s.name.lower() in q:
            return s

    # Tier 2 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â keyword/alias match
    for s in services:
        if s.keywords:
            for kw in s.keywords.lower().split(","):
                if kw.strip() and (kw.strip() in q or q in kw.strip()):
                    return s

    # Tier 3 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â GPT-mini semantic fallback
    if not services:
        return None

    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    catalog = "\n".join(
        f"{i+1}. {s.name}" + (f" (also: {s.keywords})" if s.keywords else "")
        for i, s in enumerate(services)
    )
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=10,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You match customer service requests to a salon's service list. "
                        "Reply ONLY with the number of the best match, or 0 if none fit."
                    ),
                },
                {
                    "role": "user",
                    "content": f'Customer wants: "{query}"\n\nServices:\n{catalog}',
                },
            ],
        )
        pick = int(resp.choices[0].message.content.strip().split()[0])
        if 1 <= pick <= len(services):
            logger.info("service.semantic_match query=%r pick=%d name=%r", query, pick, services[pick - 1].name)
            return services[pick - 1]
    except Exception as e:
        logger.warning("service.semantic_match failed: %s", e)

    return None


# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ OpenAI function-calling tool definitions ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

def _score_slot_adjacency(
    slot_start: datetime,
    slot_end: datetime,
    existing_bookings: list,
) -> float:
    """Score a candidate slot by how well it fills the existing day's schedule.

    Returns the minimum gap in minutes between this slot and the nearest
    existing booking.  Lower = better (slot attaches to another appointment,
    minimising dead time between clients).

    Returns float("inf") when there are no existing bookings â€” all slots are
    equal and none will be labelled RECOMMENDED.
    """
    if not existing_bookings:
        return float("inf")

    # Strip timezone info so arithmetic works regardless of DB storage format.
    s_start = slot_start.replace(tzinfo=None)
    s_end   = slot_end.replace(tzinfo=None)

    min_gap = float("inf")
    for bk in existing_bookings:
        if not bk.scheduled_start or not bk.scheduled_end:
            continue
        bk_start = bk.scheduled_start.replace(tzinfo=None)
        bk_end   = bk.scheduled_end.replace(tzinfo=None)

        if bk_end <= s_start:
            # Existing booking ends before our slot starts
            gap = (s_start - bk_end).total_seconds() / 60
        elif s_end <= bk_start:
            # Our slot ends before this booking starts
            gap = (bk_start - s_end).total_seconds() / 60
        else:
            # Overlap â€” AvailabilityService should have filtered this out
            gap = 0.0

        min_gap = min(min_gap, gap)

    return min_gap


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_services",
            "description": "List all available services for this provider with prices and durations",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check available time slots for a specific date and service",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format",
                    },
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service (e.g. 'Women\\'s Haircut', 'Balayage'). Use list_services to see available options.",
                    },
                },
                "required": ["date", "service_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hold_slot",
            "description": "Temporarily reserve a time slot while confirming details with the customer. Holds expire after 10 minutes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    "time": {"type": "string", "description": "Time in HH:MM format (24-hour)"},
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Duration in minutes",
                    },
                },
                "required": ["date", "time", "duration_minutes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book an appointment for a specific service, date, and time. Always check_availability and confirm with customer first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string", "description": "Name of the service"},
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    "time": {"type": "string", "description": "Time in HH:MM format (24-hour)"},
                    "customer_name": {
                        "type": "string",
                        "description": "Customer's name if provided",
                    },
                    "customer_email": {
                        "type": "string",
                        "description": "Customer email for verification (optional if already known)",
                    },
                    "account_action": {
                        "type": "string",
                        "description": "How to handle member account creation for unverified customers: create_now or send_link",
                        "enum": ["create_now", "send_link"]
                    },
                },
                "required": ["service_name", "date", "time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_my_bookings",
            "description": "Find upcoming bookings for the current customer",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_booking",
            "description": "Cancel an existing booking by booking ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {
                        "type": "string",
                        "description": "Booking ID to cancel",
                    },
                },
                "required": ["booking_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_booking",
            "description": "Reschedule an existing booking to a new date and time. Use find_my_bookings first to get the booking ID, then check_availability for the new date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {"type": "string", "description": "Booking ID to reschedule"},
                    "new_date": {"type": "string", "description": "New date in YYYY-MM-DD format"},
                    "new_time": {"type": "string", "description": "New time in HH:MM format (24-hour)"},
                },
                "required": ["booking_id", "new_date", "new_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_provider_info",
            "description": "Get provider information including name, location, and working hours",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_booking_link",
            "description": (
                "Generate a direct link to the visual web booking flow and return it to send to the customer. "
                "Use this when: (1) the customer prefers to book online rather than via chat, "
                "(2) they have already picked a service and you want to shortcut the process, "
                "or (3) the text-based flow feels too long. "
                "Optionally pre-selects a service in the booking page."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": (
                            "Name of the service the customer wants, to pre-select it in the "
                            "booking flow (e.g. 'Gel manicure'). Leave empty to open the "
                            "full service list."
                        ),
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_verification_link",
            "description": (
                "Send a secure one-time verification link to the customer email before finalizing booking in chat. "
                "Use when the customer is not yet verified or asks to resend the verification link."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "Customer email to verify. Optional if already captured in profile."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "join_waitlist",
            "description": (
                "Add the customer to the waitlist so they get notified (via email) when a matching slot opens. "
                "Use this when their preferred date/time has no availability."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string", "description": "Name of the service they want"},
                    "preferred_days": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Preferred days as integers: 0=Mon ... 6=Sun."
                    },
                    "earliest_hour": {"type": "integer", "description": "Earliest preferred hour (0-23)"},
                    "latest_hour": {"type": "integer", "description": "Latest preferred hour (0-23)"},
                    "customer_email": {"type": "string", "description": "Email to send offer notifications to"},
                    "customer_name": {"type": "string", "description": "Customer name for waitlist entry"}
                },
                "required": ["customer_email"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_nearby_availability",
            "description": (
                "Check availability across multiple upcoming days for a service. "
                "Use this when the requested date is full and suggest nearby dates first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string", "description": "Service to check"},
                    "start_date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    "num_days": {"type": "integer", "description": "Days forward to scan (default 7, max 14)"}
                },
                "required": ["service_name", "start_date"]
            }
        }
    },
]


# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Tool executor ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

async def execute_tool(
    tool_name: str,
    arguments: dict,
    *,
    db: Session,
    provider_id: str,
    customer_id: str | None = None,
    conversation_id: str | None = None,
) -> str:
    """Execute an AI tool call and return the result as a string.

    All tool calls go through the service layer ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â never direct DB access.

    Args:
        tool_name: Name of the function to call.
        arguments: Parsed JSON arguments from the AI.
        db: SQLAlchemy session (injected by the orchestrator).
        provider_id: Current provider context (from webhook/conversation).
        customer_id: Resolved customer ID (from Instagram identity mapping).
        conversation_id: Active conversation ID (for slot holds).
    """
    tz = ZoneInfo(settings.DEFAULT_TIMEZONE)
    state = (
        ConversationStateService.get_or_create_state(
            db,
            conversation_id,
            mode="provider",
            provider_id=provider_id,
        )
        if conversation_id
        else None
    )

    try:
        if tool_name == "list_services":
            services = ProviderService.get_provider_services(db, provider_id)
            if not services:
                return "No services found for this provider."
            lines = ["Available services:"]
            for s in services:
                price_str = f"{s.price_ex_vat:.0f} SEK ex VAT"
                home = " (home service available)" if s.home_service_available else ""
                lines.append(
                    f"  - {s.name} ({s.duration_minutes} min, {price_str}){home}"
                    + (f": {s.description}" if s.description else "")
                )
            return "\n".join(lines)

        elif tool_name == "check_availability":
            date_str = arguments.get("date", "")
            service_name = arguments.get("service_name", "")

            services = ProviderService.get_provider_services(db, provider_id)
            service = _resolve_service(service_name, services)

            if not service:
                available_names = ", ".join(s.name for s in services)
                return f"Service '{service_name}' not found. Available: {available_names}"

            if state and conversation_id:
                ConversationStateService.update_selection(
                    db,
                    conversation_id,
                    provider_id=provider_id,
                    service_id=service.service_id,
                    service_name=service.name,
                    date=date_str,
                    booking_status="pending",
                    last_ai_action="check_availability",
                )

            try:
                date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tz)
            except ValueError:
                return f"Invalid date format: {date_str}. Use YYYY-MM-DD."
            slots = AvailabilityService.get_available_slots(
                db=db,
                provider_id=provider_id,
                date=date,
                duration_minutes=service.duration_minutes,
            )

            if not slots:
                return f"No available slots on {date_str} for {service.name}. The provider might be closed or fully booked."

            # â”€â”€ Schedule-fitness: score every slot, label the best ones â”€â”€â”€â”€â”€â”€
            # Fetch existing confirmed/pending bookings for this day so we can
            # score each candidate slot by how close it sits to another booking.
            day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end   = day_start + timedelta(days=1)
            existing_bookings = (
                db.query(Booking)
                .filter(
                    Booking.provider_id == provider_id,
                    Booking.scheduled_start >= day_start,
                    Booking.scheduled_start < day_end,
                    Booking.status.in_(["confirmed", "pending"]),
                )
                .all()
            )

            # Gap â‰¤ 30 min to the nearest booking = adjacent = RECOMMENDED
            _ADJACENT_GAP = 30

            scored: list[tuple] = []  # (slot_start | None, gap_score)
            for slot in slots:
                try:
                    slot_start_dt = datetime.fromisoformat(slot["start"])
                except ValueError:
                    scored.append((None, float("inf")))
                    continue
                slot_end_dt = slot_start_dt + timedelta(minutes=service.duration_minutes)
                gap = _score_slot_adjacency(slot_start_dt, slot_end_dt, existing_bookings)
                scored.append((slot_start_dt, gap))

            # Determine which slots to mark RECOMMENDED
            finite_gaps = [g for _, g in scored if g != float("inf")]
            recommended_times: set = set()
            if finite_gaps:
                adjacent = [(t, g) for t, g in scored if t is not None and g <= _ADJACENT_GAP]
                if not adjacent:
                    # No adjacent slots â€” recommend the one(s) with the smallest gap
                    min_gap = min(finite_gaps)
                    adjacent = [(t, g) for t, g in scored if t is not None and g == min_gap]
                recommended_times = {t for t, _ in adjacent[:2]}

            lines = [f"Available slots for {service.name} on {date_str}:"]
            for slot_start_dt, _ in scored:
                if slot_start_dt is None:
                    continue
                label = " \u2b50 RECOMMENDED" if slot_start_dt in recommended_times else ""
                lines.append(f"  {slot_start_dt.strftime('%H:%M')}{label}")
            return "\n".join(lines)

        elif tool_name == "hold_slot":
            date_str = arguments.get("date", "")
            time_str = arguments.get("time", "")
            duration = arguments.get("duration_minutes", 60)

            try:
                start = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
            except ValueError:
                return "Invalid date/time format. Use YYYY-MM-DD and HH:MM."

            end = start + timedelta(minutes=duration)

            # Check if the slot is actually available
            if not AvailabilityService.check_slot_available(db, provider_id, start, end):
                return f"Sorry, the slot {date_str} at {time_str} is no longer available."

            hold = AvailabilityService.hold_slot(
                db=db,
                provider_id=provider_id,
                start=start,
                end=end,
                conversation_id=conversation_id,
                hold_minutes=10,
            )
            if state and conversation_id:
                ConversationStateService.update_selection(
                    db,
                    conversation_id,
                    provider_id=provider_id,
                    date=date_str,
                    time=time_str,
                    booking_status="pending",
                    last_ai_action="hold_slot",
                )
            return (
                f"Slot held until {hold.expires_at.strftime('%H:%M')} UTC.\n"
                f"Time: {date_str} at {time_str} ({duration} min)\n"
                f"Please confirm to finalize the booking."
            )

        elif tool_name == "book_appointment":
            service_name = arguments.get("service_name", "")
            date_str = arguments.get("date", "")
            time_str = arguments.get("time", "")
            customer_name_arg = (arguments.get("customer_name") or "").strip()

            if not customer_id:
                return "Cannot book: customer identity not resolved. Please try again."

            customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
            if not customer:
                return "Cannot book: customer profile not found. Please try again."

            email_from_args = (arguments.get("customer_email") or "").strip().lower()
            if email_from_args and email_from_args != (customer.customer_email or "").strip().lower():
                customer.customer_email = email_from_args
                db.commit()
                db.refresh(customer)

            if customer_name_arg and customer_name_arg.lower() not in {"instagram customer", "customer", "guest"}:
                current_name = (customer.display_name or "").strip().lower()
                if current_name != customer_name_arg.lower():
                    customer.display_name = customer_name_arg
                    db.commit()
                    db.refresh(customer)

            if state and conversation_id and (customer.customer_email or "").strip():
                ConversationStateService.set_contact_details(
                    db,
                    conversation_id,
                    contact_name=(customer.display_name or customer_name_arg or None),
                    contact_email=(customer.customer_email or "").strip().lower(),
                )
                state = ConversationStateService.get_state(db, conversation_id) or state

            if not (customer.customer_email or "").strip():
                return "Before I can finalize this booking, please share your email first."

            account_action = (arguments.get("account_action") or "").strip().lower()
            if not customer.user_id:
                if account_action in {"", "ask"}:
                    return (
                        f"Before I finalize: should I create your member account now with {customer.customer_email}, "
                        "or send you a signup link by email? "
                        "Reply with: create account now / send signup link."
                    )

                if account_action in {"send_link", "signup_link", "verify_link", "link"}:
                    link_result = ChatAuthService.send_verification_link(
                        db=db,
                        email=customer.customer_email,
                        provider_id=provider_id,
                        customer_id=customer_id,
                        conversation_id=conversation_id,
                    )
                    if link_result.get("sent"):
                        return (
                            f"Perfect, I sent a secure signup link to {customer.customer_email}. "
                            "Open it, then message me here and I will complete your booking."
                        )
                    return (
                        "I could not deliver the email automatically right now. "
                        f"Please open this secure link to verify: {link_result.get('verify_url')}"
                    )

                if account_action in {"create_now", "create_account_now", "create_account", "create"}:
                    ChatAuthService.create_member_account(
                        db=db,
                        email=customer.customer_email,
                        customer_id=customer_id,
                        conversation_id=conversation_id,
                    )
                    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
                    if not customer or not customer.user_id:
                        return "I could not create your member account right now. Please try again."
                else:
                    return "Please choose one: create account now / send signup link."

            services = ProviderService.get_provider_services(db, provider_id)
            service = _resolve_service(service_name, services)

            if not service:
                return f"Service '{service_name}' not found. Use list_services to see options."

            if state and conversation_id:
                ConversationStateService.update_selection(
                    db,
                    conversation_id,
                    provider_id=provider_id,
                    service_id=service.service_id,
                    service_name=service.name,
                    date=date_str,
                    time=time_str,
                    booking_status="pending",
                    last_ai_action="book_appointment_requested",
                )
                state = ConversationStateService.get_state(db, conversation_id) or state

            try:
                start = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
            except ValueError:
                return "Invalid date/time format. Use YYYY-MM-DD and HH:MM."

            end = start + timedelta(minutes=service.duration_minutes)

            if not AvailabilityService.check_slot_available(db, provider_id, start, end):
                return f"Sorry, the slot {date_str} at {time_str} is no longer available. Please check_availability again."

            try:
                booking = BookingService.create_booking(
                    db=db,
                    provider_id=provider_id,
                    customer_id=customer_id,
                    scheduled_start=start,
                    scheduled_end=end,
                    line_items=[{
                        "service_type": service.name,
                        "quantity": 1,
                        "unit_price_ex_vat": service.price_ex_vat,
                        "vat_percent": service.vat_percent,
                    }],
                    status="confirmed",
                )
            except SlotUnavailableError:
                return (
                    f"Sorry, the slot {date_str} at {time_str} was just taken by another customer! "
                    f"Please use check_availability to find other open times."
                )
            except ValueError as e:
                return f"Failed to create booking: {str(e)}"

            # BookingService now owns calendar sync. It queues provider-specific
            # calendar updates instead of writing directly to a shared Google
            # calendar from the AI flow, which avoids duplicate or wrong-calendar events.

            if state and conversation_id:
                ConversationStateService.update_selection(
                    db,
                    conversation_id,
                    provider_id=provider_id,
                    service_id=service.service_id,
                    service_name=service.name,
                    date=date_str,
                    time=time_str,
                    booking_status="confirmed",
                    last_ai_action="book_appointment_confirmed",
                )
                state = ConversationStateService.get_state(db, conversation_id) or state

            response = (
                f"Appointment booked successfully!\n"
                f"Booking #{booking.booking_number}\n"
                f"Service: {service.name}\n"
                f"Date: {date_str}\n"
                f"Time: {time_str}\n"
                f"Duration: {service.duration_minutes} minutes\n"
                f"Price: {booking.total_amount_inc_vat:.0f} SEK (incl. VAT)\n"
                f"Booking ID: {booking.booking_id}"
            )
            has_contact = bool((customer.customer_email or "").strip() and (customer.display_name or "").strip())
            if state and conversation_id and not state.contact_requested_at and not has_contact:
                ConversationStateService.mark_contact_requested(db, conversation_id)
                response += "\n\nGreat, thank you. What is your name and email and i will add to that booking?"
            return response

        elif tool_name == "find_my_bookings":
            if not customer_id:
                return "Cannot find bookings: customer identity not resolved."

            bookings = BookingService.list_bookings(
                db=db,
                provider_id=provider_id,
                customer_id=customer_id,
                status="pending",
            )
            # Also get confirmed
            bookings += BookingService.list_bookings(
                db=db,
                provider_id=provider_id,
                customer_id=customer_id,
                status="confirmed",
            )

            if not bookings:
                return "No upcoming bookings found."

            lines = ["Your upcoming bookings:"]
            for b in sorted(bookings, key=lambda x: x.scheduled_start):
                start_local = b.scheduled_start
                items_str = ", ".join(li.service_type for li in b.line_items)
                lines.append(
                    f"  - #{b.booking_number}: {items_str} on "
                    f"{start_local.strftime('%Y-%m-%d at %H:%M')} "
                    f"({b.status}) - ID: {b.booking_id}"
                )
            return "\n".join(lines)

        elif tool_name == "cancel_booking":
            booking_id = arguments.get("booking_id", "")
            try:
                booking = BookingService.update_status(db, booking_id, "cancelled")

                return f"Booking #{booking.booking_number} has been cancelled."
            except ValueError as e:
                return f"Failed to cancel: {str(e)}"

        elif tool_name == "reschedule_booking":
            booking_id = arguments.get("booking_id", "")
            new_date = arguments.get("new_date", "")
            new_time = arguments.get("new_time", "")

            try:
                new_start = datetime.strptime(f"{new_date} {new_time}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
            except ValueError:
                return "Invalid date/time format. Use YYYY-MM-DD and HH:MM."

            # Get original booking to calculate duration
            original = BookingService.get_booking(db, booking_id)
            if not original:
                return f"Booking {booking_id} not found."
            if original.status in ("cancelled", "completed"):
                return f"Cannot reschedule a {original.status} booking."

            duration = original.scheduled_end - original.scheduled_start
            new_end = new_start + duration

            # Check new slot is available
            if not AvailabilityService.check_slot_available(db, provider_id, new_start, new_end):
                return f"Sorry, {new_date} at {new_time} is not available. Please check_availability for another slot."

            try:
                booking = BookingService.reschedule_booking(db, booking_id, new_start, new_end)
            except SlotUnavailableError:
                return f"Sorry, {new_date} at {new_time} was just taken! Please use check_availability to find another slot."
            except ValueError as e:
                return f"Failed to reschedule: {str(e)}"

            return (
                f"Booking #{booking.booking_number} rescheduled!\n"
                f"New date: {new_date}\n"
                f"New time: {new_time}\n"
                f"Booking ID: {booking.booking_id}"
            )

        elif tool_name == "get_provider_info":
            provider = ProviderService.get_provider(db, provider_id)
            if not provider:
                return "Provider not found."

            hours = AvailabilityService.get_working_hours(db, provider_id)
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            hours_lines = []
            for h in hours:
                start_h, start_m = divmod(h.start_minutes, 60)
                end_h, end_m = divmod(h.end_minutes, 60)
                hours_lines.append(
                    f"  {day_names[h.day_of_week]}: {start_h:02d}:{start_m:02d} - {end_h:02d}:{end_m:02d}"
                )

            location = provider.location_salon or "Not specified"
            home_svc = "Yes" if provider.home_service else "No"

            return (
                f"Provider: {provider.name}\n"
                f"Location: {location}\n"
                f"Home service: {home_svc}\n"
                f"Working hours:\n" + ("\n".join(hours_lines) if hours_lines else "  Not configured")
            )

        elif tool_name == "send_booking_link":
            service_name = arguments.get("service_name", "").strip()
            url = f"{settings.WEB_BOOKING_BASE_URL}/book?provider_id={provider_id}"
            if service_name:
                url += f"&service={quote(service_name)}"
            # Return the bare URL ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the AI will wrap it in a friendly message
            return f"Here you can book yourself: {url}"

        elif tool_name == "send_verification_link":
            if not customer_id:
                return "Cannot send verification link: customer identity not resolved."

            customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
            if not customer:
                return "Cannot send verification link: customer profile not found."

            email = (arguments.get("email") or customer.customer_email or "").strip().lower()
            if not email:
                return "Please share your email first so I can send a secure verification link."

            if customer.customer_email != email:
                customer.customer_email = email
                db.commit()
                db.refresh(customer)

            if customer.user_id:
                return f"You are already verified with {email}."

            link_result = ChatAuthService.send_verification_link(
                db=db,
                email=email,
                provider_id=provider_id,
                customer_id=customer_id,
                conversation_id=conversation_id,
            )

            if link_result.get("sent"):
                return (
                    f"I sent a secure verification link to {email}. "
                    "Open it and then continue here so I can complete your booking."
                )

            return (
                "I could not deliver the email right now. "
                f"Please verify directly with this secure link: {link_result.get('verify_url')}"
            )
        elif tool_name == "join_waitlist":
            from app.services.waitlist_service import WaitlistService

            email = arguments.get("customer_email", "").strip()
            if not email:
                return "Cannot join waitlist: email address is required. Please ask the customer for their email."

            name = arguments.get("customer_name", "Instagram Customer")
            preferred_days = arguments.get("preferred_days", [0, 1, 2, 3, 4])
            earliest = arguments.get("earliest_hour", 8)
            latest = arguments.get("latest_hour", 18)
            service_name = arguments.get("service_name", "")

            # Resolve service ID
            service_id = None
            if service_name:
                services = ProviderService.get_provider_services(db, provider_id)
                matched = _resolve_service(service_name, services)
                if matched:
                    service_id = matched.service_id

            try:
                entry = WaitlistService.join_waitlist(
                    db=db,
                    provider_id=provider_id,
                    email=email,
                    name=name,
                    service_id=service_id,
                    preferred_days=preferred_days,
                    earliest_hour=earliest,
                    latest_hour=latest,
                )
            except Exception as e:
                return f"Failed to join waitlist: {str(e)}"

            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            days_str = ", ".join(day_names[d] for d in sorted(preferred_days) if 0 <= d <= 6)

            return (
                f"Added to the waitlist!\n"
                f"Preferred days: {days_str}\n"
                f"Time range: {earliest:02d}:00 - {latest:02d}:00\n"
                f"Email: {email}\n"
                f"We'll send an email the moment a matching slot opens. "
                f"They'll have 10 minutes to accept before it goes to the next person."
            )

        elif tool_name == "check_nearby_availability":
            service_name = arguments.get("service_name", "")
            start_date_str = arguments.get("start_date", "")
            num_days = min(arguments.get("num_days", 7), 14)

            # Find the service
            services = ProviderService.get_provider_services(db, provider_id)
            service = _resolve_service(service_name, services)

            if not service:
                available_names = ", ".join(s.name for s in services)
                return f"Service '{service_name}' not found. Available: {available_names}"

            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=tz)
            except ValueError:
                return f"Invalid date format: {start_date_str}. Use YYYY-MM-DD."

            results = []
            for i in range(num_days):
                check_date = start_date + timedelta(days=i)
                slots = AvailabilityService.get_available_slots(
                    db=db,
                    provider_id=provider_id,
                    date=check_date,
                    duration_minutes=service.duration_minutes,
                )
                if slots:
                    day_label = check_date.strftime("%A %Y-%m-%d")
                    # Score slots for this day â€” find the best-fit slot
                    day_s = check_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    day_e = day_s + timedelta(days=1)
                    day_bookings = (
                        db.query(Booking)
                        .filter(
                            Booking.provider_id == provider_id,
                            Booking.scheduled_start >= day_s,
                            Booking.scheduled_start < day_e,
                            Booking.status.in_(["confirmed", "pending"]),
                        )
                        .all()
                    )
                    best_time = None
                    best_gap  = float("inf")
                    if day_bookings:
                        for slot in slots:
                            try:
                                st = datetime.fromisoformat(slot["start"])
                                se = st + timedelta(minutes=service.duration_minutes)
                                g  = _score_slot_adjacency(st, se, day_bookings)
                                if g < best_gap:
                                    best_gap  = g
                                    best_time = st
                            except ValueError:
                                pass

                    times = []
                    for slot in slots[:5]:
                        try:
                            start_dt = datetime.fromisoformat(slot["start"])
                            star = " \u2b50" if best_time and start_dt == best_time else ""
                            times.append(f"{start_dt.strftime('%H:%M')}{star}")
                        except ValueError:
                            times.append(slot["start"])
                    extra = f" (+{len(slots) - 5} more)" if len(slots) > 5 else ""
                    results.append(f"  {day_label}: {', '.join(times)}{extra}")

            if not results:
                return (
                    f"No available slots for {service.name} in the next {num_days} days. "
                    f"Consider offering the customer the waitlist - they'll get an email when a slot opens."
                )

            header = f"Available slots for {service.name} in the next {num_days} days:"
            return header + "\n" + "\n".join(results)

        else:
            return f"Unknown tool: {tool_name}"

    except Exception as e:
        logger.exception("Error executing tool %s", tool_name)
        return f"Error executing {tool_name}: {str(e)}"



