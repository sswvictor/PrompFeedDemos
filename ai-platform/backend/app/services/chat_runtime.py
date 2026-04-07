from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.orchestrators.base import process_message
from app.orchestrators.platform import platform_process_message
from app.services.conversation_service import ConversationService
from app.services.discovery_user_service import ensure_user_for_discovery_conversation
from app.services.conversation_state_service import ConversationStateService
from app.services.customer_service import CustomerService
from app.services.instagram_service import InstagramMappingService
from app.services.provider_service import ProviderService


@dataclass
class ChatRuntimeResult:
    reply: str
    conversation_id: str
    customer_id: str | None


class ChatRuntimeService:

    @staticmethod
    def _handoff_reply(db: Session, mode: str, provider_id: str | None) -> str:
        if mode == "provider" and provider_id:
            provider = ProviderService.get_provider(db, provider_id)
            provider_name = provider.name if provider else "the provider"
            return f"I have already let {provider_name} know. They will follow up with you as soon as possible."
        return "A human has already been notified and will follow up with you as soon as possible."

    @staticmethod
    def _resolve_provider_customer(
        db: Session,
        *,
        provider_id: str,
        channel: str,
        thread_id: str,
        sender_id: str,
        customer_id: str | None,
    ) -> str | None:
        existing_conversation = db.query(Conversation).filter(
            Conversation.provider_id == provider_id,
            Conversation.channel == channel,
            Conversation.external_thread_id == thread_id,
        ).first()
        if existing_conversation and existing_conversation.customer_id:
            return existing_conversation.customer_id
        if customer_id:
            return customer_id
        if channel == "instagram_dm":
            identity = InstagramMappingService.resolve_or_create_customer(
                db=db,
                provider_id=provider_id,
                instagram_user_id=sender_id,
            )
            return identity.customer_id

        customer = CustomerService.create_customer(
            db=db,
            provider_id=provider_id,
            source_channel=channel,
        )
        return customer.customer_id

    @staticmethod
    async def handle_message(
        *,
        db: Session,
        mode: str,
        channel: str,
        thread_id: str,
        text: str,
        provider_id: str | None = None,
        sender_id: str | None = None,
        customer_id: str | None = None,
        inbound_idempotency_key: str | None = None,
    ) -> ChatRuntimeResult:
        if mode not in {"provider", "platform"}:
            raise ValueError(f"Unsupported chat mode: {mode}")
        if mode == "provider" and not provider_id:
            raise ValueError("provider_id is required for provider chat mode")

        sender_id = (sender_id or thread_id).strip()
        if not sender_id:
            raise ValueError("sender_id or thread_id is required")

        resolved_customer_id = customer_id
        if mode == "provider":
            resolved_customer_id = ChatRuntimeService._resolve_provider_customer(
                db,
                provider_id=provider_id,
                channel=channel,
                thread_id=thread_id,
                sender_id=sender_id,
                customer_id=customer_id,
            )
            conversation = ConversationService.get_or_create_conversation(
                db=db,
                provider_id=provider_id,
                channel=channel,
                external_thread_id=thread_id,
                customer_id=resolved_customer_id,
            )
        else:
            platform_user_id = ensure_user_for_discovery_conversation(
                db,
                channel=channel,
                sender_id=sender_id,
                thread_id=thread_id,
            )
            conversation = ConversationService.get_or_create_discovery_conversation(
                db=db,
                user_id=platform_user_id,
                channel=channel,
                external_thread_id=thread_id,
            )

        state = ConversationStateService.get_or_create_state(
            db,
            conversation.conversation_id,
            mode=mode,
            provider_id=provider_id,
        )

        if state.handoff_status == "requested":
            reply = ChatRuntimeService._handoff_reply(db, mode, provider_id)
            ConversationService.log_message(
                db=db,
                conversation_id=conversation.conversation_id,
                direction="out",
                text=reply,
            )
            return ChatRuntimeResult(
                reply=reply,
                conversation_id=conversation.conversation_id,
                customer_id=resolved_customer_id,
            )

        ConversationService.log_message(
            db=db,
            conversation_id=conversation.conversation_id,
            direction="in",
            text=text,
            idempotency_key=inbound_idempotency_key,
        )

        if mode == "provider":
            reply = await process_message(
                db=db,
                provider_id=provider_id,
                customer_id=resolved_customer_id,
                conversation_id=conversation.conversation_id,
                text=text,
            )
        else:
            reply = await platform_process_message(
                db=db,
                sender_ig_id=sender_id,
                conversation_id=conversation.conversation_id,
                text=text,
            )

        ConversationService.log_message(
            db=db,
            conversation_id=conversation.conversation_id,
            direction="out",
            text=reply,
        )
        return ChatRuntimeResult(
            reply=reply,
            conversation_id=conversation.conversation_id,
            customer_id=resolved_customer_id,
        )
