import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class InstagramIdentity(Base):
    __tablename__ = "instagram_identities"
    __table_args__ = (
        UniqueConstraint("provider_id", "instagram_user_id", name="uq_provider_ig_user"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=False)
    instagram_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    instagram_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.customer_id"), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    provider: Mapped["Provider"] = relationship("Provider", back_populates="instagram_identities")  # noqa: F821
    customer: Mapped["Customer"] = relationship("Customer", back_populates="instagram_identities")  # noqa: F821
    user: Mapped["User | None"] = relationship("User", back_populates="instagram_identities")  # noqa: F821
