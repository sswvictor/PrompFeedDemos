"""
Instagram DM send adapter.

Outbound message sender via Meta Graph API.
Ported from fixmeapp-instagram-bot/app/instagram.py.
"""
import logging
import httpx

logger = logging.getLogger(__name__)

GRAPH_API_URL = "https://graph.facebook.com/v21.0"


def _split_message(text: str, max_length: int = 1000) -> list[str]:
    """Split a long message into chunks that fit Instagram's limit."""
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break
        # Try to split at a newline or space
        split_at = text.rfind("\n", 0, max_length)
        if split_at == -1:
            split_at = text.rfind(" ", 0, max_length)
        if split_at == -1:
            split_at = max_length
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()

    return chunks


async def send_message(
    access_token: str,
    recipient_id: str,
    text: str,
) -> bool:
    """Send a DM to an Instagram user via Graph API.

    Splits messages >1000 chars into multiple sends.
    Returns True if all chunks sent successfully.
    """
    chunks = _split_message(text, max_length=1000)
    success = True

    async with httpx.AsyncClient(timeout=10.0) as client:
        for chunk in chunks:
            try:
                response = await client.post(
                    f"{GRAPH_API_URL}/me/messages",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={
                        "recipient": {"id": recipient_id},
                        "message": {"text": chunk},
                    },
                )
                if response.status_code != 200:
                    logger.error(
                        "Failed to send message: %s %s",
                        response.status_code,
                        response.text,
                    )
                    success = False
            except httpx.HTTPError as e:
                logger.error("HTTP error sending reply: %s", e)
                success = False

    return success
