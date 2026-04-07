const ALLOWED_REFERRAL_SOURCES = new Set([
  'provider_link',
  'instagram',
  'qr_code',
  'customer_favorite',
]);

const REFERRAL_CONTEXT_KEY = 'fixme_referral_context';
const REFERRAL_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;

function readContext() {
  try {
    const raw = localStorage.getItem(REFERRAL_CONTEXT_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function writeContext(payload) {
  try {
    localStorage.setItem(REFERRAL_CONTEXT_KEY, JSON.stringify(payload));
  } catch {
    // best effort only
  }
}

export function normalizeReferralSource(raw, fallback = null) {
  const key = String(raw || '').trim().toLowerCase();
  if (!key) return fallback;
  if (!ALLOWED_REFERRAL_SOURCES.has(key)) return fallback;
  return key;
}

export function buildCustomerFavoriteReferralQuery() {
  const params = new URLSearchParams();
  params.set('ref', 'customer_favorite');

  const userId = String(localStorage.getItem('fixme_user_id') || '').trim();
  if (userId) params.set('ref_customer', userId);

  return params.toString();
}

export function captureReferralFromSearch(search, { providerId = null, slug = null } = {}) {
  const params = new URLSearchParams(search || window.location.search || '');
  const source = normalizeReferralSource(params.get('ref'));
  if (!source) return null;

  const refCustomer = String(params.get('ref_customer') || '').trim();
  const safeRefCustomer = /^[A-Za-z0-9-]{6,64}$/.test(refCustomer) ? refCustomer : null;

  const payload = {
    source,
    ref_customer: safeRefCustomer,
    provider_id: providerId || null,
    provider_slug: slug || null,
    captured_at_ms: Date.now(),
  };
  writeContext(payload);
  return payload;
}

export function getCapturedReferralSource({ providerId = null, slug = null } = {}) {
  const ctx = readContext();
  if (!ctx) return null;
  if (!ctx.source) return null;

  const ageMs = Date.now() - Number(ctx.captured_at_ms || 0);
  if (!Number.isFinite(ageMs) || ageMs > REFERRAL_MAX_AGE_MS) return null;

  if (providerId && ctx.provider_id && ctx.provider_id !== providerId) return null;
  if (slug && ctx.provider_slug && ctx.provider_slug !== slug) return null;

  return normalizeReferralSource(ctx.source);
}

