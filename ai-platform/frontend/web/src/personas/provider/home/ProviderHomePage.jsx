import { Fragment, useState, useEffect } from 'react';
import ProviderTabBar from '../navigation/ProviderTabBar';
import SetupWizard from './SetupWizard';
import ProviderInboxPanel from './ProviderInboxPanel';
import { getHomeDashboard, updateBookingStatus, rescheduleBooking, sendProviderLateAlert, getProviderTimeBlocks, createProviderTimeBlock, deleteProviderTimeBlock, getInboxConversations, submitCustomerReliabilityReport } from '../../../api/bookingApi';

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}

function fmtTime(iso) {
  return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

function fmtDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
}

// Currency-aware formatter — uses provider's currency from API response
import { formatPrice } from '../../../utils/currency';
function fmtSek(value, currency = 'SEK') {
  return formatPrice(Number(value || 0), currency);
}

function fmtDateShort(iso) {
  if (!iso) return 'Never';
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}
function dayKeyFromIso(iso) {
  const d = new Date(iso);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function dayKeyFromDate(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function dateFromDayKey(dayKey) {
  const [y, m, d] = dayKey.split('-').map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
}

function shiftDayKey(dayKey, deltaDays) {
  const d = dateFromDayKey(dayKey);
  d.setDate(d.getDate() + deltaDays);
  return dayKeyFromDate(d);
}

function startOfWeek(date) {
  const d = new Date(date);
  const weekdayMon = (d.getDay() + 6) % 7;
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - weekdayMon);
  return d;
}

function buildWeekDays(weekStartDate) {
  return Array.from({ length: 7 }, (_, idx) => {
    const date = new Date(weekStartDate);
    date.setDate(date.getDate() + idx);
    return {
      date,
      dayNumber: date.getDate(),
      key: dayKeyFromDate(date),
      weekdayShort: date.toLocaleDateString('en-GB', { weekday: 'short' }),
    };
  });
}

function formatWeekRange(weekStartDate) {
  const from = new Date(weekStartDate);
  const to = new Date(weekStartDate);
  to.setDate(to.getDate() + 6);
  const fromLabel = from.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  const toLabel = to.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  return `${fromLabel} - ${toLabel}`;
}
function localDateTimeIso(dayKey, hhmm) {
  return `${dayKey}T${hhmm}:00`;
}

function dayRangeIso(dayKey) {
  return {
    fromAt: `${dayKey}T00:00:00`,
    toAt: `${dayKey}T23:59:59`,
  };
}

function buildCalendarDays(monthDate) {
  const year = monthDate.getFullYear();
  const month = monthDate.getMonth();
  const first = new Date(year, month, 1);
  const firstWeekdayMon = (first.getDay() + 6) % 7;
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrevMonth = new Date(year, month, 0).getDate();

  const cells = [];
  for (let i = 0; i < 42; i += 1) {
    const dayOffset = i - firstWeekdayMon + 1;
    let date;
    let inMonth = true;
    if (dayOffset <= 0) {
      date = new Date(year, month - 1, daysInPrevMonth + dayOffset);
      inMonth = false;
    } else if (dayOffset > daysInMonth) {
      date = new Date(year, month + 1, dayOffset - daysInMonth);
      inMonth = false;
    } else {
      date = new Date(year, month, dayOffset);
    }
    cells.push({
      date,
      dayNumber: date.getDate(),
      key: dayKeyFromDate(date),
      inMonth,
    });
  }
  return cells;
}

function Avatar({ url, name, size = 'md' }) {
  const sizes = { sm: 'w-8 h-8 text-xs', md: 'w-10 h-10 text-sm', lg: 'w-12 h-12 text-base' };
  if (url) {
    return <img src={url} alt={name} className={`${sizes[size]} rounded-full object-cover`} />;
  }
  const initials = (name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
  return (
    <div className={`${sizes[size]} rounded-full bg-fixme-border flex items-center justify-center text-fixme-text-secondary font-medium`}>
      {initials}
    </div>
  );
}

function SectionHeader({ title, count }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <h2 className="text-fixme-text-primary text-base font-semibold">{title}</h2>
      {count > 0 && (
        <span className="bg-fixme-text-primary text-fixme-bg text-xs font-bold px-2 py-0.5 rounded-full">{count}</span>
      )}
    </div>
  );
}

function TeamCard({ member }) {
  return (
    <div className="flex-shrink-0 w-20 flex flex-col items-center gap-1">
      <div className="relative">
        <Avatar url={member.image_url} name={member.display_name} size="lg" />
        {member.is_working_today && (
          <div className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 bg-fixme-success rounded-full border-2 border-fixme-bg" />
        )}
      </div>
      <span className="text-fixme-text-primary text-xs font-medium text-center leading-tight truncate w-full">{member.display_name}</span>
      <span className="text-fixme-text-muted text-[10px] text-center leading-tight truncate w-full">{member.role || member.member_type}</span>
    </div>
  );
}

function ordinal(n) {
  const s = ['th', 'st', 'nd', 'rd'];
  const v = n % 100;
  return s[(v - 20) % 10] || s[v] || s[0];
}

const CUSTOMER_REPORT_OPTIONS = [
  { value: 'no_show', label: 'No-show' },
  { value: 'very_late', label: 'Very late' },
  { value: 'policy_violation', label: 'Policy violation' },
  { value: 'abusive_behavior', label: 'Disturbing behavior' },
  { value: 'payment_issue', label: 'Payment issue' },
];

function BookingCard({ booking, isOpen, onToggle, onComplete, onLateAlert, onReschedule, onCancel, onReportCustomer, actionLoading }) {
  const visitLabel = booking.visit_count > 1 ? `${booking.visit_count}${ordinal(booking.visit_count)} visit` : 'New client';
  const hasLateAlert = !!booking.late_alert_minutes;
  const durationMs = new Date(booking.scheduled_end) - new Date(booking.scheduled_start);
  const durationMins = Math.round(durationMs / 60000);

  // Which sub-panel is open: null | 'late' | 'reschedule' | 'confirmCancel' | 'report'
  const [subPanel, setSubPanel] = useState(null);
  const [rescheduleDate, setRescheduleDate] = useState(() => new Date(booking.scheduled_start).toISOString().slice(0, 10));
  const [rescheduleTime, setRescheduleTime] = useState(() => {
    const d = new Date(booking.scheduled_start);
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  });
  const [reportCategory, setReportCategory] = useState('no_show');
  const [reportDetails, setReportDetails] = useState('');
  const [reportSent, setReportSent] = useState(false);

  // Reset sub-panels when card is collapsed
  useEffect(() => { if (!isOpen) setSubPanel(null); }, [isOpen]);

  function togglePanel(panel) {
    // If clicking same panel icon, close; otherwise open new one (also close ... menu)
    if (subPanel === panel) { setSubPanel(null); return; }
    setSubPanel(panel);
    if (panel === 'late' && isOpen) onToggle(); // close ... if late opens
  }

  function handleRescheduleConfirm() {
    const newStart = new Date(`${rescheduleDate}T${rescheduleTime}:00`);
    const newEnd = new Date(newStart.getTime() + durationMs);
    onReschedule(booking.booking_id, newStart.toISOString(), newEnd.toISOString());
    setSubPanel(null);
  }

  function handleReportSubmit() {
    if (!booking.customer_id) return;
    onReportCustomer(booking.customer_id, {
      category: reportCategory,
      booking_id: booking.booking_id,
      severity: reportCategory === 'abusive_behavior' ? 3 : reportCategory === 'no_show' ? 2 : 1,
      details: reportDetails || null,
    });
    setReportDetails('');
    setReportSent(true);
    setSubPanel(null);
    setTimeout(() => setReportSent(false), 3000);
  }

  return (
    <div className={`bg-fixme-card border rounded-2xl p-4 space-y-3 ${hasLateAlert ? 'border-orange-400/60' : 'border-fixme-border'}`}>
      {/* Running-late sent banner */}
      {hasLateAlert && (
        <div className="flex items-center gap-2 bg-orange-500/10 border border-orange-500/20 rounded-xl px-3 py-2 -mt-1">
          <svg className="w-3.5 h-3.5 text-orange-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-orange-300 text-xs font-semibold">Running {booking.late_alert_minutes} min late</span>
        </div>
      )}

      {/* Card header row */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <Avatar url={booking.customer_image_url} name={booking.customer_name} />
          <div>
            <p className="text-fixme-text-primary text-sm font-semibold">{booking.customer_name}</p>
            <p className="text-fixme-text-secondary text-xs">{booking.service_name}</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <span className="text-fixme-text-secondary text-xs font-medium bg-fixme-border/60 px-2 py-0.5 rounded-full">{visitLabel}</span>

          {/* Clock icon - running late */}
          <button
            onClick={() => { setSubPanel(s => s === 'late' ? null : 'late'); if (isOpen) onToggle(); }}
            title="Running late"
            className={`w-8 h-8 rounded-full border flex items-center justify-center transition-all ${
              subPanel === 'late'
                ? 'border-orange-400 text-orange-400 bg-orange-400/10'
                : hasLateAlert
                  ? 'border-orange-400/50 text-orange-400'
                  : 'border-fixme-border text-fixme-text-muted hover:border-fixme-text-secondary hover:text-fixme-text-secondary'
            }`}
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </button>

          {/* Three-dots - actions */}
          <button
            onClick={() => { onToggle(); setSubPanel(null); }}
            className={`p-1.5 rounded-lg transition-colors ${isOpen ? 'bg-fixme-border text-fixme-text-primary' : 'text-fixme-text-muted hover:text-fixme-text-secondary'}`}
          >
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
              <path d="M6 10a2 2 0 11-4 0 2 2 0 014 0zm6 0a2 2 0 11-4 0 2 2 0 014 0zm6 0a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
          </button>
        </div>
      </div>

      {/* Time row */}
      <div className="flex items-center gap-2 text-fixme-text-secondary text-xs">
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>{fmtTime(booking.scheduled_start)} &ndash; {fmtTime(booking.scheduled_end)}</span>
        {booking.is_home_visit && (
          <span className="ml-1 bg-fixme-border text-fixme-text-secondary text-[10px] px-1.5 py-0.5 rounded">Home visit</span>
        )}
      </div>

      {booking.session_preferences?.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {booking.session_preferences.map((pref, i) => (
            <span key={i} className="bg-fixme-bg border border-fixme-border text-fixme-text-secondary text-[10px] px-2 py-0.5 rounded-full">
              {pref.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      )}
      {reportSent && (
        <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/25 rounded-xl px-3 py-2">
          <svg className="w-3.5 h-3.5 text-red-300 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <span className="text-red-200 text-xs font-semibold">Customer report sent to admin</span>
        </div>
      )}

      {booking.customer_notes && (
        <p className="text-fixme-text-muted text-xs italic">&quot;{booking.customer_notes}&quot;</p>
      )}

      {/* Running-late panel (clock icon) */}
      {subPanel === 'late' && (
        <div className="border-t border-fixme-border/50 pt-3 space-y-3">
          <p className="text-fixme-text-secondary text-xs font-medium">How many minutes late?</p>
          <div className="flex gap-2">
            {[5, 10, 15, 20].map(min => (
              <button
                key={min}
                onClick={() => onLateAlert(booking.booking_id, min)}
                disabled={actionLoading}
                className={`flex-1 py-1.5 text-xs font-semibold rounded-xl border transition-all active:scale-[0.97] disabled:opacity-60 ${
                  booking.late_alert_minutes === min
                    ? 'bg-orange-400 border-orange-400 text-fixme-bg'
                    : 'border-fixme-border text-fixme-text-secondary hover:border-orange-400/60 hover:text-orange-300'
                }`}
              >
                {min} min
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Actions panel (... button) */}
      {isOpen && (
        <div className="border-t border-fixme-border/50 pt-3 space-y-3">
          {subPanel !== 'reschedule' && subPanel !== 'confirmCancel' && subPanel !== 'report' && (
            <>
              {/* Reschedule + Cancel */}
              <div className="flex gap-2">
                <button
                  onClick={() => setSubPanel('reschedule')}
                  disabled={actionLoading}
                  className="flex-1 py-2 text-xs font-semibold text-fixme-text-secondary border border-fixme-border rounded-xl active:scale-[0.98] transition-all disabled:opacity-60"
                >
                  Reschedule
                </button>
                <button
                  onClick={() => setSubPanel('confirmCancel')}
                  disabled={actionLoading}
                  className="flex-1 py-2 text-xs font-semibold text-fixme-error border border-fixme-error/30 rounded-xl active:scale-[0.98] transition-all disabled:opacity-60"
                >
                  Cancel booking
                </button>
              </div>
              <button
                onClick={() => setSubPanel('report')}
                disabled={actionLoading || !booking.customer_id}
                className="w-full py-2 text-xs font-semibold text-red-300 border border-red-400/35 rounded-xl active:scale-[0.98] transition-all disabled:opacity-50"
              >
                Report customer
              </button>

              {/* Mark as completed */}
              <button
                onClick={() => onComplete(booking.booking_id)}
                disabled={actionLoading}
                className="w-full py-2 text-xs font-semibold text-fixme-bg bg-fixme-text-primary rounded-xl active:scale-[0.98] transition-all disabled:opacity-60"
              >
                Mark as completed
              </button>
            </>
          )}

          {/* Reschedule sub-panel */}
          {subPanel === 'reschedule' && (
            <div className="space-y-2">
              <p className="text-fixme-text-muted text-xs">New date &amp; time <span className="text-fixme-text-muted/60">({durationMins} min)</span></p>
              <div className="flex gap-2">
                <input
                  type="date"
                  value={rescheduleDate}
                  onChange={e => setRescheduleDate(e.target.value)}
                  className="flex-1 bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2 text-xs text-fixme-text-primary"
                />
                <input
                  type="time"
                  value={rescheduleTime}
                  onChange={e => setRescheduleTime(e.target.value)}
                  className="w-24 bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2 text-xs text-fixme-text-primary"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setSubPanel(null)}
                  className="flex-1 py-2 text-xs font-medium text-fixme-text-secondary border border-fixme-border rounded-xl active:scale-[0.98] transition-all"
                >
                  Back
                </button>
                <button
                  onClick={handleRescheduleConfirm}
                  disabled={actionLoading}
                  className="flex-1 py-2 text-xs font-semibold text-fixme-bg bg-fixme-text-primary rounded-xl active:scale-[0.98] transition-all disabled:opacity-60"
                >
                  {actionLoading ? 'Saving...' : 'Confirm'}
                </button>
              </div>
            </div>
          )}

          {subPanel === 'report' && (
            <div className="space-y-2">
              <p className="text-fixme-text-primary text-xs font-semibold">Report customer issue</p>
              <select
                value={reportCategory}
                onChange={(e) => setReportCategory(e.target.value)}
                className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2 text-xs text-fixme-text-primary"
              >
                {CUSTOMER_REPORT_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <textarea
                value={reportDetails}
                onChange={(e) => setReportDetails(e.target.value)}
                placeholder="Optional details"
                rows={3}
                className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2 text-xs text-fixme-text-primary resize-none"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => setSubPanel(null)}
                  className="flex-1 py-2 text-xs font-medium text-fixme-text-secondary border border-fixme-border rounded-xl active:scale-[0.98] transition-all"
                >
                  Back
                </button>
                <button
                  onClick={handleReportSubmit}
                  disabled={actionLoading || !booking.customer_id}
                  className="flex-1 py-2 text-xs font-semibold text-white bg-red-500 rounded-xl active:scale-[0.98] transition-all disabled:opacity-60"
                >
                  Send report
                </button>
              </div>
            </div>
          )}

          {/* Cancel confirm sub-panel */}
          {subPanel === 'confirmCancel' && (
            <div className="space-y-2">
              <p className="text-fixme-text-primary text-xs font-semibold">Cancel this booking?</p>
              <p className="text-fixme-text-muted text-xs">The client will be notified automatically.</p>
              <div className="flex gap-2">
                <button
                  onClick={() => setSubPanel(null)}
                  className="flex-1 py-2 text-xs font-medium text-fixme-text-secondary border border-fixme-border rounded-xl active:scale-[0.98] transition-all"
                >
                  Keep it
                </button>
                <button
                  onClick={() => { onCancel(booking.booking_id); setSubPanel(null); }}
                  disabled={actionLoading}
                  className="flex-1 py-2 text-xs font-semibold text-white bg-fixme-error/80 rounded-xl active:scale-[0.98] transition-all disabled:opacity-60"
                >
                  {actionLoading ? 'Cancelling...' : 'Yes, cancel'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function UpdateCard({ update, onAccept, onDecline, loading }) {
  return (
    <div className="bg-fixme-card border border-fixme-border rounded-2xl p-4 space-y-3">
      <div className="flex items-center gap-3">
        <Avatar url={update.customer_image_url} name={update.customer_name} />
        <div className="flex-1 min-w-0">
          <p className="text-fixme-text-primary text-sm font-semibold truncate">{update.customer_name}</p>
          <p className="text-fixme-text-secondary text-xs">{update.service_name}</p>
        </div>
      </div>
      <div className="bg-fixme-bg rounded-xl p-3 space-y-1">
        <div className="flex items-center gap-2 text-xs">
          <span className="text-fixme-text-muted line-through">{fmtTime(update.original_start)} &ndash; {fmtTime(update.original_end)}</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-fixme-text-primary font-medium">{fmtTime(update.requested_start)} &ndash; {fmtTime(update.requested_end)}</span>
          <span className="text-fixme-text-muted">({fmtDate(update.requested_start)})</span>
        </div>
      </div>
      <div className="flex gap-2">
        <button
          onClick={() => onDecline(update.booking_id)}
          disabled={loading}
          className="flex-1 py-2 text-xs font-semibold text-fixme-text-secondary border border-fixme-border rounded-xl active:scale-[0.98] transition-all"
        >
          Decline
        </button>
        <button
          onClick={() => onAccept(update.booking_id)}
          disabled={loading}
          className="flex-1 py-2 text-xs font-semibold text-fixme-bg bg-fixme-text-primary rounded-xl active:scale-[0.98] transition-all"
        >
          Accept
        </button>
      </div>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="min-h-screen bg-fixme-bg pb-20 px-4 pt-8 max-w-md mx-auto animate-pulse space-y-6">
      <div className="h-8 bg-fixme-card rounded w-3/4" />
      <div className="flex gap-4 overflow-hidden">
        {[1, 2, 3].map(i => <div key={i} className="w-20 h-24 bg-fixme-card rounded-2xl flex-shrink-0" />)}
      </div>
      {[1, 2].map(i => <div key={i} className="h-32 bg-fixme-card rounded-2xl" />)}
    </div>
  );
}

export default function ProviderHomePage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [openActionId, setOpenActionId] = useState(null);
  const [setupPending, setSetupPending] = useState(false);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [calendarView, setCalendarView] = useState('week');
  const [calendarMonth, setCalendarMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [weekStartDate, setWeekStartDate] = useState(() => startOfWeek(new Date()));
  const [selectedDayKey, setSelectedDayKey] = useState(() => dayKeyFromDate(new Date()));
  const [timeBlocks, setTimeBlocks] = useState([]);
  const [blocksLoading, setBlocksLoading] = useState(false);
  const [blockSaving, setBlockSaving] = useState(false);
  const [blockKind, setBlockKind] = useState('lunch');
  const [blockStartTime, setBlockStartTime] = useState('12:00');
  const [blockEndTime, setBlockEndTime] = useState('12:30');
  const [blockReason, setBlockReason] = useState('');
  const [activeView, setActiveView] = useState(() => (new URLSearchParams(window.location.search).get('view') === 'inbox' ? 'inbox' : 'bookings'));
  const [inboxCount, setInboxCount] = useState(0);
  const [inboxPreview, setInboxPreview] = useState(null);
  const token = localStorage.getItem('fixme_provider_token');

  async function fetchDashboard() {
    try {
      setLoading(true);
      // Dev-only mock override: set localStorage key '__fixme_dev_home' to a JSON string to bypass API
      const devMock = import.meta.env.DEV && localStorage.getItem('__fixme_dev_home');
      const result = devMock ? JSON.parse(devMock) : await getHomeDashboard(token);
      setData(result);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchDashboard(); }, []);

  useEffect(() => {
    if (!token) return;
    getInboxConversations(token)
      .then((convs) => {
        const needs = convs.filter((c) => c.needs_human);
        setInboxCount(needs.length);
        setInboxPreview(needs[0] || null);
      })
      .catch(() => {});
  }, [token]);

  function handleHomeViewChange(nextView) {
    setActiveView(nextView);
    const url = new URL(window.location.href);
    if (nextView === 'inbox') url.searchParams.set('view', 'inbox');
    else url.searchParams.delete('view');
    window.history.replaceState({}, '', url.toString());
  }

  async function fetchTimeBlocks() {
    if (!token) return;
    const { fromAt, toAt } = dayRangeIso(selectedDayKey);
    try {
      setBlocksLoading(true);
      const rows = await getProviderTimeBlocks(token, fromAt, toAt);
      setTimeBlocks(Array.isArray(rows) ? rows : []);
    } catch (err) {
      console.error('Failed to load time blocks', err);
    } finally {
      setBlocksLoading(false);
    }
  }

  useEffect(() => {
    if (!calendarOpen || !token) return;
    fetchTimeBlocks();
  }, [calendarOpen, selectedDayKey, token]);

  function handleToggleAction(bookingId) {
    setOpenActionId(prev => prev === bookingId ? null : bookingId);
  }

  async function handleMarkComplete(bookingId) {
    setActionLoading(true);
    try {
      await updateBookingStatus(bookingId, 'completed', token);
      setOpenActionId(null);
      await fetchDashboard();
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleProviderLateAlert(bookingId, minutes) {
    setActionLoading(true);
    try {
      await sendProviderLateAlert(token, bookingId, minutes);
      setOpenActionId(null);
      await fetchDashboard();
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleAcceptReschedule(bookingId) {
    setActionLoading(true);
    try {
      await updateBookingStatus(bookingId, 'confirmed', token);
      await fetchDashboard();
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDeclineReschedule(bookingId) {
    setActionLoading(true);
    try {
      await updateBookingStatus(bookingId, 'cancelled', token);
      await fetchDashboard();
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReschedule(bookingId, newStart, newEnd) {
    setActionLoading(true);
    try {
      await rescheduleBooking(bookingId, newStart, newEnd, token);
      setOpenActionId(null);
      await fetchDashboard();
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleCancelBooking(bookingId) {
    setActionLoading(true);
    try {
      await updateBookingStatus(bookingId, 'cancelled', token);
      setOpenActionId(null);
      await fetchDashboard();
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReportCustomer(customerId, payload) {
    if (!customerId) return;
    setActionLoading(true);
    try {
      await submitCustomerReliabilityReport(token, customerId, payload);
    } catch (err) {
      alert(err.message || 'Could not send report.');
    } finally {
      setActionLoading(false);
    }
  }

  async function handleAddTimeBlock() {
    if (!token) return;

    const startAt = localDateTimeIso(selectedDayKey, blockStartTime);
    const endAt = localDateTimeIso(selectedDayKey, blockEndTime);
    if (startAt >= endAt) {
      alert('End time must be after start time.');
      return;
    }

    setBlockSaving(true);
    try {
      await createProviderTimeBlock(token, {
        start_at: startAt,
        end_at: endAt,
        kind: blockKind,
        reason: blockReason || null,
      });
      setBlockReason('');
      await fetchTimeBlocks();
    } catch (err) {
      alert(err.message || 'Could not create blocker.');
    } finally {
      setBlockSaving(false);
    }
  }

  async function handleDeleteTimeBlock(blockId) {
    if (!token) return;
    setBlockSaving(true);
    try {
      await deleteProviderTimeBlock(token, blockId);
      await fetchTimeBlocks();
    } catch (err) {
      alert(err.message || 'Could not delete blocker.');
    } finally {
      setBlockSaving(false);
    }
  }

  if (loading) return <><Skeleton /><ProviderTabBar active="home" /></>;

  if (error) {
    // Auth error - clear stale token and send to login
    const isAuthError = /token|401|unauthorized|expired/i.test(error);
    if (isAuthError) {
      localStorage.removeItem('fixme_provider_token');
      window.location.replace('/provider/login');
      return null;
    }
    // Network / server error - keep retry
    return (
      <div className="min-h-screen bg-fixme-bg pb-20 px-4 pt-8 max-w-md mx-auto">
        <p className="text-fixme-text-muted text-sm">Could not load dashboard. Check your connection.</p>
        <button onClick={fetchDashboard} className="mt-4 text-fixme-text-primary text-sm underline">Retry</button>
        <ProviderTabBar active="home" />
      </div>
    );
  }

  const { provider_name, today_label, team, upcoming_bookings, booking_updates, requests, pending_requests_count, booking_link, waitlist_count, referral_completed_bookings_count, referral_credit_rate_sek, referral_earned_this_month_sek, referral_pending_payout_sek, referral_balance_sek, referral_last_payout_at, trust_score = 0, trust_tier = "developing", trust_confidence = 0, trust_breakdown = { experience: 0, reliability: 0, retention: 0 } } = data;
  const firstName = provider_name ? provider_name.split(' ')[0] : '';
  const trustTierLabel = {
    elite: 'Elite',
    strong: 'Strong',
    developing: 'Developing',
    needs_attention: 'Needs attention',
  }[trust_tier] || 'Developing';

  // Only show worker join requests (booking requests are auto-confirmed now)
  const joinRequests = requests.filter(r => r.request_type !== 'booking');
  const bookingsByDay = upcoming_bookings.reduce((acc, booking) => {
    const key = dayKeyFromIso(booking.scheduled_start);
    if (!acc[key]) acc[key] = [];
    acc[key].push(booking);
    return acc;
  }, {});
  const monthCells = buildCalendarDays(calendarMonth);
  const weekDays = buildWeekDays(weekStartDate);
  const selectedDayBookings = (bookingsByDay[selectedDayKey] || [])
    .slice()
    .sort((a, b) => new Date(a.scheduled_start).getTime() - new Date(b.scheduled_start).getTime());
  const selectedDayBlocks = timeBlocks
    .slice()
    .sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime());
  const selectedDateLabel = dateFromDayKey(selectedDayKey).toLocaleDateString('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  });
  const selectedDateCompactLabel = dateFromDayKey(selectedDayKey).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
  const calendarMonthLabel = calendarMonth.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });
  const weekLabel = formatWeekRange(weekStartDate);

  if (activeView === 'inbox') {
    return (
      <div className="min-h-screen bg-fixme-bg pb-24 px-4 pt-8 max-w-md mx-auto">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h1 className="text-fixme-text-primary text-xl font-semibold tracking-tight">{getGreeting()}{firstName ? `, ${firstName}` : ''}</h1>
            <p className="text-fixme-text-muted text-xs mt-0.5">{today_label}</p>
          </div>
          <button className="relative p-2">
            <svg className="w-5 h-5 text-fixme-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            {pending_requests_count > 0 && (
              <span className="absolute top-1 right-1 w-2 h-2 bg-fixme-error rounded-full" />
            )}
          </button>
        </div>

        <div className="mb-5 inline-flex rounded-2xl border border-fixme-border bg-fixme-card p-1 gap-1">
          <button
            onClick={() => handleHomeViewChange('bookings')}
            className="px-4 py-2 rounded-xl text-sm font-semibold text-fixme-text-secondary"
          >
            Bookings
          </button>
          <button
            onClick={() => handleHomeViewChange('inbox')}
            className="relative px-4 py-2 rounded-xl text-sm font-semibold bg-fixme-accent text-fixme-bg"
          >
            Inbox
            {inboxCount > 0 && (
              <span className="absolute top-1.5 right-1.5 min-w-[18px] h-[18px] px-1 rounded-full bg-fixme-bg text-fixme-accent text-[10px] font-bold flex items-center justify-center">
                {inboxCount}
              </span>
            )}
          </button>
        </div>

        <ProviderInboxPanel token={token} />
        <ProviderTabBar active="home" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-fixme-bg pb-24 px-4 pt-8 max-w-md mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-fixme-text-primary text-xl font-semibold tracking-tight">{getGreeting()}{firstName ? `, ${firstName}` : ''}</h1>
          <p className="text-fixme-text-muted text-xs mt-0.5">{today_label}</p>
        </div>
        <button className="relative p-2">
          <svg className="w-5 h-5 text-fixme-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          {pending_requests_count > 0 && (
            <span className="absolute top-1 right-1 w-2 h-2 bg-fixme-error rounded-full" />
          )}
        </button>
      </div>

      {/* Home switch */}
      <div className="mb-5 inline-flex rounded-2xl border border-fixme-border bg-fixme-card p-1 gap-1">
        <button
          onClick={() => handleHomeViewChange('bookings')}
          className={`px-4 py-2 rounded-xl text-sm font-semibold transition-colors ${
            activeView === 'bookings'
              ? 'bg-fixme-accent text-fixme-bg'
              : 'text-fixme-text-secondary hover:text-fixme-text-primary'
          }`}
        >
          Bookings
        </button>
        <button
          onClick={() => handleHomeViewChange('inbox')}
          className={`relative px-4 py-2 rounded-xl text-sm font-semibold transition-colors ${
            activeView === 'inbox'
              ? 'bg-fixme-accent text-fixme-bg'
              : 'text-fixme-text-secondary hover:text-fixme-text-primary'
          }`}
        >
          Inbox
          {inboxCount > 0 && (
            <span className={`absolute top-1.5 right-1.5 min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-bold flex items-center justify-center ${
              activeView === 'inbox' ? 'bg-fixme-bg text-fixme-accent' : 'bg-fixme-accent text-fixme-bg'
            }`}>
              {inboxCount}
            </span>
          )}
        </button>
      </div>

      {/* Upcoming Bookings */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <h2 className="text-fixme-text-primary text-base font-semibold">Upcoming</h2>
            {upcoming_bookings.length > 0 && (
              <span className="bg-fixme-text-primary text-fixme-bg text-xs font-bold px-2 py-0.5 rounded-full">{upcoming_bookings.length}</span>
            )}
          </div>
          <button
            onClick={() => setCalendarOpen((v) => !v)}
            className={`p-2 rounded-lg border transition-colors ${
              calendarOpen
                ? 'border-fixme-text-primary text-fixme-text-primary'
                : 'border-fixme-border text-fixme-text-muted hover:text-fixme-text-secondary'
            }`}
            aria-label="Open booking calendar"
            title="Open booking calendar"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 7V3m8 4V3m-9 8h10m-12 9h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v11a2 2 0 002 2z" />
            </svg>
          </button>
        </div>

        {calendarOpen && (
          <div className="bg-fixme-card border border-fixme-border rounded-2xl p-4 mb-3">
            <div className="flex items-center justify-between gap-3 mb-3">
              <div className="inline-flex rounded-lg border border-fixme-border overflow-hidden">
                {['day', 'week', 'month'].map((view) => (
                  <button
                    key={view}
                    onClick={() => {
                      if (view === 'month') {
                        const selectedDate = dateFromDayKey(selectedDayKey);
                        setCalendarMonth(new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1));
                      }
                      if (view === 'week') {
                        setWeekStartDate(startOfWeek(dateFromDayKey(selectedDayKey)));
                      }
                      setCalendarView(view);
                    }}
                    className={`px-2.5 py-1.5 text-xs font-medium capitalize ${
                      calendarView === view
                        ? 'bg-fixme-text-primary text-fixme-bg'
                        : 'text-fixme-text-secondary bg-transparent'
                    }`}
                  >
                    {view}
                  </button>
                ))}
              </div>

              {calendarView === 'month' ? (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setCalendarMonth((prev) => new Date(prev.getFullYear(), prev.getMonth() - 1, 1))}
                    className="p-1.5 rounded-lg border border-fixme-border text-fixme-text-secondary"
                    aria-label="Previous month"
                  >
                    <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M12.707 15.707a1 1 0 01-1.414 0L6.586 11a1 1 0 010-1.414l4.707-4.707a1 1 0 111.414 1.414L8.707 10l4 4a1 1 0 010 1.414z" clipRule="evenodd" />
                    </svg>
                  </button>
                  <p className="text-fixme-text-primary text-sm font-semibold">{calendarMonthLabel}</p>
                  <button
                    onClick={() => setCalendarMonth((prev) => new Date(prev.getFullYear(), prev.getMonth() + 1, 1))}
                    className="p-1.5 rounded-lg border border-fixme-border text-fixme-text-secondary"
                    aria-label="Next month"
                  >
                    <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M7.293 4.293a1 1 0 011.414 0L13.414 9a1 1 0 010 1.414l-4.707 4.707a1 1 0 01-1.414-1.414L11.293 10l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                    </svg>
                  </button>
                </div>
              ) : calendarView === 'week' ? (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      const shifted = shiftDayKey(selectedDayKey, -7);
                      setSelectedDayKey(shifted);
                      setWeekStartDate(startOfWeek(dateFromDayKey(shifted)));
                    }}
                    className="p-1.5 rounded-lg border border-fixme-border text-fixme-text-secondary"
                    aria-label="Previous week"
                  >
                    <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M12.707 15.707a1 1 0 01-1.414 0L6.586 11a1 1 0 010-1.414l4.707-4.707a1 1 0 111.414 1.414L8.707 10l4 4a1 1 0 010 1.414z" clipRule="evenodd" />
                    </svg>
                  </button>
                  <p className="text-fixme-text-primary text-sm font-semibold">{weekLabel}</p>
                  <button
                    onClick={() => {
                      const shifted = shiftDayKey(selectedDayKey, 7);
                      setSelectedDayKey(shifted);
                      setWeekStartDate(startOfWeek(dateFromDayKey(shifted)));
                    }}
                    className="p-1.5 rounded-lg border border-fixme-border text-fixme-text-secondary"
                    aria-label="Next week"
                  >
                    <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M7.293 4.293a1 1 0 011.414 0L13.414 9a1 1 0 010 1.414l-4.707 4.707a1 1 0 01-1.414-1.414L11.293 10l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                    </svg>
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setSelectedDayKey((prev) => shiftDayKey(prev, -1))}
                    className="p-1.5 rounded-lg border border-fixme-border text-fixme-text-secondary"
                    aria-label="Previous day"
                  >
                    <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M12.707 15.707a1 1 0 01-1.414 0L6.586 11a1 1 0 010-1.414l4.707-4.707a1 1 0 111.414 1.414L8.707 10l4 4a1 1 0 010 1.414z" clipRule="evenodd" />
                    </svg>
                  </button>
                  <p className="text-fixme-text-primary text-sm font-semibold">{selectedDateCompactLabel}</p>
                  <button
                    onClick={() => setSelectedDayKey((prev) => shiftDayKey(prev, 1))}
                    className="p-1.5 rounded-lg border border-fixme-border text-fixme-text-secondary"
                    aria-label="Next day"
                  >
                    <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M7.293 4.293a1 1 0 011.414 0L13.414 9a1 1 0 010 1.414l-4.707 4.707a1 1 0 01-1.414-1.414L11.293 10l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                    </svg>
                  </button>
                </div>
              )}
            </div>

            {calendarView === 'month' && (
              <>
                <div className="grid grid-cols-7 gap-1 mb-2 text-[10px] text-fixme-text-muted uppercase">
                  {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((wd) => (
                    <div key={wd} className="text-center py-1">{wd}</div>
                  ))}
                </div>
                <div className="grid grid-cols-7 gap-1">
                  {monthCells.map((cell) => {
                    const count = bookingsByDay[cell.key]?.length || 0;
                    const isSelected = cell.key === selectedDayKey;
                    return (
                      <button
                        key={cell.key}
                        onClick={() => setSelectedDayKey(cell.key)}
                        className={`relative h-9 rounded-lg text-xs border ${
                          isSelected
                            ? 'border-fixme-text-primary text-fixme-text-primary bg-fixme-border/40'
                            : cell.inMonth
                              ? 'border-fixme-border text-fixme-text-secondary'
                              : 'border-transparent text-fixme-text-muted/50'
                        }`}
                      >
                        {cell.dayNumber}
                        {count > 0 && <span className="absolute bottom-1 right-1 w-1.5 h-1.5 rounded-full bg-fixme-accent" />}
                      </button>
                    );
                  })}
                </div>
              </>
            )}

            {calendarView === 'week' && (
              <div className="grid grid-cols-7 gap-2">
                {weekDays.map((day) => {
                  const count = bookingsByDay[day.key]?.length || 0;
                  const isSelected = day.key === selectedDayKey;
                  return (
                    <button
                      key={day.key}
                      onClick={() => setSelectedDayKey(day.key)}
                      className={`rounded-xl border px-1 py-2 text-center ${
                        isSelected
                          ? 'border-fixme-text-primary bg-fixme-border/40'
                          : 'border-fixme-border'
                      }`}
                    >
                      <p className={`text-[10px] uppercase ${isSelected ? 'text-fixme-text-primary' : 'text-fixme-text-muted'}`}>
                        {day.weekdayShort}
                      </p>
                      <p className={`text-sm font-semibold ${isSelected ? 'text-fixme-text-primary' : 'text-fixme-text-secondary'}`}>
                        {day.dayNumber}
                      </p>
                      <p className="text-[10px] text-fixme-text-muted">{count > 0 ? `${count} booked` : 'Free'}</p>
                    </button>
                  );
                })}
              </div>
            )}

            {calendarView === 'day' && (
              <div className="rounded-xl border border-fixme-border bg-fixme-bg p-3">
                <p className="text-fixme-text-primary text-sm font-semibold">{selectedDateLabel}</p>
                <p className="text-fixme-text-muted text-xs mt-1">
                  {selectedDayBookings.length > 0 || selectedDayBlocks.length > 0 ? `${selectedDayBookings.length} booking(s), ${selectedDayBlocks.length} blocker(s)` : 'No bookings for this day.'}
                </p>
              </div>
            )}

            <div className="border-t border-fixme-border/60 mt-3 pt-3">
              <p className="text-fixme-text-primary text-xs font-semibold mb-2">{selectedDateLabel}</p>
              {selectedDayBookings.length === 0 ? (
                <p className="text-fixme-text-muted text-xs">No bookings for this day.</p>
              ) : (
                <div className="space-y-2">
                  {selectedDayBookings.map((booking) => (
                    <div key={`cal-${booking.booking_id}`} className="bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2">
                      <p className="text-fixme-text-primary text-xs font-semibold">
                        {fmtTime(booking.scheduled_start)} - {fmtTime(booking.scheduled_end)}
                      </p>
                      <p className="text-fixme-text-secondary text-xs">
                        {booking.customer_name} - {booking.service_name}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              <div className="mt-4 pt-3 border-t border-fixme-border/60 space-y-2">
                <p className="text-fixme-text-primary text-xs font-semibold">Block time</p>

                <div className="inline-flex rounded-lg border border-fixme-border overflow-hidden">
                  {['lunch', 'private'].map((kind) => (
                    <button
                      key={kind}
                      onClick={() => setBlockKind(kind)}
                      className={`px-3 py-1.5 text-xs font-medium capitalize ${
                        blockKind === kind
                          ? 'bg-fixme-text-primary text-fixme-bg'
                          : 'text-fixme-text-secondary bg-transparent'
                      }`}
                    >
                      {kind}
                    </button>
                  ))}
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <label className="text-[11px] text-fixme-text-muted space-y-1">
                    <span>Start</span>
                    <input
                      type="time"
                      step="300"
                      value={blockStartTime}
                      onChange={(e) => setBlockStartTime(e.target.value)}
                      className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2 text-xs text-fixme-text-primary"
                    />
                  </label>
                  <label className="text-[11px] text-fixme-text-muted space-y-1">
                    <span>End</span>
                    <input
                      type="time"
                      step="300"
                      value={blockEndTime}
                      onChange={(e) => setBlockEndTime(e.target.value)}
                      className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2 text-xs text-fixme-text-primary"
                    />
                  </label>
                </div>

                <input
                  type="text"
                  value={blockReason}
                  onChange={(e) => setBlockReason(e.target.value)}
                  placeholder="Optional note"
                  className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2 text-xs text-fixme-text-primary"
                />

                <button
                  onClick={handleAddTimeBlock}
                  disabled={blockSaving}
                  className="w-full py-2 text-xs font-semibold text-fixme-bg bg-fixme-text-primary rounded-xl disabled:opacity-60"
                >
                  {blockSaving ? 'Saving...' : 'Add blocker'}
                </button>

                {blocksLoading ? (
                  <p className="text-fixme-text-muted text-xs">Loading blockers...</p>
                ) : selectedDayBlocks.length === 0 ? (
                  <p className="text-fixme-text-muted text-xs">No blockers on this day.</p>
                ) : (
                  <div className="space-y-2">
                    {selectedDayBlocks.map((block) => (
                      <div key={block.block_id} className="bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2 flex items-center justify-between gap-2">
                        <div>
                          <p className="text-fixme-text-primary text-xs font-semibold capitalize">
                            {block.kind} - {fmtTime(block.start_at)} to {fmtTime(block.end_at)}
                          </p>
                          {block.reason && (
                            <p className="text-fixme-text-muted text-[11px]">{block.reason}</p>
                          )}
                        </div>
                        <button
                          onClick={() => handleDeleteTimeBlock(block.block_id)}
                          disabled={blockSaving}
                          className="text-xs text-fixme-error border border-fixme-error/30 rounded-lg px-2 py-1 disabled:opacity-60"
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {upcoming_bookings.length === 0 ? (
          <div className="bg-fixme-card border border-fixme-border rounded-2xl p-6 text-center">
            <p className="text-fixme-text-muted text-sm">No upcoming bookings</p>
          </div>
        ) : (
          <div className="space-y-3">
            {upcoming_bookings.map((b, idx) => {
              const currentDateKey = new Date(b.scheduled_start).toDateString();
              const prevDateKey = idx > 0 ? new Date(upcoming_bookings[idx - 1].scheduled_start).toDateString() : null;
              const showDateHeader = idx === 0 || currentDateKey !== prevDateKey;

              return (
                <Fragment key={b.booking_id}>
                  {showDateHeader && (
                    <div className="pt-1 pb-1">
                      <p className="text-fixme-text-muted text-[11px] font-semibold uppercase tracking-wide">
                        {fmtDate(b.scheduled_start)}
                      </p>
                    </div>
                  )}
                  <BookingCard
                    booking={b}
                    isOpen={openActionId === b.booking_id}
                    onToggle={() => handleToggleAction(b.booking_id)}
                    onComplete={handleMarkComplete}
                    onLateAlert={handleProviderLateAlert}
                    onReschedule={handleReschedule}
                    onCancel={handleCancelBooking}
                    onReportCustomer={handleReportCustomer}
                    actionLoading={actionLoading}
                  />
                </Fragment>
              );
            })}
          </div>
        )}
      </div>

      {/* Share link */}
      {booking_link && (
        <button
          onClick={() => { navigator.clipboard.writeText(booking_link); }}
          className="w-full mb-6 flex items-center gap-3 bg-fixme-card border border-fixme-border rounded-xl px-4 py-3 active:scale-[0.98] transition-all"
        >
          <svg className="w-4 h-4 text-fixme-text-secondary flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
          </svg>
          <span className="text-fixme-text-muted text-xs truncate flex-1 text-left">{booking_link}</span>
          <span className="text-fixme-text-primary text-xs font-medium flex-shrink-0">Copy</span>
        </button>
      )}

      {/* Inbox attention card — only shown when messages need provider reply */}
      {inboxCount > 0 && (
        <button
          onClick={() => { handleHomeViewChange('inbox'); }}
          className="w-full mb-5 flex items-start gap-3 bg-fixme-card border border-amber-500/40 rounded-2xl px-4 py-3.5 text-left hover:border-amber-400/70 transition-colors active:scale-[0.98]"
        >
          <span className="text-xl leading-none mt-0.5">{'\u26A0\uFE0F'}</span>
          <div className="flex-1 min-w-0">
            <p className="text-fixme-text-primary text-sm font-semibold">
              {inboxCount === 1 ? '1 message needs your reply' : `${inboxCount} messages need your reply`}
            </p>
            {inboxPreview && (
              <p className="text-fixme-text-secondary text-xs truncate mt-0.5">
                {inboxPreview.customer_name || inboxPreview.customer_ig_handle || 'Customer'}: {inboxPreview.last_message?.text || 'Tap to view'}
              </p>
            )}
          </div>
          <span className="text-fixme-text-muted text-xs self-center shrink-0">{'\u2192'}</span>
        </button>
      )}

      {/* Setup wizard - shown until both cards are dismissed */}
      <SetupWizard token={token} onHasPending={setSetupPending} />

      {/* Referral credits */}
      <div className="mb-6 bg-fixme-card border border-fixme-border rounded-2xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-fixme-text-primary text-sm font-semibold">Referral credits</p>
          <span className="text-fixme-text-muted text-[11px]">Monthly auto payout</span>
        </div>
        <div className="flex items-end justify-between">
          <div>
            <p className="text-fixme-text-muted text-xs">Available balance</p>
            <p className="text-fixme-text-primary text-xl font-bold">{fmtSek(referral_balance_sek)}</p>
          </div>
          <div className="text-right">
            <p className="text-fixme-text-muted text-xs">Last payout</p>
            <p className="text-fixme-text-secondary text-xs">{fmtDateShort(referral_last_payout_at)}</p>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2">
          <div className="bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2">
            <p className="text-fixme-text-muted text-[10px] uppercase">Completed referrals</p>
            <p className="text-fixme-text-primary text-sm font-semibold">{referral_completed_bookings_count || 0}</p>
          </div>
          <div className="bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2">
            <p className="text-fixme-text-muted text-[10px] uppercase">This month</p>
            <p className="text-fixme-text-primary text-sm font-semibold">{fmtSek(referral_earned_this_month_sek)}</p>
          </div>
          <div className="bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2">
            <p className="text-fixme-text-muted text-[10px] uppercase">Pending payout</p>
            <p className="text-fixme-text-primary text-sm font-semibold">{fmtSek(referral_pending_payout_sek)}</p>
          </div>
        </div>
        <p className="text-fixme-text-muted text-[11px]">Rate: {fmtSek(referral_credit_rate_sek)} per completed referred booking.</p>
      </div>

      {/* Fair trust score */}
      <div className="mb-6 bg-fixme-card border border-fixme-border rounded-2xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-fixme-text-primary text-sm font-semibold">Fair trust score</p>
          <span className="text-fixme-text-muted text-[11px]">{trustTierLabel}</span>
        </div>

        <div className="flex items-end justify-between">
          <div>
            <p className="text-fixme-text-muted text-xs">Score</p>
            <p className="text-fixme-text-primary text-2xl font-bold">{Number(trust_score || 0).toFixed(1)}</p>
          </div>
          <div className="text-right">
            <p className="text-fixme-text-muted text-xs">Confidence</p>
            <p className="text-fixme-text-secondary text-xs">{Math.round((trust_confidence || 0) * 100)}%</p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <div className="bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2">
            <p className="text-fixme-text-muted text-[10px] uppercase">Experience</p>
            <p className="text-fixme-text-primary text-sm font-semibold">{Number(trust_breakdown?.experience || 0).toFixed(1)}</p>
          </div>
          <div className="bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2">
            <p className="text-fixme-text-muted text-[10px] uppercase">Reliability</p>
            <p className="text-fixme-text-primary text-sm font-semibold">{Number(trust_breakdown?.reliability || 0).toFixed(1)}</p>
          </div>
          <div className="bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2">
            <p className="text-fixme-text-muted text-[10px] uppercase">Retention</p>
            <p className="text-fixme-text-primary text-sm font-semibold">{Number(trust_breakdown?.retention || 0).toFixed(1)}</p>
          </div>
        </div>
        <p className="text-fixme-text-muted text-[11px]">Balanced by reviews, punctuality and real revisit behavior.</p>
      </div>
      {/* Team (hidden when no workers) */}
      {team.length > 0 && (
        <div className="mb-6">
          <SectionHeader title="Team" />
          <div className="flex gap-4 overflow-x-auto pb-2 -mx-1 px-1 scrollbar-hide">
            {team.map(member => <TeamCard key={member.id} member={member} />)}
          </div>
        </div>
      )}

      {/* Booking Updates (reschedule requests) */}
      {booking_updates.length > 0 && (
        <div className="mb-6">
          <SectionHeader title="Booking updates" count={booking_updates.length} />
          <div className="space-y-3">
            {booking_updates.map(u => (
              <UpdateCard
                key={u.booking_id}
                update={u}
                onAccept={handleAcceptReschedule}
                onDecline={handleDeclineReschedule}
                loading={actionLoading}
              />
            ))}
          </div>
        </div>
      )}

      {/* Join Requests */}
      {joinRequests.length > 0 && (
        <div className="mb-6">
          <SectionHeader title="Join requests" count={joinRequests.length} />
          <div className="space-y-3">
            {joinRequests.map(r => (
              <div key={r.request_id} className="bg-fixme-card border border-fixme-border rounded-2xl p-4 space-y-3">
                <div className="flex items-center gap-3">
                  <Avatar url={r.person_image_url} name={r.person_name} />
                  <div className="flex-1 min-w-0">
                    <p className="text-fixme-text-primary text-sm font-semibold truncate">{r.person_name}</p>
                    <p className="text-fixme-text-secondary text-xs">{r.worker_role || r.business_type} &middot; {r.worker_city}</p>
                  </div>
                </div>
                {r.worker_message && (
                  <p className="text-fixme-text-muted text-xs italic">&quot;{r.worker_message}&quot;</p>
                )}
                <div className="flex gap-2">
                  <button className="flex-1 py-2 text-xs font-semibold text-fixme-text-secondary border border-fixme-border rounded-xl active:scale-[0.98] transition-all">
                    Decline
                  </button>
                  <button className="flex-1 py-2 text-xs font-semibold text-fixme-bg bg-fixme-text-primary rounded-xl active:scale-[0.98] transition-all">
                    Accept
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Waitlist */}
      {waitlist_count > 0 && (
        <div className="mb-6">
          <div className="bg-fixme-card border border-fixme-border rounded-2xl p-4 flex items-center justify-between">
            <div>
              <p className="text-fixme-text-primary text-sm font-semibold">Waitlist</p>
              <p className="text-fixme-text-muted text-xs">{waitlist_count} people waiting</p>
            </div>
            <span className="text-fixme-text-primary text-xs font-medium">View</span>
          </div>
        </div>
      )}

      <ProviderTabBar active="home" profileAttention={setupPending} />
    </div>
  );
}

