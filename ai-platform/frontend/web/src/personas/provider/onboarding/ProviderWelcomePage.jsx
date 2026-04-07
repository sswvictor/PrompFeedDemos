/**
 * ProviderWelcomePage — /provider/welcome
 *
 * Cinematic entry for service providers.
 * Three internal phases managed with smooth CSS transitions:
 *
 *   splash  →  email  →  otp
 *
 * On successful OTP verification:
 *   - New user:      saves ONBOARDING_HANDOFF_KEY → navigates to /provider/onboarding
 *   - Existing user: saves token to localStorage → navigates to /provider/home
 */

import { useState } from 'react';
import { ROUTES } from '../../../app/routeCatalog';

const ONBOARDING_HANDOFF_KEY = 'fixme_provider_onboarding_handoff';

const SPLASH_LINES = [
  { text: 'More clients booked.', delay: 400  },
  { text: 'Fewer DMs to answer.', delay: 900  },
  { text: "That's the deal.",     delay: 1300 },
];

async function parseResponseSafe(res) {
  const raw = await res.text();
  if (!raw) return {};
  try { return JSON.parse(raw); }
  catch { return { detail: raw.slice(0, 200) || 'Unexpected server response' }; }
}

export default function ProviderWelcomePage() {
  const params       = new URLSearchParams(window.location.search);
  const type         = params.get('type') || 'freelancer';
  const isFreelancer = type === 'freelancer';

  const homeRoute      = isFreelancer ? ROUTES.provider.home      : ROUTES.salon.home;
  const loginRoute     = isFreelancer ? ROUTES.provider.login     : ROUTES.salon.login;
  const onboardRoute   = isFreelancer ? ROUTES.provider.onboarding : ROUTES.salon.onboarding;

  /* ── Phase machine ─────────────────────────────────────────────────────── */
  const [phase,         setPhase]         = useState('splash');  // 'splash' | 'email' | 'otp'
  const [exiting,       setExiting]       = useState(false);
  const [splashVisited, setSplashVisited] = useState(false);     // skip long delays on return

  const transitionTo = (next) => {
    if (exiting) return;
    if (phase === 'splash') setSplashVisited(true);
    setExiting(true);
    setTimeout(() => { setPhase(next); setExiting(false); }, 360);
  };

  /* ── Auth state ────────────────────────────────────────────────────────── */
  const [email,      setEmail]      = useState('');
  const [code,       setCode]       = useState('');
  const [devCode,    setDevCode]    = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error,      setError]      = useState('');

  /* ── Handlers ──────────────────────────────────────────────────────────── */

  const handleSendCode = async () => {
    if (!email.trim()) { setError('Enter your email'); return; }
    setError(''); setSubmitting(true);
    try {
      const res  = await fetch('/api/v1/auth/provider/send-code', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ email: email.trim() }),
      });
      const data = await parseResponseSafe(res);
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      if (data.dev_code) setDevCode(data.dev_code);
      transitionTo('otp');
    } catch (e) { setError(e.message); }
    finally { setSubmitting(false); }
  };

  const handleVerifyCodeWith = async (codeVal) => {
    if (!codeVal?.trim()) { setError('Enter the 6-digit code'); return; }
    setError(''); setSubmitting(true);
    try {
      const normalizedEmail = email.trim().toLowerCase();
      const res  = await fetch('/api/v1/auth/provider/verify-code', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ email: normalizedEmail, code: codeVal.trim() }),
      });
      const data = await parseResponseSafe(res);
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

      /* Existing provider — go straight to home */
      if (data.has_provider_profile) {
        if (data.access_token) {
          localStorage.setItem('fixme_provider_token',   data.access_token);
          localStorage.setItem('fixme_provider_persona', isFreelancer ? 'provider' : 'salon');
          localStorage.setItem('fixme_provider_email',   normalizedEmail);
        }
        if (data.provider_id) {
          localStorage.setItem('fixme_provider_id', data.provider_id);
          if (data.slug) localStorage.setItem('fixme_provider_slug', data.slug);
        }
        window.location.replace(homeRoute);
        return;
      }

      /* New user — clear any previous provider session so the ProviderFlow
         localStorage guard doesn't immediately redirect back to home */
      localStorage.removeItem('fixme_provider_token');
      localStorage.removeItem('fixme_provider_id');
      localStorage.removeItem('fixme_provider_slug');

      /* Save handoff token and enter onboarding */
      try {
        sessionStorage.setItem(ONBOARDING_HANDOFF_KEY, JSON.stringify({
          accessToken: data.access_token,
          email:       normalizedEmail,
          type,
        }));
      } catch { /* non-blocking */ }

      window.location.replace(
        `${onboardRoute}?type=${encodeURIComponent(type)}&email=${encodeURIComponent(normalizedEmail)}`
      );
    } catch (e) { setError(e.message); }
    finally { setSubmitting(false); }
  };

  /* ── Transition styles ─────────────────────────────────────────────────── */
  const exitStyle = {
    opacity:   exiting ? 0 : 1,
    transform: exiting ? 'translateY(-12px)' : 'translateY(0)',
    filter:    exiting ? 'blur(3px)' : 'blur(0)',
    transition: 'opacity 0.33s ease, transform 0.33s ease, filter 0.33s ease',
  };

  /* ── Render ────────────────────────────────────────────────────────────── */
  return (
    <div className="flex flex-col min-h-screen bg-fixme-bg overflow-hidden">
      <div className="flex-1 flex flex-col px-6 max-w-sm mx-auto w-full">

        {/* ── SPLASH ──────────────────────────────────────────────────────── */}
        {phase === 'splash' && (
          <div className="flex-1 flex flex-col pt-10 pb-12" style={exitStyle}>

            {/* Wordmark */}
            <p className="text-fixme-text-muted text-[9px] font-bold uppercase tracking-[0.42em] animate-fade-in">
              Fixmeapp
            </p>

            {/* Headline — lines reveal one by one (instant on return visits) */}
            <div className="mt-auto mb-10">
              {SPLASH_LINES.map((line, i) => (
                <div
                  key={i}
                  className="animate-line-reveal overflow-hidden"
                  style={{ animationDelay: splashVisited ? '0ms' : `${line.delay}ms` }}
                >
                  <h1 className="text-fixme-text-primary font-bold leading-[1.15] tracking-tight"
                    style={{ fontSize: 'clamp(28px, 8.5vw, 34px)' }}
                  >
                    {line.text}
                  </h1>
                </div>
              ))}

              {/* Descriptor */}
              <p
                className="text-fixme-text-muted text-sm leading-relaxed mt-5 animate-line-reveal"
                style={{ animationDelay: splashVisited ? '80ms' : '1900ms' }}
              >
                Fixmeapp handles your DMs, scheduling, and invoices —
                automatically. You focus on the work,
                we handle the rest.
              </p>
            </div>

            {/* CTA */}
            <div
              className="flex flex-col gap-3 animate-cta-reveal"
              style={{ animationDelay: splashVisited ? '140ms' : '2700ms' }}
            >
              <button
                onClick={() => transitionTo('email')}
                className="w-full bg-fixme-accent hover:bg-fixme-accent-light text-fixme-bg font-semibold text-sm rounded-2xl py-4 active:scale-[0.97] transition-all duration-150"
              >
                I'm ready →
              </button>

              <button
                onClick={() => { window.location.href = loginRoute; }}
                className="w-full text-fixme-text-muted text-xs text-center hover:text-fixme-text-secondary transition-colors py-1"
              >
                Already have an account? Sign in
              </button>
            </div>

            {/* Ambient indicator — ethical AI attribution */}
            <div
              className="flex items-center gap-2.5 mt-8 animate-cta-reveal"
              style={{ animationDelay: splashVisited ? '200ms' : '3200ms' }}
            >
              <div className="flex gap-1">
                {[0, 1, 2].map(i => (
                  <div
                    key={i}
                    className="w-1 h-1 rounded-full bg-fixme-accent/25"
                    style={{ animation: `pulse 2s ease-in-out ${i * 350}ms infinite` }}
                  />
                ))}
              </div>
              <span className="text-fixme-text-muted text-[10px] tracking-wider">
                Privacy-first · No ads · You own your data
              </span>
            </div>

          </div>
        )}

        {/* ── EMAIL ───────────────────────────────────────────────────────── */}
        {phase === 'email' && (
          <div className="flex-1 flex flex-col pt-10 pb-12 animate-step-forward" style={exitStyle}>

            <button
              onClick={() => transitionTo('splash')}
              className="text-fixme-text-muted hover:text-fixme-text-secondary transition-colors self-start text-lg leading-none mb-10"
              aria-label="Back"
            >
              ←
            </button>

            <p className="text-fixme-text-muted text-[9px] font-bold uppercase tracking-[0.42em] mb-10">
              Fixmeapp
            </p>

            <h1 className="text-fixme-text-primary text-2xl font-bold mb-2 leading-snug">
              What's your email?
            </h1>
            <p className="text-fixme-text-secondary text-sm mb-8 leading-relaxed">
              We'll send a 6-digit code. No password, ever.
            </p>

            <input
              type="email"
              autoComplete="email"
              autoFocus
              value={email}
              onChange={(e) => { setEmail(e.target.value); setError(''); }}
              onKeyDown={(e) => e.key === 'Enter' && handleSendCode()}
              placeholder="you@email.com"
              className="w-full bg-fixme-card border border-fixme-border rounded-2xl px-4 py-3.5 text-fixme-text-primary placeholder-fixme-text-muted text-sm focus:outline-none focus:border-fixme-accent transition-colors mb-3"
            />

            {error && (
              <p className="text-fixme-error text-xs mb-3 animate-fade-in">{error}</p>
            )}

            <button
              onClick={handleSendCode}
              disabled={submitting}
              className="w-full bg-fixme-accent hover:bg-fixme-accent-light text-fixme-bg font-semibold text-sm rounded-2xl py-4 active:scale-[0.97] transition-all duration-150 disabled:opacity-50"
            >
              {submitting ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-3.5 h-3.5 border-2 border-fixme-bg/40 border-t-fixme-bg rounded-full animate-spin" />
                  Sending…
                </span>
              ) : 'Send code →'}
            </button>

            <p className="text-fixme-text-muted text-xs text-center mt-6">
              No spam. Unsubscribe anytime.
            </p>

          </div>
        )}

        {/* ── OTP ─────────────────────────────────────────────────────────── */}
        {phase === 'otp' && (
          <div className="flex-1 flex flex-col pt-10 pb-12 animate-step-forward" style={exitStyle}>

            <button
              onClick={() => {
                transitionTo('email');
                setCode(''); setDevCode(null); setError('');
              }}
              className="text-fixme-text-muted hover:text-fixme-text-secondary transition-colors self-start text-lg leading-none mb-10"
              aria-label="Back"
            >
              ←
            </button>

            <p className="text-fixme-text-muted text-[9px] font-bold uppercase tracking-[0.42em] mb-10">
              Fixmeapp
            </p>

            <h1 className="text-fixme-text-primary text-2xl font-bold mb-2">
              Check your inbox
            </h1>
            <p className="text-fixme-text-secondary text-sm mb-8 leading-relaxed">
              Code sent to{' '}
              <span className="text-fixme-accent font-medium">{email}</span>
            </p>

            {/* Dev code hint (non-production only) */}
            {devCode && (
              <div className="bg-fixme-card border border-fixme-border rounded-xl px-4 py-3 mb-5 text-center animate-fade-in">
                <p className="text-fixme-text-muted text-[10px] mb-1 uppercase tracking-widest">Dev code</p>
                <p className="text-fixme-accent font-bold text-2xl tracking-[0.4em]">{devCode}</p>
              </div>
            )}

            {/* Big digit input */}
            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              autoFocus
              value={code}
              onChange={(e) => {
                const val = e.target.value.replace(/\D/g, '').slice(0, 6);
                setCode(val);
                setError('');
                if (val.length === 6) setTimeout(() => handleVerifyCodeWith(val), 120);
              }}
              onKeyDown={(e) => e.key === 'Enter' && handleVerifyCodeWith(code)}
              placeholder="000000"
              maxLength={6}
              className="w-full bg-fixme-card border border-fixme-border rounded-2xl px-4 py-5 text-fixme-text-primary placeholder-fixme-text-muted/25 text-[34px] text-center tracking-[0.55em] font-bold focus:outline-none focus:border-fixme-accent transition-colors mb-2"
            />

            <p className="text-fixme-text-muted text-[11px] text-center mb-5">
              Auto-verifies on the 6th digit
            </p>

            {error && (
              <p className="text-fixme-error text-xs mb-4 text-center animate-fade-in">{error}</p>
            )}

            <button
              onClick={() => handleVerifyCodeWith(code)}
              disabled={submitting}
              className="w-full bg-fixme-accent hover:bg-fixme-accent-light text-fixme-bg font-semibold text-sm rounded-2xl py-4 active:scale-[0.97] transition-all duration-150 disabled:opacity-50"
            >
              {submitting ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-3.5 h-3.5 border-2 border-fixme-bg/40 border-t-fixme-bg rounded-full animate-spin" />
                  Verifying…
                </span>
              ) : 'Verify →'}
            </button>

            <button
              onClick={() => {
                transitionTo('email');
                setCode(''); setDevCode(null); setError('');
              }}
              className="text-fixme-text-muted text-xs text-center mt-5 hover:text-fixme-text-secondary transition-colors"
            >
              Use a different email
            </button>

          </div>
        )}

      </div>
    </div>
  );
}
