"""
Platform Orchestrator â€” @fixmeapp discovery bot.

When a customer DMs the main @fixmeapp Instagram account, this orchestrator
handles the conversation instead of a single-provider bot.

The bot acts as a personal beauty concierge:
  1. Customer describes what they want ("balayage in Stockholm this Saturday")
  2. Bot silently checks if they've booked before (Layer 1 recognition)
  3. Bot searches across all providers on the platform
  4. Recommends the ONE best match with confidence
  5. Customer confirms â†’ bot books directly

This is a fundamentally different persona from the single-provider bots:
- No specific provider context
- Cross-provider search tools instead of single-provider booking tools
- Concierge-first ("I know just the place!") not search-engine-first
- Returns customers greeted by name with their history surfaced
"""
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.orchestrators.base import _is_confirmation_intent, _is_human_request
from app.orchestrators.platform_tools import PLATFORM_TOOLS, execute_platform_tool
from app.services.conversation_service import ConversationService
from app.services.conversation_state_service import ConversationStateService

logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_API_KEY)

tz = ZoneInfo(settings.DEFAULT_TIMEZONE)

_PLATFORM_SYSTEM_PROMPT = """You are Fixmeapp, a personal beauty concierge who helps people \
book the perfect appointment â€” all without leaving Instagram. You know every great salon and \
specialist in Sweden and always know exactly which one to recommend.

Your personality: Warm, confident, like a well-connected friend who says "I know just the place!" \
â€” not a search engine that dumps a list of 5 options.

How you work:
1. If you have RETURNING CUSTOMER CONTEXT below, greet them by name and reference their history
2. Ask what service they want and which city (if not already stated)
3. Use search_providers to find the best match
4. Recommend the TOP PICK with confidence â€” "I found the perfect spot for you! ðŸ’‡" \
   Lead with ONE great recommendation, not a numbered list. Mention 1-2 highlights \
   (name, price, next available slots).
5. If they're not sold or ask for alternatives, then briefly mention other options
6. Once they want to book, confirm the details (service, date, time, price)
7. Ask for name and email (skip name/email if already in RETURNING CUSTOMER CONTEXT), \
   then use book_with_provider to complete the booking

Guidelines:
- Keep messages short â€” this is Instagram DM, not a website
- Be a confident concierge: one strong pick beats a confusing list every time
- Use emojis sparingly but effectively (âœ… ðŸ“ ðŸ’‡ ðŸ’… ðŸŽ‰)
- Always search before recommending â€” never make up providers
- If no results: suggest broadening the date range, city, or removing the price filter
- Always confirm full booking details before calling book_with_provider
- Use get_my_bookings if the customer asks about their past bookings or wants to rebook
- Current date: {current_date}
- Timezone: Sweden (CET/CEST)

What you can help with:
- Finding the right hairdresser, nail salon, massage therapist, lash artist, etc.
- Checking real-time availability and next open slots
- Completing the booking â€” customer never needs to leave Instagram
- Viewing past bookings and rebooking previous services
{returning_context}"""


# â”€â”€ Layer 1: Silent customer recognition â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _get_returning_customer_context(db: Session, sender_ig_id: str) -> dict | None:
    """Look up whether this IG sender has booked through any provider on the platform.

    Queries InstagramIdentity by instagram_user_id across all providers (no provider_id
    filter) so a user who visited Salon A and Salon B is recognised the same way.

    Returns a context dict or None if this is a first-time sender.
    """
    try:
        from app.models.instagram_identity import InstagramIdentity
        from app.models.booking import Booking, BookingLineItem
        from app.models.customer import Customer
        from app.models.provider import Provider
        from app.models.user import User

        # Find all provider-scoped identities for this IG sender
        identities = db.query(InstagramIdentity).filter(
            InstagramIdentity.instagram_user_id == sender_ig_id
        ).all()

        if not identities:
            return None  # Truly first-time sender

        customer_ids = [i.customer_id for i in identities]

        # Most recent non-cancelled booking across all their customers
        last_booking = (
            db.query(Booking)
            .filter(
                Booking.customer_id.in_(customer_ids),
                Booking.status.in_(["completed", "confirmed", "pending"]),
            )
            .order_by(Booking.scheduled_start.desc())
            .first()
        )

        # Best display name from any of their customer records
        customer = (
            db.query(Customer)
            .filter(Customer.customer_id.in_(customer_ids))
            .filter(Customer.display_name.isnot(None))
            .first()
            or db.query(Customer).filter(Customer.customer_id.in_(customer_ids)).first()
        )

        name = None
        email = None
        service_interests: list[str] = []
        lifestyle_preferences: list[str] = []
        preferred_locations: list[str] = []
        if customer:
            name = (
                customer.display_name
                or customer.instagram_username_snapshot
                or customer.customer_email
            )
            email = customer.customer_email
            # Load cross-platform User preferences if linked
            if customer.user_id:
                user = db.query(User).filter(User.user_id == customer.user_id).first()
                if user:
                    try:
                        service_interests = json.loads(user.service_interests or "[]")
                    except Exception:
                        pass
                    try:
                        lifestyle_preferences = json.loads(user.lifestyle_preferences or "[]")
                    except Exception:
                        pass
                    try:
                        preferred_locations = json.loads(user.preferred_locations or "[]")
                    except Exception:
                        pass

        total_completed = (
            db.query(Booking)
            .filter(
                Booking.customer_id.in_(customer_ids),
                Booking.status == "completed",
            )
            .count()
        )

        ctx: dict = {
            "customer_name": name,
            "customer_email": email,
            "all_customer_ids": customer_ids,
            "total_completed": total_completed,
            "service_interests": service_interests,
            "lifestyle_preferences": lifestyle_preferences,
            "preferred_locations": preferred_locations,
        }

        if last_booking:
            provider = db.query(Provider).filter(
                Provider.provider_id == last_booking.provider_id
            ).first()
            line_item = (
                db.query(BookingLineItem)
                .filter(BookingLineItem.booking_id == last_booking.booking_id)
                .first()
            )
            ctx.update({
                "last_booking_date": last_booking.scheduled_start.strftime("%B %d, %Y"),
                "last_service": line_item.service_type if line_item else None,
                "last_provider": provider.name if provider else None,
                "last_provider_id": provider.provider_id if provider else None,
            })

        return ctx

    except Exception:
        logger.exception("platform.recognition_error sender=%s", sender_ig_id)
        return None


def _format_returning_context(ctx: dict | None) -> str:
    """Format the returning customer context block for injection into the system prompt."""
    if not ctx:
        return ""

    lines = ["\n\n--- RETURNING CUSTOMER CONTEXT ---"]

    if ctx.get("customer_name"):
        lines.append(f"Customer name: {ctx['customer_name']}")
    if ctx.get("customer_email"):
        lines.append(f"Email on file: {ctx['customer_email']}")
    if ctx.get("total_completed"):
        label = "visit" if ctx["total_completed"] == 1 else "visits"
        lines.append(f"Past bookings: {ctx['total_completed']} completed {label}")

    if ctx.get("last_service") and ctx.get("last_provider"):
        lines.append(
            f"Most recent: {ctx['last_service']} at {ctx['last_provider']}"
            f" ({ctx['last_booking_date']})"
        )

    if ctx.get("service_interests"):
        lines.append(f"Service interests: {', '.join(ctx['service_interests'])}")
    if ctx.get("lifestyle_preferences"):
        lines.append(f"Lifestyle preferences: {', '.join(ctx['lifestyle_preferences'])}")
    if ctx.get("preferred_locations"):
        lines.append(f"Preferred locations: {', '.join(ctx['preferred_locations'])}")
        lines.append(
            "When searching for providers, prioritise their preferred locations above. "
            "Pass a location from this list as the city/area parameter to search_providers."
        )

    lines.append(
        "Greet them warmly by name. Offer to rebook their last service "
        "or help them find something new."
    )
    lines.append("--- END RETURNING CUSTOMER CONTEXT ---")
    return "\n".join(lines)


def _build_platform_system_prompt(returning: dict | None = None) -> str:
    now = datetime.now(tz=tz)
    return _PLATFORM_SYSTEM_PROMPT.format(
        current_date=now.strftime("%A, %B %d, %Y at %H:%M"),
        returning_context=_format_returning_context(returning),
    )


# â”€â”€ Main orchestrator â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def platform_process_message(
    db: Session,
    sender_ig_id: str,
    conversation_id: str,
    text: str,
) -> str:
    """Process a message sent to the @fixmeapp platform account.

    Runs the full OpenAI function-calling loop with platform tools.
    Returns the final reply text to send back via Instagram.
    """
    state = ConversationStateService.get_or_create_state(
        db,
        conversation_id,
        mode="platform",
    )

    if _is_human_request(text):
        ConversationStateService.mark_handoff_requested(db, conversation_id)
        return "Of course. I've asked a human teammate to continue here as soon as possible."

    if state.booking_status == "confirmed" and _is_confirmation_intent(text):
        return "Your booking is already confirmed. If you want to change it, I can help you reschedule or book something else."

    returning = _get_returning_customer_context(db, sender_ig_id)
    if returning:
        logger.info(
            "platform.returning_customer sender=%s name=%s last_booking=%s",
            sender_ig_id,
            returning.get("customer_name"),
            returning.get("last_booking_date"),
        )

    history = ConversationService.get_conversation_history(db, conversation_id, limit=20)
    messages = [{"role": "system", "content": _build_platform_system_prompt(returning)}]

    for msg in history:
        role = "assistant" if msg.direction == "out" else "user"
        messages.append({"role": role, "content": msg.text})

    messages.append({"role": "user", "content": text})

    # â”€â”€ Agentic loop â€” keep going until no more tool calls â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    MAX_ITERATIONS = 6
    for iteration in range(MAX_ITERATIONS):
        try:
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                tools=PLATFORM_TOOLS,
                tool_choice="auto",
                max_tokens=600,
                temperature=0.4,
            )
        except Exception:
            logger.exception("platform.openai_error conversation=%s", conversation_id)
            return "Sorry, I'm having trouble right now. Please try again in a moment! ðŸ™"

        choice = response.choices[0]
        messages.append(choice.message)

        # No tool calls â€” final reply
        if not choice.message.tool_calls:
            reply = choice.message.content or "I'm not sure how to help with that. Can you tell me what service you're looking for and which city you're in?"
            logger.info(
                "platform.reply conversation=%s iterations=%d returning=%s text=%s",
                conversation_id, iteration + 1, bool(returning), reply[:80],
            )
            return reply

        # Execute each tool call
        for tc in choice.message.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}

            logger.info(
                "platform.tool_call conversation=%s tool=%s args=%s",
                conversation_id, tc.function.name, str(args)[:120],
            )

            result = await execute_platform_tool(
                tc.function.name,
                args,
                db=db,
                sender_ig_id=sender_ig_id,
                conversation_id=conversation_id,
            )

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    logger.warning("platform.max_iterations_reached conversation=%s", conversation_id)
    return "Sorry, I got a bit confused there. Could you tell me again what you're looking for? ðŸ˜Š"
