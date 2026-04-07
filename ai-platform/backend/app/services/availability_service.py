from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.availability import Availability, AvailabilityOverride
from app.models.booking import Booking
from app.models.provider_time_block import ProviderTimeBlock
from app.models.timeslot_hold import TimeSlotHold


class AvailabilityService:

    @staticmethod
    def _as_naive_utc(dt: datetime) -> datetime:
        if dt.tzinfo:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    # -- Working hours management --------------------------------------------

    @staticmethod
    def set_working_hours(
        db: Session,
        provider_id: str,
        day_of_week: int,
        start_minutes: int,
        end_minutes: int,
    ) -> Availability:
        """Set or update working hours for a specific day.
        day_of_week: 0=Monday, 6=Sunday
        start/end_minutes: minutes from midnight (e.g. 540=09:00, 1020=17:00)
        """
        if not (0 <= day_of_week <= 6):
            raise ValueError("day_of_week must be 0 (Mon) - 6 (Sun)")
        if start_minutes >= end_minutes:
            raise ValueError("start_minutes must be before end_minutes")

        existing = db.query(Availability).filter(
            Availability.provider_id == provider_id,
            Availability.day_of_week == day_of_week,
        ).first()

        if existing:
            existing.start_minutes = start_minutes
            existing.end_minutes = end_minutes
            db.commit()
            db.refresh(existing)
            return existing

        slot = Availability(
            provider_id=provider_id,
            day_of_week=day_of_week,
            start_minutes=start_minutes,
            end_minutes=end_minutes,
        )
        db.add(slot)
        db.commit()
        db.refresh(slot)
        return slot

    @staticmethod
    def get_working_hours(db: Session, provider_id: str) -> list[Availability]:
        return db.query(Availability).filter(
            Availability.provider_id == provider_id
        ).order_by(Availability.day_of_week).all()

    # -- Overrides (days off, special hours) --------------------------------

    @staticmethod
    def add_override(
        db: Session,
        provider_id: str,
        date: datetime,
        is_closed: bool = False,
        start_minutes: int | None = None,
        end_minutes: int | None = None,
        reason: str | None = None,
    ) -> AvailabilityOverride:
        override = AvailabilityOverride(
            provider_id=provider_id,
            date=date,
            is_closed=is_closed,
            start_minutes=start_minutes,
            end_minutes=end_minutes,
            reason=reason,
        )
        db.add(override)
        db.commit()
        db.refresh(override)
        return override

    # -- Intraday blocks (lunch/private) ------------------------------------

    @staticmethod
    def create_time_block(
        db: Session,
        provider_id: str,
        start_at: datetime,
        end_at: datetime,
        kind: str = "private",
        reason: str | None = None,
    ) -> ProviderTimeBlock:
        start_naive = AvailabilityService._as_naive_utc(start_at)
        end_naive = AvailabilityService._as_naive_utc(end_at)
        if start_naive >= end_naive:
            raise ValueError("start_at must be before end_at")

        block = ProviderTimeBlock(
            provider_id=provider_id,
            start_at=start_naive,
            end_at=end_naive,
            kind=(kind or "private").strip().lower(),
            reason=(reason or "").strip() or None,
        )
        db.add(block)
        db.commit()
        db.refresh(block)
        return block

    @staticmethod
    def list_time_blocks(
        db: Session,
        provider_id: str,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
    ) -> list[ProviderTimeBlock]:
        q = db.query(ProviderTimeBlock).filter(ProviderTimeBlock.provider_id == provider_id)
        if from_at is not None:
            q = q.filter(ProviderTimeBlock.end_at > AvailabilityService._as_naive_utc(from_at))
        if to_at is not None:
            q = q.filter(ProviderTimeBlock.start_at < AvailabilityService._as_naive_utc(to_at))
        return q.order_by(ProviderTimeBlock.start_at.asc()).all()

    @staticmethod
    def delete_time_block(db: Session, provider_id: str, block_id: str) -> bool:
        block = (
            db.query(ProviderTimeBlock)
            .filter(
                ProviderTimeBlock.provider_id == provider_id,
                ProviderTimeBlock.block_id == block_id,
            )
            .first()
        )
        if not block:
            return False
        db.delete(block)
        db.commit()
        return True

    # -- Slot generation ------------------------------------------------------

    @staticmethod
    def get_available_slots(
        db: Session,
        provider_id: str,
        date: datetime,
        duration_minutes: int,
        slot_interval: int = 15,
    ) -> list[dict]:
        """Generate available time slots for a specific date."""
        day_of_week = date.weekday()

        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)

        override = db.query(AvailabilityOverride).filter(
            AvailabilityOverride.provider_id == provider_id,
            AvailabilityOverride.date >= date_start,
            AvailabilityOverride.date < date_end,
        ).first()

        if override and override.is_closed:
            return []

        if override and override.start_minutes is not None:
            work_start = override.start_minutes
            work_end = override.end_minutes
        else:
            avail = db.query(Availability).filter(
                Availability.provider_id == provider_id,
                Availability.day_of_week == day_of_week,
            ).first()
            if not avail:
                return []
            work_start = avail.start_minutes
            work_end = avail.end_minutes

        existing_bookings = db.query(Booking).filter(
            Booking.provider_id == provider_id,
            Booking.scheduled_start >= date_start,
            Booking.scheduled_start < date_end,
            Booking.status.in_(["pending", "confirmed"]),
        ).all()

        booked_ranges = [(b.scheduled_start, b.scheduled_end) for b in existing_bookings]

        now = datetime.now(timezone.utc)
        active_holds = db.query(TimeSlotHold).filter(
            TimeSlotHold.provider_id == provider_id,
            TimeSlotHold.start >= date_start,
            TimeSlotHold.start < date_end,
            TimeSlotHold.expires_at > now,
        ).all()
        for hold in active_holds:
            booked_ranges.append((hold.start, hold.end))

        time_blocks = db.query(ProviderTimeBlock).filter(
            ProviderTimeBlock.provider_id == provider_id,
            ProviderTimeBlock.start_at < date_end,
            ProviderTimeBlock.end_at > date_start,
        ).all()
        for block in time_blocks:
            booked_ranges.append((block.start_at, block.end_at))

        slots = []
        current = work_start
        while current + duration_minutes <= work_end:
            slot_start_dt = date_start + timedelta(minutes=current)
            slot_end_dt = slot_start_dt + timedelta(minutes=duration_minutes)

            conflict = False
            for b_start, b_end in booked_ranges:
                b_start_naive = b_start.replace(tzinfo=None) if b_start.tzinfo else b_start
                b_end_naive = b_end.replace(tzinfo=None) if b_end.tzinfo else b_end
                s_start = slot_start_dt.replace(tzinfo=None) if slot_start_dt.tzinfo else slot_start_dt
                s_end = slot_end_dt.replace(tzinfo=None) if slot_end_dt.tzinfo else slot_end_dt

                if s_start < b_end_naive and s_end > b_start_naive:
                    conflict = True
                    break

            if not conflict:
                slots.append({
                    "start": slot_start_dt.isoformat(),
                    "end": slot_end_dt.isoformat(),
                })

            current += slot_interval

        return slots

    @staticmethod
    def check_slot_available(
        db: Session,
        provider_id: str,
        start: datetime,
        end: datetime,
    ) -> bool:
        """Check if a specific time slot is available."""
        booking_conflicts = db.query(Booking).filter(
            Booking.provider_id == provider_id,
            Booking.status.in_(["pending", "confirmed"]),
            Booking.scheduled_start < end,
            Booking.scheduled_end > start,
        ).count()

        now = datetime.now(timezone.utc)
        hold_conflicts = db.query(TimeSlotHold).filter(
            TimeSlotHold.provider_id == provider_id,
            TimeSlotHold.start < end,
            TimeSlotHold.end > start,
            TimeSlotHold.expires_at > now,
        ).count()

        block_conflicts = db.query(ProviderTimeBlock).filter(
            ProviderTimeBlock.provider_id == provider_id,
            ProviderTimeBlock.start_at < end,
            ProviderTimeBlock.end_at > start,
        ).count()

        return (booking_conflicts + hold_conflicts + block_conflicts) == 0

    # -- Slot holds -----------------------------------------------------------

    @staticmethod
    def hold_slot(
        db: Session,
        provider_id: str,
        start: datetime,
        end: datetime,
        conversation_id: str | None = None,
        hold_minutes: int = 10,
    ) -> TimeSlotHold:
        """Temporarily reserve a slot while the bot confirms with the user."""
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=hold_minutes)
        hold = TimeSlotHold(
            provider_id=provider_id,
            conversation_id=conversation_id,
            start=start,
            end=end,
            expires_at=expires_at,
        )
        db.add(hold)
        db.commit()
        db.refresh(hold)
        return hold

    @staticmethod
    def release_expired_holds(db: Session) -> int:
        """Cleanup: delete all expired holds. Run via cron or startup."""
        now = datetime.now(timezone.utc)
        count = db.query(TimeSlotHold).filter(
            TimeSlotHold.expires_at <= now,
        ).delete()
        db.commit()
        return count
