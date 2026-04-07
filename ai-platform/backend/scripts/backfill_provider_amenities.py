"""One-time backfill for provider amenities.

Current scope:
- If provider.home_service is true and provider has no active amenities,
  add the canonical "home_visits" amenity.

Run:
  python scripts/backfill_provider_amenities.py
"""

from app.db.session import SessionLocal
from app.models.provider import Provider
from app.models.provider_amenity import ProviderAmenity


def main() -> None:
    db = SessionLocal()
    created = 0
    scanned = 0
    try:
        providers = db.query(Provider).all()
        for provider in providers:
            scanned += 1
            if not provider.home_service:
                continue
            existing = (
                db.query(ProviderAmenity)
                .filter(
                    ProviderAmenity.provider_id == provider.provider_id,
                    ProviderAmenity.is_active == True,  # noqa: E712
                )
                .count()
            )
            if existing > 0:
                continue
            db.add(
                ProviderAmenity(
                    provider_id=provider.provider_id,
                    amenity_key="home_visits",
                    is_active=True,
                )
            )
            created += 1

        db.commit()
        print(f"Backfill done. Scanned={scanned}, Created={created}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
