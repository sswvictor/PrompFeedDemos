import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Conversation(Base):
    """
    DM conversation thread (Instagram, WhatsApp, web chat, etc.).

    Two conversation types:
    - "booking"   â€” started inside a provider's own Instagram/channel.
                    provider_id is set, user_id may be set once identified.
    - "discovery" â€” started inside Fixmeapp's own Instagram (@fixmeapp).
                    provider_id is NULL, user_id is set from the start.
                    The AI matches the user to providers during this conversation.

    GDPR retention lifecycle:
    1. Conversation closes â†’ signals_extracted_at is set atomically with
       MerkleContributionService.emit_event() calls.
    2. After 30 days (message text) / 90 days booking / 30 days discovery:
       DataRetentionService nulls messages then deletes the conversation.
    3. scheduled_delete_at is computed at close time for efficient indexed queries.
    4. A conversation without signals_extracted_at is NEVER auto-deleted â€”
       the extraction-first invariant is enforced here.
    """
    __tablename__ = "conversations"
    __table_args__ = (
        # Provider-scoped conversations: one thread per provider/channel/thread
        UniqueConstraint("provider_id", "channel", "external_thread_id", name="uq_provider_channel_thread"),
        # Platform-level discovery conversations: one thread per user/channel/thread
        UniqueConstraint("user_id", "channel", "external_thread_id", name="uq_user_channel_thread"),
    )

    conversation_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_type: Mapped[str] = mapped_column(String(20), default="booking")  # booking / discovery
    provider_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.user_id"), nullable=True)
    customer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("customers.customer_id"), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)  # instagram_dm, whatsapp, web
    external_thread_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/closed/archived
    needs_human: Mapped[bool] = mapped_column(Boolean, default=False)  # bot flagged / customer requested human
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # â”€â”€ GDPR retention fields â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Gate: signals must be extracted before any deletion can occur
    signals_extracted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Pre-computed deletion deadline (closed_at + retention period) for fast index scans
    scheduled_delete_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Art. 9 gate: was explicit consent given for health/beauty signal extraction?
    consent_given: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    provider: Mapped["Provider | None"] = relationship("Provider", back_populates="conversations")  # noqa: F821
    user: Mapped["User | None"] = relationship("User", back_populates="conversations")  # noqa: F821
    customer: Mapped["Customer | None"] = relationship("Customer")  # noqa: F821
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    holds: Mapped[list["TimeSlotHold"]] = relationship("TimeSlotHold", back_populates="conversation")  # noqa: F821
    state: Mapped["ConversationState | None"] = relationship(
        "ConversationState",
        back_populates="conversation",
        cascade="all, delete-orphan",
        uselist=False,
    )  # noqa: F821


class Message(Base):
    """
    Single message within a conversation.

    GDPR: text is nulled by DataRetentionService 30 days after the parent
    conversation closes. content_deleted_at records when this happened for
    the audit trail. The metadata row (direction, timestamp) is kept until
    the conversation itself is deleted.
    """
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "idempotency_key", name="uq_conversation_idempotency"),
    )

    message_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.conversation_id"), nullable=False)
    direction: Mapped[str] = mapped_column(String(4), nullable=False)  # in/out
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # â”€â”€ GDPR retention field â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Set when DataRetentionService nulls the text field. Proof of deletion.
    content_deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
