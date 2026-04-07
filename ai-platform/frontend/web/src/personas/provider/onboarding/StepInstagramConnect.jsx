/**
 * StepInstagramConnect — Onboarding step 1
 *
 * One job: connect Instagram.
 * Provider can connect via OAuth, type their handle manually, or skip.
 * On "Continue" we pass igData back to ProviderFlow which carries it into StepScrapeWebsite.
 */
import { useEffect, useState } from 'react';
import { getInstagramConnectStatus, openInstagramConnectPopup } from '@shared/instagram/client';

function IgIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="2" y="2" width="20" height="20" rx="6" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="12" cy="12" r="4.5" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="17.5" cy="6.5" r="1.2" fill="currentColor" />
    </svg>
  );
}

export default function StepInstagramConnect({ token, onComplete, onSkip }) {
  const [igConnected,     setIgConnected]     = useState(false);
  const [instagramData,   setInstagramData]   = useState(null);
  const [instagramHandle, setInstagramHandle] = useState('');
  const [connectingIg,    setConnectingIg]    = useState(false);
  const [checking,        setChecking]        = useState(true);
  const [error,           setError]           = useState('');

  // On mount: check if already connected (e.g. user navigated back)
  useEffect(() => {
    if (!token) { setChecking(false); return; }
    let active = true;
    getInstagramConnectStatus({ token })
      .then((s) => {
        if (!active || !s?.connected) return;
        setInstagramData(s);
        setIgConnected(true);
        if (s.instagram_username) setInstagramHandle(s.instagram_username);
      })
      .catch(() => {})
      .finally(() => { if (active) setChecking(false); });
    return () => { active = false; };
  }, [token]);

  async function handleConnectInstagram() {
    if (!token) { setError('Email verification required.'); return; }
    setError('');
    setConnectingIg(true);
    try {
      const result = await openInstagramConnectPopup({ token, returnTo: window.location.origin });
      setInstagramData(result || {});
      const connected = !!(result?.instagram_user_id || result?.instagram_username);
      setIgConnected(connected);
      if (result?.instagram_username) setInstagramHandle(result.instagram_username);
    } catch (err) {
      setError(err.message || 'Could not connect Instagram right now.');
    } finally {
      setConnectingIg(false);
    }
  }

  function handleContinue() {
    const data = instagramData
      ? { ...instagramData, instagram_username: instagramData.instagram_username || instagramHandle.replace('@', '').trim() }
      : instagramHandle.trim()
        ? { instagram_username: instagramHandle.replace('@', '').trim() }
        : null;
    onComplete?.(data);
  }

  if (checking) {
    return (
      <div className="flex items-center justify-center py-20">
        <span className="w-5 h-5 rounded-full border border-fixme-text-muted/40 border-t-transparent animate-spin" />
      </div>
    );
  }

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
          Connect Instagram
        </h2>
        <p className="text-fixme-text-secondary text-sm leading-relaxed">
          We pull your profile image, username, and follower count — so your
          booking page looks great from day one.
        </p>
      </div>

      {/* Instagram card */}
      <div className="bg-fixme-card border border-fixme-border rounded-2xl p-4 space-y-3">
        <p className="text-fixme-text-muted text-[10px] font-bold uppercase tracking-[0.32em]">
          Instagram
        </p>

        {/* OAuth button */}
        <button
          type="button"
          onClick={handleConnectInstagram}
          disabled={connectingIg}
          className={`w-full flex items-center gap-3 border rounded-xl px-4 py-3 text-sm text-left transition-colors disabled:opacity-60 ${
            igConnected
              ? 'border-fixme-success/40 bg-fixme-success/5 text-fixme-text-primary'
              : 'border-fixme-border bg-fixme-bg text-fixme-text-primary hover:border-[#3A3A3A]'
          }`}
        >
          <span className={igConnected ? 'text-fixme-success' : 'text-[#C13584]'}>
            <IgIcon size={18} />
          </span>
          <span className="flex-1 font-medium">
            {connectingIg
              ? 'Connecting…'
              : igConnected
              ? `Connected as @${instagramData?.instagram_username || instagramHandle}`
              : 'Connect your Instagram'}
          </span>
          {igConnected && <span className="text-fixme-success text-sm">✓</span>}
        </button>

        {/* Manual handle fallback */}
        <div className="flex items-center bg-fixme-bg border border-fixme-border rounded-xl px-3 gap-1.5">
          <span className="text-fixme-text-muted text-sm select-none">@</span>
          <input
            type="text"
            value={instagramHandle}
            onChange={(e) => setInstagramHandle(e.target.value.replace('@', ''))}
            placeholder="yourusername  (optional)"
            className="flex-1 bg-transparent py-2.5 text-sm text-fixme-text-primary placeholder-fixme-text-muted focus:outline-none"
            autoCapitalize="none"
            autoCorrect="off"
          />
        </div>
      </div>

      {error && (
        <p className="text-fixme-error text-xs text-center">{error}</p>
      )}

      {/* Privacy note */}
      <p className="text-fixme-text-muted text-xs text-center leading-relaxed">
        We only read your public profile. Nothing is stored until you approve.
      </p>

      {/* Actions */}
      <button
        type="button"
        onClick={handleContinue}
        className="w-full bg-[#F5F5F0] hover:bg-[#FAFAFA] text-[#0A0A0A] font-semibold text-sm rounded-2xl py-4 active:scale-[0.98] transition-all duration-150"
      >
        Continue →
      </button>

      <button
        type="button"
        onClick={onSkip}
        className="text-fixme-text-muted text-xs text-center hover:text-fixme-text-secondary transition-colors py-1"
      >
        Skip for now — I'll connect later
      </button>
    </div>
  );
}
