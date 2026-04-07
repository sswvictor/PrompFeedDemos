"""Resolve `users.user_id` for discovery (platform) conversations.

`Conversation.user_id` is a FK to `users`. Instagram PSIDs and ad-hoc web thread
ids are not valid user primary keys; this module creates or looks up a User row.
"""

from __future__ import annotations

import hashlib
import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)


def ensure_user_for_discovery_conversation(
    db: Session,
    *,
    channel: str,
    sender_id: str,
    thread_id: str,
) -> str:
    """
    Return a UUID `users.user_id` suitable for discovery conversations.

    - instagram_dm: match or create by `User.instagram_user_id` (IG-scoped PSID).
    - other channels (e.g. web): stable synthetic email derived from thread_id.
    """
    if channel == "instagram_dm":
        existing = (
            db.query(User).filter(User.instagram_user_id == sender_id).first()
        )
        if existing:
            return existing.user_id
        email = f"ig-{sender_id}@discovery.fixmeapp.internal"
        user = User(
            email=email,
            instagram_user_id=sender_id,
            is_customer=True,
            is_provider=False,
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
            return user.user_id
        except IntegrityError:
            db.rollback()
            again = (
                db.query(User)
                .filter(User.instagram_user_id == sender_id)
                .first()
            )
            if again:
                return again.user_id
            again = db.query(User).filter(User.email == email).first()
            if again:
                if not again.instagram_user_id:
                    again.instagram_user_id = sender_id
                    db.commit()
                return again.user_id
            logger.exception("Failed to create discovery User for instagram_dm")
            raise

    key = (thread_id or sender_id).strip()
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
    email = f"discovery-web-{digest}@fixmeapp.internal"
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return existing.user_id
    user = User(email=email, is_customer=True, is_provider=False)
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
        return user.user_id
    except IntegrityError:
        db.rollback()
        again = db.query(User).filter(User.email == email).first()
        if again:
            return again.user_id
        raise
