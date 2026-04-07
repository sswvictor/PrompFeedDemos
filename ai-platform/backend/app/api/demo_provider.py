"""Demo provider lock endpoint.

Purpose:
- Keep /demo/chat pinned to a single real provider account for investor demos.
- Avoid requiring provider login for every demo run.

This endpoint is intentionally simple and read-only.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.provider import Provider
from app.models.user import User

router = APIRouter(prefix="/demo", tags=["demo"])


class DemoProviderLockOut(BaseModel):
    provider_id: str
    provider_name: str
    provider_email: str
    slug: str | None = None


@router.get("/provider-lock", response_model=DemoProviderLockOut)
def get_demo_provider_lock(db: Session = Depends(get_db)):
    """Return the configured demo provider profile by email.

    Email source: settings.DEMO_PROVIDER_EMAIL
    """
    email = (settings.DEMO_PROVIDER_EMAIL or "").strip().lower()
    if not email:
        raise HTTPException(
            status_code=503,
            detail="DEMO_PROVIDER_EMAIL is not configured.",
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Demo provider user '{email}' not found. "
                "Run scripts/ensure_demo_provider.py first."
            ),
        )

    provider = db.query(Provider).filter(Provider.user_id == user.user_id).first()
    if not provider:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Demo provider profile for '{email}' not found. "
                "Run scripts/ensure_demo_provider.py first."
            ),
        )

    return DemoProviderLockOut(
        provider_id=provider.provider_id,
        provider_name=provider.name,
        provider_email=email,
        slug=provider.slug,
    )
