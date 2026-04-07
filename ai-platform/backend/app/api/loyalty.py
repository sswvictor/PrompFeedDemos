from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.provider import Provider
from app.services.loyalty_service import LoyaltyService
from app.utils.jwt_token import decode_access_token

router = APIRouter(prefix="/loyalty", tags=["loyalty"])
security = HTTPBearer()


@router.get("/me")
def get_my_loyalty(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        payload = decode_access_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user ID",
        )

    roles = payload.get("role", [])

    if "business" in roles:
        provider = db.query(Provider).filter(Provider.user_id == user_id).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        LoyaltyService.award_provider_active_month_if_eligible(db, provider.provider_id)
        snapshot = LoyaltyService.get_actor_snapshot(
            db,
            actor_type="provider",
            actor_id=provider.provider_id,
        )
        return {
            "actor_type": "provider",
            "actor_id": provider.provider_id,
            "score": snapshot.score,
            "tier": snapshot.tier,
            "level_badge": snapshot.level_badge,
            "completed_bookings": snapshot.completed_bookings,
            "completed_referrals": snapshot.completed_referrals,
        }

    if "customer" in roles:
        snapshot = LoyaltyService.get_actor_snapshot(
            db,
            actor_type="customer",
            actor_id=user_id,
        )
        return {
            "actor_type": "customer",
            "actor_id": user_id,
            "score": snapshot.score,
            "tier": snapshot.tier,
            "level_badge": snapshot.level_badge,
            "completed_bookings": snapshot.completed_bookings,
            "completed_referrals": snapshot.completed_referrals,
        }

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Unsupported actor role for loyalty profile",
    )
