"""Process monthly referral payouts.

Usage examples:
  python backend/scripts/process_referral_payouts.py
  python backend/scripts/process_referral_payouts.py --year 2026 --month 2 --dry-run
  python backend/scripts/process_referral_payouts.py --mark-paid
  python backend/scripts/process_referral_payouts.py --apply-subscription-credit
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.db.session import SessionLocal, assert_schema_up_to_date
from app.services.referral_service import ReferralService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create monthly referral payout rows")
    parser.add_argument("--year", type=int, default=None, help="Target payout year (default: previous month)")
    parser.add_argument("--month", type=int, default=None, help="Target payout month 1-12 (default: previous month)")
    parser.add_argument("--dry-run", action="store_true", help="Calculate without writing to database")
    parser.add_argument(
        "--mark-paid",
        action="store_true",
        help="Immediately mark created payouts as paid (use only if transfer flow is external/automated)",
    )
    parser.add_argument(
        "--apply-subscription-credit",
        action="store_true",
        help="Apply pending payout rows to Stripe customer balance for this month",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if (args.year is None) ^ (args.month is None):
        print("ERROR: --year and --month must be provided together.")
        return 1

    if args.month is not None and not (1 <= args.month <= 12):
        print("ERROR: --month must be between 1 and 12.")
        return 1

    if args.year is None:
        year, month = ReferralService.previous_month()
    else:
        year, month = args.year, args.month

    auto_mark_paid = bool(args.mark_paid or settings.REFERRAL_AUTO_MARK_PAID)

    assert_schema_up_to_date()
    db = SessionLocal()
    try:
        payouts = ReferralService.process_monthly_payouts(
            db=db,
            year=year,
            month=month,
            auto_mark_paid=auto_mark_paid,
            dry_run=args.dry_run,
        )

        total_amount = round(sum(float(p.amount_sek or 0.0) for p in payouts), 2)
        print(f"Referral payout run complete for {year}-{month:02d}")
        print(f"Created rows: {len(payouts)}")
        print(f"Total amount: {total_amount} SEK")
        print(f"Mode: {'DRY-RUN' if args.dry_run else 'WRITE'}")
        print(f"Status assigned: {'paid' if auto_mark_paid else 'pending'}")

        for payout in payouts:
            print(
                f"- provider={payout.provider_id} "
                f"credits={payout.credits_count} "
                f"amount={payout.amount_sek} "
                f"status={payout.status}"
            )

        should_apply = bool(args.apply_subscription_credit or settings.REFERRAL_AUTO_APPLY_TO_SUBSCRIPTION)
        if not args.dry_run and should_apply:
            applied = ReferralService.apply_pending_subscription_credits(db, year, month)
            print(f"Stripe subscription credits applied: {len(applied)}")

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
