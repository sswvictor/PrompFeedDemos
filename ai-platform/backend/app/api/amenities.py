"""
Provider Amenities API

Routes:
    GET  /providers/me/amenities              — get my amenities (auth required)
    PUT  /providers/me/amenities              — set my amenities (auth required, replaces all)
    GET  /providers/{provider_id}/amenities   — get any provider's amenities (public)

Amenity keys (canonical list):
    dog_friendly, wheelchair_accessible, parking, wifi,
    coffee, wine, eco_friendly, home_visits,
    private_studio, child_friendly, evening_hours, card_payment
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_provider
from app.db.session import get_db
from app.models.provider import Provider
from app.models.provider_amenity import ProviderAmenity

router = APIRouter(prefix="/providers", tags=["amenities"])

VALID_AMENITY_KEYS = {
    "dog_friendly",
    "wheelchair_accessible",
    "parking",
    "wifi",
    "coffee",
    "wine",
    "eco_friendly",
    "home_visits",
    "private_studio",
    "child_friendly",
    "evening_hours",
    "card_payment",
}


# ── Schemas ───────────────────────────────────────────────────────────────────

class AmenitiesOut(BaseModel):
    amenities: list[str]


class SetAmenitiesRequest(BaseModel):
    amenity_keys: list[str]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/me/amenities", response_model=AmenitiesOut)
def get_my_amenities(
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Get the authenticated provider's active amenities."""
    rows = (
        db.query(ProviderAmenity)
        .filter(
            ProviderAmenity.provider_id == provider_id,
            ProviderAmenity.is_active == True,  # noqa: E712
        )
        .all()
    )
    return AmenitiesOut(amenities=[r.amenity_key for r in rows])


@router.put("/me/amenities", response_model=AmenitiesOut)
def set_my_amenities(
    payload: SetAmenitiesRequest,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Replace the authenticated provider's amenities."""
    # Validate keys
    invalid = set(payload.amenity_keys) - VALID_AMENITY_KEYS
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid amenity keys: {', '.join(invalid)}",
        )

    # Replace all
    db.query(ProviderAmenity).filter(
        ProviderAmenity.provider_id == provider_id
    ).delete()

    for key in set(payload.amenity_keys):  # deduplicate
        db.add(ProviderAmenity(provider_id=provider_id, amenity_key=key))

    db.commit()
    return AmenitiesOut(amenities=list(set(payload.amenity_keys)))


@router.get("/{provider_id}/amenities", response_model=AmenitiesOut)
def get_provider_amenities(
    provider_id: str,
    db: Session = Depends(get_db),
):
    """Get any provider's amenities — public endpoint for search/discovery."""
    provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    rows = (
        db.query(ProviderAmenity)
        .filter(
            ProviderAmenity.provider_id == provider_id,
            ProviderAmenity.is_active == True,  # noqa: E712
        )
        .all()
    )
    return AmenitiesOut(amenities=[r.amenity_key for r in rows])
