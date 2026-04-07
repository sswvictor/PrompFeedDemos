"""
JWT utilities for Fixmeapp Booking Logic backend.

Uses the same JWT_SECRET as the auth backend — both services validate
the same tokens.

Token payload shape:
    {
        "sub":      "<user_id (UUID)>",
        "provider": "instagram" | "email",
        "role":     ["business"] | ["customer"],
        "exp":      <unix timestamp>,
        "iat":      <unix timestamp>
    }
"""
import os
from datetime import datetime, timedelta, timezone
from jose import jwt
from jose.exceptions import JWTError, ExpiredSignatureError
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET    = os.getenv("JWT_SECRET", "supersecret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_DAYS = 30


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT. Raises ValueError on failure."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except ExpiredSignatureError:
        raise ValueError("Token expired")
    except JWTError:
        raise ValueError("Invalid token")


def create_access_token(user_id: str, role: list[str], provider: str = "email") -> str:
    """Issue a signed JWT for a user."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub":      user_id,
        "provider": provider,
        "role":     role,
        "iat":      now,
        "exp":      now + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
