import { useState, useEffect, useMemo } from 'react';
import { useBooking } from '../../../hooks/useBooking';
import { getAvailableSlots } from '../../../api/bookingApi';
import BackButton from '../../../components/BackButton';

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

function generateCalendarDays(year, month) {
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  const startDow = (firstDay.getDay() + 6) % 7; // Monday = 0
  const days = [];

  for (let i = 0; i < startDow; i++) {
    days.push(null);
  }
  for (let d = 1; d <= lastDay.getDate(); d++) {
    days.push(new Date(year, month, d));
  }
  return days;
}

function formatDate(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function formatTimeSlot(slot) {
  if (typeof slot === 'string' && slot.includes('T')) {
    return slot.split('T')[1].substring(0, 5);
  }
  if (typeof slot === 'object' && slot.start) {
    const s = slot.start;
    return s.includes('T') ? s.split('T')[1].substring(0, 5) : s;
  }
  return String(slot).substring(0, 5);
}

export default function DateTimeStep() {
  const { provider, selectedDate, selectedTime, totalDuration, dispatch, goNext } = useBooking();
  const [viewDate, setViewDate] = useState(() => new Date());
  const [slots, setSlots] = useState([]);
  const [loadingSlots, setLoadingSlots] = useState(false);

  const today = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  const calendarDays = useMemo(
    () => generateCalendarDays(viewDate.getFullYear(), viewDate.getMonth()),
    [viewDate.getFullYear(), viewDate.getMonth()]
  );

  useEffect(() => {
    if (!selectedDate || !provider) return;
    setLoadingSlots(true);
    setSlots([]);
    getAvailableSlots(provider.provider_id, selectedDate, totalDuration || 30, 15)
      .then((data) => setSlots(Array.isArray(data) ? data : []))
      .catch(() => setSlots([]))
      .finally(() => setLoadingSlots(false));
  }, [selectedDate, provider, totalDuration]);

  const handleDateSelect = (date) => {
    if (!date || date < today) return;
    dispatch({ type: 'SET_DATE', payload: formatDate(date) });
  };

  const handleTimeSelect = (slot) => {
    dispatch({ type: 'SET_TIME', payload: slot });
  };

  const goToWaitlist = () => {
    dispatch({ type: 'SET_STEP', payload: 6 });
  };

  const prevMonth = () => setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1));
  const nextMonth = () => setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1));
  const isPrevDisabled = viewDate.getFullYear() === today.getFullYear() && viewDate.getMonth() <= today.getMonth();

  const canContinue = selectedDate && selectedTime;

  return (
    <div className={`animate-fade-in ${canContinue ? 'pb-24' : 'pb-4'}`}>
      <BackButton />

      <h1 className="text-xl font-semibold text-fixme-text-primary mt-1">Pick a date & time</h1>
      <p className="text-sm text-fixme-text-secondary mt-1">Choose when you'd like to visit</p>

      {/* Calendar */}
      <div className="mt-4 bg-fixme-card border border-fixme-border rounded-xl p-4">
        <div className="flex items-center justify-between mb-4">
          <button
            onClick={prevMonth}
            disabled={isPrevDisabled}
            className={`p-1 rounded-lg transition-colors ${isPrevDisabled ? 'text-fixme-text-muted cursor-not-allowed' : 'text-fixme-text-secondary hover:text-fixme-text-primary'}`}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="text-fixme-text-primary font-semibold">
            {MONTHS[viewDate.getMonth()]} {viewDate.getFullYear()}
          </span>
          <button onClick={nextMonth} className="p-1 rounded-lg text-fixme-text-secondary hover:text-fixme-text-primary transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>

        <div className="grid grid-cols-7 gap-1 mb-2">
          {WEEKDAYS.map((day) => (
            <div key={day} className="text-center text-xs text-fixme-text-muted font-medium py-1">
              {day}
            </div>
          ))}
        </div>

        <div className="grid grid-cols-7 gap-1">
          {calendarDays.map((date, i) => {
            if (!date) return <div key={`empty-${i}`} />;
            const dateStr = formatDate(date);
            const isToday = dateStr === formatDate(today);
            const isPast = date < today;
            const isSelectedDate = selectedDate === dateStr;

            return (
              <button
                key={dateStr}
                onClick={() => handleDateSelect(date)}
                disabled={isPast}
                className={`
                  aspect-square rounded-lg flex items-center justify-center text-sm font-medium
                  transition-all duration-150
                  ${isPast ? 'text-fixme-text-muted/40 cursor-not-allowed' : ''}
                  ${isSelectedDate ? 'bg-fixme-accent text-fixme-bg' : ''}
                  ${isToday && !isSelectedDate ? 'text-fixme-accent border border-fixme-accent/50' : ''}
                  ${!isPast && !isSelectedDate && !isToday ? 'text-fixme-text-primary hover:bg-fixme-border/50' : ''}
                `}
              >
                {date.getDate()}
              </button>
            );
          })}
        </div>
      </div>

      {/* Time slots */}
      {selectedDate && (
        <div className="mt-4 animate-fade-in">
          <h3 className="text-sm font-medium text-fixme-text-secondary mb-3">Available times (every 15 min)</h3>

          {loadingSlots ? (
            <div className="flex justify-center py-8">
              <div className="w-6 h-6 border-2 border-fixme-accent border-t-transparent rounded-full animate-spin" />
            </div>
          ) : slots.length === 0 ? (
            <div className="bg-fixme-card border border-fixme-border rounded-xl p-5 text-center">
              <p className="text-fixme-text-secondary text-sm">No available slots on this day.</p>
              <button
                onClick={goToWaitlist}
                className="mt-3 w-full py-3 rounded-xl text-sm font-semibold bg-fixme-accent text-fixme-bg hover:opacity-90 active:scale-[0.98] transition-all"
              >
                Join the waitlist â†’
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-2">
              {slots.map((slot, idx) => {
                const timeStr = formatTimeSlot(slot);
                const isSelectedSlot = selectedTime && formatTimeSlot(selectedTime) === timeStr;
                return (
                  <button
                    key={idx}
                    onClick={() => handleTimeSelect(slot)}
                    className={`
                      py-2.5 px-3 rounded-xl text-sm font-medium transition-all duration-200
                      ${isSelectedSlot
                        ? 'bg-fixme-accent text-fixme-bg'
                        : 'bg-fixme-card border border-fixme-border text-fixme-text-primary hover:border-fixme-accent/50'
                      }
                    `}
                  >
                    {timeStr}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Join waitlist â€” always visible */}
      <div className="mt-6 text-center">
        <button
          onClick={goToWaitlist}
          className="text-sm text-fixme-text-muted hover:text-fixme-accent transition-colors underline underline-offset-2"
        >
          Can't find a time? Join the waitlist
        </button>
      </div>

      {/* Fixed Continue button */}
      {canContinue && (
        <div className="fixed bottom-0 inset-x-0 z-20 flex justify-center">
          <div className="w-full max-w-md px-4 pb-6 pt-3 bg-fixme-bg/95 backdrop-blur-sm border-t border-fixme-border/30">
            <button
              onClick={goNext}
              className="w-full py-3.5 rounded-xl font-semibold text-base bg-fixme-accent text-fixme-bg hover:opacity-90 active:scale-[0.98] transition-all duration-200"
            >
              Continue
            </button>
          </div>
        </div>
      )}
    </div>
  );
}



