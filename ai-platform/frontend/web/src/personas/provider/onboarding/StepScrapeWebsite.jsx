/**
 * StepScrapeWebsite — Onboarding step 2
 *
 * One job: get the website URL, trigger the AI scan, pass results forward.
 *
 * Phases:
 *   input     → URL input field + Go button
 *   analyzing → pulsing rings + live scan step labels
 *
 * Back (during input)     → calls onBack() — ProviderFlow goes to step 1
 * Back (during analyzing) → cancels scan, returns to input phase (via onCustomBackChange)
 * Skip                    → calls onSkip() — ProviderFlow advances with no scan data
 * Go (success)            → calls onComplete({ scanData, websiteUrl })
 * Go (error)              → shows error inline, stays in input phase
 */
import { useRef, useState } from 'react';

const SCAN_STEPS = [
  'Connecting to your website…',
  'Extracting services & prices…',
  'Reading your opening hours…',
  'Reviewing policies…',
];

async function parseJsonSafe(res) {
  const text = await res.text();
  if (!text) return {};
  try { return JSON.parse(text); }
  catch { return { detail: text.slice(0, 220) }; }
}

export default function StepScrapeWebsite({ token, onComplete, onSkip, onBack, onCustomBackChange }) {
  const [phase,       setPhase]       = useState('input');
  const [websiteUrl,  setWebsiteUrl]  = useState('');
  const [scanStep,    setScanStep]    = useState(0);
  const [error,       setError]       = useState('');

  const scanGenRef      = useRef(0);
  const stepIntervalRef = useRef(null);

  // Register/unregister custom back handler based on phase.
  // During 'analyzing', back cancels the scan and returns to input.
  function setPhaseWithBack(next) {
    if (next === 'analyzing') {
      onCustomBackChange?.(() => {
        scanGenRef.current++;
        if (stepIntervalRef.current) {
          clearInterval(stepIntervalRef.current);
          stepIntervalRef.current = null;
        }
        setPhase('input');
        onCustomBackChange?.(null);
      });
    } else {
      onCustomBackChange?.(null);
    }
    setPhase(next);
  }

  async function handleGo() {
    const clean = websiteUrl.trim();
    if (!clean) { setError('Paste your website or booking page URL.'); return; }
    setError('');
    setScanStep(0);
    setPhaseWithBack('analyzing');

    const thisGen = ++scanGenRef.current;

    const interval = setInterval(() => {
      setScanStep((prev) => Math.min(prev + 1, SCAN_STEPS.length - 1));
    }, 2200);
    stepIntervalRef.current = interval;

    try {
      const url = clean.startsWith('http') ? clean : `https://${clean}`;

      let res = await fetch('/api/v1/setup/scan-website', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ url }),
      });

      // Fallback endpoint
      if (res.status === 404 || res.status === 405) {
        res = await fetch('/api/v1/setup/import-url', {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ url }),
        });
      }

      clearInterval(interval);
      stepIntervalRef.current = null;

      if (scanGenRef.current !== thisGen) return; // user backed out

      const data = await parseJsonSafe(res);
      if (!res.ok) throw new Error(data.detail || `Website scan failed (${res.status})`);

      onComplete?.({ scanData: data, websiteUrl: url });
    } catch (err) {
      clearInterval(interval);
      stepIntervalRef.current = null;
      if (scanGenRef.current !== thisGen) return;
      setError(err.message || 'Could not scan your website right now. Try again or skip.');
      setPhaseWithBack('input');
    }
  }

  /* ── Analyzing phase ──────────────────────────────────────────────────── */
  if (phase === 'analyzing') {
    return (
      <div
        className="flex flex-col items-center text-center gap-8 py-8"
        style={{ animation: 'fadeSlideUp 0.4s cubic-bezier(0.22,1,0.36,1) both' }}
      >
        <style>{`
          @keyframes fadeSlideUp {
            from { opacity: 0; transform: translateY(18px); }
            to   { opacity: 1; transform: translateY(0); }
          }
          @keyframes pulseRing {
            0%, 100% { opacity: 1;   transform: scale(1); }
            50%      { opacity: 0.3; transform: scale(1.14); }
          }
        `}</style>

        {/* Pulsing concentric rings */}
        <div className="relative w-20 h-20 flex items-center justify-center">
          <div
            className="absolute inset-0 rounded-full border border-fixme-text-muted/20"
            style={{ animation: 'pulseRing 2s ease-in-out infinite', animationDelay: '0ms' }}
          />
          <div
            className="absolute inset-3 rounded-full border border-fixme-text-muted/15"
            style={{ animation: 'pulseRing 2s ease-in-out infinite', animationDelay: '500ms' }}
          />
          <div
            className="absolute inset-6 rounded-full border border-fixme-text-muted/10"
            style={{ animation: 'pulseRing 2s ease-in-out infinite', animationDelay: '900ms' }}
          />
          <div className="w-2 h-2 rounded-full bg-fixme-accent" />
        </div>

        {/* Live scan steps */}
        <div className="space-y-2.5 w-full max-w-xs">
          {SCAN_STEPS.map((step, i) => (
            <p
              key={step}
              className={`text-sm transition-all duration-500 ${
                i < scanStep
                  ? 'text-fixme-text-muted line-through decoration-fixme-text-muted/40'
                  : i === scanStep
                  ? 'text-fixme-text-primary font-medium'
                  : 'text-fixme-text-muted/25'
              }`}
            >
              {i < scanStep ? '✓ ' : i === scanStep ? '✶ ' : ''}{step}
            </p>
          ))}
        </div>

        <p className="text-fixme-text-muted text-xs leading-relaxed max-w-[240px]">
          We only read publicly available information.<br />
          Nothing is stored until you approve.
        </p>
      </div>
    );
  }

  /* ── Input phase ──────────────────────────────────────────────────────── */
  return (
    <div
      className="flex flex-col gap-6"
      style={{ animation: 'fadeSlideUp 0.4s cubic-bezier(0.22,1,0.36,1) both' }}
    >
      <style>{`
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(18px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      {/* Heading */}
      <div>
        <h2 className="text-fixme-text-primary text-xl font-bold mb-1">
          Get your services in seconds
        </h2>
        <p className="text-fixme-text-secondary text-sm leading-relaxed">
          Our AI reads your existing booking page — services, prices, and
          opening hours. Works with any platform or your own website.
        </p>
      </div>

      {/* URL input card */}
      <div className="bg-fixme-card border border-fixme-border rounded-2xl p-4 space-y-3">
        <p className="text-fixme-text-muted text-[10px] font-bold uppercase tracking-[0.32em]">
          Your booking page
        </p>

        {/* Inline URL + Go */}
        <div className="flex items-center gap-2">
          <input
            type="url"
            value={websiteUrl}
            onChange={(e) => { setWebsiteUrl(e.target.value); setError(''); }}
            onKeyDown={(e) => e.key === 'Enter' && handleGo()}
            placeholder="https://yourbookingsite.com"
            className="flex-1 bg-fixme-bg border border-fixme-border rounded-xl px-3 py-3 text-sm text-fixme-text-primary placeholder-fixme-text-muted focus:outline-none focus:border-[#3A3A3A] transition-colors"
            autoComplete="url"
          />
          <button
            type="button"
            onClick={handleGo}
            disabled={!websiteUrl.trim()}
            className="bg-[#F5F5F0] hover:bg-[#FAFAFA] disabled:opacity-40 text-[#0A0A0A] font-semibold text-sm rounded-xl px-4 py-3 active:scale-[0.97] transition-all duration-150 whitespace-nowrap"
          >
            Go →
          </button>
        </div>

        <p className="text-fixme-text-muted text-xs">
          Fresha, Bokadirekt, your own site — any URL works.
        </p>
      </div>

      {error && (
        <p className="text-fixme-error text-xs text-center">{error}</p>
      )}

      {/* Skip */}
      <button
        type="button"
        onClick={onSkip}
        className="text-fixme-text-muted text-xs text-center hover:text-fixme-text-secondary transition-colors py-1"
      >
        Skip for now — I'll add services manually
      </button>

      {/* Back link — subtle, below skip */}
      <button
        type="button"
        onClick={onBack}
        className="text-fixme-text-muted/50 text-xs text-center hover:text-fixme-text-muted transition-colors"
      >
        ← Back to Instagram
      </button>
    </div>
  );
}
