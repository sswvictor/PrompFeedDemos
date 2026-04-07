"""
Auth dependency for FixmeApp Booking Logic API.

Bridges the auth system (JWT issued by magic-code / Instagram OAuth flow)
with the booking logic's Provider model.

Usage in routes:
    from app.api.auth import get_current_provider

    @router.get("/my-endpoint")
    def my_endpoint(provider_id: str = Depends(get_current_provider), db: Session = Depends(get_db)):
        ...
"""

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.provider import Provider

# JWT decoded locally — same secret as auth backend
from app.utils.jwt_token import decode_access_token

# auto_error=False so cookie fallback works when no Authorization header is sent
security = HTTPBearer(auto_error=False)

PROVIDER_COOKIE = "fixme_provider_token"


def _resolve_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials],
) -> str:
    """Return JWT from Bearer header (mobile) or httpOnly cookie (web browser)."""
    if credentials and credentials.credentials:
        return credentials.credentials
    cookie_token = request.cookies.get(PROVIDER_COOKIE)
    if cookie_token:
        return cookie_token
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_provider(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> str:
    """
    FastAPI dependency: validate JWT and return the authenticated provider_id.

    Flow:
        Authorization: Bearer <access_token>
        → decode JWT → get user_id from 'sub'
        → verify role contains 'business'
        → look up Provider where user_id matches
        → return provider_id

    Raises:
        401 — token missing, invalid, or expired
        403 — user is authenticated but not a business provider
        404 — user_id has no linked Provider record yet
    """
    token = _resolve_token(request, credentials)
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user ID",
            headers={"WWW-Authenticate": "Bearer"},
        )

    roles = payload.get("role", [])
    if "business" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Provider access required. This account is not registered as a business.",
        )

    provider = db.query(Provider).filter(Provider.user_id == user_id).first()
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No provider profile found for this account. Complete onboarding first.",
        )

    return provider.provider_id


def get_current_user_id(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """
    Lighter dependency: just validate JWT and return user_id.

    Used for onboarding endpoints that run before a Provider record exists,
    e.g. POST /providers (creates the provider for the first time).
    """
    token = _resolve_token(request, credentials)
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user ID",
        )

    roles = payload.get("role", [])
    if "business" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Business account required.",
        )

    return user_id
