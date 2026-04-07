import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ConversationState(Base):
    __tablename__ = "conversation_states"

    state_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.conversation_id"),
        nullable=False,
        unique=True,
        index=True,
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    selected_provider_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    selected_service_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    selected_service_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    selected_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    selected_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    contact_requested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    booking_status: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    handoff_status: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    last_ai_action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="state")  # noqa: F821
