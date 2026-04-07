/**
 * LandingChoice – /auth  (onboarding and login entry point)
 *
 * Copy angle: address the DM booking pain directly.
 * Provider path is the dominant CTA.
 */

import { ROUTES } from '../../app/routeCatalog';
import { clearFixmeSessionStorage } from '../../app/session';

const BEAUTY_TAGS = ['Hair', 'Nails', 'Skin', 'Lashes', 'Makeup', 'Wellness', 'Massage', 'Brows'];

export default function LandingChoice({ mode = 'onboarding' }) {
  const isLoginMode = mode === 'login';

  const targetFor = (role) => {
    if (role === 'provider') {
      if (isLoginMode) return ROUTES.provider.login;
      return `${ROUTES.provider.welcome}?type=freelancer`;
    }
    if (isLoginMode) return ROUTES.salon.login;
    return `${ROUTES.provider.welcome}?type=salon`;
  };

  const go = (role) => {
    if (isLoginMode) clearFixmeSessionStorage();
    window.location.href = targetFor(role);
  };

  return (
    <div className="flex flex-col min-h-screen bg-fixme-bg">
      <div className="flex-1 flex flex-col px-5 pt-10 pb-8 max-w-sm mx-auto w-full">

        {/* Wordmark */}
        <p className="text-fixme-text-muted text-[11px] font-semibold uppercase tracking-widest mb-10 animate-fade-in">
          Fixmeapp
        </p>

        {/* Hero */}
        <div className="mb-7 animate-fade-in delay-75">
          {isLoginMode ? (
            <>
              <h1 className="text-fixme-text-primary text-2xl font-bold leading-snug mb-2">
                Welcome back.
              </h1>
              <p className="text-fixme-text-secondary text-sm leading-relaxed">
                Log in to manage your bookings.
              </p>
            </>
          ) : (
            <>
              <h1 className="text-fixme-text-primary text-2xl font-bold leading-snug mb-2">
                Stop losing bookings<br />in your DMs.
              </h1>
              <p className="text-fixme-text-secondary text-sm leading-relaxed">
                Beauty & wellness pros on Instagram — your followers can book you directly, 24/7, no back-and-forth.
              </p>
            </>
          )}
        </div>

        {/* Category tags — onboarding only */}
        {!isLoginMode && (
          <div className="flex flex-wrap gap-1.5 mb-8 animate-fade-in delay-150">
            {BEAUTY_TAGS.map((tag) => (
              <span
                key={tag}
                className="px-2.5 py-1 bg-fixme-card border border-fixme-border rounded-full text-fixme-text-muted text-xs"
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* CTAs */}
        <div className="flex flex-col gap-2.5 animate-slide-up delay-225">

          {/* Provider — PRIMARY */}
          <button
            onClick={() => go('provider')}
            className="w-full bg-fixme-accent hover:bg-fixme-accent-light rounded-2xl py-4 px-4 text-left flex items-center justify-between active:scale-[0.97] transition-all duration-150"
          >
            <div>
              <p className="text-fixme-bg font-semibold text-sm">
                {"I'm a beauty professional"}
              </p>
              <p className="text-fixme-bg/50 text-xs mt-0.5">
                Freelancer · solo artist · chair renter
              </p>
            </div>
            <span className="text-fixme-bg/70 ml-4">→</span>
          </button>

          {/* Salon — SECONDARY */}
          <button
            onClick={() => go('salon')}
            className="group w-full bg-fixme-card border border-fixme-border rounded-2xl py-4 px-4 text-left flex items-center justify-between hover:border-fixme-border/80 active:scale-[0.97] transition-all duration-150"
          >
            <div>
              <p className="text-fixme-text-primary font-semibold text-sm">I run a salon or studio</p>
              <p className="text-fixme-text-muted text-xs mt-0.5">Manage a location with a team</p>
            </div>
            <span className="text-fixme-text-muted group-hover:text-fixme-text-secondary transition-colors ml-4">→</span>
          </button>

        </div>

        {/* Footer */}
        <p className="text-fixme-text-muted text-[11px] text-center mt-auto pt-8 leading-relaxed">
          {isLoginMode
            ? 'Each role starts a clean session on this device.'
            : 'For Instagram-active beauty & wellness professionals.'}
        </p>

      </div>
    </div>
  );
}
