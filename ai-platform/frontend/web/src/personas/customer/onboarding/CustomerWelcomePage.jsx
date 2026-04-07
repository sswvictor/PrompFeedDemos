/**
 * CustomerWelcomePage — /customer/welcome
 *
 * Cinematic entry for customers (people booking beauty & wellness services).
 * Messaging focuses on discovery and finding great providers — not business management.
 *
 * Smart routing:
 *   - If ?email= param present (arriving from BookingConfirmed):
 *       auto-forwards to /customer/onboarding?email=... (OTP auto-sends there)
 *   - Otherwise:
 *       shows cinematic splash → "Get started" → /customer/onboarding
 *                              → "Sign in" → /customer/login
 */

import { useState } from 'react';
import { ROUTES } from '../../../app/routeCatalog';

const CATEGORY_TAGS = ['Hair', 'Nails', 'Skin', 'Lashes', 'Makeup', 'Wellness', 'Massage', 'Brows'];

const SPLASH_LINES = [
  { text: 'The best beauty pros.', delay: 400  },
  { text: 'Book in seconds.',      delay: 900  },
  { text: 'No back-and-forth.',    delay: 1300 },
];

export default function CustomerWelcomePage() {
  const params = new URLSearchParams(window.location.search);
  const emailParam = params.get('email');

  // Coming from booking confirmation — skip splash, forward to CustomerFlow with email pre-filled
  if (emailParam) {
    window.location.replace(
      `${ROUTES.customer.onboarding}?email=${encodeURIComponent(emailParam)}`
    );
    return null;
  }

  return <CustomerSplash />;
}

function CustomerSplash() {
  const [visited, setVisited] = useState(false);

  const go = (path) => {
    setVisited(true);
    setTimeout(() => { window.location.href = path; }, 200);
  };

  return (
    <div className="flex flex-col min-h-screen bg-fixme-bg overflow-hidden">
      <div className="flex-1 flex flex-col px-6 max-w-sm mx-auto w-full">

        {/* Wordmark */}
        <p className="pt-10 text-fixme-text-muted text-[9px] font-bold uppercase tracking-[0.42em] animate-fade-in">
          Fixmeapp
        </p>

        {/* Headline lines — reveal one by one */}
        <div className="mt-auto mb-6">
          {SPLASH_LINES.map((line, i) => (
            <div
              key={i}
              className="animate-line-reveal overflow-hidden"
              style={{ animationDelay: visited ? '0ms' : `${line.delay}ms` }}
            >
              <h1
                className="text-fixme-text-primary font-bold leading-[1.15] tracking-tight"
                style={{ fontSize: 'clamp(28px, 8.5vw, 34px)' }}
              >
                {line.text}
              </h1>
            </div>
          ))}

          {/* Descriptor */}
          <p
            className="text-fixme-text-muted text-sm leading-relaxed mt-5 animate-line-reveal"
            style={{ animationDelay: visited ? '80ms' : '1900ms' }}
          >
            Discover top stylists, nail techs, lash artists and more
            — and book them directly through Instagram, 24/7.
          </p>
        </div>

        {/* Category tags */}
        <div
          className="flex flex-wrap gap-1.5 mb-8 animate-line-reveal"
          style={{ animationDelay: visited ? '100ms' : '2300ms' }}
        >
          {CATEGORY_TAGS.map((tag) => (
            <span
              key={tag}
              className="px-2.5 py-1 bg-fixme-card border border-fixme-border rounded-full text-fixme-text-muted text-xs"
            >
              {tag}
            </span>
          ))}
        </div>

        {/* CTAs */}
        <div
          className="flex flex-col gap-3 pb-12 animate-cta-reveal"
          style={{ animationDelay: visited ? '140ms' : '2700ms' }}
        >
          <button
            onClick={() => go(ROUTES.customer.onboarding)}
            className="w-full bg-fixme-accent hover:bg-fixme-accent-light text-fixme-bg font-semibold text-sm rounded-2xl py-4 active:scale-[0.97] transition-all duration-150"
          >
            Find providers {'\u2192'}
          </button>

          <button
            onClick={() => go(ROUTES.customer.login)}
            className="w-full text-fixme-text-muted text-xs text-center hover:text-fixme-text-secondary transition-colors py-1"
          >
            Already have an account? Sign in
          </button>
        </div>

      </div>
    </div>
  );
}
