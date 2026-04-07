import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LoyaltyEvent(Base):
    __tablename__ = "loyalty_events"

    event_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)  # customer | provider
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    unique_event_key: Mapped[str | None] = mapped_column(
        String(191), nullable=True, unique=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
