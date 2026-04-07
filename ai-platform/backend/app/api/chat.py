from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.chat_runtime import ChatRuntimeService


router = APIRouter(prefix="/chat", tags=["chat"])


class ProviderChatMessageIn(BaseModel):
    provider_id: str
    thread_id: str
    message: str
    sender_id: str | None = None
    customer_id: str | None = None


class PlatformChatMessageIn(BaseModel):
    thread_id: str
    message: str
    sender_id: str | None = None


class ChatMessageOut(BaseModel):
    reply: str
    conversation_id: str
    customer_id: str | None = None


@router.post("/provider/message", response_model=ChatMessageOut)
async def provider_chat_message(payload: ProviderChatMessageIn, db: Session = Depends(get_db)):
    result = await ChatRuntimeService.handle_message(
        db=db,
        mode="provider",
        channel="web",
        thread_id=payload.thread_id,
        text=payload.message,
        provider_id=payload.provider_id,
        sender_id=payload.sender_id,
        customer_id=payload.customer_id,
    )
    return ChatMessageOut(**result.__dict__)


@router.post("/platform/message", response_model=ChatMessageOut)
async def platform_chat_message(payload: PlatformChatMessageIn, db: Session = Depends(get_db)):
    result = await ChatRuntimeService.handle_message(
        db=db,
        mode="platform",
        channel="web",
        thread_id=payload.thread_id,
        text=payload.message,
        sender_id=payload.sender_id,
    )
    return ChatMessageOut(**result.__dict__)
