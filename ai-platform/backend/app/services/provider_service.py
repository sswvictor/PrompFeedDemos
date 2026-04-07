from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.provider import Provider
from app.models.service import Service


class ProviderService:

    @staticmethod
    def search_providers(
        db: Session,
        location: str | None = None,
        service_category: str | None = None,
        service_name: str | None = None,
        home_service: bool | None = None,
        provider_name: str | None = None,
    ) -> list[Provider]:
        """Search providers by location, service type, provider name, or home service.

        Location matches both city and location_salon — onboarding only sets city,
        so searching 'Stockholm' must hit city too.

        Service category also matches Service.name — services created at onboarding
        have category=None, so a search for 'hair' must still find 'Haircut' services.

        Provider name and instagram_username are also searchable so customers can
        find a specific person or salon by name.
        """
        q = db.query(Provider).filter(Provider.name.isnot(None))  # base query

        # Location: match city OR full address (location_salon)
        # Onboarding sets city but leaves location_salon null — we need both.
        if location:
            q = q.filter(
                or_(
                    Provider.city.ilike(f"%{location}%"),
                    Provider.location_salon.ilike(f"%{location}%"),
                )
            )

        if home_service is not None:
            q = q.filter(Provider.home_service == home_service)

        # Provider name / Instagram username search
        if provider_name:
            q = q.filter(
                or_(
                    Provider.name.ilike(f"%{provider_name}%"),
                    Provider.instagram_username.ilike(f"%{provider_name}%"),
                )
            )

        # Service match: category OR name (covers onboarding providers where category=None)
        if service_category or service_name:
            q = q.join(Service, Service.provider_id == Provider.provider_id)
            q = q.filter(Service.is_active == True)  # noqa: E712
            if service_category:
                q = q.filter(
                    or_(
                        Service.category.ilike(f"%{service_category}%"),
                        Service.name.ilike(f"%{service_category}%"),
                    )
                )
            if service_name:
                q = q.filter(Service.name.ilike(f"%{service_name}%"))

        return q.distinct().all()

    @staticmethod
    def get_provider(db: Session, provider_id: str) -> Provider | None:
        return db.query(Provider).filter(Provider.provider_id == provider_id).first()

    @staticmethod
    def get_provider_services(
        db: Session,
        provider_id: str,
        category: str | None = None,
        active_only: bool = True,
    ) -> list[Service]:
        q = db.query(Service).filter(Service.provider_id == provider_id)
        if active_only:
            q = q.filter(Service.is_active == True)  # noqa: E712
        if category:
            q = q.filter(Service.category.ilike(f"%{category}%"))
        return q.order_by(Service.category, Service.name).all()

    @staticmethod
    def create_service(
        db: Session,
        provider_id: str,
        name: str,
        duration_minutes: int,
        price_ex_vat: float,
        category: str | None = None,
        description: str | None = None,
        vat_percent: float | None = None,
        home_service_available: bool = False,
    ) -> Service:
        service = Service(
            provider_id=provider_id,
            name=name,
            category=category,
            description=description,
            duration_minutes=duration_minutes,
            price_ex_vat=price_ex_vat,
            vat_percent=vat_percent,
            home_service_available=home_service_available,
        )
        db.add(service)
        db.commit()
        db.refresh(service)
        return service

    @staticmethod
    def update_service(db: Session, service_id: str, **kwargs) -> Service:
        service = db.query(Service).filter(Service.service_id == service_id).first()
        if not service:
            raise ValueError(f"Service {service_id} not found")
        allowed = {"name", "category", "description", "duration_minutes", "price_ex_vat", "vat_percent", "is_active", "home_service_available"}
        for key, val in kwargs.items():
            if key in allowed and val is not None:
                setattr(service, key, val)
        db.commit()
        db.refresh(service)
        return service

    @staticmethod
    def delete_service(db: Session, service_id: str, provider_id: str) -> None:
        service = db.query(Service).filter(
            Service.service_id == service_id,
            Service.provider_id == provider_id,
        ).first()
        if not service:
            raise ValueError(f"Service {service_id} not found")
        db.delete(service)
        db.commit()
