/**
 * Currency formatting utilities for Fixmeapp.
 *
 * Provider prices are always in the provider's currency (ISO 4217).
 * Customer sees the provider price + an approximate conversion hint
 * based on their browser locale.
 */

// ── Exchange rate cache ──────────────────────────────────────────────────────
let _rateCache = {};     // { base: { target: rate, ... } }
let _rateFetchedAt = {}; // { base: timestamp }
const RATE_TTL_MS = 4 * 60 * 60 * 1000; // 4 hours

async function _fetchRates(base) {
  const now = Date.now();
  if (_rateCache[base] && _rateFetchedAt[base] && now - _rateFetchedAt[base] < RATE_TTL_MS) {
    return _rateCache[base];
  }
  try {
    const res = await fetch(`https://open.er-api.com/v6/latest/${base}`);
    if (!res.ok) return _rateCache[base] || null;
    const data = await res.json();
    if (data.result === 'success' && data.rates) {
      _rateCache[base] = data.rates;
      _rateFetchedAt[base] = now;
      return data.rates;
    }
  } catch {
    // Silent fail — show no hint
  }
  return _rateCache[base] || null;
}

// Pre-fetch common currencies on module load (non-blocking)
if (typeof window !== 'undefined') {
  _fetchRates('SEK');
  _fetchRates('EUR');
  _fetchRates('USD');
}

// ── Locale → currency mapping ────────────────────────────────────────────────
const LOCALE_CURRENCY_MAP = {
  'sv': 'SEK', 'nb': 'NOK', 'nn': 'NOK', 'da': 'DKK',
  'fr': 'EUR', 'de': 'EUR', 'it': 'EUR', 'es': 'EUR', 'nl': 'EUR',
  'pt': 'EUR', 'fi': 'EUR', 'el': 'EUR',
  'en-US': 'USD', 'en-GB': 'GBP', 'en-AU': 'AUD', 'en-CA': 'CAD',
  'en-NZ': 'NZD', 'en-SG': 'SGD',
  'ja': 'JPY', 'ko': 'KRW', 'th': 'THB', 'hi': 'INR',
  'pl': 'PLN', 'cs': 'CZK', 'hu': 'HUF', 'ro': 'RON',
  'tr': 'TRY', 'is': 'ISK',
};

/**
 * Detect the customer's likely currency from navigator.language.
 * Falls back to EUR.
 */
export function getLocaleCurrency() {
  if (typeof navigator === 'undefined') return 'EUR';
  const lang = navigator.language || 'en';
  // Try exact match first (en-US), then language only (en)
  return LOCALE_CURRENCY_MAP[lang] || LOCALE_CURRENCY_MAP[lang.split('-')[0]] || 'EUR';
}

/**
 * Format a price in the given currency using Intl.NumberFormat.
 *
 * @param {number} amount  - The numeric price
 * @param {string} currencyCode - ISO 4217 code (e.g. "SEK", "EUR", "USD")
 * @returns {string} Formatted price string
 */
export function formatPrice(amount, currencyCode = 'SEK') {
  if (amount == null || isNaN(amount)) return '';
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: currencyCode,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(Math.round(amount));
  } catch {
    // Fallback for unknown currency codes
    return `${Math.round(amount)} ${currencyCode}`;
  }
}

/**
 * Format provider price + approximate conversion hint for the customer.
 *
 * Shows the provider's price formatted, plus (~X) in the customer's
 * local currency if different. The hint is approximate and display-only.
 *
 * @param {number} amount - Price in provider's currency
 * @param {string} providerCurrency - Provider's ISO 4217 code
 * @returns {string} e.g. "500 kr" or "500 kr (~€44)"
 */
export function formatPriceWithHint(amount, providerCurrency = 'SEK') {
  const base = formatPrice(amount, providerCurrency);
  const localCurrency = getLocaleCurrency();

  if (localCurrency === providerCurrency || !_rateCache[providerCurrency]) {
    return base;
  }

  const rates = _rateCache[providerCurrency];
  const rate = rates[localCurrency];
  if (!rate) return base;

  const converted = Math.round(amount * rate);
  const hint = formatPrice(converted, localCurrency);
  return `${base} (~${hint})`;
}

/**
 * Ensure exchange rates are loaded for a given currency.
 * Call this when provider data loads so hints are ready.
 *
 * @param {string} currencyCode
 */
export async function preloadRates(currencyCode) {
  await _fetchRates(currencyCode);
}
