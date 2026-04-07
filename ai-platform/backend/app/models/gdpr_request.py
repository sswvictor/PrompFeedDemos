import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class GDPRRequest(Base):
    __tablename__ = "gdpr_requests"

    request_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.user_id"), nullable=False, index=True
    )

    # "export" | "deletion"
    request_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # "pending" | "in_progress" | "completed" | "rejected"
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)        # user's optional message
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # internal ops notes

    requested_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")  # noqa: F821
