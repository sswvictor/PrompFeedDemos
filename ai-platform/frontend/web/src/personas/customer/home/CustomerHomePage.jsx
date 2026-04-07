import { useState, useEffect, useMemo } from 'react';
import CustomerTabBar from '../navigation/CustomerTabBar';
import {
  getCustomerDashboard,
  getCustomerPreferences,
  updateCustomerPreferences,
  cancelCustomerBooking,
  sendLateNotification,
  submitProviderIncidentReport,
} from '../../../api/bookingApi';
import { SERVICE_OPTIONS, LIFESTYLE_OPTIONS } from '../../../constants/customerPreferences';

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
  const now = new Date();
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  if (d.toDateString() === now.toDateString()) return 'Today';
  if (d.toDateString() === tomorrow.toDateString()) return 'Tomorrow';
  return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
}

function fmtFullDate(iso) {
  return new Date(iso).toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: '2-digit',
  });
}

function arraysEqual(a, b) {
  const aa = [...(a || [])].sort();
  const bb = [...(b || [])].sort();
  if (aa.length !== bb.length) return false;
  return aa.every((v, i) => v === bb[i]);
}

function optionSummary(options, selected) {
  if (!selected || selected.length === 0) return 'Not set yet';
  const labels = options
    .filter((opt) => selected.includes(opt.key))
    .map((opt) => opt.label);
  if (labels.length <= 2) return labels.join(', ');
  return `${labels.slice(0, 2).join(', ')} +${labels.length - 2}`;
}

function StatusBadge({ status }) {
  const styles = {
    confirmed: 'bg-fixme-success/15 text-fixme-success',
    pending: 'bg-yellow-500/15 text-yellow-400',
    completed: 'bg-fixme-text-muted/15 text-fixme-text-muted',
    cancelled: 'bg-fixme-error/15 text-fixme-error',
  };
  const labels = {
    confirmed: 'Confirmed',
    pending: 'Pending',
    completed: 'Completed',
    cancelled: 'Cancelled',
  };
  return (
    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${styles[status] || styles.pending}`}>
      {labels[status] || status}
    </span>
  );
}

function ProviderAvatar({ name, imageUrl, size = 'md' }) {
  const sizeClasses = {
    sm: 'w-8 h-8 text-xs',
    md: 'w-10 h-10 text-sm',
    lg: 'w-14 h-14 text-base',
  };
  const dim = sizeClasses[size] || sizeClasses.md;
  const initial = (name || '?')[0].toUpperCase();
  if (imageUrl) {
    return <img src={imageUrl} alt={name} className={`${dim} rounded-full object-cover flex-shrink-0`} />;
  }
  return (
    <div
      className={`${dim} rounded-full bg-fixme-border flex items-center justify-center text-fixme-text-secondary font-semibold flex-shrink-0`}
    >
      {initial}
    </div>
  );
}

const LATE_OPTIONS = [5, 10, 15, 20, 30];
const PROVIDER_REPORT_OPTIONS = [
  { value: 'no_show_provider', label: 'Provider did not show up' },
  { value: 'unsafe_behavior', label: 'Unsafe behavior' },
  { value: 'policy_violation', label: 'Policy violation' },
  { value: 'other', label: 'Other issue' },
];

function UpcomingBookingCard({ booking, token, onCancelled }) {
  const [expanded, setExpanded] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState(null);

  const [lateOpen, setLateOpen] = useState(false);
  const [lateMinutes, setLateMinutes] = useState(null);
  const [lateSending, setLateSending] = useState(false);
  const [lateSent, setLateSent] = useState(null);
  const [lateError, setLateError] = useState(null);

  const [reportOpen, setReportOpen] = useState(false);
  const [reportType, setReportType] = useState("unsafe_behavior");
  const [reportDetails, setReportDetails] = useState("");
  const [reportSending, setReportSending] = useState(false);
  const [reportSent, setReportSent] = useState(false);
  const [reportError, setReportError] = useState(null);

  const providerHref = booking.provider_slug ? `/p/${booking.provider_slug}` : null;
  const rescheduleHref = booking.provider_slug ? `/b/${booking.provider_slug}` : `/?provider=${booking.provider_id}`;

  function toggleEdit() {
    setExpanded((e) => !e);
    setLateOpen(false);
    setReportOpen(false);
    setConfirming(false);
    setCancelError(null);
  }

  function toggleLate() {
    setLateOpen((e) => !e);
    setExpanded(false);
    setReportOpen(false);
    setLateMinutes(null);
    setLateError(null);
  }

  function toggleReport() {
    setReportOpen((e) => !e);
    setExpanded(false);
    setLateOpen(false);
    setReportError(null);
  }

  async function handleCancel() {
    if (!confirming) {
      setConfirming(true);
      return;
    }

    setCancelling(true);
    setCancelError(null);
    try {
      await cancelCustomerBooking(token, booking.booking_id);
      onCancelled(booking.booking_id);
    } catch (err) {
      setCancelError(err.message || 'Could not cancel. Please try again.');
      setCancelling(false);
      setConfirming(false);
    }
  }

  async function handleSendLate() {
    if (!lateMinutes) return;
    setLateSending(true);
    setLateError(null);
    try {
      await sendLateNotification(token, booking.booking_id, lateMinutes);
      setLateSent(lateMinutes);
      setLateOpen(false);
    } catch (err) {
      setLateError(err.message || 'Could not send. Try again.');
    } finally {
      setLateSending(false);
    }
  }

  async function handleSendReport() {
    setReportSending(true);
    setReportError(null);
    try {
      await submitProviderIncidentReport(token, booking.booking_id, {
        report_type: reportType,
        severity: reportType === 'unsafe_behavior' ? 3 : reportType === 'no_show_provider' ? 2 : 1,
        details: reportDetails || null,
      });
      setReportSent(true);
      setReportOpen(false);
      setReportDetails('');
      setTimeout(() => setReportSent(false), 3000);
    } catch (err) {
      setReportError(err.message || 'Could not send report. Try again.');
    } finally {
      setReportSending(false);
    }
  }

  return (
    <div className="bg-fixme-card border border-fixme-border rounded-2xl p-4 space-y-3 animate-fade-in">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <ProviderAvatar name={booking.provider_name} imageUrl={booking.provider_image_url} />
          <div className="min-w-0">
            {providerHref ? (
              <a
                href={providerHref}
                className="text-fixme-text-primary text-sm font-semibold hover:text-fixme-accent transition-colors truncate block"
              >
                {booking.provider_name}
              </a>
            ) : (
              <p className="text-fixme-text-primary text-sm font-semibold truncate">{booking.provider_name}</p>
            )}
            <p className="text-fixme-text-secondary text-xs truncate">{booking.service_name}</p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 flex-shrink-0">
          <button
            onClick={toggleReport}
            title="Report issue"
            className={`w-8 h-8 rounded-full border flex items-center justify-center transition-all ${
              reportOpen
                ? 'border-red-400 text-red-300 bg-red-500/10'
                : reportSent
                  ? 'border-red-400/60 text-red-300'
                  : 'border-fixme-border text-fixme-text-muted hover:border-fixme-text-secondary hover:text-fixme-text-secondary'
            }`}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </button>

          <button
            onClick={toggleLate}
            title="I'm running late"
            className={`w-8 h-8 rounded-full border flex items-center justify-center transition-all ${
              lateOpen
                ? 'border-orange-400 text-orange-400 bg-orange-400/10'
                : lateSent
                  ? 'border-orange-400/50 text-orange-400'
                  : 'border-fixme-border text-fixme-text-muted hover:border-fixme-text-secondary hover:text-fixme-text-secondary'
            }`}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </button>

          <button
            onClick={toggleEdit}
            className={`text-xs font-medium px-3 py-1 rounded-full border transition-all ${
              expanded
                ? 'border-fixme-accent text-fixme-accent bg-fixme-accent/10'
                : 'border-fixme-border text-fixme-text-secondary hover:border-fixme-text-muted'
            }`}
          >
            {expanded ? 'Close' : 'Edit'}
          </button>
        </div>
      </div>

      <div className="flex items-center gap-4 text-fixme-text-secondary text-xs">
        <div className="flex items-center gap-1.5">
          <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
            />
          </svg>
          <span className="font-medium text-fixme-text-primary">{fmtDate(booking.scheduled_start)}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span>{fmtTime(booking.scheduled_start)} - {fmtTime(booking.scheduled_end)}</span>
        </div>
      </div>

      {lateSent && (
        <div className="flex items-center gap-2 bg-orange-500/10 border border-orange-500/25 rounded-xl px-3 py-2">
          <svg className="w-3.5 h-3.5 text-orange-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <span className="text-orange-300 text-xs font-medium">Running {lateSent} min late - provider notified</span>
        </div>
      )}

      {reportSent && (
        <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/25 rounded-xl px-3 py-2">
          <svg className="w-3.5 h-3.5 text-red-300 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <span className="text-red-200 text-xs font-medium">Report sent to Fixmeapp support</span>
        </div>
      )}

      {booking.customer_notes && (
        <p className="text-fixme-text-muted text-xs italic border-t border-fixme-border/50 pt-2">"{booking.customer_notes}"</p>
      )}

      {lateOpen && (
        <div className="border-t border-fixme-border/50 pt-3 space-y-3">
          <p className="text-fixme-text-secondary text-xs font-medium">How many minutes late?</p>
          <div className="flex gap-2 flex-wrap">
            {LATE_OPTIONS.map((min) => (
              <button
                key={min}
                onClick={() => setLateMinutes(min)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-full border transition-all ${
                  lateMinutes === min
                    ? 'bg-orange-400 border-orange-400 text-fixme-bg'
                    : 'border-fixme-border text-fixme-text-secondary hover:border-orange-400/60 hover:text-orange-300'
                }`}
              >
                {min} min
              </button>
            ))}
          </div>
          {lateError && <p className="text-fixme-error text-xs">{lateError}</p>}
          <button
            onClick={handleSendLate}
            disabled={!lateMinutes || lateSending}
            className={`w-full py-2.5 text-sm font-semibold rounded-xl transition-all active:scale-[0.98] ${
              lateMinutes && !lateSending
                ? 'bg-orange-400 text-fixme-bg'
                : 'bg-fixme-border/50 text-fixme-text-muted cursor-not-allowed'
            }`}
          >
            {lateSending ? 'Sending...' : 'Notify provider'}
          </button>
        </div>
      )}

      {reportOpen && (
        <div className="border-t border-fixme-border/50 pt-3 space-y-3">
          <p className="text-fixme-text-secondary text-xs font-medium">Report issue with this booking</p>
          <select
            value={reportType}
            onChange={(e) => setReportType(e.target.value)}
            className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2 text-xs text-fixme-text-primary"
          >
            {PROVIDER_REPORT_OPTIONS.map((opt) => (
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
          {reportError && <p className="text-fixme-error text-xs">{reportError}</p>}
          <button
            onClick={handleSendReport}
            disabled={reportSending}
            className={`w-full py-2.5 text-sm font-semibold rounded-xl transition-all active:scale-[0.98] ${
              reportSending
                ? 'bg-fixme-border/50 text-fixme-text-muted cursor-not-allowed'
                : 'bg-red-500 text-white'
            }`}
          >
            {reportSending ? 'Sending...' : 'Send report'}
          </button>
        </div>
      )}

      {expanded && (
        <div className="border-t border-fixme-border/50 pt-3 space-y-2">
          {cancelError && <p className="text-fixme-error text-xs">{cancelError}</p>}
          <div className="flex gap-2">
            <a
              href={rescheduleHref}
              className="flex-1 text-center py-2 text-xs font-semibold text-fixme-text-primary border border-fixme-border rounded-xl hover:border-fixme-accent transition-colors"
            >
              Reschedule
            </a>
            <button
              onClick={handleCancel}
              disabled={cancelling}
              className={`flex-1 py-2 text-xs font-semibold rounded-xl transition-all active:scale-[0.98] ${
                confirming
                  ? 'bg-fixme-error text-white border border-fixme-error'
                  : 'border border-fixme-border text-fixme-error hover:border-fixme-error'
              }`}
            >
              {cancelling ? 'Cancelling...' : confirming ? 'Tap to confirm' : 'Cancel booking'}
            </button>
          </div>
          {confirming && !cancelling && (
            <p className="text-fixme-text-muted text-[10px] text-center">This cannot be undone</p>
          )}
        </div>
      )}
    </div>
  );
}

function PastBookingRow({ booking }) {
  const providerHref = booking.provider_slug ? `/p/${booking.provider_slug}` : null;

  return (
    <div className="flex items-center gap-3 py-3 border-b border-fixme-border/40 last:border-0">
      <ProviderAvatar name={booking.provider_name} imageUrl={booking.provider_image_url} size="sm" />
      <div className="flex-1 min-w-0">
        <p className="text-fixme-text-secondary text-sm font-medium truncate">{booking.service_name}</p>
        <p className="text-fixme-text-muted text-xs truncate">
          {providerHref ? (
            <a href={providerHref} className="hover:text-fixme-accent transition-colors">{booking.provider_name}</a>
          ) : (
            booking.provider_name
          )}
          {' | '}{fmtFullDate(booking.scheduled_start)}
        </p>
      </div>
      <StatusBadge status={booking.status} />
    </div>
  );
}

// ── Dev mock data — remove when API returns real past bookings ──────────────
const DEV_MOCK_PAST_BOOKINGS = [
  {
    booking_id: 'mock-rebook-1',
    provider_id: 'mock-p1',
    provider_name: 'Studio Noir',
    provider_image_url: null,
    provider_slug: 'studio-noir',
    service_name: 'Hair Color + Highlights',
    scheduled_start: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString(),
    status: 'completed',
  },
  {
    booking_id: 'mock-rebook-2',
    provider_id: 'mock-p2',
    provider_name: 'Hammam & Spa',
    provider_image_url: null,
    provider_slug: 'hammam-spa',
    service_name: 'Full Body Ritual',
    scheduled_start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
    status: 'completed',
  },
  {
    booking_id: 'mock-rebook-3',
    provider_id: 'mock-p3',
    provider_name: 'Lash Lab',
    provider_image_url: null,
    provider_slug: 'lash-lab',
    service_name: 'Classic Lash Set',
    scheduled_start: new Date(Date.now() - 21 * 24 * 60 * 60 * 1000).toISOString(),
    status: 'completed',
  },
];

function BookAgainCard({ booking }) {
  const bookHref = booking.provider_slug
    ? `/p/${booking.provider_slug}?rebook=1&service=${encodeURIComponent(booking.service_name)}`
    : null;

  return (
    <div className="flex-shrink-0 w-44 bg-fixme-card border border-fixme-border rounded-2xl p-3.5 space-y-2.5 flex flex-col">
      {/* Provider row */}
      <div className="flex items-center gap-2 min-w-0">
        <ProviderAvatar name={booking.provider_name} imageUrl={booking.provider_image_url} size="sm" />
        <div className="min-w-0">
          <p className="text-fixme-text-primary text-xs font-semibold truncate">{booking.provider_name}</p>
          <p className="text-fixme-text-muted text-[10px] truncate">{fmtFullDate(booking.scheduled_start)}</p>
        </div>
      </div>

      {/* Service name */}
      <p className="text-fixme-text-secondary text-xs leading-snug line-clamp-2 flex-1">
        {booking.service_name}
      </p>

      {/* Book again button */}
      {bookHref ? (
        <a
          href={bookHref}
          className="block w-full text-center py-2 text-xs font-semibold rounded-xl bg-fixme-accent text-fixme-bg active:scale-[0.97] transition-transform"
        >
          Book again
        </a>
      ) : (
        <button
          disabled
          className="w-full py-2 text-xs font-semibold rounded-xl bg-fixme-border text-fixme-text-muted cursor-not-allowed"
        >
          Book again
        </button>
      )}
    </div>
  );
}

function BookAgainSection({ pastBookings }) {
  const completed = pastBookings.filter((b) => b.status === 'completed');
  // Fallback to mock data in dev when no real completed bookings yet
  const items = completed.length > 0 ? completed.slice(0, 5) : DEV_MOCK_PAST_BOOKINGS;

  if (items.length === 0) return null;

  return (
    <div className="mb-7">
      <h2 className="text-fixme-text-primary text-base font-semibold mb-3">Book again</h2>
      <div className="flex gap-3 overflow-x-auto pb-2 -mx-4 px-4 scrollbar-hide">
        {items.map((b) => (
          <BookAgainCard key={b.booking_id} booking={b} />
        ))}
      </div>
    </div>
  );
}

function MyProviders({ bookings, followedProviders = [] }) {
  const bookedMap = new Map();
  for (const b of bookings) {
    if (!bookedMap.has(b.provider_id)) {
      bookedMap.set(b.provider_id, b);
    } else {
      const existing = bookedMap.get(b.provider_id);
      if (b.scheduled_start > existing.scheduled_start) {
        bookedMap.set(b.provider_id, b);
      }
    }
  }

  const bookedSorted = [...bookedMap.values()].sort((a, b) => b.scheduled_start.localeCompare(a.scheduled_start));

  const bookedIds = new Set(bookedMap.keys());
  const followedOnly = followedProviders.filter((p) => !bookedIds.has(p.provider_id));

  const allProviders = [
    ...bookedSorted.map((b) => ({
      provider_id: b.provider_id,
      name: b.provider_name,
      image_url: b.provider_image_url,
      slug: b.provider_slug,
      isFollowedOnly: false,
    })),
    ...followedOnly.map((p) => ({
      provider_id: p.provider_id,
      name: p.name,
      image_url: p.image_url,
      slug: p.slug,
      isFollowedOnly: true,
    })),
  ];

  if (allProviders.length === 0) return null;

  return (
    <div className="mb-6">
      <h2 className="text-fixme-text-primary text-base font-semibold mb-3">Your providers</h2>
      <div className="flex gap-4 overflow-x-auto pb-2 -mx-4 px-4 scrollbar-hide">
        {allProviders.map((p) => {
          const href = p.slug ? `/p/${p.slug}` : null;
          const inner = (
            <div className="flex flex-col items-center gap-2 min-w-[64px]">
              <div className="relative">
                <ProviderAvatar name={p.name} imageUrl={p.image_url} size="lg" />
                {p.isFollowedOnly && (
                  <span className="absolute -bottom-0.5 -right-0.5 w-4 h-4 rounded-full bg-fixme-bg border border-fixme-border flex items-center justify-center text-[9px]">
                    {'\u2665'}
                  </span>
                )}
              </div>
              <span className="text-fixme-text-secondary text-xs text-center leading-tight max-w-[72px] truncate">
                {(p.name || '?').split(' ')[0]}
              </span>
            </div>
          );

          return href ? (
            <a key={p.provider_id} href={href} className="flex-shrink-0 hover:opacity-80 active:scale-95 transition-all">
              {inner}
            </a>
          ) : (
            <div key={p.provider_id} className="flex-shrink-0">{inner}</div>
          );
        })}
      </div>
    </div>
  );
}

function PreferenceCard({
  title,
  subtitle,
  options,
  selected,
  expanded,
  onToggleExpanded,
  onToggleChoice,
  onSave,
  saving,
  dirty,
}) {
  return (
    <section className="bg-fixme-card border border-fixme-border rounded-2xl p-4 space-y-3">
      <button type="button" onClick={onToggleExpanded} className="w-full text-left">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-fixme-text-primary text-sm font-semibold">{title}</h3>
            <p className="text-fixme-text-muted text-xs mt-0.5">{subtitle}</p>
          </div>
          <div className="text-right flex-shrink-0">
            <p className="text-fixme-text-secondary text-xs">{selected.length} selected</p>
            <p className="text-fixme-text-muted text-[11px]">{optionSummary(options, selected)}</p>
          </div>
        </div>
      </button>


      {expanded && (
        <>
          <div className="flex flex-wrap gap-2">
            {options.map((opt) => {
              const active = selected.includes(opt.key);
              return (
                <button
                  key={opt.key}
                  type="button"
                  onClick={() => onToggleChoice(opt.key)}
                  className={`px-3 py-1.5 rounded-full text-xs border transition-all ${
                    active
                      ? 'border-fixme-accent bg-fixme-accent/10 text-fixme-text-primary'
                      : 'border-fixme-border bg-fixme-bg text-fixme-text-secondary'
                  }`}
                >
                  {opt.emoji && <span className="mr-1">{opt.emoji}</span>}
                  {opt.label}
                </button>
              );
            })}
          </div>

          <button
            type="button"
            onClick={onSave}
            disabled={saving || !dirty}
            className="w-full rounded-xl px-4 py-3 text-sm font-semibold bg-fixme-accent text-fixme-bg disabled:opacity-50 transition-all active:scale-[0.98]"
          >
            {saving ? 'Saving...' : dirty ? 'Save' : 'Up to date'}
          </button>
        </>
      )}
    </section>
  );
}

function Skeleton() {
  return (
    <div className="min-h-screen bg-fixme-bg pb-24 px-4 pt-8 max-w-md mx-auto animate-pulse space-y-6">
      <div className="h-7 bg-fixme-card rounded-lg w-48" />
      <div className="h-4 bg-fixme-card rounded w-32" />
      <div className="space-y-3">
        {[1, 2].map((i) => (
          <div key={i} className="h-28 bg-fixme-card rounded-2xl" />
        ))}
      </div>
      <div className="h-24 bg-fixme-card rounded-2xl" />
      <div className="h-24 bg-fixme-card rounded-2xl" />
    </div>
  );
}

function EmptyState() {
  return (
    <div className="bg-fixme-card border border-fixme-border rounded-2xl p-8 text-center space-y-3">
      <div className="w-12 h-12 mx-auto bg-fixme-border rounded-full flex items-center justify-center">
        <svg className="w-6 h-6 text-fixme-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
          />
        </svg>
      </div>
      <p className="text-fixme-text-secondary text-sm font-medium">No upcoming bookings</p>
      <p className="text-fixme-text-muted text-xs leading-relaxed">
        Book your next appointment through a provider link or via Instagram DM.
      </p>
    </div>
  );
}

export default function CustomerHomePage() {
  const [data, setData] = useState(null);
  const [serviceInterests, setServiceInterests] = useState([]);
  const [lifestylePreferences, setLifestylePreferences] = useState([]);
  const [serverServiceInterests, setServerServiceInterests] = useState([]);
  const [serverLifestylePreferences, setServerLifestylePreferences] = useState([]);
  const [serviceExpanded, setServiceExpanded] = useState(false);
  const [lifestyleExpanded, setLifestyleExpanded] = useState(false);
  const [prefsSaving, setPrefsSaving] = useState(false);
  const [prefsError, setPrefsError] = useState(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const token = localStorage.getItem('fixme_token');

  const serviceDirty = useMemo(
    () => !arraysEqual(serviceInterests, serverServiceInterests),
    [serviceInterests, serverServiceInterests],
  );
  const lifestyleDirty = useMemo(
    () => !arraysEqual(lifestylePreferences, serverLifestylePreferences),
    [lifestylePreferences, serverLifestylePreferences],
  );

  async function fetchDashboard() {
    if (!token) {
      setError('not_logged_in');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const [dashboard, prefs] = await Promise.all([
        getCustomerDashboard(token),
        getCustomerPreferences(token).catch(() => ({ service_interests: [], lifestyle_preferences: [] })),
      ]);

      const services = prefs.service_interests || [];
      const lifestyle = prefs.lifestyle_preferences || [];

      setData(dashboard);
      setServiceInterests(services);
      setLifestylePreferences(lifestyle);
      setServerServiceInterests(services);
      setServerLifestylePreferences(lifestyle);
      setError(null);

      const shouldPrompt = localStorage.getItem('fixme_customer_show_preference_prompt') === '1';
      if (shouldPrompt || (!services.length && !lifestyle.length)) {
        setServiceExpanded(true);
        setLifestyleExpanded(true);
      }
      localStorage.removeItem('fixme_customer_show_preference_prompt');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchDashboard();
  }, []);

  async function savePreferences() {
    if (!token) return;
    setPrefsSaving(true);
    setPrefsError(null);
    try {
      const updated = await updateCustomerPreferences(token, serviceInterests, lifestylePreferences);
      const services = updated.service_interests || [];
      const lifestyle = updated.lifestyle_preferences || [];
      setServiceInterests(services);
      setLifestylePreferences(lifestyle);
      setServerServiceInterests(services);
      setServerLifestylePreferences(lifestyle);
    } catch (err) {
      setPrefsError(err.message || 'Could not save preferences.');
    } finally {
      setPrefsSaving(false);
    }
  }

  function toggleServiceChoice(key) {
    setServiceInterests((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));
  }

  function toggleLifestyleChoice(key) {
    setLifestylePreferences((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));
  }

  if (loading) {
    return (
      <>
        <Skeleton />
        <CustomerTabBar active="home" />
      </>
    );
  }

  if (error === 'not_logged_in') {
    return (
      <div className="min-h-screen bg-fixme-bg pb-24 px-4 pt-16 max-w-md mx-auto text-center space-y-4">
        <h1 className="text-fixme-text-primary text-xl font-semibold">Welcome to Fixmeapp</h1>
        <p className="text-fixme-text-secondary text-sm">Log in to see your bookings.</p>
        <button
          onClick={() => {
            window.location.href = '/customer/login';
          }}
          className="mt-4 px-8 py-3 bg-fixme-accent text-fixme-bg text-sm font-semibold rounded-xl active:scale-[0.98] transition-all"
        >
          Log in
        </button>
        <CustomerTabBar active="home" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-fixme-bg pb-24 px-4 pt-8 max-w-md mx-auto">
        <p className="text-fixme-error text-sm">{error}</p>
        <button onClick={fetchDashboard} className="mt-4 text-fixme-accent text-sm underline">Retry</button>
        <CustomerTabBar active="home" />
      </div>
    );
  }

  function handleCancelled(bookingId) {
    setData((prev) => ({
      ...prev,
      upcoming_bookings: prev.upcoming_bookings.filter((b) => b.booking_id !== bookingId),
    }));
  }

  const { upcoming_bookings, past_bookings, followed_providers = [] } = data;
  const allBookings = [...upcoming_bookings, ...past_bookings];

  return (
    <div className="min-h-screen bg-fixme-bg pb-24 px-4 pt-8 max-w-md mx-auto">
      <div className="mb-7">
        <h1 className="text-fixme-text-primary text-2xl font-bold tracking-tight">{getGreeting()}</h1>
        <p className="text-fixme-text-muted text-sm mt-0.5">Your appointments at a glance</p>
      </div>

      <div className="mb-7">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="text-fixme-text-primary text-base font-semibold">Upcoming</h2>
          {upcoming_bookings.length > 0 && (
            <span className="bg-fixme-accent text-fixme-bg text-[10px] font-bold px-2 py-0.5 rounded-full">
              {upcoming_bookings.length}
            </span>
          )}
        </div>
        {upcoming_bookings.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="space-y-3">
            {upcoming_bookings.map((b) => (
              <UpcomingBookingCard key={b.booking_id} booking={b} token={token} onCancelled={handleCancelled} />
            ))}
          </div>
        )}
      </div>

      <BookAgainSection pastBookings={past_bookings} />

      <div className="mb-7 space-y-3">
        <h2 className="text-fixme-text-primary text-base font-semibold">Make bookings smarter</h2>

        <PreferenceCard
          title="Service interests"
          subtitle="Tell us what you usually book"
          options={SERVICE_OPTIONS}
          selected={serviceInterests}
          expanded={serviceExpanded}
          onToggleExpanded={() => setServiceExpanded((v) => !v)}
          onToggleChoice={toggleServiceChoice}
          onSave={savePreferences}
          saving={prefsSaving}
          dirty={serviceDirty || lifestyleDirty}
        />

        <PreferenceCard
          title="Lifestyle preferences"
          subtitle="Help providers tailor your experience"
          options={LIFESTYLE_OPTIONS}
          selected={lifestylePreferences}
          expanded={lifestyleExpanded}
          onToggleExpanded={() => setLifestyleExpanded((v) => !v)}
          onToggleChoice={toggleLifestyleChoice}
          onSave={savePreferences}
          saving={prefsSaving}
          dirty={serviceDirty || lifestyleDirty}
        />

        {prefsError && <p className="text-fixme-error text-xs">{prefsError}</p>}
      </div>

      {past_bookings.length > 0 && (
        <div className="mb-7">
          <h2 className="text-fixme-text-primary text-base font-semibold mb-3">Past bookings</h2>
          <div className="bg-fixme-card border border-fixme-border rounded-2xl px-4 divide-y divide-fixme-border/40">
            {past_bookings.slice(0, 10).map((b) => (
              <PastBookingRow key={b.booking_id} booking={b} />
            ))}
          </div>
        </div>
      )}

      <MyProviders bookings={allBookings} followedProviders={followed_providers} />

      <CustomerTabBar active="home" />
    </div>
  );
}






