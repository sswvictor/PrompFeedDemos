/**
 * StepReview — Onboarding step 3 (full-screen, self-contained)
 *
 * Multi-step wizard matching mobile review.tsx exactly:
 *   Step 0: Identity   — Instagram profile pic, @username, followers
 *   Step 1: Business   — name, city, cancellation, hours, amenities
 *   Steps 2..N: [Cat]  — one step per AI-detected service category
 *
 * Dynamic progress bar: 2 + number of service categories segments.
 * Slide + fade transition between steps.
 */
import { useEffect, useMemo, useRef, useState } from 'react';

// ── Design helpers ────────────────────────────────────────────────────────────

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const DAY_SHORT = { Monday:'Mon', Tuesday:'Tue', Wednesday:'Wed', Thursday:'Thu', Friday:'Fri', Saturday:'Sat', Sunday:'Sun' };

const KNOWN_AMENITIES = [
  { key: 'parking',      label: 'Parking nearby' },
  { key: 'dogs_allowed', label: 'Dogs allowed' },
  { key: 'private_room', label: 'Private room' },
  { key: 'wifi',         label: 'WiFi' },
  { key: 'card_payment', label: 'Card payment' },
  { key: 'coffee',       label: 'Coffee & drinks' },
  { key: 'accessible',   label: 'Wheelchair accessible' },
  { key: 'music',        label: 'Music' },
];

function fmtFollowers(n) {
  if (!n) return null;
  if (n >= 1000) return (n / 1000).toFixed(1).replace('.0', '') + 'k';
  return String(n);
}

function toInitials(s) {
  return (s || '')
    .split(' ')
    .map((w) => w[0] ?? '')
    .join('')
    .toUpperCase()
    .slice(0, 2) || '?';
}

function cleanServiceName(name) {
  return (name || '')
    .replace(/\s*[-–|,]?\s*\d+\s*(min(uter?|utes?)?|h(rs?|ours?)?|tim(mar|me)?)\.?\b/gi, '')
    .replace(/\s*\(\d+\s*(min|h)\)/gi, '')
    .trim();
}

/** Parse draft.working_hours (various backend formats) into { [fullDay]: { enabled, open, close } } */
function parseHours(raw) {
  const result = {};
  DAYS.forEach((day) => {
    const short = DAY_SHORT[day];
    const v = raw?.[short] ?? raw?.[day] ?? raw?.[day.toLowerCase()] ?? null;
    if (!v) {
      result[day] = { enabled: ['Monday','Tuesday','Wednesday','Thursday','Friday'].includes(day), open: '09:00', close: '18:00' };
      return;
    }
    if (typeof v === 'string') {
      const [open = '09:00', close = '18:00'] = v.split(/[-–]/);
      result[day] = { enabled: true, open: open.trim(), close: close.trim() };
    } else {
      result[day] = {
        enabled: v.open !== false,
        open:    v.start ?? v.open_time  ?? '09:00',
        close:   v.end   ?? v.close_time ?? '18:00',
      };
    }
  });
  return result;
}

// ── Sub-components ────────────────────────────────────────────────────────────

/** Click-to-edit field — tap value or "Edit" to open input */
function EditableRow({ label, value, onChange, multiline, placeholder }) {
  const [editing, setEditing] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (editing && ref.current) ref.current.focus();
  }, [editing]);

  return (
    <div className="mb-5">
      <p className="text-fixme-text-muted text-[10px] font-bold uppercase tracking-[0.32em] mb-1.5">{label}</p>
      {editing ? (
        multiline ? (
          <textarea
            ref={ref}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onBlur={() => setEditing(false)}
            placeholder={placeholder}
            rows={3}
            className="w-full bg-fixme-card border border-fixme-accent/40 rounded-xl px-3 py-2.5 text-sm text-fixme-text-primary placeholder-fixme-text-muted focus:outline-none resize-none"
          />
        ) : (
          <input
            ref={ref}
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onBlur={() => setEditing(false)}
            onKeyDown={(e) => e.key === 'Enter' && setEditing(false)}
            placeholder={placeholder}
            className="w-full bg-fixme-card border border-fixme-accent/40 rounded-xl px-3 py-2.5 text-sm text-fixme-text-primary placeholder-fixme-text-muted focus:outline-none"
          />
        )
      ) : (
        <div
          className="flex items-start justify-between gap-3 cursor-pointer group"
          onClick={() => setEditing(true)}
        >
          <p className={`text-sm flex-1 leading-relaxed ${value ? 'text-fixme-text-primary' : 'text-fixme-text-muted'}`}>
            {value || (placeholder ?? 'Not found — tap to add')}
          </p>
          <span className="text-fixme-text-muted text-xs group-hover:text-fixme-text-secondary transition-colors mt-0.5 shrink-0">
            Edit
          </span>
        </div>
      )}
    </div>
  );
}

function HoursRow({ day, hours, onChange }) {
  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-fixme-border/50 last:border-0">
      <span className={`text-xs w-8 shrink-0 ${hours.enabled ? 'text-fixme-text-secondary' : 'text-fixme-text-muted'}`}>
        {DAY_SHORT[day]}
      </span>
      <button
        type="button"
        onClick={() => onChange(day, { ...hours, enabled: !hours.enabled })}
        className={`relative w-10 h-6 rounded-full transition-colors shrink-0 ${hours.enabled ? 'bg-fixme-success/60' : 'bg-fixme-border'}`}
      >
        <span className={`absolute left-0.5 top-0.5 w-5 h-5 rounded-full bg-white shadow-sm transition-transform duration-200 ${hours.enabled ? 'translate-x-4' : 'translate-x-0'}`} />
      </button>
      {hours.enabled ? (
        <div className="flex items-center gap-1.5 flex-1">
          <input
            type="time"
            value={hours.open}
            onChange={(e) => onChange(day, { ...hours, open: e.target.value })}
            className="flex-1 bg-fixme-card border border-fixme-border rounded-lg px-2 py-1 text-xs text-fixme-text-primary focus:outline-none text-center"
          />
          <span className="text-fixme-text-muted text-xs">–</span>
          <input
            type="time"
            value={hours.close}
            onChange={(e) => onChange(day, { ...hours, close: e.target.value })}
            className="flex-1 bg-fixme-card border border-fixme-border rounded-lg px-2 py-1 text-xs text-fixme-text-primary focus:outline-none text-center"
          />
        </div>
      ) : (
        <span className="text-fixme-text-muted text-xs">Closed</span>
      )}
    </div>
  );
}

function AmenityChip({ label, active, onToggle }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`px-3 py-1.5 rounded-full border text-xs transition-colors ${
        active
          ? 'border-fixme-success/40 bg-fixme-success/10 text-fixme-success font-semibold'
          : 'border-fixme-border bg-white/[0.03] text-fixme-text-muted hover:border-[#3A3A3A]'
      }`}
    >
      {label}
    </button>
  );
}

function ServiceEditRow({ service, index, onChange }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="border-b border-fixme-border/50 py-3.5 last:border-0">
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded((e) => !e)}
      >
        <div className="flex-1 min-w-0 mr-3">
          <p className="text-fixme-text-primary text-sm font-medium truncate">
            {service.name || 'Unnamed service'}
          </p>
          <p className="text-fixme-text-muted text-xs mt-0.5">
            {[service.price ? service.price + ' kr' : null, service.duration ? service.duration + ' min' : null]
              .filter(Boolean).join('  ·  ') || 'No details'}
          </p>
        </div>
        <span className="text-fixme-text-muted text-xs shrink-0">{expanded ? 'Done' : 'Edit'}</span>
      </div>

      {expanded && (
        <div className="mt-3 space-y-2">
          <input
            type="text"
            value={service.name}
            onChange={(e) => onChange(index, { ...service, name: e.target.value })}
            placeholder="Service name"
            className="w-full bg-fixme-bg border border-fixme-border rounded-lg px-3 py-2 text-sm text-fixme-text-primary focus:outline-none"
          />
          <div className="flex gap-2">
            <input
              type="number"
              value={service.price}
              onChange={(e) => onChange(index, { ...service, price: e.target.value })}
              placeholder="Price (kr)"
              className="flex-1 bg-fixme-bg border border-fixme-border rounded-lg px-3 py-2 text-sm text-fixme-text-primary focus:outline-none"
            />
            <input
              type="number"
              value={service.duration}
              onChange={(e) => onChange(index, { ...service, duration: e.target.value })}
              placeholder="Duration (min)"
              className="flex-1 bg-fixme-bg border border-fixme-border rounded-lg px-3 py-2 text-sm text-fixme-text-primary focus:outline-none"
            />
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function StepReview({ draft, igData, onFinish, onSkip }) {
  // ── Build dynamic step list from service categories ───────────────────────
  const { steps, servicesByCategory } = useMemo(() => {
    const rawServices = Array.isArray(draft?.services) ? draft.services : [];
    const catMap = {};
    rawServices.forEach((s) => {
      const cat = (s.category || 'Other').trim();
      if (!catMap[cat]) catMap[cat] = [];
      catMap[cat].push({
        name:     cleanServiceName(s.name ?? ''),
        category: cat,
        price:    String(s.price_ex_vat ?? s.price ?? ''),
        duration: String(s.duration_minutes ?? s.duration ?? ''),
      });
    });
    const cats = Object.keys(catMap);
    return {
      steps:              ['identity', 'business', ...cats.map((c) => `cat:${c}`)],
      servicesByCategory: catMap,
    };
  }, [draft]);

  const [stepIdx,    setStepIdx]    = useState(0);
  const [busy,       setBusy]       = useState(false);
  const [error,      setError]      = useState('');
  const [animState,  setAnimState]  = useState('visible'); // 'visible' | 'exit' | 'enter'
  const [direction,  setDirection]  = useState('forward');

  // ── Editable state ────────────────────────────────────────────────────────
  const [name,          setName]          = useState(draft?.name || '');
  const [city,          setCity]          = useState(draft?.city || '');
  const [cancelPolicy,  setCancelPolicy]  = useState(draft?.cancellation_policy || draft?.booking_policy || '');
  const [bookingPolicy, setBookingPolicy] = useState(draft?.booking_policy || '');
  const [hours,         setHours]         = useState(() => parseHours(draft?.working_hours));
  const [amenities,     setAmenities]     = useState(new Set(Array.isArray(draft?.amenity_keys) ? draft.amenity_keys : []));
  const [serviceMap,    setServiceMap]    = useState(servicesByCategory);

  function updateHour(day, h) { setHours((prev) => ({ ...prev, [day]: h })); }
  function toggleAmenity(key) {
    setAmenities((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }
  function updateService(cat, i, updated) {
    setServiceMap((prev) => ({
      ...prev,
      [cat]: prev[cat].map((s, idx) => (idx === i ? updated : s)),
    }));
  }

  // ── Animation ─────────────────────────────────────────────────────────────
  function transition(nextIdx, dir) {
    setDirection(dir);
    setAnimState('exit');
    setTimeout(() => {
      setStepIdx(nextIdx);
      setAnimState('enter');
      window.scrollTo({ top: 0, behavior: 'instant' });
      setTimeout(() => setAnimState('visible'), 300);
    }, 140);
  }

  function goNext() { transition(stepIdx + 1, 'forward'); }
  function goBack() { if (stepIdx > 0) transition(stepIdx - 1, 'back'); }

  const currentStep = steps[stepIdx] ?? 'identity';
  const isLast      = stepIdx === steps.length - 1;
  const catKey      = currentStep.startsWith('cat:') ? currentStep.slice(4) : null;
  const catServices = catKey ? (serviceMap[catKey] ?? []) : [];

  const animStyle = {
    transition: animState === 'exit'
      ? 'opacity 140ms ease-in, transform 140ms ease-in'
      : 'opacity 300ms ease-out, transform 300ms ease-out',
    opacity:   animState === 'visible' ? 1 : 0,
    transform: animState === 'exit'
      ? `translateX(${direction === 'forward' ? '-24px' : '24px'})`
      : animState === 'enter'
      ? `translateX(${direction === 'forward' ? '24px' : '-24px'})`
      : 'translateX(0)',
  };

  // ── Finish ────────────────────────────────────────────────────────────────
  function handleFinish() {
    const allServices = Object.values(serviceMap).flat();
    const workingHours = {};
    DAYS.forEach((day) => {
      const h = hours[day];
      const short = DAY_SHORT[day];
      workingHours[short] = {
        open:  h?.enabled ?? false,
        start: h?.enabled ? (h.open  || '09:00') : null,
        end:   h?.enabled ? (h.close || '18:00') : null,
      };
    });

    onFinish?.({
      ...draft,
      name,
      city,
      cancellation_policy: cancelPolicy,
      booking_policy:      bookingPolicy,
      amenity_keys:        Array.from(amenities),
      working_hours:       workingHours,
      services:            allServices.map((s) => ({
        name:             s.name,
        category:         s.category || null,
        price_ex_vat:     s.price    ? parseFloat(s.price)  : null,
        duration_minutes: s.duration ? parseInt(s.duration) : null,
      })),
    });
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col min-h-screen bg-fixme-bg">
      <style>{`
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(16px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      {/* ── Sticky header + dynamic progress bar ── */}
      <div className="sticky top-0 z-10 bg-fixme-bg/95 backdrop-blur-md border-b border-fixme-border/30 px-5 py-3">
        <div className="flex items-center justify-between max-w-sm mx-auto">
          <button
            type="button"
            onClick={stepIdx > 0 ? goBack : onSkip}
            className="text-fixme-text-muted hover:text-fixme-text-secondary transition-colors w-7 text-lg leading-none"
          >
            ←
          </button>
          <p className="text-fixme-text-muted text-[11px] font-semibold uppercase tracking-widest">
            Fixmeapp
          </p>
          <span className="text-fixme-text-muted text-[11px] w-7 text-right">
            {stepIdx + 1}/{steps.length}
          </span>
        </div>

        {/* Dynamic segments */}
        <div className="flex gap-1 mt-2.5 max-w-sm mx-auto">
          {steps.map((_, i) => (
            <div
              key={i}
              className="h-[2px] flex-1 rounded-full transition-all duration-400"
              style={{ background: i <= stepIdx ? '#F5F5F0' : 'rgba(245,245,240,0.12)' }}
            />
          ))}
        </div>
      </div>

      {/* ── Animated step content ── */}
      <div className="flex-1 px-5 pt-6 pb-32 max-w-sm mx-auto w-full" style={animStyle}>

        {/* ── Identity step ── */}
        {currentStep === 'identity' && (
          <div style={{ animation: 'fadeSlideUp 0.4s cubic-bezier(0.22,1,0.36,1) both' }}>
            <div className="mb-8">
              <p className="text-fixme-text-muted text-[10px] font-bold uppercase tracking-[0.32em] mb-2">
                This is you
              </p>
              <h2 className="text-fixme-text-primary text-[28px] font-extrabold leading-tight tracking-tight">
                Your Instagram{'\n'}profile
              </h2>
            </div>

            {/* Profile card */}
            <div className="bg-fixme-card border border-fixme-border rounded-3xl p-7 flex flex-col items-center gap-4">
              {/* Avatar */}
              <div
                className="w-[90px] h-[90px] rounded-full overflow-hidden flex items-center justify-center border-2"
                style={{ borderColor: 'rgba(200,169,126,0.25)', backgroundColor: 'rgba(200,169,126,0.12)' }}
              >
                {(igData?.profile_picture_url || draft?.ig_profile_picture_url) ? (
                  <img
                    src={igData?.profile_picture_url || draft?.ig_profile_picture_url}
                    alt="Instagram profile"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <span className="text-fixme-accent text-2xl font-bold">
                    {toInitials(igData?.instagram_username || draft?.instagram_username || 'U')}
                  </span>
                )}
              </div>

              {/* Username + followers */}
              <div className="text-center space-y-1">
                <p className="text-fixme-text-primary text-xl font-bold">
                  @{igData?.instagram_username || igData?.username || draft?.instagram_username || '—'}
                </p>
                {fmtFollowers(igData?.followers_count) && (
                  <p className="text-fixme-text-muted text-sm">
                    {fmtFollowers(igData?.followers_count)} followers
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── Business step ── */}
        {currentStep === 'business' && (
          <div style={{ animation: 'fadeSlideUp 0.4s cubic-bezier(0.22,1,0.36,1) both' }}>
            <div className="mb-8">
              <p className="text-fixme-text-muted text-[10px] font-bold uppercase tracking-[0.32em] mb-2">
                From your website
              </p>
              <h2 className="text-fixme-text-primary text-[28px] font-extrabold leading-tight tracking-tight">
                Your business
              </h2>
            </div>

            <EditableRow label="Business name"       value={name}          onChange={setName}          placeholder="Your business name" />
            <EditableRow label="City"                value={city}          onChange={setCity}          placeholder="City" />
            <EditableRow label="Cancellation policy" value={cancelPolicy}  onChange={setCancelPolicy}  placeholder="e.g. 24h notice required" multiline />
            <EditableRow label="Booking policy"      value={bookingPolicy} onChange={setBookingPolicy} placeholder="e.g. Pay on arrival" multiline />

            {/* Working hours */}
            <div className="mb-6">
              <p className="text-fixme-text-muted text-[10px] font-bold uppercase tracking-[0.32em] mb-3">
                Working hours
              </p>
              <div className="bg-fixme-card border border-fixme-border rounded-2xl px-4 py-1">
                {DAYS.map((day) => (
                  <HoursRow
                    key={day}
                    day={day}
                    hours={hours[day]}
                    onChange={updateHour}
                  />
                ))}
              </div>
            </div>

            {/* Amenities */}
            <div>
              <p className="text-fixme-text-muted text-[10px] font-bold uppercase tracking-[0.32em] mb-3">
                Amenities
              </p>
              <div className="flex flex-wrap gap-2">
                {KNOWN_AMENITIES.map((a) => (
                  <AmenityChip
                    key={a.key}
                    label={a.label}
                    active={amenities.has(a.key)}
                    onToggle={() => toggleAmenity(a.key)}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── Service category step ── */}
        {catKey && (
          <div style={{ animation: 'fadeSlideUp 0.4s cubic-bezier(0.22,1,0.36,1) both' }}>
            <div className="mb-8">
              <p className="text-fixme-text-muted text-[10px] font-bold uppercase tracking-[0.32em] mb-2">
                {catServices.length} service{catServices.length !== 1 ? 's' : ''} found
              </p>
              <h2 className="text-fixme-text-primary text-[28px] font-extrabold leading-tight tracking-tight">
                {catKey}
              </h2>
            </div>

            {catServices.length > 0 ? (
              <div className="bg-fixme-card border border-fixme-border rounded-2xl px-4">
                {catServices.map((s, i) => (
                  <ServiceEditRow
                    key={i}
                    service={s}
                    index={i}
                    onChange={(idx, updated) => updateService(catKey, idx, updated)}
                  />
                ))}
              </div>
            ) : (
              <p className="text-fixme-text-muted text-sm">
                No services found — add them from settings after launch.
              </p>
            )}
          </div>
        )}

        {error && (
          <p className="text-fixme-error text-xs text-center mt-4">{error}</p>
        )}
      </div>

      {/* ── Sticky bottom nav ── */}
      <div className="fixed bottom-0 left-0 right-0 bg-fixme-bg/95 backdrop-blur-md border-t border-fixme-border/30 px-5 pt-3 pb-6">
        <div className="flex items-center justify-between max-w-sm mx-auto">
          {stepIdx > 0 ? (
            <button
              type="button"
              onClick={goBack}
              disabled={busy}
              className="text-fixme-text-muted text-sm hover:text-fixme-text-secondary transition-colors disabled:opacity-40"
            >
              ← Back
            </button>
          ) : (
            <button
              type="button"
              onClick={onSkip}
              className="text-fixme-text-muted text-xs hover:text-fixme-text-secondary transition-colors"
            >
              Skip all
            </button>
          )}

          {!isLast ? (
            <button
              type="button"
              onClick={goNext}
              className="bg-[#F5F5F0] hover:bg-[#FAFAFA] text-[#0A0A0A] font-bold text-sm rounded-2xl px-6 py-3 active:scale-[0.97] transition-all duration-150"
            >
              {currentStep === 'identity' ? 'Looks right →' : 'Approve →'}
            </button>
          ) : (
            <button
              type="button"
              onClick={handleFinish}
              disabled={busy}
              className="bg-[#F5F5F0] hover:bg-[#FAFAFA] text-[#0A0A0A] font-bold text-sm rounded-2xl px-6 py-3 active:scale-[0.97] transition-all duration-150 disabled:opacity-50 flex items-center gap-2"
            >
              {busy ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-[#0A0A0A]/30 border-t-[#0A0A0A] rounded-full animate-spin" />
                  Saving…
                </>
              ) : 'Finish →'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
