/**
 * CustomerDataPage — /customer/my-data
 *
 * GDPR-compliant "My Data & Privacy" hub, surfacing:
 *
 *   1. Data inventory       — plain-language table of what we store, why, who sees it
 *   2. AI transparency      — EU AI Act Art. 13: how AI uses your data (reliability score,
 *                             provider matching); your right to explanation and contest
 *   3. Data retention       — how long each category is kept
 *   4. Your rights          — GDPR Art. 15–21 with action buttons
 *   5. Active requests      — live view of pending/completed data rights requests
 *   6. Third-party info     — who else may see your data
 *
 * Privacy-preserving design principles:
 *   • We never sell data to advertisers
 *   • Real name only shared with providers you have booked
 *   • Reliability score computed on-platform (no external profiling)
 *   • You can delete everything at any time
 */

import { useEffect, useState } from 'react';
import {
  getCustomerDashboard,
  getCustomerPreferences,
  submitGdprRequest,
  getMyGdprRequests,
} from '../../../api/bookingApi';

// ── Small reusable components ────────────────────────────────────────────────

function SectionCard({ children, className = '' }) {
  return (
    <section className={`bg-fixme-card border border-fixme-border rounded-2xl p-4 ${className}`}>
      {children}
    </section>
  );
}

function SectionTitle({ icon, title, subtitle }) {
  return (
    <div className="mb-3">
      <div className="flex items-center gap-2">
        {icon && <span className="text-base">{icon}</span>}
        <h2 className="text-fixme-text-primary text-sm font-semibold uppercase tracking-wide">{title}</h2>
      </div>
      {subtitle && <p className="text-fixme-text-muted text-xs mt-0.5 ml-6">{subtitle}</p>}
    </div>
  );
}

function DataRow({ category, what, legalBasis, whoSees, retention }) {
  return (
    <div className="border-b border-fixme-border/50 last:border-b-0 py-2.5 space-y-1">
      <div className="flex items-start justify-between gap-3">
        <p className="text-fixme-text-primary text-xs font-semibold flex-shrink-0 w-28">{category}</p>
        <p className="text-fixme-text-secondary text-xs flex-1">{what}</p>
      </div>
      <div className="ml-0 flex flex-wrap gap-x-4 gap-y-0.5">
        <span className="text-fixme-text-muted text-[10px]">
          <span className="text-fixme-accent/70 font-medium">Legal basis:</span> {legalBasis}
        </span>
        <span className="text-fixme-text-muted text-[10px]">
          <span className="text-fixme-accent/70 font-medium">Visible to:</span> {whoSees}
        </span>
        <span className="text-fixme-text-muted text-[10px]">
          <span className="text-fixme-accent/70 font-medium">Kept for:</span> {retention}
        </span>
      </div>
    </div>
  );
}

function RightItem({ emoji, title, description, action }) {
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-fixme-border/50 last:border-b-0">
      <span className="text-lg flex-shrink-0 mt-0.5">{emoji}</span>
      <div className="flex-1 min-w-0">
        <p className="text-fixme-text-primary text-xs font-semibold">{title}</p>
        <p className="text-fixme-text-muted text-[11px] leading-snug mt-0.5">{description}</p>
      </div>
      {action}
    </div>
  );
}

const STATUS_COLOURS = {
  pending:     'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  in_progress: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  completed:   'bg-fixme-accent/15 text-fixme-accent border-fixme-accent/30',
  rejected:    'bg-fixme-error/15 text-fixme-error border-fixme-error/30',
};

const STATUS_LABELS = {
  pending:     'Pending',
  in_progress: 'In progress',
  completed:   'Completed',
  rejected:    'Rejected',
};

const TYPE_LABELS = {
  export:   'Data export',
  deletion: 'Account deletion',
};

// ── Main page ────────────────────────────────────────────────────────────────

export default function CustomerDataPage() {
  const token = localStorage.getItem('fixme_token');

  const [loading, setLoading]       = useState(true);
  const [dashboard, setDashboard]   = useState(null);
  const [prefs, setPrefs]           = useState(null);
  const [requests, setRequests]     = useState([]);
  const [toast, setToast]           = useState(null);
  const [submitting, setSubmitting] = useState(null); // "export" | "deletion" | null
  const [confirm, setConfirm]       = useState(null); // "deletion" to show confirm dialog

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  useEffect(() => {
    if (!token) { setLoading(false); return; }
    Promise.all([
      getCustomerDashboard(token).catch(() => null),
      getCustomerPreferences(token).catch(() => null),
      getMyGdprRequests(token).catch(() => []),
    ]).then(([dash, customerPrefs, reqs]) => {
      setDashboard(dash);
      setPrefs(customerPrefs);
      setRequests(Array.isArray(reqs) ? reqs : []);
    }).finally(() => setLoading(false));
  }, []);

  const hasPendingOf = (type) =>
    requests.some((r) => r.request_type === type && ['pending', 'in_progress'].includes(r.status));

  async function handleRequest(type) {
    if (!token || submitting) return;
    setSubmitting(type);
    try {
      const created = await submitGdprRequest(token, type);
      setRequests((prev) => [created, ...prev]);
      showToast(
        type === 'export'
          ? 'Data export requested — we will email you within 30 days.'
          : 'Deletion request submitted — we will process it within 30 days.',
      );
    } catch (err) {
      showToast(err.message || 'Could not submit request', 'error');
    } finally {
      setSubmitting(null);
      setConfirm(null);
    }
  }

  if (!token) {
    return (
      <div className="min-h-screen bg-fixme-bg px-4 pt-10 max-w-md mx-auto text-center space-y-4">
        <p className="text-fixme-text-secondary text-sm">Sign in to view your data.</p>
        <button
          onClick={() => { window.location.href = '/customer/login'; }}
          className="px-6 py-3 bg-fixme-accent text-fixme-bg text-sm font-semibold rounded-xl"
        >
          Sign in
        </button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-fixme-bg px-4 pt-8 max-w-md mx-auto animate-pulse space-y-4">
        <div className="h-6 bg-fixme-card rounded w-32" />
        <div className="h-48 bg-fixme-card rounded-2xl" />
        <div className="h-36 bg-fixme-card rounded-2xl" />
        <div className="h-36 bg-fixme-card rounded-2xl" />
      </div>
    );
  }

  const upcomingCount   = dashboard?.upcoming_bookings?.length ?? 0;
  const pastCount       = dashboard?.past_bookings?.length ?? 0;
  const totalBookings   = upcomingCount + pastCount;
  const hasLocations    = (dashboard?.preferred_locations?.length ?? 0) > 0;
  const serviceInterests    = prefs?.service_interests ?? [];
  const lifestylePrefs      = prefs?.lifestyle_preferences ?? [];
  const allPrefs            = [...serviceInterests, ...lifestylePrefs];
  const hasPrefs            = allPrefs.length > 0;

  return (
    <div className="min-h-screen bg-fixme-bg pb-12 px-4 pt-4 max-w-md mx-auto space-y-5">

      {/* Header */}
      <div className="flex items-center gap-3 pt-2 pb-1">
        <button
          onClick={() => window.history.back()}
          className="text-fixme-text-muted hover:text-fixme-text-secondary transition-colors text-lg leading-none w-7"
          aria-label="Back"
        >
          {'\u2190'}
        </button>
        <div className="flex-1">
          <h1 className="text-fixme-text-primary font-bold text-lg">My data & privacy</h1>
          <p className="text-fixme-text-muted text-xs">Privacy-first, transparent by design</p>
        </div>
      </div>

      {/* ── Privacy promise ──────────────────────────────────── */}
      <div className="bg-fixme-accent/8 border border-fixme-accent/20 rounded-2xl px-4 py-3 flex gap-3 items-start">
        <span className="text-xl flex-shrink-0">{'\u{1F512}'}</span>
        <div className="space-y-0.5">
          <p className="text-fixme-text-primary text-xs font-semibold">Privacy-preserving by design</p>
          <p className="text-fixme-text-muted text-[11px] leading-relaxed">
            We never sell your data. We never show ads. Your real name is only shared with providers
            you have actually booked. You can delete everything at any time.
          </p>
        </div>
      </div>

      {/* ── 1. Data inventory ────────────────────────────────── */}
      <SectionCard>
        <SectionTitle
          icon={'\u{1F4CB}'}
          title="What we store"
          subtitle="Plain-language view of every category of personal data"
        />
        <div className="space-y-0">
          <DataRow
            category="Identity"
            what={`Display name, real name, email, profile photo${dashboard?.display_name ? ` (your name: ${dashboard.display_name})` : ''}`}
            legalBasis="Contract"
            whoSees="You; real name only shown to providers you have booked"
            retention="Until account deletion"
          />
          <DataRow
            category="Booking history"
            what={`${totalBookings} booking${totalBookings !== 1 ? 's' : ''} — provider, service, time, status, notes`}
            legalBasis="Contract"
            whoSees="You + the provider of each booking"
            retention="7 years (legal/financial obligation)"
          />
          <DataRow
            category="Reliability score"
            what="AI-computed score (0–100) based on booking completion, cancellations and no-shows"
            legalBasis="Legitimate interest (fraud prevention)"
            whoSees="You + providers when they review a booking request"
            retention="Recalculated continuously; raw signals kept 2 years"
          />
          <DataRow
            category="Preferences"
            what={hasPrefs ? allPrefs.join(', ') : 'Not yet set'}
            legalBasis="Consent (you chose them)"
            whoSees="You + our AI matching system"
            retention="Until you change or delete them"
          />
          <DataRow
            category="Locations"
            what={hasLocations ? dashboard.preferred_locations.join(', ') : 'None saved'}
            legalBasis="Consent (you added them)"
            whoSees="You + our AI booking assistant"
            retention="Until you remove them"
          />
          <DataRow
            category="Instagram"
            what="Instagram username (if you connected during booking via DM)"
            legalBasis="Consent (you initiated the DM)"
            whoSees="You + the provider you messaged"
            retention="Until account deletion or disconnection"
          />
          <DataRow
            category="Device / session"
            what="No cookies, no persistent device fingerprinting, no third-party tracking"
            legalBasis="n/a — we don&apos;t collect this"
            whoSees="n/a"
            retention="n/a"
          />
        </div>
      </SectionCard>

      {/* ── 2. AI transparency (EU AI Act Art. 13) ───────────── */}
      <SectionCard>
        <SectionTitle
          icon={'\u{1F916}'}
          title="How our AI uses your data"
          subtitle="EU AI Act Article 13 — transparency about automated processing"
        />
        <div className="space-y-3">

          <div className="bg-fixme-bg rounded-xl p-3 space-y-1.5">
            <p className="text-fixme-text-primary text-xs font-semibold">Reliability score</p>
            <p className="text-fixme-text-muted text-[11px] leading-relaxed">
              An algorithm computes a score from 0–100 using: booking completion rate, cancellation
              rate, no-show rate, and time to cancel. No external data is used — only your activity
              on our platform.
            </p>
            <p className="text-fixme-text-muted text-[11px] leading-relaxed">
              <span className="text-fixme-accent/80 font-medium">Impact:</span> Providers may see
              this score when reviewing a booking. A low score may influence their acceptance.
            </p>
            <p className="text-fixme-text-muted text-[11px] leading-relaxed">
              <span className="text-fixme-accent/80 font-medium">Your right:</span> You can contest
              a score you believe is inaccurate — contact us via the request form below.
            </p>
          </div>

          <div className="bg-fixme-bg rounded-xl p-3 space-y-1.5">
            <p className="text-fixme-text-primary text-xs font-semibold">Provider matching</p>
            <p className="text-fixme-text-muted text-[11px] leading-relaxed">
              When you search or book via DM, our AI uses your service preferences, lifestyle tags
              and saved locations to suggest the most relevant providers and time slots.
            </p>
            <p className="text-fixme-text-muted text-[11px] leading-relaxed">
              <span className="text-fixme-accent/80 font-medium">No profiling:</span> We do not
              build a demographic profile or infer sensitive attributes (religion, health, etc.).
              Only data you explicitly provided is used.
            </p>
          </div>

          <div className="bg-fixme-bg rounded-xl p-3 space-y-1.5">
            <p className="text-fixme-text-primary text-xs font-semibold">DM booking assistant</p>
            <p className="text-fixme-text-muted text-[11px] leading-relaxed">
              When you message a provider via Instagram DM, our AI reads only the messages in that
              thread to understand and fulfill your booking request. Message content is not stored
              indefinitely or used for profiling.
            </p>
          </div>
        </div>
      </SectionCard>

      {/* ── 3. Third-party processors ───────────────────────── */}
      <SectionCard>
        <SectionTitle
          icon={'\u{1F310}'}
          title="Third parties"
          subtitle="We share the minimum necessary — never for advertising"
        />
        <div className="space-y-2">
          {[
            {
              name: 'Railway / Supabase (hosting)',
              purpose: 'Database and infrastructure hosting (EU/US)',
              data: 'All data — encrypted at rest and in transit',
            },
            {
              name: 'Meta (Instagram API)',
              purpose: 'Reading DMs for booking requests you initiate',
              data: 'DM thread only, when you message a provider',
            },
            {
              name: 'Stripe (payments)',
              purpose: 'Provider subscription billing',
              data: 'Provider billing only — no customer payment data stored',
            },
            {
              name: 'Anthropic / OpenAI',
              purpose: 'AI language model for booking assistant',
              data: 'Anonymised booking context (no name or email sent to LLM)',
            },
          ].map((p) => (
            <div key={p.name} className="flex gap-2 py-2 border-b border-fixme-border/50 last:border-b-0">
              <div className="flex-1 min-w-0">
                <p className="text-fixme-text-primary text-xs font-semibold">{p.name}</p>
                <p className="text-fixme-text-muted text-[11px]">{p.purpose}</p>
                <p className="text-fixme-text-muted text-[10px] italic mt-0.5">Data: {p.data}</p>
              </div>
            </div>
          ))}
        </div>
      </SectionCard>

      {/* ── 4. Your rights ──────────────────────────────────── */}
      <SectionCard>
        <SectionTitle
          icon={'\u2696\uFE0F'}
          title="Your rights (GDPR)"
          subtitle="GDPR Articles 15\u201321 \u2014 all requests processed within 30 days"
        />

        <RightItem
          emoji={'\u{1F4E4}'}
          title="Right to access + portability (Art. 15 + 20)"
          description="Request a full copy of all personal data we hold — delivered in a machine-readable format."
          action={
            hasPendingOf('export') ? (
              <span className="flex-shrink-0 text-[10px] text-yellow-400 bg-yellow-500/10 border border-yellow-500/30 px-2 py-1 rounded-full">
                Pending
              </span>
            ) : (
              <button
                type="button"
                disabled={!!submitting}
                onClick={() => handleRequest('export')}
                className="flex-shrink-0 text-xs font-semibold text-fixme-accent border border-fixme-accent/40 px-3 py-1.5 rounded-full hover:bg-fixme-accent/10 transition-colors disabled:opacity-50"
              >
                {submitting === 'export' ? 'Sending\u2026' : 'Request export'}
              </button>
            )
          }
        />

        <RightItem
          emoji={'\u270F\uFE0F'}
          title="Right to rectification (Art. 16)"
          description="Correct inaccurate data — your name, email and preferences are all editable in Settings."
          action={
            <button
              type="button"
              onClick={() => { window.location.href = '/customer/settings'; }}
              className="flex-shrink-0 text-xs font-semibold text-fixme-text-secondary border border-fixme-border px-3 py-1.5 rounded-full hover:border-fixme-accent/40 transition-colors"
            >
              Settings
            </button>
          }
        />

        <RightItem
          emoji={'\u{1F6AB}'}
          title="Right to erasure (Art. 17)"
          description="Request deletion of your account and all associated personal data. Booking records may be retained 7 years for legal/financial obligations."
          action={
            hasPendingOf('deletion') ? (
              <span className="flex-shrink-0 text-[10px] text-yellow-400 bg-yellow-500/10 border border-yellow-500/30 px-2 py-1 rounded-full">
                Pending
              </span>
            ) : (
              <button
                type="button"
                onClick={() => setConfirm('deletion')}
                className="flex-shrink-0 text-xs font-semibold text-fixme-error border border-fixme-error/30 px-3 py-1.5 rounded-full hover:bg-fixme-error/10 transition-colors"
              >
                Request deletion
              </button>
            )
          }
        />

        <RightItem
          emoji={'\u{1F6D1}'}
          title="Right to object to AI processing (Art. 21 + AI Act)"
          description="Object to our AI reliability score or provider matching using your data. Contact us with details of your objection."
          action={
            <a
              href="mailto:privacy@fixmeapp.ai"
              className="flex-shrink-0 text-xs font-semibold text-fixme-text-secondary border border-fixme-border px-3 py-1.5 rounded-full hover:border-fixme-accent/40 transition-colors"
            >
              Contact DPO
            </a>
          }
        />

        <div className="mt-3 pt-3 border-t border-fixme-border/50">
          <p className="text-fixme-text-muted text-[11px] leading-relaxed">
            To exercise any right or ask a question about your data, you can also email{' '}
            <a href="mailto:privacy@fixmeapp.ai" className="text-fixme-accent underline">
              privacy@fixmeapp.ai
            </a>. We are required to respond within 30 days. You also have the right to lodge a
            complaint with your national data protection authority.
          </p>
        </div>
      </SectionCard>

      {/* ── 5. Active requests ──────────────────────────────── */}
      <SectionCard>
        <SectionTitle
          icon={'\u{1F4EC}'}
          title="My requests"
          subtitle="History of your data rights requests"
        />
        {requests.length === 0 ? (
          <p className="text-fixme-text-muted text-xs text-center py-3">No requests submitted yet</p>
        ) : (
          <div className="space-y-2">
            {requests.map((r) => (
              <div key={r.request_id} className="flex items-start gap-3 py-2 border-b border-fixme-border/50 last:border-b-0">
                <div className="flex-1 min-w-0">
                  <p className="text-fixme-text-primary text-xs font-semibold">
                    {TYPE_LABELS[r.request_type] || r.request_type}
                  </p>
                  <p className="text-fixme-text-muted text-[11px]">
                    {new Date(r.requested_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                  </p>
                  {r.notes && (
                    <p className="text-fixme-text-muted text-[11px] italic mt-0.5">{'\u201C'}{r.notes}{'\u201D'}</p>
                  )}
                </div>
                <span className={`flex-shrink-0 text-[10px] font-medium px-2 py-1 rounded-full border ${STATUS_COLOURS[r.status] || 'bg-fixme-border/40 text-fixme-text-muted border-fixme-border'}`}>
                  {STATUS_LABELS[r.status] || r.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      {/* ── Deletion confirmation dialog ─────────────────────── */}
      {confirm === 'deletion' && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 backdrop-blur-sm pb-6 px-4">
          <div className="bg-fixme-card border border-fixme-border rounded-2xl p-5 w-full max-w-sm space-y-4">
            <div className="text-center space-y-1">
              <p className="text-2xl">{'\u26A0\uFE0F'}</p>
              <p className="text-fixme-text-primary text-sm font-semibold">Request account deletion?</p>
              <p className="text-fixme-text-muted text-xs leading-relaxed">
                This will queue a deletion request. Our ops team will process it within 30 days.
                Booking records may be retained for up to 7 years as required by law.
              </p>
            </div>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setConfirm(null)}
                className="flex-1 rounded-xl border border-fixme-border py-3 text-sm font-semibold text-fixme-text-secondary hover:border-fixme-accent/40 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={submitting === 'deletion'}
                onClick={() => handleRequest('deletion')}
                className="flex-1 rounded-xl bg-fixme-error text-fixme-text-primary py-3 text-sm font-semibold disabled:opacity-60 transition-all"
              >
                {submitting === 'deletion' ? 'Submitting\u2026' : 'Yes, request deletion'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-5 py-2.5 rounded-full text-sm font-medium shadow-lg animate-slide-up max-w-[340px] text-center ${
          toast.type === 'error' ? 'bg-fixme-error text-fixme-text-primary' : 'bg-fixme-accent text-fixme-bg'
        }`}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}
