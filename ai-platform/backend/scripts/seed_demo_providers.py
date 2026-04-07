"""Seed demo providers for investor rehearsal (idempotent).

Creates:
- 5 providers with realistic categories/amenities/services
- Weekly working hours for each provider
- A "fully booked" provider with confirmed bookings tomorrow
- Active waitlist entries for that fully booked provider

Run:
  python scripts/seed_demo_providers.py
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func

from app.db.session import SessionLocal, assert_schema_up_to_date
from app.models.availability import Availability
from app.models.booking import Booking, BookingLineItem
from app.models.customer import Customer
from app.models.provider import Provider, BUSINESS_TYPE_FREELANCER
from app.models.provider_amenity import ProviderAmenity
from app.models.service import Service
from app.models.waitlist import WaitlistEntry


@dataclass
class ServiceSeed:
    name: str
    category: str
    duration_minutes: int
    price_ex_vat: float
    keywords: str
    home_service_available: bool = False


@dataclass
class ProviderSeed:
    slug: str
    name: str
    city: str
    location_salon: str
    bio: str
    price_level: int
    categories: list[str]
    amenities: list[str]
    services: list[ServiceSeed]
    hours: list[tuple[int, int, int]]  # (day_of_week, start_minutes, end_minutes)


def stable_uuid(key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"fixmeapp:{key}"))


def next_customer_number(db, provider_id: str) -> int:
    max_num = (
        db.query(func.max(Customer.customer_number))
        .filter(Customer.provider_id == provider_id)
        .scalar()
    )
    return int(max_num or 0) + 1


def next_booking_number(db, provider_id: str) -> int:
    max_num = (
        db.query(func.max(Booking.booking_number))
        .filter(Booking.provider_id == provider_id)
        .scalar()
    )
    return int(max_num or 0) + 1


def upsert_provider(db, seed: ProviderSeed) -> Provider:
    provider = db.query(Provider).filter(Provider.slug == seed.slug).first()
    if not provider:
        provider = Provider(
            provider_id=stable_uuid(f"provider:{seed.slug}"),
            slug=seed.slug,
        )
        db.add(provider)

    provider.name = seed.name
    provider.city = seed.city
    provider.location_salon = seed.location_salon
    provider.bio = seed.bio
    provider.business_type = BUSINESS_TYPE_FREELANCER
    provider.service_categories = json.dumps(seed.categories)
    provider.price_level = seed.price_level
    provider.home_service = "home_visits" in seed.amenities
    provider.instagram_username = seed.slug.replace("-", "_")
    provider.phone = "+46 70 000 00 00"

    db.flush()
    return provider


def upsert_services(db, provider: Provider, services: list[ServiceSeed]) -> None:
    for svc in services:
        row = (
            db.query(Service)
            .filter(
                Service.provider_id == provider.provider_id,
                Service.name == svc.name,
            )
            .first()
        )
        if not row:
            row = Service(
                service_id=stable_uuid(f"service:{provider.slug}:{svc.name.lower()}"),
                provider_id=provider.provider_id,
                name=svc.name,
            )
            db.add(row)

        row.category = svc.category
        row.duration_minutes = svc.duration_minutes
        row.price_ex_vat = svc.price_ex_vat
        row.vat_percent = 25.0
        row.keywords = svc.keywords
        row.home_service_available = svc.home_service_available
        row.is_active = True


def upsert_amenities(db, provider: Provider, amenity_keys: list[str]) -> None:
    existing = {
        a.amenity_key: a
        for a in db.query(ProviderAmenity)
        .filter(ProviderAmenity.provider_id == provider.provider_id)
        .all()
    }
    wanted = set(amenity_keys)
    for key in wanted:
        row = existing.get(key)
        if not row:
            row = ProviderAmenity(
                amenity_id=stable_uuid(f"amenity:{provider.slug}:{key}"),
                provider_id=provider.provider_id,
                amenity_key=key,
                is_active=True,
            )
            db.add(row)
        else:
            row.is_active = True

    for key, row in existing.items():
        if key not in wanted:
            row.is_active = False


def upsert_hours(db, provider: Provider, hours: list[tuple[int, int, int]]) -> None:
    existing = {
        (h.day_of_week, h.start_minutes, h.end_minutes): h
        for h in db.query(Availability)
        .filter(Availability.provider_id == provider.provider_id)
        .all()
    }
    wanted = set(hours)
    for item in wanted:
        if item in existing:
            continue
        day, start_m, end_m = item
        db.add(
            Availability(
                availability_id=stable_uuid(
                    f"availability:{provider.slug}:{day}:{start_m}:{end_m}"
                ),
                provider_id=provider.provider_id,
                day_of_week=day,
                start_minutes=start_m,
                end_minutes=end_m,
            )
        )


def get_or_create_customer(db, provider_id: str, email: str, name: str) -> Customer:
    row = (
        db.query(Customer)
        .filter(
            Customer.provider_id == provider_id,
            Customer.customer_email == email,
        )
        .first()
    )
    if row:
        if name and not row.display_name:
            row.display_name = name
        return row

    row = Customer(
        customer_id=stable_uuid(f"customer:{provider_id}:{email.lower()}"),
        provider_id=provider_id,
        customer_email=email.lower(),
        display_name=name,
        customer_number=next_customer_number(db, provider_id),
        source_channel="app",
    )
    db.add(row)
    db.flush()
    return row


def seed_full_calendar_and_waitlist(db, provider: Provider) -> tuple[int, int]:
    target_service = (
        db.query(Service)
        .filter(
            Service.provider_id == provider.provider_id,
            Service.is_active == True,  # noqa: E712
        )
        .order_by(Service.duration_minutes.asc())
        .first()
    )
    if not target_service:
        return 0, 0

    tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
    start_hours = [9, 10, 11, 13, 14, 15]

    created_bookings = 0
    for hour in start_hours:
        start_dt = datetime.combine(tomorrow, time(hour=hour, minute=0), tzinfo=timezone.utc)
        end_dt = start_dt + timedelta(minutes=target_service.duration_minutes)

        existing = (
            db.query(Booking)
            .filter(
                Booking.provider_id == provider.provider_id,
                Booking.scheduled_start == start_dt,
            )
            .first()
        )
        if existing:
            continue

        email = f"seed-booked-{hour}@fixmeapp.test"
        customer = get_or_create_customer(db, provider.provider_id, email, f"Booked Customer {hour}")
        amount_ex = float(target_service.price_ex_vat)
        vat = round(amount_ex * 0.25, 2)

        booking = Booking(
            booking_id=stable_uuid(f"booking:{provider.slug}:{tomorrow.isoformat()}:{hour}"),
            provider_id=provider.provider_id,
            customer_id=customer.customer_id,
            booking_number=next_booking_number(db, provider.provider_id),
            status="confirmed",
            scheduled_start=start_dt,
            scheduled_end=end_dt,
            total_amount_ex_vat=amount_ex,
            total_vat_amount=vat,
            total_amount_inc_vat=round(amount_ex + vat, 2),
            customer_notes="Seeded demo booking (full calendar).",
            referral_source="instagram",
        )
        db.add(booking)
        db.flush()

        db.add(
            BookingLineItem(
                booking_item_id=stable_uuid(f"booking-item:{booking.booking_id}:1"),
                booking_id=booking.booking_id,
                service_type=target_service.name,
                quantity=1,
                unit_price_ex_vat=amount_ex,
                vat_percent=25.0,
                total_line_ex_vat=amount_ex,
                total_line_vat=vat,
                total_line_inc_vat=round(amount_ex + vat, 2),
            )
        )
        created_bookings += 1

    waitlist_rows = [
        ("waitlist1@fixmeapp.test", "Anna Waitlist"),
        ("waitlist2@fixmeapp.test", "Nora Queue"),
        ("waitlist3@fixmeapp.test", "Mila Standby"),
    ]
    created_waitlist = 0
    for email, name in waitlist_rows:
        existing = (
            db.query(WaitlistEntry)
            .filter(
                WaitlistEntry.provider_id == provider.provider_id,
                WaitlistEntry.customer_email == email,
                WaitlistEntry.status == "active",
            )
            .first()
        )
        if existing:
            continue

        db.add(
            WaitlistEntry(
                entry_id=stable_uuid(f"waitlist:{provider.slug}:{email}"),
                provider_id=provider.provider_id,
                customer_email=email,
                customer_name=name,
                service_id=target_service.service_id,
                preferred_days=json.dumps([0, 1, 2, 3, 4, 5]),
                preferred_earliest_hour=9,
                preferred_latest_hour=18,
                status="active",
            )
        )
        created_waitlist += 1

    return created_bookings, created_waitlist


def seeds() -> list[ProviderSeed]:
    weekday_hours = [(d, 9 * 60, 17 * 60) for d in range(0, 5)]
    extended_hours = [(d, 10 * 60, 19 * 60) for d in range(0, 6)]
    return [
        ProviderSeed(
            slug="lina-berg-hair",
            name="Lina Berg Hair",
            city="Stockholm",
            location_salon="Hornsgatan 10, Stockholm",
            bio="Blondes, balayage and precision cuts with low-maintenance finish.",
            price_level=3,
            categories=["hair"],
            amenities=["wifi", "coffee", "card_payment"],
            services=[
                ServiceSeed("Haircut Short", "hair", 45, 650, "short haircut, trim"),
                ServiceSeed("Haircut Medium", "hair", 60, 820, "medium length haircut"),
                ServiceSeed("Balayage Refresh", "hair", 120, 1600, "balayage, highlights"),
            ],
            hours=weekday_hours,
        ),
        ProviderSeed(
            slug="emma-color-stockholm",
            name="Emma Color Studio",
            city="Stockholm",
            location_salon="Norrlandsgatan 12, Stockholm",
            bio="Color specialist for dimensional blondes and brunettes.",
            price_level=4,
            categories=["hair"],
            amenities=["dog_friendly", "wine", "card_payment", "wifi"],
            services=[
                ServiceSeed("Full Color", "hair", 150, 2100, "hair color, full color"),
                ServiceSeed("Root Touch Up", "hair", 90, 1200, "roots, regrowth"),
                ServiceSeed("Gloss + Blowout", "hair", 75, 980, "gloss, toner, blow dry"),
            ],
            hours=extended_hours,
        ),
        ProviderSeed(
            slug="noor-nails-sodermalm",
            name="Noor Nails Sodermalm",
            city="Stockholm",
            location_salon="Gotgatan 88, Stockholm",
            bio="Clean nail art and gel sets with strong retention.",
            price_level=2,
            categories=["nails"],
            amenities=["wifi", "coffee", "child_friendly"],
            services=[
                ServiceSeed("Gel Manicure", "nails", 60, 550, "gel manicure, shellac"),
                ServiceSeed("Nail Art Level 1", "nails", 90, 800, "nail art, design"),
                ServiceSeed("Gel Removal + New Set", "nails", 80, 700, "gel removal"),
            ],
            hours=weekday_hours,
        ),
        ProviderSeed(
            slug="sara-balayage-vasastan",
            name="Sara Balayage Vasastan",
            city="Stockholm",
            location_salon="Odengatan 54, Stockholm",
            bio="High-demand balayage specialist with long-session color work.",
            price_level=4,
            categories=["hair"],
            amenities=["wifi", "coffee", "card_payment"],
            services=[
                ServiceSeed("Signature Balayage", "hair", 180, 2600, "balayage, color correction"),
                ServiceSeed("Face Frame Highlights", "hair", 90, 1100, "face frame, highlights"),
                ServiceSeed("Haircut + Styling", "hair", 70, 900, "haircut, styling"),
            ],
            hours=weekday_hours,
        ),
        ProviderSeed(
            slug="oliver-barber-solna",
            name="Oliver Barber Solna",
            city="Solna",
            location_salon="Rasundavagen 41, Solna",
            bio="Classic and modern barber cuts with beard detail work.",
            price_level=2,
            categories=["barber", "hair"],
            amenities=["parking", "coffee", "card_payment"],
            services=[
                ServiceSeed("Skin Fade", "barber", 45, 500, "skin fade, fade"),
                ServiceSeed("Beard Trim", "barber", 30, 320, "beard trim, beard shape"),
                ServiceSeed("Cut + Beard Combo", "barber", 60, 700, "haircut and beard"),
            ],
            hours=extended_hours,
        ),
    ]


def main() -> None:
    assert_schema_up_to_date()
    db = SessionLocal()
    upserted = 0
    created_bookings = 0
    created_waitlist = 0
    try:
        for seed in seeds():
            provider = upsert_provider(db, seed)
            upsert_services(db, provider, seed.services)
            upsert_amenities(db, provider, seed.amenities)
            upsert_hours(db, provider, seed.hours)
            upserted += 1

            if seed.slug == "sara-balayage-vasastan":
                b_count, w_count = seed_full_calendar_and_waitlist(db, provider)
                created_bookings += b_count
                created_waitlist += w_count

        db.commit()
        print(
            "Demo seed complete: "
            f"providers_upserted={upserted}, "
            f"bookings_created={created_bookings}, "
            f"waitlist_created={created_waitlist}"
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
