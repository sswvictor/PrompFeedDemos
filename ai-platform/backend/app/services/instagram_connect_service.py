from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import requests
from sqlalchemy.orm import Session

from app.config import settings
from app.models.provider import Provider
from app.models.provider_instagram_page import ProviderInstagramPage
from app.models.user import User
from app.services.token_crypto import decrypt_token, encrypt_token


GRAPH_API_BASE = "https://graph.facebook.com/v21.0"
OAUTH_DIALOG_BASE = "https://www.facebook.com/v21.0/dialog/oauth"
STATE_TTL_SECONDS = 15 * 60


class InstagramConnectError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class InstagramConnectPayload:
    page_id: str
    page_name: str | None
    page_access_token: str
    ig_user_id: str
    username: str
    profile_picture_url: str | None
    followers_count: int | None
    follows_count: int | None
    media_count: int | None
    biography: str | None
    website: str | None


class InstagramConnectService:
    @staticmethod
    def _state_secret() -> str:
        return (
            (settings.INSTAGRAM_OAUTH_STATE_SECRET or "").strip()
            or os.getenv("JWT_SECRET", "").strip()
            or "fixmeapp-state-secret"
        )

    @staticmethod
    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

    @staticmethod
    def _b64url_decode(data: str) -> bytes:
        padding = "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode((data + padding).encode("utf-8"))

    @classmethod
    def build_signed_state(cls, *, user_id: str, return_to: str | None = None) -> str:
        payload = {
            "user_id": user_id,
            "iat": int(time.time()),
            "nonce": secrets.token_urlsafe(12),
            "return_to": return_to or "",
        }
        payload_raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        sig = hmac.new(
            cls._state_secret().encode("utf-8"),
            payload_raw,
            hashlib.sha256,
        ).digest()
        return f"{cls._b64url(payload_raw)}.{cls._b64url(sig)}"

    @classmethod
    def verify_signed_state(cls, state: str) -> dict[str, Any]:
        if not state or "." not in state:
            raise InstagramConnectError("Invalid OAuth state", status_code=400)

        payload_part, sig_part = state.split(".", 1)
        payload_raw = cls._b64url_decode(payload_part)
        expected_sig = hmac.new(
            cls._state_secret().encode("utf-8"),
            payload_raw,
            hashlib.sha256,
        ).digest()
        provided_sig = cls._b64url_decode(sig_part)
        if not hmac.compare_digest(expected_sig, provided_sig):
            raise InstagramConnectError("Invalid OAuth state signature", status_code=403)

        try:
            payload = json.loads(payload_raw.decode("utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            raise InstagramConnectError("Malformed OAuth state", status_code=400) from exc

        issued_at = int(payload.get("iat") or 0)
        if int(time.time()) - issued_at > STATE_TTL_SECONDS:
            raise InstagramConnectError("OAuth state expired. Please reconnect.", status_code=410)

        user_id = str(payload.get("user_id") or "").strip()
        if not user_id:
            raise InstagramConnectError("OAuth state missing user", status_code=400)

        return payload

    @staticmethod
    def _oauth_client_id() -> str:
        return (settings.INSTAGRAM_CLIENT_ID or settings.INSTAGRAM_APP_ID or "").strip()

    @staticmethod
    def _oauth_client_secret() -> str:
        return (settings.INSTAGRAM_CLIENT_SECRET or settings.INSTAGRAM_APP_SECRET or "").strip()

    @classmethod
    def build_auth_url(cls, *, state: str) -> str:
        client_id = cls._oauth_client_id()
        client_secret = cls._oauth_client_secret()
        if not client_id or not client_secret:
            raise InstagramConnectError("Instagram OAuth is not configured (missing client id/secret)", status_code=500)

        params = {
            "client_id": client_id,
            "redirect_uri": settings.INSTAGRAM_OAUTH_REDIRECT_URI,
            "response_type": "code",
            "scope": settings.INSTAGRAM_OAUTH_SCOPES,
            "state": state,
        }
        return f"{OAUTH_DIALOG_BASE}?{urlencode(params)}"

    @classmethod
    def _exchange_code_for_short_lived_token(cls, code: str) -> str:
        client_id = cls._oauth_client_id()
        client_secret = cls._oauth_client_secret()
        params = {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": settings.INSTAGRAM_OAUTH_REDIRECT_URI,
            "code": code,
        }
        resp = requests.get(f"{GRAPH_API_BASE}/oauth/access_token", params=params, timeout=20)
        if not resp.ok:
            raise InstagramConnectError(
                f"Instagram token exchange failed ({resp.status_code})",
                status_code=502,
            )
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise InstagramConnectError("Instagram token exchange returned no access token", status_code=502)
        return token

    @classmethod
    def _exchange_for_long_lived_user_token(cls, short_lived_token: str) -> tuple[str, int | None]:
        client_id = cls._oauth_client_id()
        client_secret = cls._oauth_client_secret()
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "fb_exchange_token": short_lived_token,
        }
        resp = requests.get(f"{GRAPH_API_BASE}/oauth/access_token", params=params, timeout=20)
        if not resp.ok:
            raise InstagramConnectError(
                f"Instagram long-lived token exchange failed ({resp.status_code})",
                status_code=502,
            )
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise InstagramConnectError("Instagram long-lived exchange returned no token", status_code=502)
        expires_in = data.get("expires_in")
        return token, int(expires_in) if expires_in is not None else None

    @staticmethod
    def _fetch_pages_with_ig(user_access_token: str) -> list[dict[str, Any]]:
        fields = (
            "id,name,access_token,"
            "instagram_business_account{"
            "id,username,profile_picture_url,followers_count,follows_count,media_count,biography,website"
            "}"
        )
        resp = requests.get(
            f"{GRAPH_API_BASE}/me/accounts",
            params={"fields": fields, "access_token": user_access_token},
            timeout=20,
        )
        if not resp.ok:
            raise InstagramConnectError(
                f"Failed to fetch Instagram pages ({resp.status_code})",
                status_code=502,
            )
        data = resp.json()
        pages = data.get("data") or []
        return [p for p in pages if (p.get("instagram_business_account") or {}).get("id")]

    @classmethod
    def exchange_code_and_fetch_payload(cls, code: str) -> tuple[InstagramConnectPayload, int | None]:
        short_token = cls._exchange_code_for_short_lived_token(code)
        user_token, expires_in = cls._exchange_for_long_lived_user_token(short_token)
        pages = cls._fetch_pages_with_ig(user_token)

        if not pages:
            raise InstagramConnectError(
                "No Instagram Business account found. Make sure your Instagram is linked to a Facebook Page.",
                status_code=400,
            )

        selected = pages[0]
        ig = selected.get("instagram_business_account") or {}
        page_access_token = selected.get("access_token")
        if not page_access_token:
            raise InstagramConnectError("No page access token returned by Meta", status_code=502)

        payload = InstagramConnectPayload(
            page_id=str(selected.get("id") or ""),
            page_name=selected.get("name"),
            page_access_token=page_access_token,
            ig_user_id=str(ig.get("id") or ""),
            username=str(ig.get("username") or ""),
            profile_picture_url=ig.get("profile_picture_url"),
            followers_count=ig.get("followers_count"),
            follows_count=ig.get("follows_count"),
            media_count=ig.get("media_count"),
            biography=ig.get("biography"),
            website=ig.get("website"),
        )
        if not payload.ig_user_id:
            raise InstagramConnectError("Instagram account id missing in OAuth response", status_code=502)

        return payload, expires_in

    @staticmethod
    def upsert_provider_connection(
        db: Session,
        *,
        user_id: str,
        payload: InstagramConnectPayload,
    ) -> ProviderInstagramPage:
        provider = db.query(Provider).filter(Provider.user_id == user_id).first()
        user = db.query(User).filter(User.user_id == user_id).first()

        encrypted_token = encrypt_token(payload.page_access_token)

        page = (
            db.query(ProviderInstagramPage)
            .filter(ProviderInstagramPage.instagram_page_id == payload.ig_user_id)
            .first()
        )
        if page:
            page.provider_id = provider.provider_id if provider else page.provider_id
            page.page_name = payload.username or payload.page_name or page.page_name
            page.access_token = encrypted_token
            page.is_platform_page = False
        else:
            page = ProviderInstagramPage(
                provider_id=provider.provider_id if provider else None,
                instagram_page_id=payload.ig_user_id,
                page_name=payload.username or payload.page_name,
                access_token=encrypted_token,
                is_platform_page=False,
            )
            db.add(page)

        if provider:
            if payload.username:
                provider.instagram_username = payload.username
            provider.ig_profile_picture_url = payload.profile_picture_url
            provider.ig_followers_count = payload.followers_count
            provider.ig_following_count = payload.follows_count
            provider.ig_stats_synced_at = datetime.now(timezone.utc)

        if user:
            user.instagram_user_id = payload.ig_user_id
            user.instagram_username = payload.username or user.instagram_username
            if payload.profile_picture_url and not user.image_url:
                user.image_url = payload.profile_picture_url

        db.commit()
        db.refresh(page)
        return page

    @staticmethod
    def get_connection_status(db: Session, *, user_id: str) -> dict[str, Any]:
        provider = db.query(Provider).filter(Provider.user_id == user_id).first()
        user = db.query(User).filter(User.user_id == user_id).first()

        page = None
        if provider:
            page = (
                db.query(ProviderInstagramPage)
                .filter(
                    ProviderInstagramPage.provider_id == provider.provider_id,
                    ProviderInstagramPage.is_platform_page.is_(False),
                )
                .order_by(ProviderInstagramPage.created_at.desc())
                .first()
            )

        if not page and user and user.instagram_user_id:
            page = (
                db.query(ProviderInstagramPage)
                .filter(
                    ProviderInstagramPage.instagram_page_id == user.instagram_user_id,
                    ProviderInstagramPage.is_platform_page.is_(False),
                )
                .order_by(ProviderInstagramPage.created_at.desc())
                .first()
            )

        if not page:
            return {"connected": False}

        decrypted = decrypt_token(page.access_token)
        return {
            "connected": bool(decrypted),
            "instagram_user_id": page.instagram_page_id,
            "instagram_username": (provider.instagram_username if provider else (user.instagram_username if user else None)),
            "profile_picture_url": (provider.ig_profile_picture_url if provider else (user.image_url if user else None)),
            "followers_count": provider.ig_followers_count if provider else None,
            "following_count": provider.ig_following_count if provider else None,
        }

    @staticmethod
    def disconnect_for_user(db: Session, *, user_id: str) -> int:
        provider = db.query(Provider).filter(Provider.user_id == user_id).first()
        user = db.query(User).filter(User.user_id == user_id).first()

        pages = []
        if provider:
            pages.extend(
                db.query(ProviderInstagramPage)
                .filter(
                    ProviderInstagramPage.provider_id == provider.provider_id,
                    ProviderInstagramPage.is_platform_page.is_(False),
                )
                .all()
            )

        if user and user.instagram_user_id:
            extra = (
                db.query(ProviderInstagramPage)
                .filter(
                    ProviderInstagramPage.instagram_page_id == user.instagram_user_id,
                    ProviderInstagramPage.is_platform_page.is_(False),
                )
                .all()
            )
            seen = {p.id for p in pages}
            pages.extend([p for p in extra if p.id not in seen])

        for page in pages:
            page.access_token = None

        db.commit()
        return len(pages)


