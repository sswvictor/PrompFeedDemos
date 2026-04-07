/**
 * ProviderFlow — Provider onboarding orchestrator
 *
 * Flow (matching mobile exactly):
 *   Step 0  →  Email + OTP auth             (inline, no progress bar)
 *   Step 1  →  StepInstagramConnect          (progress 1/3)
 *   Step 2  →  StepScrapeWebsite            (progress 2/3)
 *   Step 3  →  StepReview                   (progress 3/3) → createProvider → home
 *
 * Data layer lives here:
 *   - igData       set by StepInstagramConnect
 *   - scanResult   set by StepScrapeWebsite
 *   - draft        built from igData + scanResult before entering StepReview
 *   - handleCreateProvider  POSTs to /api/v1/onboarding/provider
 */
import { useEffect, useRef, useState } from 'react';
import { ROUTES } from '../../../app/routeCatalog';
import StepInstagramConnect from './StepInstagramConnect';
import StepScrapeWebsite   from './StepScrapeWebsite';
import StepReview          from './StepReview';

// ── Constants ────────────────────────────────────────────────────────────────

const TOTAL_STEPS = 3;

const ONBOARDING_HANDOFF_KEY = 'fixme_provider_onboarding_handoff';

const DEFAULT_HOURS = {
  Mon: { open: true,  start: '09:00', end: '18:00' },
  Tue: { open: true,  start: '09:00', end: '18:00' },
  Wed: { open: true,  start: '09:00', end: '18:00' },
  Thu: { open: true,  start: '09:00', end: '18:00' },
  Fri: { open: true,  start: '09:00', end: '17:00' },
  Sat: { open: true,  start: '10:00', end: '16:00' },
  Sun: { open: false, start: '10:00', end: '15:00' },
};

const DAY_INDEX = { Mon: 0, Tue: 1, Wed: 2, Thu: 3, Fri: 4, Sat: 5, Sun: 6 };

// ── Helpers ──────────────────────────────────────────────────────────────────

function toMinutes(hhmm) {
  const [h, m] = String(hhmm || '09:00').split(':').map(Number);
  return h * 60 + m;
}

function normalizeScannedServices(services) {
  return (Array.isArray(services) ? services : [])
    .map((s) => ({
      name:              (s?.name || s?.service_name || '').trim(),
      duration_minutes:  Number(s?.duration_minutes ?? s?.duration ?? 60) || 60,
      price_ex_vat:      s?.price_ex_vat != null ? Number(s.price_ex_vat) : null,
      price_inc_vat:     s?.price_inc_vat != null ? Number(s.price_inc_vat) : (s?.price != null ? Number(s.price) : null),
      price:             s?.price != null ? Number(s.price) : null,
      description:       s?.description || null,
      confidence:        s?.confidence || 'medium',
      keywords:          s?.keywords || null,
    }))
    .filter((s) => s.name);
}

/** Merge igData + scanData into the onboarding draft object. */
function buildDraft({ scanData, igData, handle }) {
  return {
    source_url:             scanData?.source_url || '',
    name:                   scanData?.name || igData?.name || '',
    city:                   scanData?.city || '',
    bio:                    scanData?.bio || igData?.biography || '',
    services:               Array.isArray(scanData?.services) ? scanData.services : [],
    working_hours:          scanData?.working_hours || {},
    amenity_keys:           Array.isArray(scanData?.amenity_keys) ? scanData.amenity_keys : [],
    booking_policy:         scanData?.booking_policy || '',
    cancellation_policy:    scanData?.cancellation_policy || '',
    instagram_username:     igData?.instagram_username || igData?.username || handle || '',
    ig_profile_picture_url: igData?.profile_picture_url || '',
    ig_user_id:             igData?.ig_user_id || igData?.instagram_user_id || null,
    ig_access_token:        null,
    ai_vibe_tags:           Array.isArray(scanData?.ai_vibe_tags) ? scanData.ai_vibe_tags : [],
    vibe_summary:           scanData?.vibe_summary || null,
  };
}

function resolveFallbackName(email) {
  const local = String(email || '').split('@')[0]?.trim();
  if (!local) return 'New Provider';
  return local.charAt(0).toUpperCase() + local.slice(1);
}

async function parseResponseSafe(res) {
  const raw = await res.text();
  if (!raw) return {};
  try { return JSON.parse(raw); }
  catch { return { detail: raw.slice(0, 200) || 'Unexpected server response' }; }
}

function saveOnboardingHandoff({ accessToken, email, type }) {
  try {
    sessionStorage.setItem(ONBOARDING_HANDOFF_KEY, JSON.stringify({
      accessToken, email: (email || '').toLowerCase(), type,
    }));
  } catch { /* non-blocking */ }
}

function consumeOnboardingHandoff({ type, email }) {
  try {
    const raw = sessionStorage.getItem(ONBOARDING_HANDOFF_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const normalizedEmail = (email || '').toLowerCase();
    const handoffEmail    = (parsed.email || '').toLowerCase();
    if (parsed.type !== type) return null;
    if (normalizedEmail && handoffEmail && normalizedEmail !== handoffEmail) return null;
    sessionStorage.removeItem(ONBOARDING_HANDOFF_KEY);
    return parsed;
  } catch { return null; }
}

function clearOnboardingHandoff() {
  try { sessionStorage.removeItem(ONBOARDING_HANDOFF_KEY); } catch { /* ignore */ }
}

// ── ProviderFlow ─────────────────────────────────────────────────────────────

export default function ProviderFlow({ mode = 'onboarding' }) {
  const params          = new URLSearchParams(window.location.search);
  const type            = params.get('type') || 'freelancer';
  const prefilledEmail  = params.get('email') || '';
  const isSalon         = type === 'salon';
  const isLoginFlow     = mode === 'login';
  const homeRoute       = isSalon ? ROUTES.salon.home       : ROUTES.provider.home;
  const loginRoute      = isSalon ? ROUTES.salon.login      : ROUTES.provider.login;
  const onboardingRoute = isSalon ? ROUTES.salon.onboarding : ROUTES.provider.onboarding;

  // Redirect immediately if already logged in
  useEffect(() => {
    const token      = localStorage.getItem('fixme_provider_token');
    const providerId = localStorage.getItem('fixme_provider_id');
    if (token && providerId) window.location.replace(homeRoute);
  }, [homeRoute]);

  // Start at step 1 if handoff token already exists (e.g. page reload)
  const initialStep = (() => {
    if (isLoginFlow) return 0;
    try {
      const raw = sessionStorage.getItem(ONBOARDING_HANDOFF_KEY);
      if (!raw) return 0;
      const parsed = JSON.parse(raw);
      if (parsed.type !== type) return 0;
      return 1;
    } catch { return 0; }
  })();

  // ── State ───────────────────────────────────────────────────────────────────
  const dirRef       = useRef('forward');
  const customBackRef = useRef(null); // steps register phase-aware back handlers here

  const [step,       setStep]       = useState(initialStep);
  const [authToken,  setAuthToken]  = useState(null);
  const [authEmail,  setAuthEmail]  = useState(prefilledEmail);

  // OTP form state
  const [authCodeSent, setAuthCodeSent] = useState(false);
  const [authCode,     setAuthCode]     = useState('');
  const [devCode,      setDevCode]      = useState(null);
  const [submitting,   setSubmitting]   = useState(false);
  const [error,        setError]        = useState('');

  // Onboarding data collected across steps
  const [igData,       setIgData]       = useState(null);
  const [onboardingDraft, setOnboardingDraft] = useState(null);

  // Consume handoff token on mount (page navigated from ProviderWelcomePage)
  useEffect(() => {
    if (isLoginFlow) return;
    const handoff = consumeOnboardingHandoff({ type, email: prefilledEmail });
    if (!handoff?.accessToken) return;
    setAuthToken(handoff.accessToken);
    if (handoff.email) setAuthEmail(handoff.email);
    dirRef.current = 'forward';
    setStep(1);
    window.scrollTo({ top: 0, behavior: 'instant' });
  }, [isLoginFlow, prefilledEmail, type]);

  // ── Navigation helpers ──────────────────────────────────────────────────────

  const next = () => {
    setError('');
    dirRef.current = 'forward';
    setStep((s) => Math.min(s + 1, TOTAL_STEPS));
    window.scrollTo({ top: 0, behavior: 'instant' });
  };

  const back = () => {
    setError('');
    if (customBackRef.current) { customBackRef.current(); return; }
    if (step <= 1) { window.location.href = ROUTES.legacy.onboardingRoot; return; }
    dirRef.current = 'back';
    setStep((s) => s - 1);
    window.scrollTo({ top: 0, behavior: 'instant' });
  };

  // ── Auth handlers (step 0) ──────────────────────────────────────────────────

  const handleSendCode = async () => {
    if (!authEmail.trim()) { setError('Enter your email'); return; }
    setError(''); setSubmitting(true);
    try {
      const res  = await fetch('/api/v1/auth/provider/send-code', {
        method:      'POST',
        credentials: 'include',
        headers:     { 'Content-Type': 'application/json' },
        body:        JSON.stringify({ email: authEmail.trim() }),
      });
      const data = await parseResponseSafe(res);
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setAuthCodeSent(true);
      if (data.dev_code) setDevCode(data.dev_code);
    } catch (e) { setError(e.message); }
    finally { setSubmitting(false); }
  };

  const handleVerifyCodeWith = async (code) => {
    if (!code?.trim()) { setError('Enter the 6-digit code'); return; }
    setError(''); setSubmitting(true);
    try {
      const normalizedEmail = authEmail.trim().toLowerCase();
      const res  = await fetch('/api/v1/auth/provider/verify-code', {
        method:      'POST',
        credentials: 'include',   // ← browser stores the httpOnly cookie from response
        headers:     { 'Content-Type': 'application/json' },
        body:        JSON.stringify({ email: normalizedEmail, code: code.trim() }),
      });
      const data = await parseResponseSafe(res);
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

      if (data.has_provider_profile) {
        // Existing provider — persist session and go home
        localStorage.setItem('fixme_provider_token',   data.access_token);
        localStorage.setItem('fixme_provider_persona', isSalon ? 'salon' : 'provider');
        localStorage.setItem('fixme_provider_email',   normalizedEmail);
        if (data.provider_id) {
          localStorage.setItem('fixme_provider_id', data.provider_id);
          if (data.slug) localStorage.setItem('fixme_provider_slug', data.slug);
        }
        clearOnboardingHandoff();
        window.location.replace(homeRoute);
        return;
      }

      if (isLoginFlow) {
        saveOnboardingHandoff({ accessToken: data.access_token, email: normalizedEmail, type });
        window.location.replace(`${onboardingRoute}?type=${encodeURIComponent(type)}&email=${encodeURIComponent(normalizedEmail)}`);
        return;
      }

      setAuthToken(data.access_token);
      dirRef.current = 'forward';
      setStep(1);
      window.scrollTo({ top: 0, behavior: 'instant' });
    } catch (e) { setError(e.message); }
    finally { setSubmitting(false); }
  };

  // ── Create provider (called from StepReview Finish or Skip) ─────────────────

  const handleCreateProvider = async (draft) => {
    setError(''); setSubmitting(true);
    try {
      const resolvedName       = (draft?.name || resolveFallbackName(authEmail)).trim();
      const normalizedServices = normalizeScannedServices(draft?.services);

      const body = {
        name:                  resolvedName,
        phone:                 null,
        city:                  draft?.city || null,
        bio:                   draft?.bio || null,
        instagram_username:    draft?.instagram_username || null,
        business_type:         isSalon ? 'owner' : 'freelancer',
        service_categories:    [],
        amenity_keys:          Array.isArray(draft?.amenity_keys) ? draft.amenity_keys : [],
        home_service:          false,
        location_salon:        null,
        parent_provider_id:    null,
        scanned_services:      normalizedServices,
        booking_policy:        draft?.booking_policy || null,
        cancellation_policy:   draft?.cancellation_policy || null,
        ig_access_token:       draft?.ig_access_token || null,
        ig_user_id:            draft?.ig_user_id || null,
      };

      const res = await fetch('/api/v1/onboarding/provider', {
        method:      'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        },
        body: JSON.stringify(body),
      });
      const data = await parseResponseSafe(res);
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

      // Persist session to localStorage (Phase 2 will remove this)
      localStorage.setItem('fixme_provider_token',   authToken);
      localStorage.setItem('fixme_provider_persona', isSalon ? 'salon' : 'provider');
      localStorage.setItem('fixme_provider_email',   authEmail.trim().toLowerCase());
      localStorage.setItem('fixme_provider_name',    resolvedName);
      localStorage.setItem('fixme_provider_id',      data.provider_id);
      if (data.slug) localStorage.setItem('fixme_provider_slug', data.slug);
      clearOnboardingHandoff();

      // Apply working hours (fire-and-forget, non-blocking)
      const hours = draft?.working_hours && Object.keys(draft.working_hours).length > 0
        ? draft.working_hours
        : DEFAULT_HOURS;

      Object.entries(hours).forEach(([day, value]) => {
        if (!value?.open || !value?.start || !value?.end) return;
        fetch('/api/v1/availability/hours', {
          method:      'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
          },
          body: JSON.stringify({
            provider_id:    data.provider_id,
            day_of_week:    DAY_INDEX[day],
            start_minutes:  toMinutes(value.start),
            end_minutes:    toMinutes(value.end),
          }),
        }).catch(() => {});
      });

      // Vibe/AI analysis (fire-and-forget)
      if (draft?.ai_vibe_tags || draft?.vibe_summary) {
        fetch('/api/v1/intelligence/analyze', {
          method:      'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
          },
          body: JSON.stringify({ scan_data: draft }),
        }).catch(() => {});
      }

      window.location.replace(homeRoute);
    } catch (e) {
      setError(e.message || 'Could not create provider profile.');
    } finally { setSubmitting(false); }
  };

  // Build a minimal fallback draft for skip flows
  const buildFallbackDraft = () => buildDraft({
    scanData: null,
    igData:   igData,
    handle:   igData?.instagram_username || '',
  });

  // ── Step 0: Auth (OTP) ──────────────────────────────────────────────────────

  if (step === 0) {
    return (
      <div className="flex flex-col min-h-screen bg-fixme-bg px-5 pt-10 pb-8 max-w-sm mx-auto">
        <button
          onClick={() => window.location.href = ROUTES.legacy.onboardingRoot}
          className="text-fixme-text-muted hover:text-fixme-text-secondary transition-colors mb-8 self-start text-lg leading-none"
          aria-label="Back"
        >
          ←
        </button>

        <p className="text-fixme-text-muted text-[11px] font-semibold uppercase tracking-widest mb-8 text-center">
          Fixmeapp
        </p>

        {!authCodeSent ? (
          <div className="animate-fade-in flex flex-col gap-0">
            <h1 className="text-fixme-text-primary text-2xl font-bold mb-2 leading-snug">
              {isLoginFlow ? 'Log in' : "What's your email?"}
            </h1>
            <p className="text-fixme-text-secondary text-sm mb-6 leading-relaxed">
              {isLoginFlow
                ? 'Enter your email to access your account.'
                : "We'll send a 6-digit code. No password needed."}
            </p>

            <input
              type="email"
              autoComplete="email"
              value={authEmail}
              onChange={(e) => { setAuthEmail(e.target.value); setError(''); }}
              placeholder="you@email.com"
              className="w-full bg-fixme-card border border-fixme-border rounded-2xl px-4 py-3 text-fixme-text-primary placeholder-fixme-text-muted text-sm focus:outline-none focus:border-fixme-accent transition-colors mb-3"
              onKeyDown={(e) => e.key === 'Enter' && handleSendCode()}
            />
            {error && <p className="text-fixme-error text-xs mb-3">{error}</p>}
            <button
              onClick={handleSendCode}
              disabled={submitting}
              className="w-full bg-fixme-accent hover:bg-fixme-accent-light text-fixme-bg font-semibold text-sm rounded-2xl py-4 active:scale-[0.97] transition-all duration-150 disabled:opacity-50"
            >
              {submitting ? 'Sending…' : isLoginFlow ? 'Continue' : 'Send code'}
            </button>
            <p className="text-fixme-text-muted text-xs text-center mt-4">No spam, ever.</p>
          </div>
        ) : (
          <div className="animate-fade-in flex flex-col gap-0">
            <h1 className="text-fixme-text-primary text-2xl font-bold mb-2">Check your email</h1>
            <p className="text-fixme-text-secondary text-sm mb-6">
              Code sent to <span className="text-fixme-accent">{authEmail}</span>
            </p>

            {devCode && (
              <div className="bg-fixme-card border border-fixme-border rounded-xl px-4 py-3 mb-4 text-center">
                <p className="text-fixme-text-muted text-[10px] mb-1 uppercase tracking-widest">Dev code</p>
                <p className="text-fixme-accent font-bold text-2xl tracking-[0.4em]">{devCode}</p>
              </div>
            )}

            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              value={authCode}
              onChange={(e) => {
                const val = e.target.value.replace(/\D/g, '').slice(0, 6);
                setAuthCode(val);
                setError('');
                if (val.length === 6) setTimeout(() => handleVerifyCodeWith(val), 100);
              }}
              placeholder="000000"
              maxLength={6}
              className="w-full bg-fixme-card border border-fixme-border rounded-2xl px-4 py-5 text-fixme-text-primary placeholder-fixme-text-muted/30 text-3xl text-center tracking-[0.4em] font-bold focus:outline-none focus:border-fixme-accent transition-colors mb-3"
              onKeyDown={(e) => e.key === 'Enter' && handleVerifyCodeWith(authCode)}
            />
            <p className="text-fixme-text-muted text-[11px] text-center mb-4">
              Auto-verifies when you type all 6 digits
            </p>
            {error && <p className="text-fixme-error text-xs mb-3 text-center">{error}</p>}

            <button
              onClick={() => handleVerifyCodeWith(authCode)}
              disabled={submitting}
              className="w-full bg-fixme-accent hover:bg-fixme-accent-light text-fixme-bg font-semibold text-sm rounded-2xl py-4 active:scale-[0.97] transition-all duration-150 disabled:opacity-50"
            >
              {submitting ? 'Verifying…' : isLoginFlow ? 'Log in' : 'Verify'}
            </button>
            <button
              onClick={() => { setAuthCodeSent(false); setAuthCode(''); setDevCode(null); setError(''); clearOnboardingHandoff(); }}
              className="w-full text-fixme-text-muted text-xs mt-3 text-center hover:text-fixme-text-secondary transition-colors"
            >
              Use a different email
            </button>
          </div>
        )}
      </div>
    );
  }

  // ── Step 3: StepReview owns its own full-screen layout ──────────────────────

  if (step === 3 && onboardingDraft) {
    return (
      <StepReview
        draft={onboardingDraft}
        igData={igData}
        onFinish={(confirmedDraft) => handleCreateProvider(confirmedDraft)}
        onSkip={() => handleCreateProvider(onboardingDraft)}
      />
    );
  }

  // ── Steps 1-2: Onboarding with progress bar ──────────────────────────────────

  const animClass = dirRef.current === 'forward' ? 'animate-step-forward' : 'animate-step-back';

  return (
    <div className="flex flex-col min-h-screen bg-fixme-bg">

      {/* Sticky header with progress bar */}
      <div className="sticky top-0 z-10 bg-fixme-bg/95 backdrop-blur-md border-b border-fixme-border/30 px-5 py-3">
        <div className="flex items-center justify-between max-w-sm mx-auto">
          <button
            onClick={back}
            className="text-fixme-text-muted hover:text-fixme-text-secondary transition-colors w-7 text-lg leading-none"
          >
            ←
          </button>
          <p className="text-fixme-text-muted text-[11px] font-semibold uppercase tracking-widest">
            Fixmeapp
          </p>
          <span className="text-fixme-text-muted text-[11px] w-7 text-right">
            {step}/{TOTAL_STEPS}
          </span>
        </div>

        {/* Progress segments */}
        <div className="flex gap-1 mt-2.5 max-w-sm mx-auto">
          {Array.from({ length: TOTAL_STEPS }, (_, i) => (
            <div
              key={i}
              className="h-[2px] flex-1 rounded-full transition-all duration-400"
              style={{ background: i < step || step === TOTAL_STEPS ? '#F5F5F0' : 'rgba(245,245,240,0.12)' }}
            />
          ))}
        </div>
      </div>

      {/* Step content */}
      <div key={step} className={`${animClass} flex-1 px-5 pt-6 pb-8 max-w-sm mx-auto w-full`}>
        {error && (
          <p className="text-fixme-error text-xs mb-4 text-center">{error}</p>
        )}

        {/* ── Step 1: Instagram connect ── */}
        {step === 1 && (
          <StepInstagramConnect
            token={authToken}
            onComplete={(data) => {
              setIgData(data);
              next();
            }}
            onSkip={() => {
              setIgData(null);
              next();
            }}
          />
        )}

        {/* ── Step 2: Website scrape ── */}
        {step === 2 && (
          <StepScrapeWebsite
            token={authToken}
            onComplete={({ scanData, websiteUrl: _url }) => {
              const draft = buildDraft({
                scanData,
                igData,
                handle: igData?.instagram_username || '',
              });
              setOnboardingDraft(draft);
              next();
            }}
            onSkip={() => {
              const draft = buildDraft({ scanData: null, igData, handle: igData?.instagram_username || '' });
              setOnboardingDraft(draft);
              next();
            }}
            onBack={() => {
              dirRef.current = 'back';
              setStep(1);
              window.scrollTo({ top: 0, behavior: 'instant' });
            }}
            onCustomBackChange={(fn) => { customBackRef.current = fn; }}
          />
        )}

      </div>
    </div>
  );
}
