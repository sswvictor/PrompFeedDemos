import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class TimeSlotHold(Base):
    """Temporary slot reservation during a conversation (e.g. while IG bot confirms)."""
    __tablename__ = "timeslot_holds"
    __table_args__ = (
        Index("ix_hold_provider_time", "provider_id", "start", "end"),
    )

    hold_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("conversations.conversation_id"), nullable=True)
    start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    provider: Mapped["Provider"] = relationship("Provider", back_populates="timeslot_holds")  # noqa: F821
    conversation: Mapped["Conversation | None"] = relationship("Conversation", back_populates="holds")  # noqa: F821
