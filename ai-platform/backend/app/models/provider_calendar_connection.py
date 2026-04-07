import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ProviderCalendarConnection(Base):
    __tablename__ = "provider_calendar_connections"
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "connector",
            "external_calendar_id",
            name="uq_provider_connector_calendar",
        ),
    )

    connection_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.provider_id"), nullable=False)

    connector: Mapped[str] = mapped_column(String(20), nullable=False)  # google | microsoft | ics
    external_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_calendar_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    webhook_channel_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    webhook_resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sync_direction: Mapped[str] = mapped_column(String(20), default="read_write", nullable=False)

    last_sync_cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    provider: Mapped["Provider"] = relationship("Provider")  # noqa: F821