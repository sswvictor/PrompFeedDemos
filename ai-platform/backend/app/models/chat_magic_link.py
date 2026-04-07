import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ChatMagicLink(Base):
    __tablename__ = "chat_magic_links"

    token_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)

    provider_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("providers.provider_id"),
        nullable=True,
    )
    customer_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("customers.customer_id"),
        nullable=True,
    )
    conversation_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("conversations.conversation_id"),
        nullable=True,
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    provider: Mapped["Provider | None"] = relationship("Provider")  # noqa: F821
    customer: Mapped["Customer | None"] = relationship("Customer")  # noqa: F821
    conversation: Mapped["Conversation | None"] = relationship("Conversation")  # noqa: F821
