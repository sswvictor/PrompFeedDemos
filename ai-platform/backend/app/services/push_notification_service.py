"""
Push notification service for Expo Push Service.

Expo Push Service proxies to both APNs (iOS) and FCM (Android) —
no Firebase SDK or Apple certificates needed at the app level.
Gateway: https://exp.host/--/api/v2/push/send
"""

import logging

import httpx

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


class PushNotificationService:

    @staticmethod
    def send(token: str, title: str, body: str, data: dict | None = None) -> bool:
        """Send a single push notification via Expo Push Service.

        Returns True if the request was accepted (HTTP 200), False otherwise.
        Never raises — all errors are logged and swallowed so callers can
        treat this as best-effort.
        """
        if not token or not token.startswith("ExponentPushToken"):
            logger.debug("send() skipped — invalid or missing push token: %r", token)
            return False

        payload = {
            "to":    token,
            "title": title,
            "body":  body,
            "sound": "default",
            "data":  data or {},
        }
        try:
            resp = httpx.post(
                EXPO_PUSH_URL,
                json=payload,
                timeout=10,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                logger.warning(
                    "Expo push returned %s for token %s: %s",
                    resp.status_code, token[:30], resp.text[:200],
                )
                return False
            # Expo may still report per-message errors inside the 200 body
            result = resp.json()
            statuses = result.get("data", [])
            if statuses and statuses[0].get("status") == "error":
                logger.warning(
                    "Expo push error for token %s: %s",
                    token[:30], statuses[0].get("message"),
                )
                return False
            return True
        except Exception:
            logger.exception("Push notification request failed for token %s", token[:30])
            return False

    # ── High-level event helpers ──────────────────────────────────────────────

    @staticmethod
    def notify_new_booking(
        db,
        provider_id: str,
        customer_name: str,
        service: str,
        time: str,
    ) -> None:
        """Push: provider has received a new booking."""
        from app.models.provider import Provider  # local import avoids circular deps

        provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
        if not provider or not provider.push_token:
            return

        PushNotificationService.send(
            token=provider.push_token,
            title="\U0001F4C5 New booking!",
            body=f"{customer_name} booked {service} at {time}",
            data={"type": "new_booking", "provider_id": provider_id},
        )

    @staticmethod
    def notify_booking_cancelled(
        db,
        provider_id: str,
        customer_name: str,
        time: str,
    ) -> None:
        """Push: a booking was cancelled."""
        from app.models.provider import Provider

        provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
        if not provider or not provider.push_token:
            return

        PushNotificationService.send(
            token=provider.push_token,
            title="\u274C Booking cancelled",
            body=f"{customer_name} cancelled their {time} appointment",
            data={"type": "cancelled", "provider_id": provider_id},
        )

    @staticmethod
    def notify_booking_confirmed(
        db,
        provider_id: str,
        customer_name: str,
        service: str,
        time: str,
    ) -> None:
        """Push: a pending booking was confirmed."""
        from app.models.provider import Provider

        provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
        if not provider or not provider.push_token:
            return

        PushNotificationService.send(
            token=provider.push_token,
            title="\u2705 Booking confirmed",
            body=f"{customer_name} confirmed {service} at {time}",
            data={"type": "confirmed", "provider_id": provider_id},
        )
