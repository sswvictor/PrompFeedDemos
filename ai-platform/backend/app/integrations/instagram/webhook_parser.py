"""
Instagram webhook payload parser.

Converts raw Meta webhook JSON into structured dicts
that our service layer understands.

Ported from fixmeapp-instagram-bot/app/instagram.py.
"""
import hmac
import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


def verify_webhook_signature(raw_body: bytes, signature_header: str, app_secret: str) -> bool:
    """Validate the X-Hub-Signature-256 header using HMAC-SHA256.

    Meta sends this header on every webhook POST so we can verify
    the payload hasn't been tampered with.
    """
    if not signature_header or not app_secret:
        return False
    expected = "sha256=" + hmac.new(
        app_secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def parse_webhook_challenge(
    hub_mode: str | None,
    hub_verify_token: str | None,
    hub_challenge: str | None,
    expected_token: str,
) -> str | None:
    """Handle Meta webhook verification (GET /webhook).

    Returns hub_challenge if valid, else None.
    """
    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        return hub_challenge
    return None


def parse_messaging_events(payload: dict[str, Any]) -> list[dict]:
    """Extract message events from an Instagram webhook payload.

    Skips echo messages, read receipts, and delivery confirmations.

    Returns list of dicts with keys:
        sender_id, recipient_id, timestamp, text, message_id
    """
    messages: list[dict] = []

    if payload.get("object") != "instagram":
        return messages

    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            # Skip echo messages (our own sent messages)
            if event.get("message", {}).get("is_echo"):
                continue

            # Skip read receipts and delivery confirmations
            if "read" in event or "delivery" in event:
                continue

            message_data = event.get("message", {})
            text = message_data.get("text")
            if not text:
                continue

            sender_id = event.get("sender", {}).get("id", "")
            recipient_id = event.get("recipient", {}).get("id", "")
            timestamp = event.get("timestamp", 0)
            message_id = message_data.get("mid", "")

            if sender_id:
                messages.append({
                    "sender_id": sender_id,
                    "recipient_id": recipient_id,
                    "timestamp": timestamp,
                    "text": text,
                    "message_id": message_id,
                })

    return messages
