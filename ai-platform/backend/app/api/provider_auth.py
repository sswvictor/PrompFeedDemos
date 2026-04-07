"""
Provider authentication - email magic code flow.

Routes:
    POST /auth/provider/send-code    - send 6-digit OTP to provider email
    POST /auth/provider/verify-code  - verify OTP, return JWT with role=["business"]
    GET  /auth/provider/me           - resolve JWT to provider profile + persisted email
"""

import logging
import os
import random
import string
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.api.auth import get_current_user_id
from app.db.session import engine, get_db
from app.utils.jwt_token import create_access_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/provider", tags=["provider-auth"])

# In-memory OTP store
_otp_store: dict[str, dict] = {}
OTP_EXPIRE_MINUTES = 10

_rate_limit: dict[str, dict] = {}
RATE_LIMIT_MAX_SENDS = 3
RATE_LIMIT_WINDOW_MINUTES = 10


class SendCodeRequest(BaseModel):
    email: EmailStr


class SendCodeResponse(BaseModel):
    message: str
    dev_code: str | None = None


class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str


class VerifyCodeResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    is_new_user: bool
    has_provider_profile: bool = False
    provider_id: str | None = None
    slug: str | None = None


class ProviderMeResponse(BaseModel):
    user_id: str
    email: str
    has_provider_profile: bool
    provider_id: str | None = None
    provider_name: str | None = None
    slug: str | None = None


def _generate_otp() -> str:
    return "".join(random.choices(string.digits, k=6))


def _send_code_email(email: str, code: str) -> None:
    """MVP: log to console. Replace with SendGrid/Resend for production."""
    logger.info("=== PROVIDER OTP for %s: %s ===", email, code)


def _store_otp(email: str, code: str) -> None:
    _otp_store[email.lower()] = {
        "code": code,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES),
    }


def _otp_matches(email: str, code: str) -> bool:
    entry = _otp_store.get(email.lower())
    if not entry:
        return False
    if datetime.now(timezone.utc) > entry["expires_at"]:
        _otp_store.pop(email.lower(), None)
        return False
    if entry["code"] != code.strip():
        return False
    return True


def _cleanup_expired_otps() -> None:
    now = datetime.now(timezone.utc)
    expired = [k for k, v in _otp_store.items() if now > v["expires_at"]]
    for k in expired:
        _otp_store.pop(k, None)


def _is_rate_limited(email: str) -> bool:
    key = email.lower()
    now = datetime.now(timezone.utc)
    entry = _rate_limit.get(key)
    if not entry:
        _rate_limit[key] = {"count": 1, "window_start": now}
        return False
    window_end = entry["window_start"] + timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)
    if now > window_end:
        _rate_limit[key] = {"count": 1, "window_start": now}
        return False
    if entry["count"] >= RATE_LIMIT_MAX_SENDS:
        return True
    entry["count"] += 1
    return False


def _table_exists(db: Session, table_name: str) -> bool:  # noqa: ARG001
    inspector = sa.inspect(engine)
    return table_name in inspector.get_table_names()


def _column_exists(db: Session, table_name: str, column_name: str) -> bool:  # noqa: ARG001
    inspector = sa.inspect(engine)
    try:
        cols = inspector.get_columns(table_name)
    except Exception:
        return False
    return any(c.get("name") == column_name for c in cols)


@router.post("/send-code", response_model=SendCodeResponse)
def send_code(payload: SendCodeRequest):
    """Generate a 6-digit OTP and send it to the provider's email."""
    _cleanup_expired_otps()

    if _is_rate_limited(payload.email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Please wait {RATE_LIMIT_WINDOW_MINUTES} minutes.",
        )

    try:
        code = _generate_otp()
        _store_otp(payload.email, code)
        _send_code_email(payload.email, code)
    except Exception:
        logger.exception("Provider send-code failed for %s", payload.email)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Temporary login issue. Please retry in a moment.",
        )

    is_dev = os.getenv("ENVIRONMENT", "development") == "development"

    return SendCodeResponse(
        message=f"Code sent to {payload.email}. Check your inbox.",
        dev_code=code if is_dev else None,
    )


@router.post("/verify-code", response_model=VerifyCodeResponse)
def verify_code(payload: VerifyCodeRequest, http_response: Response, db: Session = Depends(get_db)):
    """Verify OTP and return a business-scoped JWT. Creates User if first time."""
    if not _otp_matches(payload.email, payload.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired code. Request a new one.",
        )

    email = payload.email.lower()

    try:
        if not _table_exists(db, "users"):
            raise RuntimeError("users table missing")

        user_row = db.execute(
            sa.text(
                "SELECT user_id, email, is_provider "
                "FROM users WHERE lower(email) = :email LIMIT 1"
            ),
            {"email": email},
        ).mappings().first()

        is_new = user_row is None

        if is_new:
            new_user_id = str(uuid.uuid4())
            db.execute(
                sa.text(
                    "INSERT INTO users (user_id, email, is_customer, is_provider, status, created_at) "
                    "VALUES (:user_id, :email, :is_customer, :is_provider, :status, :created_at)"
                ),
                {
                    "user_id": new_user_id,
                    "email": email,
                    "is_customer": False,
                    "is_provider": True,
                    "status": "active",
                    "created_at": datetime.now(timezone.utc),
                },
            )
            db.commit()
            user_id = new_user_id
            logger.info("New provider user created: %s (%s)", user_id, email)
        else:
            user_id = str(user_row["user_id"])
            is_provider = bool(user_row.get("is_provider", False))
            if not is_provider and _column_exists(db, "users", "is_provider"):
                db.execute(
                    sa.text("UPDATE users SET is_provider = :is_provider WHERE user_id = :user_id"),
                    {"is_provider": True, "user_id": user_id},
                )
                db.commit()

        token = create_access_token(
            user_id=user_id,
            role=["business"],
            provider="email",
        )

        provider_id = None
        slug = None
        if _table_exists(db, "providers") and _column_exists(db, "providers", "provider_id") and _column_exists(db, "providers", "user_id"):
            if _column_exists(db, "providers", "slug"):
                provider_row = db.execute(
                    sa.text("SELECT provider_id, slug FROM providers WHERE user_id = :user_id LIMIT 1"),
                    {"user_id": user_id},
                ).mappings().first()
                if provider_row:
                    provider_id = provider_row.get("provider_id")
                    slug = provider_row.get("slug")
            else:
                provider_row = db.execute(
                    sa.text("SELECT provider_id FROM providers WHERE user_id = :user_id LIMIT 1"),
                    {"user_id": user_id},
                ).mappings().first()
                if provider_row:
                    provider_id = provider_row.get("provider_id")

        response = VerifyCodeResponse(
            access_token=token,
            user_id=user_id,
            is_new_user=is_new,
            has_provider_profile=provider_id is not None,
            provider_id=provider_id,
            slug=slug,
        )
    except Exception:
        db.rollback()
        logger.exception("Provider verify-code failed for %s", email)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Temporary login issue. Please retry in a moment.",
        )

    # Consume OTP only after successful auth flow.
    _otp_store.pop(email, None)

    _is_secure = os.getenv("ENVIRONMENT", "development") != "development"
    http_response.set_cookie(
        key="fixme_provider_token",
        value=token,
        httponly=True,
        secure=_is_secure,
        samesite="lax",
        max_age=30 * 24 * 3600,  # 30 days — matches JWT expiry
        path="/",
    )

    return response


@router.get("/me", response_model=ProviderMeResponse)
def get_provider_me(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Resolve authenticated provider JWT to persistent identity in DB.

    Frontend uses this to bind provider chat/home/settings to the correct
    provider profile and avoid writing bookings to the wrong provider.
    """
    try:
        user_row = db.execute(
            sa.text("SELECT user_id, email FROM users WHERE user_id = :user_id LIMIT 1"),
            {"user_id": user_id},
        ).mappings().first()

        if not user_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        provider_id = None
        provider_name = None
        slug = None

        if _table_exists(db, "providers") and _column_exists(db, "providers", "provider_id") and _column_exists(db, "providers", "user_id"):
            select_cols = ["provider_id"]
            if _column_exists(db, "providers", "name"):
                select_cols.append("name")
            if _column_exists(db, "providers", "slug"):
                select_cols.append("slug")
            cols_sql = ", ".join(select_cols)
            row = db.execute(
                sa.text(f"SELECT {cols_sql} FROM providers WHERE user_id = :user_id LIMIT 1"),
                {"user_id": user_id},
            ).mappings().first()
            if row:
                provider_id = row.get("provider_id")
                provider_name = row.get("name")
                slug = row.get("slug")

        return ProviderMeResponse(
            user_id=str(user_row["user_id"]),
            email=str(user_row["email"]),
            has_provider_profile=provider_id is not None,
            provider_id=provider_id,
            provider_name=provider_name,
            slug=slug,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Provider /me failed for user_id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Temporary login issue. Please retry in a moment.",
        )


@router.post("/logout")
def logout(http_response: Response):
    """Clear the provider auth cookie. Client should also wipe localStorage."""
    http_response.delete_cookie(key="fixme_provider_token", path="/")
    return {"message": "Logged out"}
