"""
Token encryption helpers.

Used for sensitive third-party access tokens (Instagram, etc.).
Backward compatible with legacy plaintext rows:
    - values starting with "enc:v1:" are decrypted
    - other values are treated as plaintext legacy tokens
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

_PREFIX = "enc:v1:"


def _build_fernet() -> Fernet:
    # Prefer explicit encryption key; fall back to JWT secret for local/dev continuity.
    raw_secret = (
        (settings.TOKEN_ENCRYPTION_KEY or "").strip()
        or os.getenv("JWT_SECRET", "").strip()
        or "fixmeapp-dev-secret"
    )
    key = base64.urlsafe_b64encode(hashlib.sha256(raw_secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_token(token: str | None) -> str | None:
    if not token:
        return None
    fernet = _build_fernet()
    encrypted = fernet.encrypt(token.encode("utf-8")).decode("utf-8")
    return f"{_PREFIX}{encrypted}"


def decrypt_token(stored_value: str | None) -> str | None:
    if not stored_value:
        return None
    if not stored_value.startswith(_PREFIX):
        # Legacy plaintext token.
        return stored_value

    encrypted = stored_value[len(_PREFIX) :]
    try:
        fernet = _build_fernet()
        return fernet.decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return None
