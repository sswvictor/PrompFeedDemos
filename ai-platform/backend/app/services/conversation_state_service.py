from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.conversation_state import ConversationState


class ConversationStateService:

    @staticmethod
    def get_state(db: Session, conversation_id: str) -> ConversationState | None:
        return db.query(ConversationState).filter(
            ConversationState.conversation_id == conversation_id
        ).first()

    @staticmethod
    def get_or_create_state(
        db: Session,
        conversation_id: str,
        *,
        mode: str,
        provider_id: str | None = None,
    ) -> ConversationState:
        state = ConversationStateService.get_state(db, conversation_id)
        if state:
            changed = False
            if state.mode != mode:
                state.mode = mode
                changed = True
            if provider_id and state.provider_id != provider_id:
                state.provider_id = provider_id
                changed = True
            if mode == "provider" and provider_id and state.selected_provider_id != provider_id:
                state.selected_provider_id = provider_id
                changed = True
            if changed:
                state.updated_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(state)
            return state

        state = ConversationState(
            conversation_id=conversation_id,
            mode=mode,
            provider_id=provider_id,
            selected_provider_id=provider_id if mode == "provider" else None,
        )
        db.add(state)
        db.commit()
        db.refresh(state)
        return state

    @staticmethod
    def update_state(db: Session, conversation_id: str, **fields) -> ConversationState:
        state = ConversationStateService.get_state(db, conversation_id)
        if not state:
            conv = db.query(Conversation).filter(
                Conversation.conversation_id == conversation_id
            ).first()
            if not conv:
                raise ValueError(f"Conversation {conversation_id} not found")
            state = ConversationStateService.get_or_create_state(
                db,
                conversation_id,
                mode="platform" if conv.conversation_type == "discovery" else "provider",
                provider_id=conv.provider_id,
            )

        changed = False
        for key, value in fields.items():
            if value is None:
                continue
            if getattr(state, key) != value:
                setattr(state, key, value)
                changed = True

        if changed:
            state.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(state)
        return state

    @staticmethod
    def mark_handoff_requested(db: Session, conversation_id: str) -> ConversationState:
        return ConversationStateService.update_state(
            db,
            conversation_id,
            handoff_status="requested",
            last_ai_action="handoff_requested",
        )

    @staticmethod
    def mark_contact_requested(db: Session, conversation_id: str) -> ConversationState:
        return ConversationStateService.update_state(
            db,
            conversation_id,
            contact_requested_at=datetime.now(timezone.utc),
            last_ai_action="contact_requested",
        )

    @staticmethod
    def set_contact_details(
        db: Session,
        conversation_id: str,
        *,
        contact_name: str | None,
        contact_email: str,
    ) -> ConversationState:
        return ConversationStateService.update_state(
            db,
            conversation_id,
            contact_name=contact_name or "",
            contact_email=contact_email,
            contact_received_at=datetime.now(timezone.utc),
            last_ai_action="contact_captured",
        )

    @staticmethod
    def update_selection(
        db: Session,
        conversation_id: str,
        *,
        provider_id: str | None = None,
        service_id: str | None = None,
        service_name: str | None = None,
        date: str | None = None,
        time: str | None = None,
        booking_status: str | None = None,
        last_ai_action: str | None = None,
    ) -> ConversationState:
        fields = {
            "selected_provider_id": provider_id,
            "selected_service_id": service_id,
            "selected_service_name": service_name,
            "selected_date": date,
            "selected_time": time,
            "booking_status": booking_status,
            "last_ai_action": last_ai_action,
        }
        return ConversationStateService.update_state(db, conversation_id, **fields)
