import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.models.chat_magic_link import ChatMagicLink
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.instagram_identity import InstagramIdentity
from app.models.user import User
from app.services.email_service import EmailService
from app.services.provider_service import ProviderService


class ChatAuthService:
    TOKEN_TTL_MINUTES = 10

    @staticmethod
    def _hash_secret(secret: str) -> str:
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()

    @staticmethod
    def _build_verify_url(token: str) -> str:
        base = (
            os.getenv("MAGIC_LINK_BASE_URL")
            or os.getenv("API_BASE_URL")
            or "http://127.0.0.1:8000"
        ).rstrip("/")
        return f"{base}/api/v1/auth/customer/verify-chat-link?token={quote(token, safe='')}"

    @staticmethod
    def send_verification_link(
        db: Session,
        *,
        email: str,
        provider_id: str | None,
        customer_id: str | None,
        conversation_id: str | None,
    ) -> dict:
        email_normalized = (email or "").strip().lower()
        if not email_normalized:
            raise ValueError("Email is required to send verification link")

        token_id = str(uuid.uuid4())
        secret = secrets.token_urlsafe(24)
        token = f"{token_id}.{secret}"
        token_hash = ChatAuthService._hash_secret(secret)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=ChatAuthService.TOKEN_TTL_MINUTES)

        magic = ChatMagicLink(
            token_id=token_id,
            token_hash=token_hash,
            email=email_normalized,
            provider_id=provider_id,
            customer_id=customer_id,
            conversation_id=conversation_id,
            expires_at=expires_at,
        )
        db.add(magic)
        db.commit()

        verify_url = ChatAuthService._build_verify_url(token)

        provider_name = "FixMe"
        if provider_id:
            provider = ProviderService.get_provider(db, provider_id)
            if provider and provider.name:
                provider_name = provider.name

        email_sent = EmailService.send_chat_verification_link(
            to=email_normalized,
            provider_name=provider_name,
            verify_url=verify_url,
            expires_minutes=ChatAuthService.TOKEN_TTL_MINUTES,
        )

        return {
            "sent": email_sent,
            "verify_url": verify_url,
            "expires_minutes": ChatAuthService.TOKEN_TTL_MINUTES,
        }

    
    @staticmethod
    def create_member_account(
        db: Session,
        *,
        email: str,
        customer_id: str | None,
        conversation_id: str | None,
    ) -> dict:
        """Create/link a customer member account immediately (no magic link flow)."""
        email_normalized = (email or "").strip().lower()
        if not email_normalized:
            raise ValueError("Email is required to create member account")

        user = db.query(User).filter(User.email == email_normalized).first()
        created_user = False
        if not user:
            user = User(email=email_normalized, is_customer=True, is_provider=False)
            db.add(user)
            db.flush()
            created_user = True
        elif not user.is_customer:
            user.is_customer = True

        customer = None
        if customer_id:
            customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
            if customer:
                customer.user_id = user.user_id
                customer.customer_email = email_normalized

                db.query(InstagramIdentity).filter(
                    InstagramIdentity.customer_id == customer.customer_id,
                    InstagramIdentity.user_id.is_(None),
                ).update({"user_id": user.user_id}, synchronize_session=False)

        # Link any historical customer rows sharing this email so existing bookings
        # are visible on the verified account homepage immediately.
        db.query(Customer).filter(
            Customer.customer_email == email_normalized,
            Customer.user_id.is_(None),
        ).update({"user_id": user.user_id}, synchronize_session=False)

        if conversation_id:
            conversation = db.query(Conversation).filter(
                Conversation.conversation_id == conversation_id
            ).first()
            if conversation:
                conversation.user_id = user.user_id
                if customer and not conversation.customer_id:
                    conversation.customer_id = customer.customer_id

        db.commit()
        return {
            "email": email_normalized,
            "user_id": user.user_id,
            "customer_id": customer.customer_id if customer else None,
            "created_user": created_user,
        }
    @staticmethod
    def consume_verification_link(db: Session, token: str) -> dict:
        token = (token or "").strip()
        if "." not in token:
            raise ValueError("Invalid verification link")

        token_id, secret = token.split(".", 1)
        if not token_id or not secret:
            raise ValueError("Invalid verification link")

        magic = db.query(ChatMagicLink).filter(ChatMagicLink.token_id == token_id).first()
        if not magic:
            raise ValueError("Verification link not found")

        if magic.consumed_at is not None:
            raise ValueError("This verification link has already been used")

        now = datetime.now(timezone.utc)
        if magic.expires_at < now:
            raise ValueError("Verification link has expired")

        if ChatAuthService._hash_secret(secret) != magic.token_hash:
            raise ValueError("Invalid verification link")

        account = ChatAuthService.create_member_account(
            db=db,
            email=magic.email,
            customer_id=magic.customer_id,
            conversation_id=magic.conversation_id,
        )
        magic.consumed_at = now
        db.commit()

        return {
            "email": magic.email,
            "user_id": account["user_id"],
            "customer_id": account.get("customer_id"),
        }
