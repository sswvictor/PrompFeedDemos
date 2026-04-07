from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math

from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.customer import Customer
from app.models.customer_reliability_report import CustomerReliabilityReport
from app.models.invoice import Invoice


class CustomerReliabilityService:
    """Objective customer reliability scoring.

    Signal set:
    1) Punctuality
    2) Commitment (no-shows/cancellations)
    3) Payment reliability
    5) Structured anonymous provider reports
    """

    REPORT_CATEGORIES = {
        "no_show",
        "very_late",
        "policy_violation",
        "abusive_behavior",
        "payment_issue",
    }

    BASE_PUNCTUALITY = 80.0
    BASE_COMMITMENT = 82.0
    BASE_PAYMENT = 88.0

    @staticmethod
    def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
        return max(lo, min(hi, value))

    @staticmethod
    def _confidence(volume: int, target: int) -> float:
        if target <= 0:
            return 1.0
        return CustomerReliabilityService._clamp(math.log1p(max(volume, 0)) / math.log1p(target), 0.0, 1.0)

    @staticmethod
    def _default_payload(window_days: int) -> dict:
        return {
            "window_days": window_days,
            "reliability_score": 0.0,
            "reliability_tier": "new",
            "confidence": 0.0,
            "breakdown": {
                "punctuality": 0.0,
                "commitment": 0.0,
                "payment": 0.0,
            },
            "signals": {
                "total_bookings": 0,
                "completed_bookings": 0,
                "cancelled_bookings": 0,
                "late_notifications": 0,
                "avg_late_minutes": 0.0,
                "invoice_count": 0,
                "paid_invoices": 0,
                "anonymous_reports_count": 0,
                "report_counts": {k: 0 for k in sorted(CustomerReliabilityService.REPORT_CATEGORIES)},
            },
            "recommendations": [],
        }

    @staticmethod
    def submit_provider_report(
        db: Session,
        *,
        provider_id: str,
        customer_id: str,
        category: str,
        booking_id: str | None = None,
        severity: int = 1,
        details: str | None = None,
    ) -> CustomerReliabilityReport:
        category_key = (category or "").strip().lower()
        if category_key not in CustomerReliabilityService.REPORT_CATEGORIES:
            allowed = ", ".join(sorted(CustomerReliabilityService.REPORT_CATEGORIES))
            raise ValueError(f"Unsupported report category '{category}'. Allowed: {allowed}")

        customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
        if not customer:
            raise ValueError("Customer not found")
        if customer.provider_id != provider_id:
            raise ValueError("Customer does not belong to this provider")

        booking_obj = None
        if booking_id:
            booking_obj = (
                db.query(Booking)
                .filter(
                    Booking.booking_id == booking_id,
                    Booking.customer_id == customer_id,
                    Booking.provider_id == provider_id,
                )
                .first()
            )
            if not booking_obj:
                raise ValueError("Booking not found for this provider/customer")

        report = (
            db.query(CustomerReliabilityReport)
            .filter(
                CustomerReliabilityReport.provider_id == provider_id,
                CustomerReliabilityReport.customer_id == customer_id,
                CustomerReliabilityReport.booking_id == booking_id,
                CustomerReliabilityReport.category == category_key,
            )
            .first()
        )

        safe_severity = max(1, min(int(severity), 3))

        if report:
            report.severity = safe_severity
            report.details = (details or "").strip() or None
            report.created_at = datetime.now(timezone.utc).replace(tzinfo=None)
            report.admin_status = "open"
            report.admin_action_taken = "none"
            report.admin_notes = None
            report.admin_resolved_at = None
            report.admin_resolved_by = None
        else:
            report = CustomerReliabilityReport(
                provider_id=provider_id,
                customer_id=customer_id,
                booking_id=booking_obj.booking_id if booking_obj else None,
                category=category_key,
                severity=safe_severity,
                details=(details or "").strip() or None,
                admin_status="open",
                admin_action_taken="none",
            )
            db.add(report)

        db.commit()
        db.refresh(report)
        return report

    @staticmethod
    def calculate_for_customer(db: Session, customer_id: str, window_days: int = 180) -> dict:
        customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")

        payload = CustomerReliabilityService.calculate_for_customer_ids(db, [customer_id], window_days=window_days)
        payload["customer_id"] = customer_id
        payload["provider_id"] = customer.provider_id
        return payload

    @staticmethod
    def calculate_for_customer_ids(db: Session, customer_ids: list[str], window_days: int = 180) -> dict:
        ids = [cid for cid in customer_ids if cid]
        if not ids:
            return CustomerReliabilityService._default_payload(window_days)

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        window_start = now - timedelta(days=window_days)

        bookings = (
            db.query(Booking)
            .filter(
                Booking.customer_id.in_(ids),
                Booking.scheduled_start >= window_start,
            )
            .all()
        )

        invoices = (
            db.query(Invoice)
            .filter(
                Invoice.customer_id.in_(ids),
                Invoice.issued_date >= window_start,
            )
            .all()
        )

        reports = (
            db.query(CustomerReliabilityReport)
            .filter(
                CustomerReliabilityReport.customer_id.in_(ids),
                CustomerReliabilityReport.created_at >= window_start,
            )
            .all()
        )

        report_counts = {k: 0 for k in sorted(CustomerReliabilityService.REPORT_CATEGORIES)}
        weighted_reports = 0.0
        for report in reports:
            if report.category in report_counts:
                report_counts[report.category] += 1
                weighted_reports += float(max(1, min(int(report.severity or 1), 3)))

        total_bookings = len(bookings)
        completed_bookings = sum(1 for b in bookings if b.status == "completed")
        cancelled_bookings = sum(1 for b in bookings if b.status == "cancelled")

        late_values = [
            float(b.late_notification_minutes)
            for b in bookings
            if b.late_notification_minutes is not None and b.late_notification_minutes > 0
        ]
        late_notifications = len(late_values)
        avg_late_minutes = (sum(late_values) / late_notifications) if late_notifications > 0 else 0.0

        # 1) Punctuality
        on_time_events = sum(
            1
            for b in bookings
            if b.late_notification_minutes is None or int(b.late_notification_minutes) <= 5
        )
        on_time_rate = (on_time_events / total_bookings) if total_bookings > 0 else 0.9
        punctuality_penalty = min(30.0, avg_late_minutes * 1.4)
        punctuality_penalty += report_counts["very_late"] * 4.0
        punctuality_penalty += report_counts["no_show"] * 2.0
        punctuality_raw = CustomerReliabilityService._clamp((on_time_rate * 100.0) - punctuality_penalty)
        punctuality_conf = CustomerReliabilityService._confidence(total_bookings + len(reports), 30)
        punctuality_score = (punctuality_raw * punctuality_conf) + (
            CustomerReliabilityService.BASE_PUNCTUALITY * (1.0 - punctuality_conf)
        )

        # 2) Commitment
        no_show_reports = report_counts["no_show"]
        policy_reports = report_counts["policy_violation"]
        commitment_base_denom = max(1, completed_bookings + cancelled_bookings + no_show_reports)
        commitment_rate = completed_bookings / commitment_base_denom
        commitment_penalty = (cancelled_bookings * 2.0) + (no_show_reports * 8.0) + (policy_reports * 4.0)
        commitment_raw = CustomerReliabilityService._clamp((commitment_rate * 100.0) - commitment_penalty + 10.0)
        commitment_conf = CustomerReliabilityService._confidence(total_bookings + len(reports), 25)
        commitment_score = (commitment_raw * commitment_conf) + (
            CustomerReliabilityService.BASE_COMMITMENT * (1.0 - commitment_conf)
        )

        # 3) Payment reliability
        invoice_count = len(invoices)
        paid_invoices = sum(1 for inv in invoices if inv.status == "paid")
        payment_issue_reports = report_counts["payment_issue"]
        paid_rate = (paid_invoices / invoice_count) if invoice_count > 0 else 0.95
        payment_penalty = payment_issue_reports * 18.0
        payment_raw = CustomerReliabilityService._clamp((paid_rate * 100.0) - payment_penalty)
        payment_conf = CustomerReliabilityService._confidence(invoice_count + payment_issue_reports, 18)
        payment_score = (payment_raw * payment_conf) + (
            CustomerReliabilityService.BASE_PAYMENT * (1.0 - payment_conf)
        )

        reliability_score = (0.50 * punctuality_score) + (0.30 * commitment_score) + (0.20 * payment_score)
        reliability_score = round(CustomerReliabilityService._clamp(reliability_score), 1)

        if reliability_score >= 85:
            reliability_tier = "excellent"
        elif reliability_score >= 70:
            reliability_tier = "solid"
        elif reliability_score >= 55:
            reliability_tier = "watch"
        else:
            reliability_tier = "risk"

        recommendations: list[str] = []
        if punctuality_score < 72:
            recommendations.append("Improve on-time arrival consistency")
        if commitment_score < 70:
            recommendations.append("Reduce late cancellations and no-shows")
        if payment_score < 75:
            recommendations.append("Resolve payment issues before next booking")

        confidence = round((punctuality_conf + commitment_conf + payment_conf) / 3.0, 3)

        return {
            "window_days": window_days,
            "reliability_score": reliability_score,
            "reliability_tier": reliability_tier,
            "confidence": confidence,
            "breakdown": {
                "punctuality": round(punctuality_score, 1),
                "commitment": round(commitment_score, 1),
                "payment": round(payment_score, 1),
            },
            "signals": {
                "total_bookings": total_bookings,
                "completed_bookings": completed_bookings,
                "cancelled_bookings": cancelled_bookings,
                "late_notifications": late_notifications,
                "avg_late_minutes": round(avg_late_minutes, 2),
                "invoice_count": invoice_count,
                "paid_invoices": paid_invoices,
                "anonymous_reports_count": len(reports),
                "report_weighted_score": round(weighted_reports, 1),
                "report_counts": report_counts,
            },
            "recommendations": recommendations,
        }

