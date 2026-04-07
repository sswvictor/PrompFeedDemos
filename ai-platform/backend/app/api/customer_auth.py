"""
Customer authentication Ã¢â‚¬â€ email magic code flow.

Routes:
    POST /auth/customer/send-code    Ã¢â‚¬â€ send 6-digit OTP to customer email
    POST /auth/customer/verify-code  Ã¢â‚¬â€ verify OTP, return JWT

OTP emails are sent through the shared EmailService when configured.
If email delivery is not configured, the code is still logged locally as a fallback.

OTP storage is in-memory (lost on restart). Upgrade to Redis when needed Ã¢â‚¬â€
the infra already has a Redis cluster available via REDIS_URL.
"""

import logging
import random
import string
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.customer import Customer
from app.models.user import User
from app.utils.jwt_token import create_access_token
from app.services.chat_auth_service import ChatAuthService
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/customer", tags=["customer-auth"])

# Ã¢â€â‚¬Ã¢â€â‚¬ In-memory OTP store Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
# { email: { "code": "123456", "expires_at": datetime } }
_otp_store: dict[str, dict] = {}
OTP_EXPIRE_MINUTES = 10

# Ã¢â€â‚¬Ã¢â€â‚¬ Rate limiting Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
# Same in-memory pattern as OTP store. Upgrade to Redis when scaling.
# { email_lower: { "count": int, "window_start": datetime } }
_rate_limit: dict[str, dict] = {}
RATE_LIMIT_MAX_SENDS = 3        # max OTP sends per window
RATE_LIMIT_WINDOW_MINUTES = 10  # rolling window length


# Ã¢â€â‚¬Ã¢â€â‚¬ Schemas Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class SendCodeRequest(BaseModel):
    email: EmailStr


class SendCodeResponse(BaseModel):
    message: str
    # In production this would NOT return the code Ã¢â‚¬â€ only for dev/MVP
    dev_code: str | None = None


class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str


class VerifyCodeResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    is_new_user: bool


# Ã¢â€â‚¬Ã¢â€â‚¬ Helpers Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

def _generate_otp() -> str:
    return "".join(random.choices(string.digits, k=6))

def _send_code_email(email: str, code: str) -> bool:
    """Send the OTP email through EmailService, with local logging fallback."""
    sent = EmailService.send_customer_otp(
        to=email,
        code=code,
        expires_minutes=OTP_EXPIRE_MINUTES,
    )
    if sent:
        return True

    logger.warning("OTP email delivery not configured or failed for %s; using local fallback log", email)
    logger.info(f"[DEV] Magic code for {email}: {code}")
    print(f"\n{'='*40}\nMagic code for {email}: {code}\n{'='*40}\n")
    return False

def _is_rate_limited(email: str) -> bool:
    """
    Return True if this email has hit the send limit for the current window.
    Side-effect: increments the counter if not limited.
    """
    key = email.lower()
    now = datetime.now(timezone.utc)
    window_cutoff = now - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)

    if key not in _rate_limit:
        _rate_limit[key] = {"count": 1, "window_start": now}
        return False

    entry = _rate_limit[key]
    if entry["window_start"] < window_cutoff:
        # Previous window has expired Ã¢â‚¬â€ start fresh
        _rate_limit[key] = {"count": 1, "window_start": now}
        return False

    if entry["count"] >= RATE_LIMIT_MAX_SENDS:
        return True  # blocked

    entry["count"] += 1
    return False


def _cleanup_expired_otps() -> None:
    """Remove expired OTP entries to prevent unbounded memory growth."""
    now = datetime.now(timezone.utc)
    expired = [k for k, v in _otp_store.items() if v["expires_at"] < now]
    for k in expired:
        del _otp_store[k]


def _store_otp(email: str, code: str) -> None:
    _otp_store[email.lower()] = {
        "code": code,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES),
    }


def _verify_otp(email: str, code: str) -> bool:
    entry = _otp_store.get(email.lower())
    if not entry:
        return False
    if datetime.now(timezone.utc) > entry["expires_at"]:
        _otp_store.pop(email.lower(), None)
        return False
    if entry["code"] != code.strip():
        return False
    # Consume the code so it can't be reused
    _otp_store.pop(email.lower(), None)
    return True


# Ã¢â€â‚¬Ã¢â€â‚¬ Endpoints Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@router.post("/send-code", response_model=SendCodeResponse)
def send_code(payload: SendCodeRequest):
    """Generate a 6-digit OTP and send it to the customer's email."""
    _cleanup_expired_otps()  # Keep memory tidy on every request

    if _is_rate_limited(payload.email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Please wait {RATE_LIMIT_WINDOW_MINUTES} minutes before requesting a new code.",
        )

    code = _generate_otp()
    _store_otp(payload.email, code)
    _send_code_email(payload.email, code)

    import os
    is_dev = os.getenv("ENVIRONMENT", "development") == "development"

    return SendCodeResponse(
        message=f"Code sent to {payload.email}. Check your inbox.",
        # Only expose code in dev/Railway for easy testing
        dev_code=code if is_dev else None,
    )


@router.post("/verify-code", response_model=VerifyCodeResponse)
def verify_code(payload: VerifyCodeRequest, db: Session = Depends(get_db)):
    """Verify OTP and return a JWT. Creates a User record if first time."""
    if not _verify_otp(payload.email, payload.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired code. Request a new one.",
        )

    # Find or create User
    email = payload.email.lower()
    user = db.query(User).filter(User.email == email).first()
    is_new = user is None

    if is_new:
        user = User(email=email, is_customer=True, is_provider=False)
        db.add(user)
        db.flush()  # get user_id before linking
        logger.info(f"New customer created: {user.user_id} ({email})")

    # Link any existing Customer records (from web bookings) that share this
    # email but have no user_id yet Ã¢â‚¬â€ happens when someone books before signing up.
    db.query(Customer).filter(
        Customer.customer_email == email,
        Customer.user_id.is_(None),
    ).update({"user_id": user.user_id})

    # Copy the best available name from those Customer records to User.display_name
    # so the customer profile shows their name immediately after first login.
    if not user.display_name:
        best = (
            db.query(Customer.display_name)
            .filter(
                Customer.customer_email == email,
                Customer.display_name.isnot(None),
                Customer.display_name != "",
            )
            .order_by(Customer.created_at.desc())
            .first()
        )
        if best and best[0]:
            user.display_name = best[0]
            logger.info("Synced display_name '%s' to user %s on login", best[0], user.user_id)

    db.commit()
    db.refresh(user)

    token = create_access_token(
        user_id=user.user_id,
        role=["customer"],
        provider="email",
    )

    return VerifyCodeResponse(
        access_token=token,
        user_id=user.user_id,
        is_new_user=is_new,
    )

@router.get("/verify-chat-link")
def verify_chat_link(token: str, db: Session = Depends(get_db)):
    """Consume one-time chat verification link and bind email identity."""
    try:
        result = ChatAuthService.consume_verification_link(db, token)
    except ValueError as e:
        return HTMLResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=(
                "<html><body style='font-family:sans-serif;padding:24px;'>"
                "<h2>Verification failed</h2>"
                f"<p>{str(e)}</p>"
                "<p>Please return to chat and ask for a new verification link.</p>"
                "</body></html>"
            ),
        )

    return HTMLResponse(
        content=(
            "<html><body style='font-family:sans-serif;padding:24px;'>"
            "<h2>Email verified</h2>"
            f"<p>{result['email']} is now verified.</p>"
            "<p>You can now return to your chat and continue booking.</p>"
            "</body></html>"
        )
    )
