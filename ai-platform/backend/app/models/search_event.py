import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SearchEvent(Base):
    """
    Zero-PII search telemetry for prompt/feed demand analysis.

    We intentionally do NOT store raw prompt text here.
    """

    __tablename__ = "search_events"
    __table_args__ = (
        Index("ix_search_events_searched_at", "searched_at"),
        Index("ix_search_events_query_category", "query_category"),
        Index("ix_search_events_city", "city"),
    )

    search_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    query_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    result_count_band: Mapped[str] = mapped_column(String(20), default="none")
    price_preference: Mapped[int | None] = mapped_column(Integer, nullable=True)
    converted_to_booking: Mapped[bool] = mapped_column(Boolean, default=False)
    platform: Mapped[str] = mapped_column(String(30), default="prompt_feed")
    searched_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )