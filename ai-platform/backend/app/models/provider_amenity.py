"""ProviderAmenity — features/perks a provider offers (coffee, wifi, parking, etc.)."""
import uuid

from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ProviderAmenity(Base):
    __tablename__ = "provider_amenities"

    amenity_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=False)
    amenity_key: Mapped[str] = mapped_column(String(50), nullable=False)  # coffee, wine, eco_friendly, wifi, parking, dog_friendly, wheelchair_accessible
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    provider: Mapped["Provider"] = relationship("Provider", back_populates="amenities")  # noqa: F821
