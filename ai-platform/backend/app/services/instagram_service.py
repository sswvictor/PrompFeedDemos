from sqlalchemy.orm import Session

from app.models.instagram_identity import InstagramIdentity
from app.services.customer_service import CustomerService


class InstagramMappingService:

    @staticmethod
    def resolve_or_create_customer(
        db: Session,
        provider_id: str,
        instagram_user_id: str,
        instagram_username: str | None = None,
    ) -> InstagramIdentity:
        """
        Core Instagram bot resolution:
        1. Look up existing mapping for this provider + instagram_user_id
        2. If found, return it (update username if changed)
        3. If not found, create a new Customer + InstagramIdentity
        """
        existing = db.query(InstagramIdentity).filter(
            InstagramIdentity.provider_id == provider_id,
            InstagramIdentity.instagram_user_id == instagram_user_id,
        ).first()

        if existing:
            # Update username snapshot if it changed
            if instagram_username and existing.instagram_username != instagram_username:
                existing.instagram_username = instagram_username
                existing.customer.instagram_username_snapshot = instagram_username
                db.commit()
                db.refresh(existing)
            return existing

        # Create new customer for this provider
        customer = CustomerService.create_customer(
            db=db,
            provider_id=provider_id,
            instagram_username_snapshot=instagram_username,
        )

        identity = InstagramIdentity(
            provider_id=provider_id,
            instagram_user_id=instagram_user_id,
            instagram_username=instagram_username,
            customer_id=customer.customer_id,
        )
        db.add(identity)
        db.commit()
        db.refresh(identity)
        return identity

    @staticmethod
    def get_identity(db: Session, provider_id: str, instagram_user_id: str) -> InstagramIdentity | None:
        return db.query(InstagramIdentity).filter(
            InstagramIdentity.provider_id == provider_id,
            InstagramIdentity.instagram_user_id == instagram_user_id,
        ).first()

    @staticmethod
    def link_to_user(db: Session, identity_id: str, user_id: str) -> InstagramIdentity:
        """Link an Instagram identity to a platform User account."""
        identity = db.query(InstagramIdentity).filter(InstagramIdentity.id == identity_id).first()
        if not identity:
            raise ValueError(f"InstagramIdentity {identity_id} not found")
        identity.user_id = user_id
        db.commit()
        db.refresh(identity)
        return identity
