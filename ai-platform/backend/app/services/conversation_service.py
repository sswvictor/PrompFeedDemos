import hashlib
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.conversation import Conversation, Message
from app.models.discovery_event import DiscoveryEvent

# Matches Message.idempotency_key (String(128)); Instagram Graph message ids are often longer.
_MESSAGE_IDEMPOTENCY_MAX_LEN = 128


def _normalize_message_idempotency_key(key: str | None) -> str | None:
    if not key:
        return None
    if len(key) <= _MESSAGE_IDEMPOTENCY_MAX_LEN:
        return key
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class ConversationService:

    @staticmethod
    def get_or_create_conversation(
        db: Session,
        provider_id: str,
        channel: str,
        external_thread_id: str,
        customer_id: str | None = None,
        user_id: str | None = None,
    ) -> Conversation:
        """
        Find or create a provider-scoped booking conversation.
        Idempotent on (provider_id, channel, external_thread_id).
        """
        existing = db.query(Conversation).filter(
            Conversation.provider_id == provider_id,
            Conversation.channel == channel,
            Conversation.external_thread_id == external_thread_id,
        ).first()

        if existing:
            updated = False
            if customer_id and not existing.customer_id:
                existing.customer_id = customer_id
                updated = True
            if user_id and not existing.user_id:
                existing.user_id = user_id
                updated = True
            if updated:
                db.commit()
                db.refresh(existing)
            return existing

        conv = Conversation(
            conversation_type="booking",
            provider_id=provider_id,
            user_id=user_id,
            customer_id=customer_id,
            channel=channel,
            external_thread_id=external_thread_id,
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return conv

    @staticmethod
    def get_or_create_discovery_conversation(
        db: Session,
        user_id: str,
        channel: str,
        external_thread_id: str,
    ) -> Conversation:
        """
        Find or create a platform-level discovery conversation on Fixmeapp's own channel.
        No provider is set — the AI bot matches the user to providers during this conversation.
        Idempotent on (user_id, channel, external_thread_id).
        """
        existing = db.query(Conversation).filter(
            Conversation.user_id == user_id,
            Conversation.channel == channel,
            Conversation.external_thread_id == external_thread_id,
            Conversation.provider_id.is_(None),
        ).first()

        if existing:
            return existing

        conv = Conversation(
            conversation_type="discovery",
            provider_id=None,
            user_id=user_id,
            channel=channel,
            external_thread_id=external_thread_id,
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return conv

    @staticmethod
    def attach_provider(
        db: Session,
        conversation_id: str,
        provider_id: str,
        customer_id: str | None = None,
    ) -> Conversation:
        """
        Attach a provider to a discovery conversation once the user has chosen one.
        Typically called after the discovery bot has matched and the user confirms a provider.
        Does NOT change the conversation_type — the conversation remains "discovery"
        so the full journey is traceable.
        """
        conv = db.query(Conversation).filter(
            Conversation.conversation_id == conversation_id
        ).first()
        if not conv:
            raise ValueError(f"Conversation {conversation_id} not found")
        conv.provider_id = provider_id
        if customer_id:
            conv.customer_id = customer_id
        db.commit()
        db.refresh(conv)
        return conv

    @staticmethod
    def log_message(
        db: Session,
        conversation_id: str,
        direction: str,
        text: str | None = None,
        raw_payload_json: str | None = None,
        idempotency_key: str | None = None,
    ) -> Message:
        """Log a message. Skips duplicate if idempotency_key already exists."""
        key = _normalize_message_idempotency_key(idempotency_key)
        if key:
            existing = db.query(Message).filter(
                Message.conversation_id == conversation_id,
                Message.idempotency_key == key,
            ).first()
            if existing:
                return existing

        msg = Message(
            conversation_id=conversation_id,
            direction=direction,
            text=text,
            raw_payload_json=raw_payload_json,
            idempotency_key=key,
        )
        db.add(msg)

        # Update conversation last_message_at
        conv = db.query(Conversation).filter(
            Conversation.conversation_id == conversation_id
        ).first()
        if conv:
            conv.last_message_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(msg)
        return msg

    @staticmethod
    def get_conversation_history(
        db: Session,
        conversation_id: str,
        limit: int = 50,
    ) -> list[Message]:
        return db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.timestamp.asc()).limit(limit).all()

    @staticmethod
    def close_conversation(db: Session, conversation_id: str) -> Conversation:
        conv = db.query(Conversation).filter(
            Conversation.conversation_id == conversation_id
        ).first()
        if not conv:
            raise ValueError(f"Conversation {conversation_id} not found")

        already_closed = conv.status == "closed"

        # Discovery conversations are mirrored into a lightweight event stream
        # consumed by the Merkle contribution pipeline.
        if conv.conversation_type == "discovery" and not already_closed:
            discovery_event = DiscoveryEvent(
                user_id=conv.user_id,
                conversation_id=conv.conversation_id,
                service_category=None,
                city=None,
                provider_found=conv.provider_id is not None,
                availability_found=False,
                converted_to_booking=False,
                channel=conv.channel,
            )
            db.add(discovery_event)

        if not already_closed:
            conv.status = "closed"
            conv.closed_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(conv)
        return conv
