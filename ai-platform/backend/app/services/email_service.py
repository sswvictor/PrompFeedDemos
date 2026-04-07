import logging
import os

import httpx

logger = logging.getLogger(__name__)

# Config from environment
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "FixMe <noreply@fixmeapp.ai>")
APP_BASE_URL = os.getenv("APP_BASE_URL", "https://fixmeapp.ai")


class EmailService:
    """Lightweight email sender via Resend API (httpx, already in deps)."""

    @staticmethod
    def _send(to: str, subject: str, html: str) -> bool:
        """Send an email. Returns True on success, False on failure. Never raises."""
        if not RESEND_API_KEY:
            logger.warning("RESEND_API_KEY not set — email to %s skipped: %s", to, subject)
            return False

        try:
            resp = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={
                    "from": FROM_EMAIL,
                    "to": [to],
                    "subject": subject,
                    "html": html,
                },
                timeout=10,
            )
            if resp.status_code in (200, 201):
                logger.info("email.sent to=%s subject=%s", to, subject)
                return True
            logger.error(
                "email.send_failed to=%s subject=%s status=%s body=%s",
                to, subject, resp.status_code, resp.text,
            )
            return False
        except Exception:
            logger.exception("email.send_error to=%s subject=%s", to, subject)
            return False

    @staticmethod
    def send_waitlist_offer(
        to: str,
        provider_name: str,
        slot_date: str,
        slot_time: str,
        offer_id: str,
        offer_secret: str = "",
    ) -> bool:
        """Email: a slot opened for you! Accept within 10 minutes."""
        accept_url = f"{APP_BASE_URL}/waitlist/offer/{offer_id}?secret={offer_secret}"

        html = f"""\
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; background: #0D0D0D; color: #fff; padding: 32px 24px; border-radius: 16px;">
  <div style="text-align: center; margin-bottom: 24px;">
    <span style="color: #C8A97E; font-weight: 700; font-size: 20px;">FixMe</span>
  </div>

  <h1 style="font-size: 22px; font-weight: 700; margin: 0 0 8px; text-align: center;">
    A slot just opened!
  </h1>

  <p style="color: #999; font-size: 14px; text-align: center; margin: 0 0 24px;">
    Great news — <strong style="color: #fff;">{provider_name}</strong> has an opening that matches your preferences.
  </p>

  <div style="background: #1A1A1A; border: 1px solid #2A2A2A; border-radius: 12px; padding: 20px; text-align: center; margin-bottom: 24px;">
    <div style="color: #C8A97E; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Available slot</div>
    <div style="font-size: 20px; font-weight: 700;">{slot_date}</div>
    <div style="font-size: 28px; font-weight: 700; color: #C8A97E; margin-top: 4px;">{slot_time}</div>
  </div>

  <div style="background: #1A1A1A; border: 1px solid #2A2A2A; border-radius: 12px; padding: 16px; text-align: center; margin-bottom: 24px;">
    <div style="color: #E53935; font-size: 13px; font-weight: 600;">This offer expires in 10 minutes</div>
    <div style="color: #999; font-size: 12px; margin-top: 4px;">If you don't respond, the slot goes to the next person in line.</div>
  </div>

  <a href="{accept_url}" style="display: block; background: #C8A97E; color: #0D0D0D; text-align: center; padding: 14px; border-radius: 12px; font-weight: 700; font-size: 16px; text-decoration: none; margin-bottom: 12px;">
    View &amp; Accept Slot
  </a>

  <p style="color: #666; font-size: 11px; text-align: center; margin-top: 24px;">
    You're receiving this because you joined the waitlist at {provider_name} via FixMe.
  </p>
</div>"""

        return EmailService._send(
            to=to,
            subject=f"A slot just opened at {provider_name}! ?",
            html=html,
        )
    @staticmethod
    def send_customer_otp(
        to: str,
        code: str,
        expires_minutes: int = 10,
    ) -> bool:
        """Email: one-time login code for customer auth."""
        html = f"""\
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; background: #0D0D0D; color: #fff; padding: 32px 24px; border-radius: 16px;">
  <div style="text-align: center; margin-bottom: 24px;">
    <span style="color: #C8A97E; font-weight: 700; font-size: 20px;">FixMe</span>
  </div>

  <h1 style="font-size: 22px; font-weight: 700; margin: 0 0 8px; text-align: center;">
    Your login code
  </h1>

  <p style="color: #999; font-size: 14px; text-align: center; margin: 0 0 24px;">
    Use this one-time code to sign in to your FixMe account.
  </p>

  <div style="background: #1A1A1A; border: 1px solid #2A2A2A; border-radius: 12px; padding: 20px; text-align: center; margin-bottom: 24px;">
    <div style="color: #C8A97E; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">One-time code</div>
    <div style="font-size: 34px; font-weight: 700; letter-spacing: 6px; color: #C8A97E;">{code}</div>
  </div>

  <p style="color: #999; font-size: 12px; text-align: center; margin: 12px 0 0;">
    This code expires in {expires_minutes} minutes.
  </p>
</div>"""

        return EmailService._send(
            to=to,
            subject="Your FixMe login code",
            html=html,
        )



    @staticmethod
    def send_waitlist_confirmed(
        to: str,
        provider_name: str,
        booking_number: int,
        slot_date: str,
        slot_time: str,
    ) -> bool:
        """Email: your waitlist booking is confirmed."""
        html = f"""\
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; background: #0D0D0D; color: #fff; padding: 32px 24px; border-radius: 16px;">
  <div style="text-align: center; margin-bottom: 24px;">
    <span style="color: #C8A97E; font-weight: 700; font-size: 20px;">FixMe</span>
  </div>

  <div style="text-align: center; margin-bottom: 16px;">
    <div style="width: 56px; height: 56px; border-radius: 50%; background: #4CAF50; display: inline-flex; align-items: center; justify-content: center;">
      <span style="font-size: 28px;">&#10003;</span>
    </div>
  </div>

  <h1 style="font-size: 22px; font-weight: 700; margin: 0 0 8px; text-align: center;">
    Booking confirmed!
  </h1>

  <p style="color: #999; font-size: 14px; text-align: center; margin: 0 0 24px;">
    Your waitlist spot at <strong style="color: #fff;">{provider_name}</strong> has been converted to a booking.
  </p>

  <div style="background: #1A1A1A; border: 1px solid #2A2A2A; border-radius: 12px; padding: 20px; margin-bottom: 24px;">
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
      <span style="color: #999; font-size: 13px;">Reference</span>
      <span style="font-weight: 600;">#{booking_number}</span>
    </div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
      <span style="color: #999; font-size: 13px;">Date</span>
      <span style="font-weight: 600;">{slot_date}</span>
    </div>
    <div style="display: flex; justify-content: space-between;">
      <span style="color: #999; font-size: 13px;">Time</span>
      <span style="font-weight: 600; color: #C8A97E;">{slot_time}</span>
    </div>
  </div>

  <p style="color: #666; font-size: 11px; text-align: center;">
    Booked via FixMe for {provider_name}.
  </p>
</div>"""

        return EmailService._send(
            to=to,
            subject=f"Booking confirmed at {provider_name} — #{booking_number}",
            html=html,
        )


    @staticmethod
    def send_booking_confirmed(
        to: str,
        provider_name: str,
        booking_number: int,
        service_name: str,
        slot_date: str,
        slot_time: str,
    ) -> bool:
        """Email: standard booking confirmation from AI/manual flow."""
        html = f"""\
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; background: #0D0D0D; color: #fff; padding: 32px 24px; border-radius: 16px;">
  <div style="text-align: center; margin-bottom: 24px;">
    <span style="color: #C8A97E; font-weight: 700; font-size: 20px;">FixMe</span>
  </div>

  <div style="text-align: center; margin-bottom: 16px;">
    <div style="width: 56px; height: 56px; border-radius: 50%; background: #4CAF50; display: inline-flex; align-items: center; justify-content: center;">
      <span style="font-size: 28px;">&#10003;</span>
    </div>
  </div>

  <h1 style="font-size: 22px; font-weight: 700; margin: 0 0 8px; text-align: center;">
    Your booking is confirmed
  </h1>

  <p style="color: #999; font-size: 14px; text-align: center; margin: 0 0 24px;">
    We have locked in your appointment at <strong style="color: #fff;">{provider_name}</strong>.
  </p>

  <div style="background: #1A1A1A; border: 1px solid #2A2A2A; border-radius: 12px; padding: 20px; margin-bottom: 24px;">
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
      <span style="color: #999; font-size: 13px;">Reference</span>
      <span style="font-weight: 600;">#{booking_number}</span>
    </div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
      <span style="color: #999; font-size: 13px;">Service</span>
      <span style="font-weight: 600;">{service_name}</span>
    </div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
      <span style="color: #999; font-size: 13px;">Date</span>
      <span style="font-weight: 600;">{slot_date}</span>
    </div>
    <div style="display: flex; justify-content: space-between;">
      <span style="color: #999; font-size: 13px;">Time</span>
      <span style="font-weight: 600; color: #C8A97E;">{slot_time}</span>
    </div>
  </div>

  <p style="color: #666; font-size: 11px; text-align: center;">
    You are receiving this because you booked with {provider_name} through FixMe.
  </p>
</div>"""

        return EmailService._send(
            to=to,
            subject=f"Booking confirmed at {provider_name} - #{booking_number}",
            html=html,
        )

    @staticmethod
    def send_booking_cancelled(
        to: str,
        provider_name: str,
        booking_number: int,
        service_name: str,
        slot_date: str,
        slot_time: str,
    ) -> bool:
        """Email: your booking has been cancelled."""
        html = f"""\
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; background: #0D0D0D; color: #fff; padding: 32px 24px; border-radius: 16px;">
  <div style="text-align: center; margin-bottom: 24px;">
    <span style="color: #C8A97E; font-weight: 700; font-size: 20px;">FixMe</span>
  </div>

  <div style="text-align: center; margin-bottom: 16px;">
    <div style="width: 56px; height: 56px; border-radius: 50%; background: #2A2A2A; border: 2px solid #E53935; display: inline-flex; align-items: center; justify-content: center;">
      <span style="font-size: 24px; color: #E53935;">&#10005;</span>
    </div>
  </div>

  <h1 style="font-size: 22px; font-weight: 700; margin: 0 0 8px; text-align: center;">
    Booking cancelled
  </h1>

  <p style="color: #999; font-size: 14px; text-align: center; margin: 0 0 24px;">
    Your appointment at <strong style="color: #fff;">{provider_name}</strong> has been cancelled.
  </p>

  <div style="background: #1A1A1A; border: 1px solid #2A2A2A; border-radius: 12px; padding: 20px; margin-bottom: 24px;">
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
      <span style="color: #999; font-size: 13px;">Reference</span>
      <span style="font-weight: 600; color: #999;">#{booking_number}</span>
    </div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
      <span style="color: #999; font-size: 13px;">Service</span>
      <span style="font-weight: 600; color: #999;">{service_name}</span>
    </div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
      <span style="color: #999; font-size: 13px;">Date</span>
      <span style="font-weight: 600; color: #999;">{slot_date}</span>
    </div>
    <div style="display: flex; justify-content: space-between;">
      <span style="color: #999; font-size: 13px;">Time</span>
      <span style="font-weight: 600; color: #999;">{slot_time}</span>
    </div>
  </div>

  <p style="color: #999; font-size: 13px; text-align: center; margin-bottom: 24px;">
    Want to rebook? Visit the provider's booking page to choose a new time.
  </p>

  <p style="color: #666; font-size: 11px; text-align: center;">
    You are receiving this because you had a booking with {provider_name} through FixMe.
  </p>
</div>"""

        return EmailService._send(
            to=to,
            subject=f"Booking cancelled — {provider_name} #{booking_number}",
            html=html,
        )

    @staticmethod
    def send_booking_rescheduled(
        to: str,
        provider_name: str,
        booking_number: int,
        service_name: str,
        old_slot_date: str,
        old_slot_time: str,
        new_slot_date: str,
        new_slot_time: str,
    ) -> bool:
        """Email: your booking has been rescheduled."""
        html = f"""\
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; background: #0D0D0D; color: #fff; padding: 32px 24px; border-radius: 16px;">
  <div style="text-align: center; margin-bottom: 24px;">
    <span style="color: #C8A97E; font-weight: 700; font-size: 20px;">FixMe</span>
  </div>

  <div style="text-align: center; margin-bottom: 16px;">
    <div style="width: 56px; height: 56px; border-radius: 50%; background: #1A2A3A; border: 2px solid #C8A97E; display: inline-flex; align-items: center; justify-content: center;">
      <span style="font-size: 24px;">&#128197;</span>
    </div>
  </div>

  <h1 style="font-size: 22px; font-weight: 700; margin: 0 0 8px; text-align: center;">
    Your booking has been rescheduled
  </h1>

  <p style="color: #999; font-size: 14px; text-align: center; margin: 0 0 24px;">
    <strong style="color: #fff;">{provider_name}</strong> has moved your appointment to a new time.
  </p>

  <div style="background: #1A1A1A; border: 1px solid #2A2A2A; border-radius: 12px; padding: 20px; margin-bottom: 16px;">
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
      <span style="color: #999; font-size: 13px;">Reference</span>
      <span style="font-weight: 600;">#{booking_number}</span>
    </div>
    <div style="display: flex; justify-content: space-between;">
      <span style="color: #999; font-size: 13px;">Service</span>
      <span style="font-weight: 600;">{service_name}</span>
    </div>
  </div>

  <div style="background: #151515; border: 1px solid #2A2A2A; border-radius: 12px; padding: 16px; margin-bottom: 14px;">
    <div style="color: #999; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Previous time</div>
    <div style="font-size: 15px; color: #999;">{old_slot_date} at {old_slot_time}</div>
  </div>

  <div style="background: #1A2A3A; border: 1px solid #35506A; border-radius: 12px; padding: 18px; margin-bottom: 24px;">
    <div style="color: #C8A97E; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">New time</div>
    <div style="font-size: 18px; font-weight: 700; color: #fff;">{new_slot_date}</div>
    <div style="font-size: 24px; font-weight: 700; color: #C8A97E; margin-top: 4px;">{new_slot_time}</div>
  </div>

  <p style="color: #666; font-size: 11px; text-align: center;">
    You are receiving this because you have a booking with {provider_name} through FixMe.
  </p>
</div>"""

        return EmailService._send(
            to=to,
            subject=f"Booking rescheduled at {provider_name} - #{booking_number}",
            html=html,
        )

    @staticmethod
    def send_provider_new_booking(
        to: str,
        customer_name: str,
        booking_number: int,
        service_name: str,
        slot_date: str,
        slot_time: str,
        customer_notes: str | None = None,
    ) -> bool:
        """Email: notify provider that a new booking has arrived."""
        notes_block = ""
        if customer_notes:
            notes_block = f"""\
    <div style="background: #1A1A1A; border: 1px solid #2A2A2A; border-radius: 12px; padding: 16px; margin-bottom: 16px;">
      <div style="color: #C8A97E; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">Customer note</div>
      <div style="color: #ccc; font-size: 13px; line-height: 1.5;">{customer_notes}</div>
    </div>"""

        html = f"""\
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; background: #0D0D0D; color: #fff; padding: 32px 24px; border-radius: 16px;">
  <div style="text-align: center; margin-bottom: 24px;">
    <span style="color: #C8A97E; font-weight: 700; font-size: 20px;">FixMe</span>
  </div>

  <div style="text-align: center; margin-bottom: 16px;">
    <div style="width: 56px; height: 56px; border-radius: 50%; background: #1A3A1A; border: 2px solid #4CAF50; display: inline-flex; align-items: center; justify-content: center;">
      <span style="font-size: 24px;">&#128197;</span>
    </div>
  </div>

  <h1 style="font-size: 22px; font-weight: 700; margin: 0 0 8px; text-align: center;">
    New booking!
  </h1>

  <p style="color: #999; font-size: 14px; text-align: center; margin: 0 0 24px;">
    <strong style="color: #fff;">{customer_name}</strong> just booked an appointment with you.
  </p>

  <div style="background: #1A1A1A; border: 1px solid #2A2A2A; border-radius: 12px; padding: 20px; margin-bottom: 16px;">
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
      <span style="color: #999; font-size: 13px;">Booking #</span>
      <span style="font-weight: 600;">#{booking_number}</span>
    </div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
      <span style="color: #999; font-size: 13px;">Service</span>
      <span style="font-weight: 600;">{service_name}</span>
    </div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
      <span style="color: #999; font-size: 13px;">Date</span>
      <span style="font-weight: 600;">{slot_date}</span>
    </div>
    <div style="display: flex; justify-content: space-between;">
      <span style="color: #999; font-size: 13px;">Time</span>
      <span style="font-weight: 600; color: #C8A97E;">{slot_time}</span>
    </div>
  </div>

  {notes_block}

  <p style="color: #666; font-size: 11px; text-align: center; margin-top: 24px;">
    Manage your bookings at fixmeapp.ai/provider/home
  </p>
</div>"""

        return EmailService._send(
            to=to,
            subject=f"New booking from {customer_name} — {slot_date} at {slot_time}",
            html=html,
        )

    @staticmethod
    def send_booking_reminder(
        to: str,
        provider_name: str,
        booking_number: int,
        service_name: str,
        slot_date: str,
        slot_time: str,
        hours_until: int,
    ) -> bool:
        """Email: reminder sent 24h or 2h before an appointment."""
        timing_label = "tomorrow" if hours_until >= 20 else "in about 2 hours"
        subject_timing = "tomorrow" if hours_until >= 20 else "in 2 hours"

        html = f"""\
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; background: #0D0D0D; color: #fff; padding: 32px 24px; border-radius: 16px;">
  <div style="text-align: center; margin-bottom: 24px;">
    <span style="color: #C8A97E; font-weight: 700; font-size: 20px;">FixMe</span>
  </div>

  <div style="text-align: center; margin-bottom: 16px;">
    <div style="width: 56px; height: 56px; border-radius: 50%; background: #1A2A3A; border: 2px solid #C8A97E; display: inline-flex; align-items: center; justify-content: center;">
      <span style="font-size: 24px;">&#9200;</span>
    </div>
  </div>

  <h1 style="font-size: 22px; font-weight: 700; margin: 0 0 8px; text-align: center;">
    Your appointment is {timing_label}
  </h1>

  <p style="color: #999; font-size: 14px; text-align: center; margin: 0 0 24px;">
    Don't forget your appointment at <strong style="color: #fff;">{provider_name}</strong>.
  </p>

  <div style="background: #1A1A1A; border: 1px solid #C8A97E; border-radius: 12px; padding: 20px; margin-bottom: 24px;">
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
      <span style="color: #999; font-size: 13px;">Service</span>
      <span style="font-weight: 600;">{service_name}</span>
    </div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
      <span style="color: #999; font-size: 13px;">Date</span>
      <span style="font-weight: 600;">{slot_date}</span>
    </div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
      <span style="color: #999; font-size: 13px;">Time</span>
      <span style="font-weight: 700; color: #C8A97E; font-size: 16px;">{slot_time}</span>
    </div>
    <div style="display: flex; justify-content: space-between;">
      <span style="color: #999; font-size: 13px;">Reference</span>
      <span style="font-weight: 600;">#{booking_number}</span>
    </div>
  </div>

  <p style="color: #666; font-size: 11px; text-align: center;">
    See you {timing_label}! — FixMe &amp; {provider_name}
  </p>
</div>"""

        return EmailService._send(
            to=to,
            subject=f"Reminder: {service_name} at {provider_name} {subject_timing} ({slot_time})",
            html=html,
        )

    @staticmethod
    def send_chat_verification_link(
        to: str,
        provider_name: str,
        verify_url: str,
        expires_minutes: int = 10,
    ) -> bool:
        """Email: verify customer identity before creating bookings in chat."""
        html = f"""\
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; background: #0D0D0D; color: #fff; padding: 32px 24px; border-radius: 16px;">
  <div style="text-align: center; margin-bottom: 24px;">
    <span style="color: #C8A97E; font-weight: 700; font-size: 20px;">FixMe</span>
  </div>

  <h1 style="font-size: 22px; font-weight: 700; margin: 0 0 8px; text-align: center;">
    Verify your booking chat
  </h1>

  <p style="color: #999; font-size: 14px; text-align: center; margin: 0 0 24px;">
    Confirm your email to continue booking with <strong style="color: #fff;">{provider_name}</strong>.
  </p>

  <a href="{verify_url}" style="display: block; background: #C8A97E; color: #0D0D0D; text-align: center; padding: 14px; border-radius: 12px; font-weight: 700; font-size: 16px; text-decoration: none; margin-bottom: 12px;">
    Verify my email
  </a>

  <p style="color: #999; font-size: 12px; text-align: center; margin: 12px 0 0;">
    This secure link expires in {expires_minutes} minutes.
  </p>
</div>"""

        return EmailService._send(
            to=to,
            subject=f"Verify your booking chat with {provider_name}",
            html=html,
        )
