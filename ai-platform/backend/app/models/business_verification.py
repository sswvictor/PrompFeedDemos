import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class BusinessVerification(Base):
    """
    Stores a pending business / professional-license verification request.

    Sensitive identifiers (license_number, org_number) are stored in plaintext
    ONLY while status == 'pending'.  They are wiped (set to NULL) immediately
    after the submission is approved or rejected by an admin reviewer.
    """

    __tablename__ = "business_verifications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    provider_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("providers.provider_id"), nullable=False, index=True
    )

    # ── What was submitted ────────────────────────────────────────────────────
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="US")
    # US-specific
    us_state: Mapped[str | None] = mapped_column(String(2), nullable=True)    # e.g. "CA"
    license_type: Mapped[str | None] = mapped_column(String(64), nullable=True) # e.g. "cosmetologist"
    # Sensitive — wiped after review
    license_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    org_number: Mapped[str | None] = mapped_column(String(128), nullable=True)   # non-US

    document_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Review state ─────────────────────────────────────────────────────────
    # pending | approved | rejected
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
