/**
 * SetupWizard — appears at the top of the provider dashboard after onboarding.
 *
 * Two dismissible cards:
 *   1. Profile Import  — paste URL → scrape → AI preview → apply to profile
 *   2. Business Verify — org number (+ optional doc) → Verified Pro badge
 *
 * Dismissal stored in localStorage. Dismissed (but incomplete) items are
 * signalled to the parent via onHasPending so the Profile tab can show
 * an attention dot.
 */

import { useState, useEffect } from 'react';

const SK_IMPORT  = 'fixme_setup_import_dismissed';
const SK_VERIFY  = 'fixme_setup_verify_dismissed';
const SK_IMPORT_DONE = 'fixme_setup_import_done';
const SK_VERIFY_DONE = 'fixme_setup_verify_done';

const SCAN_HINTS = ['Booking page', 'Your website', 'Instagram', 'Menu / price list'];

// ── helpers ──────────────────────────────────────────────────────────────────

function ls(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}
function lsSet(key, val) {
  try { localStorage.setItem(key, val); } catch {}
}

function XButton({ onClick, label = 'Dismiss' }) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full text-fixme-text-muted hover:text-fixme-text-secondary hover:bg-fixme-border/60 transition-all text-xs"
    >
      ✕
    </button>
  );
}

function GoldStar() {
  return <span className="text-fixme-text-secondary text-xs flex-shrink-0">✦</span>;
}

// ── ImportCard ────────────────────────────────────────────────────────────────

function ImportCard({ token, onDismiss }) {
  const [url, setUrl]                   = useState('');
  const [loading, setLoading]           = useState(false);
  const [error, setError]               = useState('');
  const [preview, setPreview]           = useState(null);   // extracted data
  const [applying, setApplying]         = useState(false);
  const [done, setDone]                 = useState(false);

  const handleScan = async () => {
    const clean = url.trim();
    if (!clean) { setError('Paste a URL to scan'); return; }
    setLoading(true); setError('');
    try {
      const res = await fetch('/api/v1/setup/import-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ url: clean }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data?.detail || 'Could not scan that URL. Try another.'); return; }
      setPreview(data);
    } catch {
      setError('Network error — check your connection.');
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async () => {
    setApplying(true);
    setError('');
    try {
      const res = await fetch('/api/v1/setup/import-apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(preview),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data?.detail || 'Could not apply imported profile data.');
        return;
      }
    } catch {
      setError('Network error while applying import.');
      return;
    } finally {
      setApplying(false);
    }
    setDone(true);
    lsSet(SK_IMPORT_DONE, 'true');
    setTimeout(() => onDismiss(), 1800);
  };

  // ── Done state ──────────────────────────────────────────────────────────────
  if (done) {
    return (
      <div className="bg-fixme-card border border-fixme-success/30 rounded-2xl px-4 py-4 flex items-center gap-3 animate-scale-in">
        <div className="w-8 h-8 rounded-full bg-fixme-success/15 flex items-center justify-center flex-shrink-0">
          <svg className="w-4 h-4 text-fixme-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <div>
          <p className="text-fixme-text-primary text-sm font-semibold">Profile imported!</p>
          <p className="text-fixme-text-muted text-xs mt-0.5">Check your settings to review what was added.</p>
        </div>
      </div>
    );
  }

  // ── Preview state ───────────────────────────────────────────────────────────
  if (preview) {
    const previewAmenities = preview.amenity_keys || preview.amenities || [];
    const fields = [
      preview.bio          && { label: 'Bio',                value: preview.bio.slice(0, 80) + (preview.bio.length > 80 ? '...' : '') },
      preview.services?.length && { label: `Services (${preview.services.length})`, value: preview.services.slice(0, 3).map(s => s.name).join(', ') + (preview.services.length > 3 ? '...' : '') },
      preview.working_hours && { label: 'Working hours',     value: formatHoursSummary(preview.working_hours) },
      previewAmenities.length && { label: 'Amenities',       value: previewAmenities.slice(0, 4).join(', ') },
      preview.cancellation_policy && { label: 'Cancellation policy', value: preview.cancellation_policy.slice(0, 60) + '...' },
    ].filter(Boolean);

    return (
      <div className="bg-fixme-card border border-fixme-accent/20 rounded-2xl p-4 flex flex-col gap-3 animate-scale-in">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <GoldStar />
            <p className="text-fixme-text-primary text-sm font-semibold">
              Found {fields.length} item{fields.length !== 1 ? 's' : ''} to import
            </p>
          </div>
          <XButton onClick={() => setPreview(null)} label="Back to URL input" />
        </div>

        <div className="flex flex-col gap-2">
          {fields.map((f, i) => (
            <div key={i} className="flex items-start gap-2.5">
              <div className="w-1.5 h-1.5 rounded-full bg-fixme-text-muted mt-1.5 flex-shrink-0" />
              <div className="min-w-0">
                <span className="text-fixme-text-muted text-[11px] uppercase tracking-wider font-semibold">{f.label}: </span>
                <span className="text-fixme-text-secondary text-xs">{f.value}</span>
              </div>
            </div>
          ))}
        </div>

        {error && <p className="text-fixme-error text-xs">{error}</p>}

        <div className="flex gap-2">
          <button
            onClick={handleApply}
            disabled={applying}
            className="flex-1 bg-fixme-accent hover:bg-fixme-accent-light text-fixme-bg font-semibold text-xs rounded-xl py-3 active:scale-[0.97] transition-all disabled:opacity-50"
          >
            {applying ? 'Applying…' : 'Apply to my profile'}
          </button>
          <button
            onClick={() => { setPreview(null); setUrl(''); }}
            className="bg-fixme-bg border border-fixme-border text-fixme-text-muted text-xs rounded-xl px-3 hover:border-fixme-accent/30 transition-all"
          >
            Try another
          </button>
        </div>
        <p className="text-fixme-text-muted text-[10px]">
          You can review and edit everything in Settings after applying.
        </p>
      </div>
    );
  }

  // ── Default (URL input) state ───────────────────────────────────────────────
  return (
    <div className="bg-fixme-card border border-fixme-border rounded-2xl p-4 flex flex-col gap-3"
      style={{ boxShadow: '0 4px 24px rgba(0,0,0,0.4)' }}>

      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <GoldStar />
          <p className="text-fixme-text-primary text-sm font-semibold">Import your existing profile</p>
        </div>
        <XButton onClick={onDismiss} />
      </div>

      <p className="text-fixme-text-secondary text-xs leading-relaxed">
        Paste the link to your booking page or website — our AI reads it and fills in your services, hours, and prices automatically.
      </p>

      {/* URL input */}
      <div className="flex items-center gap-2">
        <div className="flex-1 flex items-center bg-fixme-bg border border-fixme-border rounded-xl overflow-hidden focus-within:border-fixme-accent transition-colors">
          <input
            type="url"
            inputMode="url"
            placeholder="Your booking page or website URL"
            value={url}
            onChange={(e) => { setUrl(e.target.value); setError(''); }}
            onKeyDown={(e) => e.key === 'Enter' && handleScan()}
            className="flex-1 bg-transparent px-3 py-2.5 text-fixme-text-primary placeholder-fixme-text-muted text-xs focus:outline-none"
          />
        </div>
        <button
          onClick={handleScan}
          disabled={loading}
          className="bg-fixme-accent hover:bg-fixme-accent-light text-fixme-bg font-semibold text-xs rounded-xl px-3 py-2.5 active:scale-[0.97] transition-all disabled:opacity-50 flex-shrink-0 whitespace-nowrap"
        >
          {loading ? (
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 border-2 border-fixme-bg/40 border-t-fixme-bg rounded-full animate-spin inline-block" />
              Scanning
            </span>
          ) : 'Scan →'}
        </button>
      </div>

      {error && <p className="text-fixme-error text-xs">{error}</p>}

      {/* Hint chips */}
      <div className="flex flex-wrap gap-1.5">
        {SCAN_HINTS.map(h => (
          <span key={h} className="text-fixme-text-muted text-[10px] px-2 py-0.5 bg-fixme-bg border border-fixme-border rounded-full">
            {h}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── VerifyCard ────────────────────────────────────────────────────────────────

const US_STATES = [
  ['AL','Alabama'],['AK','Alaska'],['AZ','Arizona'],['AR','Arkansas'],['CA','California'],
  ['CO','Colorado'],['CT','Connecticut'],['DE','Delaware'],['FL','Florida'],['GA','Georgia'],
  ['HI','Hawaii'],['ID','Idaho'],['IL','Illinois'],['IN','Indiana'],['IA','Iowa'],
  ['KS','Kansas'],['KY','Kentucky'],['LA','Louisiana'],['ME','Maine'],['MD','Maryland'],
  ['MA','Massachusetts'],['MI','Michigan'],['MN','Minnesota'],['MS','Mississippi'],['MO','Missouri'],
  ['MT','Montana'],['NE','Nebraska'],['NV','Nevada'],['NH','New Hampshire'],['NJ','New Jersey'],
  ['NM','New Mexico'],['NY','New York'],['NC','North Carolina'],['ND','North Dakota'],['OH','Ohio'],
  ['OK','Oklahoma'],['OR','Oregon'],['PA','Pennsylvania'],['RI','Rhode Island'],['SC','South Carolina'],
  ['SD','South Dakota'],['TN','Tennessee'],['TX','Texas'],['UT','Utah'],['VT','Vermont'],
  ['VA','Virginia'],['WA','Washington'],['WV','West Virginia'],['WI','Wisconsin'],['WY','Wyoming'],
];

const US_LICENSE_TYPES = [
  'Cosmetologist','Barber','Esthetician','Nail Technician','Massage Therapist',
  'Hair Braider','Electrologist','Makeup Artist','Other',
];

const COUNTRY_OPTIONS = [
  { code: 'US', label: '🇺🇸 United States' },
  { code: 'GB', label: '🇬🇧 United Kingdom' },
  { code: 'SE', label: '🇸🇪 Sweden' },
  { code: 'DE', label: '🇩🇪 Germany' },
  { code: 'ES', label: '🇪🇸 Spain' },
  { code: 'OTHER', label: '🌍 Other country' },
];

function VerifyCard({ token, onDismiss }) {
  const [open, setOpen]               = useState(false);
  const [country, setCountry]         = useState('US');
  const [usState, setUsState]         = useState('');
  const [licenseType, setLicenseType] = useState('');
  const [licenseNumber, setLicenseNumber] = useState('');
  const [orgNumber, setOrgNumber]     = useState('');
  const [docFile, setDocFile]         = useState(null);
  const [submitting, setSubmitting]   = useState(false);
  const [error, setError]             = useState('');
  const [done, setDone]               = useState(false);

  const isUS = country === 'US';

  const handleSubmit = async () => {
    setError('');
    if (isUS) {
      if (!usState)              { setError('Select your state'); return; }
      if (!licenseType)          { setError('Select your license type'); return; }
      if (!licenseNumber.trim()) { setError('Enter your license number'); return; }
    } else {
      if (!orgNumber.trim()) { setError('Enter your registration / org number'); return; }
    }

    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append('country', country);
      if (isUS) {
        fd.append('us_state', usState);
        fd.append('license_type', licenseType);
        fd.append('license_number', licenseNumber.trim());
      } else {
        fd.append('org_number', orgNumber.trim());
      }
      if (docFile) fd.append('document', docFile);

      const res = await fetch('/api/v1/setup/verify-business', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      const data = await res.json();
      if (!res.ok) { setError(data?.detail || 'Verification failed — try again'); return; }
      setDone(true);
      lsSet(SK_VERIFY_DONE, 'true');
      setTimeout(() => onDismiss(), 2500);
    } catch {
      setError('Network error — check your connection.');
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <div className="bg-fixme-card border border-fixme-success/30 rounded-2xl px-4 py-4 flex items-center gap-3 animate-scale-in">
        <div className="w-8 h-8 rounded-full bg-fixme-success/15 flex items-center justify-center flex-shrink-0">
          <svg className="w-4 h-4 text-fixme-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <div>
          <p className="text-fixme-text-primary text-sm font-semibold">Verification submitted!</p>
          <p className="text-fixme-text-muted text-xs mt-0.5">We'll review within 24 h. Your badge appears once approved.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-fixme-card border border-fixme-border rounded-2xl p-4 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          {/* Shield icon */}
          <svg className="w-3.5 h-3.5 text-fixme-text-muted flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
          <p className="text-fixme-text-primary text-sm font-semibold">Get your Verified Pro badge</p>
        </div>
        <XButton onClick={onDismiss} />
      </div>

      <p className="text-fixme-text-secondary text-xs leading-relaxed">
        Verified pros get 3× more client trust. Takes 2 minutes — just your state license number.
      </p>

      {!open ? (
        <button
          onClick={() => setOpen(true)}
          className="self-start text-xs font-semibold text-fixme-text-primary border border-fixme-border rounded-xl px-3 py-2 hover:border-fixme-accent/40 active:scale-[0.97] transition-all"
        >
          Start verification →
        </button>
      ) : (
        <div className="flex flex-col gap-3 animate-fade-in">

          {/* Country */}
          <div>
            <label className="block text-fixme-text-muted text-[11px] font-semibold uppercase tracking-widest mb-1.5">
              Country
            </label>
            <select
              value={country}
              onChange={(e) => { setCountry(e.target.value); setError(''); }}
              className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2.5 text-fixme-text-primary text-xs focus:outline-none focus:border-fixme-accent transition-colors appearance-none cursor-pointer"
            >
              {COUNTRY_OPTIONS.map(({ code, label }) => (
                <option key={code} value={code}>{label}</option>
              ))}
            </select>
          </div>

          {isUS ? (
            <>
              {/* State */}
              <div>
                <label className="block text-fixme-text-muted text-[11px] font-semibold uppercase tracking-widest mb-1.5">
                  State
                </label>
                <select
                  value={usState}
                  onChange={(e) => { setUsState(e.target.value); setError(''); }}
                  className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2.5 text-fixme-text-primary text-xs focus:outline-none focus:border-fixme-accent transition-colors appearance-none cursor-pointer"
                >
                  <option value="">Select state…</option>
                  {US_STATES.map(([code, name]) => (
                    <option key={code} value={code}>{name}</option>
                  ))}
                </select>
              </div>

              {/* License type */}
              <div>
                <label className="block text-fixme-text-muted text-[11px] font-semibold uppercase tracking-widest mb-1.5">
                  License type
                </label>
                <select
                  value={licenseType}
                  onChange={(e) => { setLicenseType(e.target.value); setError(''); }}
                  className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2.5 text-fixme-text-primary text-xs focus:outline-none focus:border-fixme-accent transition-colors appearance-none cursor-pointer"
                >
                  <option value="">Select license type…</option>
                  {US_LICENSE_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>

              {/* License number */}
              <div>
                <label className="block text-fixme-text-muted text-[11px] font-semibold uppercase tracking-widest mb-1.5">
                  License number
                </label>
                <input
                  type="text"
                  placeholder="e.g. C123456"
                  value={licenseNumber}
                  onChange={(e) => { setLicenseNumber(e.target.value); setError(''); }}
                  className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2.5 text-fixme-text-primary placeholder-fixme-text-muted text-xs focus:outline-none focus:border-fixme-accent transition-colors"
                />
                <p className="text-fixme-text-muted text-[10px] mt-1">
                  Issued by your state cosmetology / barbering board
                </p>
              </div>
            </>
          ) : (
            /* Non-US: org / registration number */
            <div>
              <label className="block text-fixme-text-muted text-[11px] font-semibold uppercase tracking-widest mb-1.5">
                Business / registration number
              </label>
              <input
                type="text"
                placeholder="e.g. 12345678 or 556000-0000"
                value={orgNumber}
                onChange={(e) => { setOrgNumber(e.target.value); setError(''); }}
                className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2.5 text-fixme-text-primary placeholder-fixme-text-muted text-xs focus:outline-none focus:border-fixme-accent transition-colors"
              />
            </div>
          )}

          {/* Optional doc upload */}
          <div>
            <label className="block text-fixme-text-muted text-[11px] font-semibold uppercase tracking-widest mb-1.5">
              Supporting document <span className="normal-case font-normal text-fixme-text-muted">(optional — speeds up review)</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer group">
              <div className="flex-1 flex items-center gap-2 bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2.5 group-hover:border-fixme-accent/30 transition-colors">
                <svg className="w-4 h-4 text-fixme-text-muted flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                </svg>
                <span className="text-xs text-fixme-text-muted truncate">
                  {docFile ? docFile.name : isUS ? 'Attach license photo, business cert…' : 'Attach business cert, registration doc…'}
                </span>
              </div>
              <input
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                className="sr-only"
                onChange={(e) => setDocFile(e.target.files?.[0] || null)}
              />
            </label>
            <p className="text-fixme-text-muted text-[10px] mt-1">PDF, JPG or PNG — our team reviews it manually</p>
          </div>

          {error && <p className="text-fixme-error text-xs">{error}</p>}

          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="w-full bg-fixme-accent hover:bg-fixme-accent-light text-fixme-bg font-semibold text-xs rounded-xl py-3 active:scale-[0.97] transition-all disabled:opacity-50"
          >
            {submitting ? 'Submitting…' : 'Submit for review'}
          </button>
        </div>
      )}
    </div>
  );
}

// ── Root SetupWizard ──────────────────────────────────────────────────────────

export default function SetupWizard({ token, onHasPending }) {
  const [importDismissed, setImportDismissed] = useState(() => ls(SK_IMPORT) === 'true');
  const [verifyDismissed, setVerifyDismissed] = useState(() => ls(SK_VERIFY) === 'true');

  // Notify parent whether there are pending (dismissed but undone) items
  useEffect(() => {
    const hasPending = (
      (importDismissed && ls(SK_IMPORT_DONE) !== 'true') ||
      (verifyDismissed && ls(SK_VERIFY_DONE) !== 'true')
    );
    onHasPending?.(hasPending);
  }, [importDismissed, verifyDismissed]);

  const dismissImport = () => {
    lsSet(SK_IMPORT, 'true');
    setImportDismissed(true);
  };
  const dismissVerify = () => {
    lsSet(SK_VERIFY, 'true');
    setVerifyDismissed(true);
  };

  // Both dismissed → nothing to show
  if (importDismissed && verifyDismissed) return null;

  return (
    <div className="mb-6 flex flex-col gap-3">
      {/* Section label */}
      <p className="text-fixme-text-muted text-[11px] font-semibold uppercase tracking-widest">
        Finish setting up
      </p>

      {!importDismissed && (
        <ImportCard token={token} onDismiss={dismissImport} />
      )}

      {!verifyDismissed && (
        <VerifyCard token={token} onDismiss={dismissVerify} />
      )}
    </div>
  );
}

// ── helpers ───────────────────────────────────────────────────────────────────

function formatHoursSummary(hours) {
  if (!hours || typeof hours !== 'object') return '';
  const open = Object.entries(hours)
    .filter(([, v]) => v?.open)
    .map(([day]) => day);
  if (!open.length) return 'Closed';
  if (open.length >= 5) return `${open[0]}–${open[open.length - 1]}`;
  return open.join(', ');
}
