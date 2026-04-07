"""
ConsentService — GDPR Article 7 / Article 9 consent management.

All consent operations go through this service. Direct writes to
ConsentRecord are not permitted from other services.

Usage:
    # At Instagram DM onboarding — after explaining data use:
    ConsentService.record_consent(db, user_id, "marketplace_signals", "instagram_dm", "2026-02")

    # Before extracting health signals from a conversation:
    if not ConsentService.check_consent(db, user_id, "health_data_processing"):
        # skip health signal extraction
        pass

    # When user requests withdrawal:
    ConsentService.withdraw_consent(db, user_id, "marketplace_signals", "User requested in app")
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.consent_record import ConsentRecord, CONSENT_TYPES
from app.models.data_retention_log import DataRetentionLog


CURRENT_PRIVACY_POLICY_VERSION = "2026-02"


class ConsentService:

    @staticmethod
    def record_consent(
        db: Session,
        user_id: str,
        consent_type: str,
        channel: str,
        version: str = CURRENT_PRIVACY_POLICY_VERSION,
    ) -> ConsentRecord:
        """
        Record explicit consent from a user.

        Idempotent: if an active consent of this type already exists for this
        user + version, returns the existing record without creating a duplicate.

        Args:
            user_id:      Platform-level User.user_id.
            consent_type: One of CONSENT_TYPES.
            channel:      Where consent was collected (instagram_dm / web / app).
            version:      Privacy policy version the user consented to.
        """
        if consent_type not in CONSENT_TYPES:
            raise ValueError(f"Unknown consent_type '{consent_type}'. Valid: {CONSENT_TYPES}")

        # Check for existing active consent for this version
        existing = db.query(ConsentRecord).filter(
            ConsentRecord.user_id == user_id,
            ConsentRecord.consent_type == consent_type,
            ConsentRecord.version == version,
            ConsentRecord.withdrawn_at.is_(None),
        ).first()
        if existing:
            return existing

        record = ConsentRecord(
            user_id=user_id,
            consent_type=consent_type,
            channel=channel,
            version=version,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def check_consent(
        db: Session,
        user_id: str,
        consent_type: str,
    ) -> bool:
        """
        Return True if the user has an active, non-withdrawn consent of this type.

        Use this as a gate before any signal extraction or marketplace processing.
        """
        if consent_type not in CONSENT_TYPES:
            raise ValueError(f"Unknown consent_type '{consent_type}'.")

        record = db.query(ConsentRecord).filter(
            ConsentRecord.user_id == user_id,
            ConsentRecord.consent_type == consent_type,
            ConsentRecord.withdrawn_at.is_(None),
        ).first()
        return record is not None

    @staticmethod
    def withdraw_consent(
        db: Session,
        user_id: str,
        consent_type: str,
        reason: str | None = None,
    ) -> list[ConsentRecord]:
        """
        Withdraw all active consents of this type for the user.

        Sets withdrawn_at on all matching active records. The original grant
        records are preserved for the audit trail (append-only log principle).

        Returns the list of records that were withdrawn.
        """
        if consent_type not in CONSENT_TYPES:
            raise ValueError(f"Unknown consent_type '{consent_type}'.")

        active = db.query(ConsentRecord).filter(
            ConsentRecord.user_id == user_id,
            ConsentRecord.consent_type == consent_type,
            ConsentRecord.withdrawn_at.is_(None),
        ).all()

        now = datetime.now(timezone.utc)
        for record in active:
            record.withdrawn_at = now
            record.withdrawal_reason = reason

        if active:
            # Log the withdrawal for the GDPR audit trail
            log = DataRetentionLog(
                action="consent_withdrawn",
                target_type="consent_records",
                target_count=len(active),
                retention_policy="consent_withdrawal",
                notes=f"user_id={user_id} consent_type={consent_type}",
            )
            db.add(log)
            db.commit()

        return active

    @staticmethod
    def get_active_consents(db: Session, user_id: str) -> list[ConsentRecord]:
        """Return all active (non-withdrawn) consents for a user."""
        return db.query(ConsentRecord).filter(
            ConsentRecord.user_id == user_id,
            ConsentRecord.withdrawn_at.is_(None),
        ).all()

    @staticmethod
    def get_consent_history(db: Session, user_id: str) -> list[ConsentRecord]:
        """Return full consent history (including withdrawn) for Art. 20 data export."""
        return db.query(ConsentRecord).filter(
            ConsentRecord.user_id == user_id,
        ).order_by(ConsentRecord.given_at.asc()).all()
