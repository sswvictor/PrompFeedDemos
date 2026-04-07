"""
DataRetentionService — GDPR-compliant automated data deletion pipeline.

Designed to run as a daily scheduled job. Executes the four-phase
retention lifecycle defined in the GDPR architecture plan.

The extraction-first invariant is enforced throughout:
    A conversation without signals_extracted_at is NEVER auto-deleted.
    If signals have not been extracted, the retention job skips the row
    and logs a warning — human review is required.

Run manually:
    python -m app.services.data_retention_service

Schedule via cron (daily at 02:00):
    0 2 * * * cd /app && python -m app.services.data_retention_service

GDPR references:
    Art. 5(1)(e) — storage limitation
    Art. 5(2)    — accountability (DataRetentionLog provides the proof)
    Art. 17      — right to erasure (erase_user method)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from sqlalchemy.orm import Session

from app.models.conversation import Conversation, Message
from app.models.data_retention_log import DataRetentionLog
from app.models.customer import Customer
from app.models.customer_preference import CustomerPreference
from app.models.instagram_identity import InstagramIdentity
from app.models.consent_record import ConsentRecord
from app.models.user import User

log = logging.getLogger(__name__)


# ── Retention windows ──────────────────────────────────────────────────────────

MESSAGE_TEXT_RETENTION_DAYS = 30    # null message text after this many days post-close
BOOKING_CONV_RETENTION_DAYS = 90    # delete booking conversation records after this
DISCOVERY_CONV_RETENTION_DAYS = 30  # delete discovery conversation records after this


class RetentionResult(NamedTuple):
    """Summary returned after each retention run."""
    messages_nulled: int
    conversations_deleted: int
    phase1_extracted: int   # safety-net extractions
    warnings: list[str]


class DataRetentionService:

    # ── Public: daily job ──────────────────────────────────────────────────────

    @classmethod
    def run_daily_job(cls, db: Session) -> RetentionResult:
        """
        Execute the full four-phase daily retention job.

        Phase 1 — Safety net: extract signals from conversations that closed
                  but have no signals_extracted_at (missed by the synchronous hook).
        Phase 2 — Null message text for conversations past the 30-day window.
        Phase 3 — Delete conversation + message rows past the full retention window.
        Phase 4 — Log everything to DataRetentionLog.

        Returns a RetentionResult summary.
        """
        now = datetime.now(timezone.utc)
        warnings: list[str] = []

        # Phase 1: safety-net signal extraction
        phase1_count = cls._phase1_extract_missed_signals(db, now, warnings)

        # Phase 2: null message text (30 days after close)
        messages_nulled = cls._phase2_null_message_text(db, now)

        # Phase 3: delete expired conversation records
        conversations_deleted = cls._phase3_delete_conversations(db, now)

        # Phase 4: log the run
        cls._log(db, "message_content_nulled", "messages", messages_nulled, "30_day_message")
        cls._log(db, "conversation_deleted", "conversations", conversations_deleted,
                 "90_day_booking / 30_day_discovery")
        if phase1_count:
            cls._log(db, "signals_extracted", "conversations", phase1_count, "safety_net")

        result = RetentionResult(
            messages_nulled=messages_nulled,
            conversations_deleted=conversations_deleted,
            phase1_extracted=phase1_count,
            warnings=warnings,
        )
        log.info(
            "DataRetentionService daily run complete: "
            f"messages_nulled={messages_nulled}, "
            f"conversations_deleted={conversations_deleted}, "
            f"safety_net_extractions={phase1_count}, "
            f"warnings={len(warnings)}"
        )
        return result

    # ── Public: Art. 17 erasure ────────────────────────────────────────────────

    @classmethod
    def erase_user(cls, db: Session, user_id: str) -> dict:
        """
        Execute a full GDPR Article 17 right-to-erasure request.

        Deletes in order (respecting FK constraints):
          1. ConsentRecords
          2. CustomerPreferences (via customers)
          3. InstagramIdentities
          4. Conversations + Messages (not already deleted by retention job)
          5. Customers
          6. User record itself

        Does NOT delete:
          - Booking/invoice records (Swedish 7-year legal obligation)
          - Merkle contribution events (HMAC token is irreversible — Art. 17 satisfied
            by deleting the source user_id, making the token a permanent orphan)
          - DataRetentionLog rows (immutable audit trail)

        Returns a summary dict of deleted row counts.
        """
        now = datetime.now(timezone.utc)
        summary: dict[str, int] = {}

        # 1. Consent records
        consent_count = db.query(ConsentRecord).filter_by(user_id=user_id).delete()
        summary["consent_records"] = consent_count

        # 2. Customer-scoped data
        customers = db.query(Customer).filter_by(user_id=user_id).all()
        customer_ids = [c.customer_id for c in customers]
        pref_count = 0
        conv_count = 0
        msg_count = 0
        ig_count = 0

        for cid in customer_ids:
            pref_count += db.query(CustomerPreference).filter_by(customer_id=cid).delete()
            ig_count += db.query(InstagramIdentity).filter_by(customer_id=cid).delete()
            # Delete conversations scoped to this customer
            convs = db.query(Conversation).filter_by(customer_id=cid).all()
            for conv in convs:
                msg_count += db.query(Message).filter_by(conversation_id=conv.conversation_id).delete()
                conv_count += 1
                db.delete(conv)

        summary["customer_preferences"] = pref_count
        summary["instagram_identities"] = ig_count

        # 3. Platform-level conversations (discovery bot — user_id on conversation)
        platform_convs = db.query(Conversation).filter_by(user_id=user_id).all()
        for conv in platform_convs:
            msg_count += db.query(Message).filter_by(conversation_id=conv.conversation_id).delete()
            conv_count += 1
            db.delete(conv)

        summary["conversations"] = conv_count
        summary["messages"] = msg_count

        # 4. Customers
        for customer in customers:
            db.delete(customer)
        summary["customers"] = len(customers)

        # 5. User
        user = db.query(User).filter_by(user_id=user_id).first()
        if user:
            db.delete(user)
            summary["users"] = 1
        else:
            summary["users"] = 0

        db.flush()

        # 6. Audit log — immutable proof of erasure
        target_ids = user_id  # single user erasure: log the user_id
        cls._log(
            db, "user_erased", "users", 1, "art17_erasure",
            target_ids=target_ids,
            notes=f"Full Art.17 cascade. customers={len(customer_ids)} "
                  f"convs={conv_count} msgs={msg_count}",
        )
        db.commit()

        log.info(f"Art.17 erasure complete for user_id={user_id}: {summary}")
        return summary

    # ── Private: phase implementations ────────────────────────────────────────

    @classmethod
    def _phase1_extract_missed_signals(
        cls, db: Session, now: datetime, warnings: list[str]
    ) -> int:
        """
        Safety net: find conversations that closed but have no signals_extracted_at.
        These were missed by the synchronous hook in close_conversation().
        Log a warning — this should not happen in normal operation.
        """
        missed = db.query(Conversation).filter(
            Conversation.status == "closed",
            Conversation.signals_extracted_at.is_(None),
            Conversation.closed_at.isnot(None),
        ).all()

        for conv in missed:
            warnings.append(
                f"Conversation {conv.conversation_id} closed at {conv.closed_at} "
                f"but signals_extracted_at is NULL — manual review required."
            )
            log.warning(
                f"[DataRetentionService] Missed signal extraction: "
                f"conversation_id={conv.conversation_id}"
            )

        # NOTE: We do NOT auto-extract here because we lack the AI context.
        # This is intentional — extraction requires the original message content,
        # and we can't retroactively run the AI model safely in a background job.
        # The warning is the signal for the engineering team to investigate.
        return 0  # phase1_count — no auto-extraction in safety net

    @classmethod
    def _phase2_null_message_text(cls, db: Session, now: datetime) -> int:
        """
        Null the text field on messages belonging to conversations that:
        - Have signals_extracted_at set (extraction-first invariant)
        - closed_at > MESSAGE_TEXT_RETENTION_DAYS days ago
        - Messages have not already had content_deleted_at set
        """
        cutoff = now - timedelta(days=MESSAGE_TEXT_RETENTION_DAYS)

        # Find eligible conversations
        eligible_conv_ids = db.query(Conversation.conversation_id).filter(
            Conversation.signals_extracted_at.isnot(None),
            Conversation.closed_at <= cutoff,
            Conversation.status == "closed",
        ).subquery()

        # Null text on their messages (only where content not already deleted)
        messages = db.query(Message).filter(
            Message.conversation_id.in_(eligible_conv_ids),
            Message.content_deleted_at.is_(None),
            Message.text.isnot(None),
        ).all()

        count = 0
        for msg in messages:
            msg.text = None
            msg.raw_payload_json = None  # also strip raw webhook payload
            msg.content_deleted_at = now
            count += 1

        if count:
            db.commit()

        return count

    @classmethod
    def _phase3_delete_conversations(cls, db: Session, now: datetime) -> int:
        """
        Delete entire Conversation + Message records past the full retention window.
        Respects conversation_type for different retention periods.
        Extraction-first invariant enforced: only deletes if signals_extracted_at is set.
        """
        booking_cutoff = now - timedelta(days=BOOKING_CONV_RETENTION_DAYS)
        discovery_cutoff = now - timedelta(days=DISCOVERY_CONV_RETENTION_DAYS)
        count = 0

        for conv in db.query(Conversation).filter(
            Conversation.signals_extracted_at.isnot(None),
            Conversation.status == "closed",
        ).all():
            if not conv.closed_at:
                continue
            cutoff = (
                booking_cutoff if conv.conversation_type == "booking"
                else discovery_cutoff
            )
            if conv.closed_at <= cutoff:
                # Messages cascade-delete via relationship
                db.delete(conv)
                count += 1

        if count:
            db.commit()

        return count

    @classmethod
    def _log(
        cls,
        db: Session,
        action: str,
        target_type: str,
        count: int,
        policy: str,
        target_ids: str | None = None,
        notes: str | None = None,
    ) -> None:
        """Write an immutable entry to DataRetentionLog."""
        entry = DataRetentionLog(
            action=action,
            target_type=target_type,
            target_count=count,
            retention_policy=policy,
            target_ids=target_ids,
            notes=notes,
        )
        db.add(entry)
        db.commit()


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    from app.db.session import SessionLocal
    import app.models  # noqa: F401 — register all models

    db = SessionLocal()
    try:
        result = DataRetentionService.run_daily_job(db)
        print(f"\n✓ Retention job complete")
        print(f"  Messages nulled:          {result.messages_nulled}")
        print(f"  Conversations deleted:    {result.conversations_deleted}")
        print(f"  Safety-net extractions:   {result.phase1_extracted}")
        if result.warnings:
            print(f"\n  ⚠ Warnings ({len(result.warnings)}):")
            for w in result.warnings:
                print(f"    - {w}")
        sys.exit(0)
    except Exception as e:
        log.error(f"Retention job failed: {e}")
        sys.exit(1)
    finally:
        db.close()
