"""Ensure a stable demo provider exists for /demo/chat.

Usage:
  py scripts/ensure_demo_provider.py

This script is idempotent: safe to run many times.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.db.session import SessionLocal, assert_schema_up_to_date
from app.models.availability import Availability
from app.models.booking import Booking, BookingLineItem
from app.models.customer import Customer
from app.models.provider import BUSINESS_TYPE_FREELANCER, Provider
from app.models.service import Service
from app.models.user import User


def ensure_user(db: Session, email: str, display_name: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            display_name=display_name,
            is_provider=True,
            is_customer=False,
        )
        db.add(user)
        db.flush()
    else:
        user.is_provider = True
        if not (user.display_name or "").strip():
            user.display_name = display_name
    return user


def ensure_provider(db: Session, user: User, name: str, slug: str) -> Provider:
    provider = db.query(Provider).filter(Provider.user_id == user.user_id).first()
    if not provider:
        provider = db.query(Provider).filter(Provider.slug == slug).first()

    if not provider:
        provider = Provider(
            user_id=user.user_id,
            name=name,
            slug=slug,
            business_type=BUSINESS_TYPE_FREELANCER,
            city="Stockholm",
            location_salon="Demo Studio, Stockholm",
            service_categories=json.dumps(["hair"]),
            home_service=False,
            phone="+46 70 000 00 00",
            bio="Demo profile for investor booking flow.",
            price_level=3,
        )
        db.add(provider)
        db.flush()
        return provider

    provider.user_id = user.user_id
    if not (provider.name or "").strip():
        provider.name = name
    if not (provider.slug or "").strip():
        provider.slug = slug
    if not (provider.business_type or "").strip():
        provider.business_type = BUSINESS_TYPE_FREELANCER
    if not (provider.city or "").strip():
        provider.city = "Stockholm"
    if not (provider.location_salon or "").strip():
        provider.location_salon = "Demo Studio, Stockholm"
    if not (provider.service_categories or "").strip():
        provider.service_categories = json.dumps(["hair"])
    if provider.price_level is None:
        provider.price_level = 3
    return provider


def ensure_services(db: Session, provider: Provider) -> int:
    seeds = [
        {
            "name": "Haircut",
            "category": "hair",
            "duration_minutes": 60,
            "price_ex_vat": 820.0,
            "keywords": "haircut, cut, klippning",
        },
        {
            "name": "Balayage",
            "category": "hair",
            "duration_minutes": 150,
            "price_ex_vat": 2100.0,
            "keywords": "balayage, highlights, slingor",
        },
        {
            "name": "Haircut + Balayage",
            "category": "hair",
            "duration_minutes": 180,
            "price_ex_vat": 2600.0,
            "keywords": "haircut and balayage, klippning och balayage",
        },
    ]

    changed = 0
    for seed in seeds:
        row = (
            db.query(Service)
            .filter(Service.provider_id == provider.provider_id, Service.name == seed["name"])
            .first()
        )
        if not row:
            row = Service(provider_id=provider.provider_id, name=seed["name"])
            db.add(row)
            changed += 1

        row.category = seed["category"]
        row.duration_minutes = seed["duration_minutes"]
        row.price_ex_vat = seed["price_ex_vat"]
        row.vat_percent = 25.0
        row.keywords = seed["keywords"]
        row.is_active = True

    return changed


def ensure_hours(db: Session, provider: Provider) -> int:
    # Mon-Fri 09:00-17:00
    changed = 0
    for day in range(5):
        row = (
            db.query(Availability)
            .filter(Availability.provider_id == provider.provider_id, Availability.day_of_week == day)
            .first()
        )
        if not row:
            row = Availability(
                provider_id=provider.provider_id,
                day_of_week=day,
                start_minutes=9 * 60,
                end_minutes=17 * 60,
            )
            db.add(row)
            changed += 1
        else:
            row.start_minutes = 9 * 60
            row.end_minutes = 17 * 60

    return changed


def _next_customer_number(db: Session, provider_id: str) -> int:
    max_number = (
        db.query(func.max(Customer.customer_number))
        .filter(Customer.provider_id == provider_id)
        .scalar()
    )
    return int(max_number or 0) + 1


def _next_booking_number(db: Session, provider_id: str) -> int:
    max_number = (
        db.query(func.max(Booking.booking_number))
        .filter(Booking.provider_id == provider_id)
        .scalar()
    )
    return int(max_number or 0) + 1


def _get_or_create_customer(db: Session, provider_id: str, email: str, name: str) -> Customer:
    customer = (
        db.query(Customer)
        .filter(Customer.provider_id == provider_id, Customer.customer_email == email)
        .first()
    )
    if customer:
        if not (customer.display_name or "").strip():
            customer.display_name = name
        return customer

    customer = Customer(
        provider_id=provider_id,
        customer_email=email,
        display_name=name,
        customer_number=_next_customer_number(db, provider_id),
        source_channel="app",
        merge_status="primary",
    )
    db.add(customer)
    db.flush()
    return customer


def ensure_demo_bookings(db: Session, provider: Provider) -> int:
    services = (
        db.query(Service)
        .filter(Service.provider_id == provider.provider_id, Service.is_active == True)  # noqa: E712
        .order_by(Service.duration_minutes.asc(), Service.name.asc())
        .all()
    )
    if not services:
        return 0

    now = datetime.now(timezone.utc)
    start_of_tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    # 6 realistic upcoming bookings over next two days.
    slots = [
        (0, 9, 0),
        (0, 11, 0),
        (0, 14, 30),
        (1, 9, 30),
        (1, 12, 30),
        (1, 15, 0),
    ]

    created = 0
    for index, (day_offset, hour, minute) in enumerate(slots, start=1):
        service = services[(index - 1) % len(services)]
        start_at = start_of_tomorrow + timedelta(days=day_offset, hours=hour, minutes=minute)
        if start_at <= now:
            continue

        exists = (
            db.query(Booking)
            .filter(Booking.provider_id == provider.provider_id, Booking.scheduled_start == start_at)
            .first()
        )
        if exists:
            continue

        customer = _get_or_create_customer(
            db,
            provider_id=provider.provider_id,
            email=f"demo.customer.{index}@fixmeapp.ai",
            name=f"Demo Customer {index}",
        )

        ex_vat = float(service.price_ex_vat or 0.0)
        vat = round(ex_vat * 0.25, 2)
        inc_vat = round(ex_vat + vat, 2)
        end_at = start_at + timedelta(minutes=int(service.duration_minutes or 60))

        booking = Booking(
            provider_id=provider.provider_id,
            customer_id=customer.customer_id,
            booking_number=_next_booking_number(db, provider.provider_id),
            status="confirmed",
            scheduled_start=start_at,
            scheduled_end=end_at,
            total_amount_ex_vat=ex_vat,
            total_vat_amount=vat,
            total_amount_inc_vat=inc_vat,
            customer_notes="Seeded demo booking for provider home page.",
            session_preferences=json.dumps(["quiet_session"] if index % 2 else ["coffee_please"]),
            referral_source="provider_link" if index % 2 else "instagram",
        )
        db.add(booking)
        db.flush()

        db.add(
            BookingLineItem(
                booking_id=booking.booking_id,
                service_type=service.name,
                quantity=1,
                unit_price_ex_vat=ex_vat,
                vat_percent=25.0,
                total_line_ex_vat=ex_vat,
                total_line_vat=vat,
                total_line_inc_vat=inc_vat,
            )
        )
        created += 1

    return created


def main() -> None:
    assert_schema_up_to_date()

    email = (settings.DEMO_PROVIDER_EMAIL or "johanna@fixmeapp.ai").strip().lower()
    provider_name = "Johanna Fixme Hair"
    provider_slug = "johanna-fixme-hair"

    db = SessionLocal()
    try:
        user = ensure_user(db, email=email, display_name="Johanna")
        provider = ensure_provider(db, user=user, name=provider_name, slug=provider_slug)
        service_changes = ensure_services(db, provider)
        hour_changes = ensure_hours(db, provider)
        booking_changes = ensure_demo_bookings(db, provider)
        db.commit()

        print("Demo provider ready")
        print(f"email={email}")
        print(f"provider_id={provider.provider_id}")
        print(f"provider_name={provider.name}")
        print(f"provider_slug={provider.slug}")
        print(f"service_changes={service_changes}")
        print(f"hour_changes={hour_changes}")
        print(f"booking_changes={booking_changes}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
