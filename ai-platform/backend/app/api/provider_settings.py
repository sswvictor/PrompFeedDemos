"""
Provider settings API - edit profile, services, hours, amenities after onboarding.

Routes:
    GET   /providers/me/settings         - full settings payload
    PATCH /providers/me/settings         - update profile fields
    PATCH /providers/me/services/{id}    - update a single service
    POST  /providers/me/services         - add a new service
    DELETE /providers/me/services/{id}   - deactivate a service
"""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_provider
from app.db.session import get_db
from app.models.provider import Provider
from app.models.provider_amenity import ProviderAmenity
from app.models.service import Service
from app.models.user import User

router = APIRouter(tags=["provider-settings"])


class ServiceSettingsOut(BaseModel):
    service_id: str
    name: str
    category: str | None
    description: str | None
    duration_minutes: int
    price_ex_vat: float
    is_active: bool
    home_service_available: bool

    model_config = {"from_attributes": True}


class WorkingHourOut(BaseModel):
    day_of_week: int  # 0=Mon ... 6=Sun
    start_minutes: int
    end_minutes: int

    model_config = {"from_attributes": True}


class ProviderSettingsOut(BaseModel):
    """Everything the settings page needs."""

    provider_id: str
    name: str
    email: str | None
    phone: str | None
    city: str | None
    bio: str | None
    image_url: str | None
    instagram_username: str | None
    business_type: str | None
    home_service: bool
    location_salon: str | None
    categories: list[str]
    services: list[ServiceSettingsOut]
    amenities: list[str]
    working_hours: list[WorkingHourOut]


class ProfileUpdateIn(BaseModel):
    """Partial update - only send the fields you want to change."""

    name: str | None = None
    phone: str | None = None
    city: str | None = None
    bio: str | None = None
    instagram_username: str | None = None
    home_service: bool | None = None
    location_salon: str | None = None


class ServiceUpdateIn(BaseModel):
    """Partial update for a single service."""

    name: str | None = None
    category: str | None = None
    description: str | None = None
    duration_minutes: int | None = None
    price_ex_vat: float | None = None
    home_service_available: bool | None = None
    is_active: bool | None = None


class ServiceAddIn(BaseModel):
    """Add a new service."""

    name: str
    category: str | None = None
    description: str | None = None
    duration_minutes: int = 60
    price_ex_vat: float = 0.0
    home_service_available: bool = False


@router.get("/providers/me/settings", response_model=ProviderSettingsOut)
def get_settings(
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Full settings payload - profile, services, hours, amenities."""
    provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    categories: list[str] = []
    if provider.service_categories:
        try:
            categories = json.loads(provider.service_categories)
        except Exception:
            categories = []

    services = [
        ServiceSettingsOut.model_validate(s)
        for s in db.query(Service)
        .filter(Service.provider_id == provider_id)
        .order_by(Service.category, Service.name)
        .all()
    ]

    amenities = [
        a.amenity_key
        for a in db.query(ProviderAmenity)
        .filter(ProviderAmenity.provider_id == provider_id, ProviderAmenity.is_active == True)
        .all()
    ]

    if not amenities and provider.home_service:
        try:
            db.add(
                ProviderAmenity(
                    provider_id=provider_id,
                    amenity_key="home_visits",
                    is_active=True,
                )
            )
            db.commit()
            amenities = ["home_visits"]
        except Exception:
            db.rollback()

    working_hours: list[WorkingHourOut] = []
    try:
        from app.models.working_hours import WorkingHours

        hours_rows = (
            db.query(WorkingHours)
            .filter(WorkingHours.provider_id == provider_id)
            .order_by(WorkingHours.day_of_week)
            .all()
        )
        working_hours = [WorkingHourOut.model_validate(h) for h in hours_rows]
    except Exception:
        pass

    user_email = None
    if provider.user_id:
        user = db.query(User).filter(User.user_id == provider.user_id).first()
        user_email = user.email if user else None

    return ProviderSettingsOut(
        provider_id=provider.provider_id,
        name=provider.name,
        email=user_email,
        phone=provider.phone,
        city=provider.city,
        bio=provider.bio,
        image_url=provider.image_url,
        instagram_username=provider.instagram_username,
        business_type=provider.business_type,
        home_service=bool(provider.home_service),
        location_salon=provider.location_salon,
        categories=categories,
        services=services,
        amenities=amenities,
        working_hours=working_hours,
    )


@router.patch("/providers/me/settings", response_model=ProviderSettingsOut)
def update_settings(
    body: ProfileUpdateIn,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Update profile fields - only the fields you send will change."""
    provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    update_data = body.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(provider, field, value)

    db.commit()
    db.refresh(provider)

    return get_settings(provider_id=provider_id, db=db)


@router.patch("/providers/me/services/{service_id}", response_model=ServiceSettingsOut)
def update_service(
    service_id: str,
    body: ServiceUpdateIn,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Update a single service - toggle home_service_available, change price, etc."""
    service = (
        db.query(Service)
        .filter(Service.service_id == service_id, Service.provider_id == provider_id)
        .first()
    )
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    update_data = body.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(service, field, value)

    db.commit()
    db.refresh(service)
    return service


@router.post("/providers/me/services", response_model=ServiceSettingsOut, status_code=201)
def add_service(
    body: ServiceAddIn,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Add a new service to the provider's catalog."""
    provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
    vat = provider.vat_percent if provider else 25.0

    service = Service(
        service_id=str(uuid.uuid4()),
        provider_id=provider_id,
        name=body.name,
        category=body.category,
        description=body.description,
        duration_minutes=body.duration_minutes,
        price_ex_vat=body.price_ex_vat,
        vat_percent=vat,
        home_service_available=body.home_service_available,
        is_active=True,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@router.delete("/providers/me/services/{service_id}")
def deactivate_service(
    service_id: str,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Soft-delete a service (set is_active = False)."""
    service = (
        db.query(Service)
        .filter(Service.service_id == service_id, Service.provider_id == provider_id)
        .first()
    )
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    service.is_active = False
    db.commit()
    return {"detail": "Service deactivated"}
