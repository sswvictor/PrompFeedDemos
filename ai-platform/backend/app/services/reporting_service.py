from datetime import datetime, timezone, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.invoice import Invoice


def _period_range(period: str) -> tuple[datetime, datetime]:
    """Return (start, end) datetimes for named periods."""
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "this_week":
        start = today - timedelta(days=today.weekday())  # Monday
        end = now
    elif period == "last_week":
        this_monday = today - timedelta(days=today.weekday())
        start = this_monday - timedelta(weeks=1)
        end = this_monday
    elif period == "this_month":
        start = today.replace(day=1)
        end = now
    elif period == "last_month":
        first_this = today.replace(day=1)
        last_month_end = first_this - timedelta(days=1)
        start = last_month_end.replace(day=1)
        end = first_this
    elif period == "this_quarter":
        q_month = ((today.month - 1) // 3) * 3 + 1
        start = today.replace(month=q_month, day=1)
        end = now
    elif period == "last_quarter":
        q_month = ((today.month - 1) // 3) * 3 + 1
        start_this_q = today.replace(month=q_month, day=1)
        last_q_end = start_this_q - timedelta(days=1)
        lq_month = ((last_q_end.month - 1) // 3) * 3 + 1
        start = last_q_end.replace(month=lq_month, day=1)
        end = start_this_q
    elif period == "this_year":
        start = today.replace(month=1, day=1)
        end = now
    elif period == "last_year":
        start = today.replace(year=today.year - 1, month=1, day=1)
        end = today.replace(month=1, day=1)
    else:
        raise ValueError(f"Unknown period: {period}")

    return start, end


class ReportingService:

    @staticmethod
    def get_booking_summary(
        db: Session,
        provider_id: str,
        period: str = "this_month",
    ) -> dict:
        start, end = _period_range(period)

        bookings = db.query(Booking).filter(
            Booking.provider_id == provider_id,
            Booking.scheduled_start >= start,
            Booking.scheduled_start < end,
        ).all()

        total_count = len(bookings)
        status_counts = {}
        total_revenue_ex = 0.0
        total_revenue_inc = 0.0
        total_vat = 0.0

        for b in bookings:
            status_counts[b.status] = status_counts.get(b.status, 0) + 1
            total_revenue_ex += b.total_amount_ex_vat
            total_revenue_inc += b.total_amount_inc_vat
            total_vat += b.total_vat_amount

        return {
            "provider_id": provider_id,
            "period": period,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "total_bookings": total_count,
            "by_status": status_counts,
            "total_revenue_ex_vat": round(total_revenue_ex, 2),
            "total_vat": round(total_vat, 2),
            "total_revenue_inc_vat": round(total_revenue_inc, 2),
        }

    @staticmethod
    def get_invoice_summary(
        db: Session,
        provider_id: str,
        period: str = "this_month",
    ) -> dict:
        start, end = _period_range(period)

        invoices = db.query(Invoice).filter(
            Invoice.provider_id == provider_id,
            Invoice.issued_date >= start,
            Invoice.issued_date < end,
        ).all()

        status_counts = {}
        total_invoiced = 0.0
        for inv in invoices:
            status_counts[inv.status] = status_counts.get(inv.status, 0) + 1
            total_invoiced += inv.total_inc_vat

        return {
            "provider_id": provider_id,
            "period": period,
            "total_invoices": len(invoices),
            "by_status": status_counts,
            "total_invoiced_inc_vat": round(total_invoiced, 2),
        }
