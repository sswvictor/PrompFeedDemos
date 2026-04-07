"""
Platform tool definitions + executor for the @fixmeapp discovery bot.

Unlike the single-provider tools, these tools operate across ALL providers.
The platform bot helps customers FIND and BOOK the right provider.

Tools:
    1. search_providers    — find salons/specialists by service + city + date
    2. get_provider_details — full profile of one provider
    3. book_with_provider   — create a booking with a specific provider
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import settings
from app.services.platform_search_service import search_providers as _search
from app.services.provider_service import ProviderService
from app.services.availability_service import AvailabilityService
from app.services.booking_service import BookingService, SlotUnavailableError
from app.services.customer_service import CustomerService
from app.services.conversation_state_service import ConversationStateService

logger = logging.getLogger(__name__)

tz = ZoneInfo(settings.DEFAULT_TIMEZONE)

# ── Tool definitions (OpenAI function-calling format) ────────────────────────

PLATFORM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_providers",
            "description": (
                "Search for beauty/wellness providers on Fixmeapp by service, city, and optional date. "
                "Returns up to 5 ranked providers with real-time availability. "
                "Use this when a customer is looking for a provider — always search before recommending."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "The service the customer wants, e.g. 'balayage', 'manicure', 'haircut', 'Ghana braids'",
                    },
                    "city": {
                        "type": "string",
                        "description": "City or area to search in, e.g. 'Stockholm', 'Gothenburg'. Ask the customer if not mentioned.",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date to check availability for, in YYYY-MM-DD format. Optional — omit if customer hasn't specified.",
                    },
                    "max_price_sek": {
                        "type": "number",
                        "description": "Maximum price in SEK (inc VAT) the customer is willing to pay. Optional.",
                    },
                    "amenity_keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional required amenities, e.g. ['dog_friendly', 'wine_served']. Only providers with all listed amenities are returned.",
                    },
                },
                "required": ["service", "city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_provider_details",
            "description": "Get full details about a specific provider: all services, working hours, location, and bio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "provider_id": {
                        "type": "string",
                        "description": "The provider_id from search results.",
                    },
                },
                "required": ["provider_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_with_provider",
            "description": (
                "Book an appointment with a specific provider. "
                "Only call this after the customer has confirmed: provider, service, date, and time. "
                "You MUST have the customer's name and email before calling this."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "provider_id": {"type": "string"},
                    "service_id": {"type": "string", "description": "service_id from search or details results"},
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                    "time": {"type": "string", "description": "HH:MM (24h)"},
                    "customer_name": {"type": "string"},
                    "customer_email": {"type": "string"},
                },
                "required": ["provider_id", "service_id", "date", "time", "customer_name", "customer_email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_bookings",
            "description": (
                "Look up this customer's past bookings on Fixmeapp. "
                "Use when the customer asks about their booking history, wants to rebook a previous service, "
                "or when you want to personalise recommendations based on past visits. "
                "Works without any arguments — uses the customer's Instagram identity automatically. "
                "Optionally accept an email if the customer provides one to find additional bookings."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "Customer's email address. Optional — looks up by Instagram identity if omitted.",
                    },
                },
                "required": [],
            },
        },
    },
]


# ── Tool executor ─────────────────────────────────────────────────────────────

async def execute_platform_tool(
    tool_name: str,
    arguments: dict,
    *,
    db: Session,
    sender_ig_id: str | None = None,
    conversation_id: str | None = None,
) -> str:
    """Execute a platform tool call and return the result as a string for the AI."""

    state = (
        ConversationStateService.get_or_create_state(
            db,
            conversation_id,
            mode="platform",
        )
        if conversation_id
        else None
    )

    if tool_name == "search_providers":
        service = arguments.get("service", "")
        city = arguments.get("city", "")
        date_str = arguments.get("date", "")
        max_price = arguments.get("max_price_sek")
        amenity_keys = arguments.get("amenity_keys") or []

        if state and conversation_id:
            ConversationStateService.update_selection(
                db,
                conversation_id,
                service_name=service or None,
                date=date_str or None,
                booking_status="none",
                last_ai_action="search_providers",
            )
            state = ConversationStateService.get_state(db, conversation_id) or state

        date = None
        if date_str:
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tz)
            except ValueError:
                pass

        results = _search(
            db=db,
            service_query=service,
            city=city,
            date=date,
            max_price_inc_vat=float(max_price) if max_price else None,
            amenity_keys=amenity_keys,
        )

        if not results:
            return (
                f"No providers found for '{service}' in {city}"
                + (f" on {date_str}" if date_str else "")
                + ". Try a different city or service, or remove the date filter."
            )

        def _fmt_slots(slots: list[str]) -> str:
            times = []
            for s in slots:
                try:
                    times.append(datetime.fromisoformat(s).strftime("%H:%M"))
                except Exception:
                    times.append(s)
            return ", ".join(times)

        top = results[0]
        top_price = f"{top['price_inc_vat']:.0f} SEK"
        top_duration = f"{top['duration_minutes']} min"

        lines = [
            f"TOP PICK for '{service}' in {city}:",
            f"**{top['provider_name']}** — {top['service_name']}, {top_duration}, {top_price}",
        ]
        if top["slots"]:
            lines.append(f"Available slots: {_fmt_slots(top['slots'])}")
        elif top["has_availability"] is None:
            lines.append("(no specific date requested — ask customer which day they prefer)")
        if top["instagram_username"]:
            lines.append(f"@{top['instagram_username']}")
        lines.append(f"provider_id: {top['provider_id']} | service_id: {top['service_id']}")

        if len(results) > 1:
            lines.append(
                "\nALTERNATIVES — only surface these if the customer explicitly asks "
                "for other options or if TOP PICK has no availability on their date:"
            )
            for r in results[1:]:
                alt = (
                    f"• {r['provider_name']} — {r['service_name']}, "
                    f"{r['price_inc_vat']:.0f} SEK"
                )
                if r["slots"]:
                    alt += f" | {_fmt_slots(r['slots'])}"
                alt += f" | provider_id: {r['provider_id']} | service_id: {r['service_id']}"
                lines.append(alt)

        lines.append(
            "\n[INSTRUCTION] Recommend the TOP PICK confidently like a trusted friend — "
            "\"I found the perfect spot for you! 💇\" — not a numbered list. "
            "Only mention alternatives if the customer is unsatisfied or asks for more options."
        )
        return "\n".join(lines)

    elif tool_name == "get_provider_details":
        provider_id = arguments.get("provider_id", "")
        provider = ProviderService.get_provider(db, provider_id)
        if not provider:
            return f"Provider not found: {provider_id}"

        if state and conversation_id:
            ConversationStateService.update_selection(
                db,
                conversation_id,
                provider_id=provider_id,
                booking_status="none",
                last_ai_action="get_provider_details",
            )
            state = ConversationStateService.get_state(db, conversation_id) or state

        services = ProviderService.get_provider_services(db, provider_id)
        hours = AvailabilityService.get_working_hours(db, provider_id)

        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        hours_lines = []
        for h in hours:
            sh, sm = divmod(h.start_minutes, 60)
            eh, em = divmod(h.end_minutes, 60)
            hours_lines.append(f"  {day_names[h.day_of_week]}: {sh:02d}:{sm:02d}–{eh:02d}:{em:02d}")

        svc_lines = [
            f"  - {s.name} ({s.duration_minutes} min, {round(s.price_ex_vat * 1.25):.0f} SEK) [service_id: {s.service_id}]"
            for s in services
        ]

        parts = [
            f"**{provider.name}**",
            f"City: {provider.city or 'Not specified'}",
            f"Instagram: @{provider.instagram_username}" if provider.instagram_username else "",
            f"Bio: {provider.bio}" if provider.bio else "",
            "",
            "Services:",
            *svc_lines,
            "",
            "Working hours:",
            *hours_lines,
        ]
        return "\n".join(p for p in parts if p is not None)

    elif tool_name == "book_with_provider":
        provider_id = arguments.get("provider_id", "")
        service_id = arguments.get("service_id", "")
        date_str = arguments.get("date", "")
        time_str = arguments.get("time", "")
        customer_name = arguments.get("customer_name", "")
        customer_email = arguments.get("customer_email", "").lower().strip()

        provider = ProviderService.get_provider(db, provider_id)
        if not provider:
            return f"Provider not found: {provider_id}"

        services = ProviderService.get_provider_services(db, provider_id)
        service = next((s for s in services if s.service_id == service_id), None)
        if not service:
            return f"Service not found: {service_id}"

        if state and conversation_id:
            if not state.selected_provider_id:
                return "Please confirm which provider you want first before I complete the booking."
            if state.selected_provider_id != provider_id:
                return "Please confirm this provider first before I switch the booking to a different provider."
            ConversationStateService.update_selection(
                db,
                conversation_id,
                provider_id=provider_id,
                service_id=service_id,
                service_name=service.name,
                date=date_str,
                time=time_str,
                booking_status="pending",
                last_ai_action="book_with_provider_requested",
            )
            state = ConversationStateService.get_state(db, conversation_id) or state

        try:
            start = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
        except ValueError:
            return "Invalid date/time format. Use YYYY-MM-DD and HH:MM."

        from datetime import timedelta
        end = start + timedelta(minutes=service.duration_minutes)

        customer = CustomerService.find_by_email_and_provider(db, provider_id, customer_email)
        if not customer:
            customer = CustomerService.create_customer(
                db=db,
                provider_id=provider_id,
                customer_email=customer_email,
                display_name=customer_name,
                source_channel="instagram_dm",
            )

        try:
            from app.models.user import User
            from app.models.instagram_identity import InstagramIdentity as _IGId
            matched_user = db.query(User).filter(User.email == customer_email).first()
            if matched_user:
                if not customer.user_id:
                    customer.user_id = matched_user.user_id
                    db.add(customer)
                if sender_ig_id:
                    unlinked = db.query(_IGId).filter(
                        _IGId.instagram_user_id == sender_ig_id,
                        _IGId.user_id.is_(None),
                    ).all()
                    for ig in unlinked:
                        ig.user_id = matched_user.user_id
                db.commit()
                logger.info(
                    "platform.user_stitched sender=%s user=%s identities_linked=%d",
                    sender_ig_id, matched_user.user_id, len(unlinked) if sender_ig_id else 0,
                )
        except Exception:
            logger.exception("platform.user_stitching failed (non-blocking)")

        if not AvailabilityService.check_slot_available(db, provider_id, start, end):
            return f"Sorry, {time_str} on {date_str} is no longer available. Please choose another slot."

        try:
            line_items = [{
                "service_type": service.name,
                "unit_price_ex_vat": service.price_ex_vat,
                "quantity": 1,
            }]
            booking = BookingService.create_booking(
                db=db,
                provider_id=provider_id,
                customer_id=customer.customer_id,
                scheduled_start=start,
                scheduled_end=end,
                line_items=line_items,
                customer_notes="Booked via Fixmeapp discovery chat",
                referral_source="instagram",
            )
        except SlotUnavailableError:
            return f"Sorry, {time_str} on {date_str} was just taken by another customer! Please choose a different time."
        except Exception as e:
            logger.exception("platform.book_with_provider failed provider=%s", provider_id)
            return f"Booking failed: {e}"

        if state and conversation_id:
            ConversationStateService.set_contact_details(
                db,
                conversation_id,
                contact_name=customer_name or customer.display_name or None,
                contact_email=customer_email,
            )
            ConversationStateService.update_selection(
                db,
                conversation_id,
                provider_id=provider_id,
                service_id=service_id,
                service_name=service.name,
                date=date_str,
                time=time_str,
                booking_status="confirmed",
                last_ai_action="book_with_provider_confirmed",
            )

        price_inc = round(service.price_ex_vat * 1.25)
        return (
            f"✅ Booked! Here are your details:\n\n"
            f"📍 {provider.name}\n"
            f"💇 {service.name}\n"
            f"📅 {start.strftime('%A, %B %d')} at {start.strftime('%H:%M')}\n"
            f"💰 {price_inc} SEK\n"
            f"📋 Booking #{booking.booking_number}\n\n"
            f"A confirmation has been sent to {customer_email}. See you there! 🎉"
        )

    elif tool_name == "get_my_bookings":
        from app.models.instagram_identity import InstagramIdentity
        from app.models.booking import Booking, BookingLineItem
        from app.models.customer import Customer
        from app.models.provider import Provider

        email = arguments.get("email", "").lower().strip()
        customer_ids: list[str] = []

        # Primary: look up by Instagram identity (zero friction — customer doesn't need to type anything)
        if sender_ig_id:
            identities = db.query(InstagramIdentity).filter(
                InstagramIdentity.instagram_user_id == sender_ig_id
            ).all()
            customer_ids.extend(i.customer_id for i in identities)

        # Secondary: add any additional customers found by email
        if email:
            email_customers = db.query(Customer).filter(
                Customer.customer_email == email
            ).all()
            customer_ids.extend(c.customer_id for c in email_customers)

        customer_ids = list(dict.fromkeys(customer_ids))  # deduplicate, preserve order

        if not customer_ids:
            return (
                "No booking history found for this Instagram account yet. "
                "Once you make your first booking through Fixmeapp, it'll show up here! 🎉"
            )

        # Fetch the 5 most recent bookings (any status except internally cancelled)
        bookings = (
            db.query(Booking)
            .filter(
                Booking.customer_id.in_(customer_ids),
                Booking.status.in_(["completed", "confirmed", "pending", "cancelled"]),
            )
            .order_by(Booking.scheduled_start.desc())
            .limit(5)
            .all()
        )

        if not bookings:
            return "No bookings found yet."

        status_emoji = {
            "completed": "✅",
            "confirmed": "📅",
            "pending": "🕐",
            "cancelled": "❌",
        }

        lines = ["Your recent Fixmeapp bookings:\n"]
        for b in bookings:
            provider = db.query(Provider).filter(Provider.provider_id == b.provider_id).first()
            line_item = (
                db.query(BookingLineItem)
                .filter(BookingLineItem.booking_id == b.booking_id)
                .first()
            )
            service_name = line_item.service_type if line_item else "Appointment"
            salon_name = provider.name if provider else "Salon"
            date_str = b.scheduled_start.strftime("%B %d, %Y at %H:%M")
            emoji = status_emoji.get(b.status, "•")

            line = f"{emoji} {service_name} at {salon_name} — {date_str}"
            if b.status == "completed" and provider:
                line += f"\n   Rebook: provider_id={provider.provider_id}"
            lines.append(line)

        lines.append("\nWant to rebook any of these, or are you looking for something new? ✨")
        return "\n".join(lines)

    else:
        return f"Unknown platform tool: {tool_name}"
