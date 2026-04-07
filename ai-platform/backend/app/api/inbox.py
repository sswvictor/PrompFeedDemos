"""
Provider Inbox API — Instagram DM conversation management.

Endpoints:
  GET  /inbox/conversations                        list conversations for provider
  POST /inbox/conversations/{id}/flag-human        mark needs_human=True (bot paused)
  POST /inbox/conversations/{id}/provider-reply    provider sends a message directly
  POST /inbox/conversations/{id}/resume-bot        clear needs_human → bot takes over again
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_provider
from app.db.session import get_db
from app.models.conversation import Conversation, Message
from app.models.customer import Customer
from app.models.provider_instagram_page import ProviderInstagramPage
from app.integrations.instagram.messenger import send_message
from app.services.token_crypto import decrypt_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inbox", tags=["inbox"])


# ── Response schemas ──────────────────────────────────────────────────────────


class MessagePreview(BaseModel):
    message_id: str
    direction: str
    text: str | None
    timestamp: datetime


class ConversationListItem(BaseModel):
    conversation_id: str
    channel: str
    external_thread_id: str
    status: str
    needs_human: bool
    last_message_at: datetime | None
    customer_name: str | None
    customer_ig_handle: str | None
    last_message: MessagePreview | None


class ConversationDetail(ConversationListItem):
    messages: list[MessagePreview]


class ProviderReplyIn(BaseModel):
    text: str


# ── Helpers ───────────────────────────────────────────────────────────────────


def _to_list_item(conv: Conversation, db: Session) -> ConversationListItem:
    customer_name: str | None = None
    customer_ig_handle: str | None = None

    if conv.customer_id:
        customer = db.query(Customer).filter(Customer.customer_id == conv.customer_id).first()
        if customer:
            customer_name = customer.name
            # IG handle stored in customer.instagram_handle if present
            customer_ig_handle = getattr(customer, "instagram_handle", None)

    last_msg: MessagePreview | None = None
    if conv.messages:
        # messages are lazy-loaded; get most recent
        recent = (
            db.query(Message)
            .filter(Message.conversation_id == conv.conversation_id)
            .order_by(Message.timestamp.desc())
            .first()
        )
        if recent:
            last_msg = MessagePreview(
                message_id=recent.message_id,
                direction=recent.direction,
                text=recent.text,
                timestamp=recent.timestamp,
            )

    return ConversationListItem(
        conversation_id=conv.conversation_id,
        channel=conv.channel,
        external_thread_id=conv.external_thread_id,
        status=conv.status,
        needs_human=conv.needs_human,
        last_message_at=conv.last_message_at,
        customer_name=customer_name,
        customer_ig_handle=customer_ig_handle,
        last_message=last_msg,
    )


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("/conversations", response_model=list[ConversationListItem])
def list_conversations(
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """List all active conversations for this provider, sorted by last activity."""
    conversations = (
        db.query(Conversation)
        .filter(
            Conversation.provider_id == provider_id,
            Conversation.status == "active",
        )
        .order_by(Conversation.last_message_at.desc().nullslast())
        .limit(100)
        .all()
    )
    return [_to_list_item(c, db) for c in conversations]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Get full conversation thread."""
    conv = db.query(Conversation).filter(
        Conversation.conversation_id == conversation_id,
        Conversation.provider_id == provider_id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages_raw = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.timestamp.asc())
        .limit(200)
        .all()
    )
    msgs = [
        MessagePreview(
            message_id=m.message_id,
            direction=m.direction,
            text=m.text,
            timestamp=m.timestamp,
        )
        for m in messages_raw
    ]

    item = _to_list_item(conv, db)
    return ConversationDetail(**item.model_dump(), messages=msgs)


@router.post("/conversations/{conversation_id}/flag-human", response_model=ConversationListItem)
def flag_human(
    conversation_id: str,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Mark conversation as needing human reply — bot stops responding."""
    conv = db.query(Conversation).filter(
        Conversation.conversation_id == conversation_id,
        Conversation.provider_id == provider_id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv.needs_human = True
    db.commit()
    db.refresh(conv)
    return _to_list_item(conv, db)


@router.post("/conversations/{conversation_id}/provider-reply", response_model=ConversationListItem)
async def provider_reply(
    conversation_id: str,
    payload: ProviderReplyIn,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """
    Provider sends a direct reply. Logs the message as direction='out' and
    sends it to the customer via Instagram DM (if page token is available).
    Bot stays paused (needs_human remains True) until provider resumes it.
    """
    conv = db.query(Conversation).filter(
        Conversation.conversation_id == conversation_id,
        Conversation.provider_id == provider_id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="Reply text cannot be empty")

    text = payload.text.strip()

    # Log message to DB
    msg = Message(
        conversation_id=conversation_id,
        direction="out",
        text=text,
    )
    db.add(msg)
    conv.last_message_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(conv)

    # Send via Instagram DM if this is an IG conversation and we have a page token
    if conv.channel == "instagram_dm":
        ig_page = (
            db.query(ProviderInstagramPage)
            .filter(
                ProviderInstagramPage.provider_id == provider_id,
                ProviderInstagramPage.access_token.isnot(None),
            )
            .first()
        )
        if ig_page and ig_page.access_token:
            decrypted_token = decrypt_token(ig_page.access_token)
            if not decrypted_token:
                logger.warning("Instagram token could not be decrypted for provider %s", provider_id)
                return _to_list_item(conv, db)
            sent = await send_message(
                access_token=decrypted_token,
                recipient_id=conv.external_thread_id,
                text=text,
            )
            if not sent:
                logger.warning(
                    "Failed to send Instagram DM for conversation %s", conversation_id
                )

    return _to_list_item(conv, db)


@router.post("/conversations/{conversation_id}/resume-bot", response_model=ConversationListItem)
def resume_bot(
    conversation_id: str,
    provider_id: str = Depends(get_current_provider),
    db: Session = Depends(get_db),
):
    """Resume bot for this conversation — clears the needs_human flag."""
    conv = db.query(Conversation).filter(
        Conversation.conversation_id == conversation_id,
        Conversation.provider_id == provider_id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv.needs_human = False
    db.commit()
    db.refresh(conv)
    return _to_list_item(conv, db)
