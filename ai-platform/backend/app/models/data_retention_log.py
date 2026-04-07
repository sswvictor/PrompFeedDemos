"""
DataRetentionLog — cryptographic audit trail for all data deletions.

Every deletion executed by DataRetentionService is recorded here.
This is the proof layer required by GDPR Article 5(2) (accountability principle)
and Article 17 (right to erasure).

This table is APPEND-ONLY. Records are never updated or deleted.
It is the evidence that we did what we promised.

Actions:
  message_content_nulled   — Message.text set to NULL (content erased, metadata kept)
  conversation_deleted     — Conversation + Message rows fully deleted
  user_erased              — Full Art. 17 cascade: User + all linked records deleted
  preference_deleted       — CustomerPreference records deleted on consent withdrawal
  signals_extracted        — Signals extracted from conversation before deletion window

Retention policies:
  30_day_message           — message text nulled 30 days after conversation close
  90_day_booking           — booking conversation deleted 90 days after close
  30_day_discovery         — discovery conversation deleted 30 days after close
  art17_erasure            — explicit user erasure request
  consent_withdrawal       — user withdrew consent, triggering signal deletion
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Integer, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DataRetentionLog(Base):
    """
    Immutable audit log. One row per deletion batch executed.
    Never update or delete rows in this table.
    """
    __tablename__ = "data_retention_log"
    __table_args__ = (
        Index("ix_retention_log_executed_at", "executed_at"),
        Index("ix_retention_log_action", "action"),
    )

    log_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)   # table name
    target_count: Mapped[int] = mapped_column(Integer, nullable=False)     # rows affected
    retention_policy: Mapped[str] = mapped_column(String(50), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    # Optional: comma-separated IDs for high-value deletions (Art. 17 erasures)
    # Not populated for bulk retention runs (too many rows)
    target_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
