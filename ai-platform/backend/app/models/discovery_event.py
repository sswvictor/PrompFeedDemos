import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DiscoveryEvent(Base):
    """
    Lightweight discovery conversation outcome log for Merkle batching.
    """

    __tablename__ = "discovery_events"
    __table_args__ = (
        Index("ix_discovery_events_discovered_at", "discovered_at"),
        Index("ix_discovery_events_user_id", "user_id"),
        Index("ix_discovery_events_channel", "channel"),
    )

    discovery_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.user_id"), nullable=True
    )
    conversation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conversations.conversation_id"), nullable=True
    )
    service_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_found: Mapped[bool] = mapped_column(Boolean, default=False)
    availability_found: Mapped[bool] = mapped_column(Boolean, default=False)
    converted_to_booking: Mapped[bool] = mapped_column(Boolean, default=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )