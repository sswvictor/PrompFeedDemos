"""
Maps Instagram Page IDs to Providers — or to the Fixmeapp platform itself.

When Meta sends a webhook, the recipient_id is the IG page ID.
This table auto-resolves which provider the message belongs to,
removing the need for the X-Provider-Id header hack.

Platform page (is_platform_page=True):
    provider_id is NULL. The page belongs to Fixmeapp's own Instagram account
    (@fixmeapp). Incoming DMs are routed to the discovery bot instead of any
    provider's booking bot.

Provider page (is_platform_page=False, default):
    provider_id is set. The page belongs to a connected provider. Incoming DMs
    are routed to that provider's booking bot as before.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ProviderInstagramPage(Base):
    __tablename__ = "provider_instagram_pages"
    __table_args__ = (
        UniqueConstraint("instagram_page_id", name="uq_instagram_page_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=True)
    is_platform_page: Mapped[bool] = mapped_column(Boolean, default=False)
    instagram_page_id: Mapped[str] = mapped_column(String(128), nullable=False)
    page_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    provider: Mapped["Provider | None"] = relationship("Provider", back_populates="instagram_pages")  # noqa: F821
