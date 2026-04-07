/**
 * Currency formatting for the provider mobile app.
 *
 * Provider always sees prices in their own currency.
 * No conversion hints — this is the provider's app.
 */

/**
 * Format a price in the given currency.
 *
 * Uses Intl.NumberFormat for proper locale-aware formatting.
 *
 * @param amount - Numeric price
 * @param currencyCode - ISO 4217 code (default "SEK")
 * @returns Formatted string, e.g. "€500" or "500 kr"
 */
export function formatPrice(amount: number | undefined | null, currencyCode = 'SEK'): string {
  if (amount == null || isNaN(amount)) return '';
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: currencyCode,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(Math.round(amount));
  } catch {
    // Fallback for unknown/unsupported currency codes
    return `${Math.round(amount)} ${currencyCode}`;
  }
}
