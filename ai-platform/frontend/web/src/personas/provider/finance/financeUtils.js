import { FINANCE_PERIODS } from './financeConfig';
import { formatPrice } from '../../../utils/currency';

/**
 * Format a monetary value in the provider's currency.
 * Falls back to SEK if no currency is provided (backward compat).
 *
 * @param {number} value
 * @param {string} currency - ISO 4217 code
 */
export function fmtMoney(value, currency = 'SEK') {
  return formatPrice(Number(value || 0), currency);
}

/** @deprecated Use fmtMoney(value, currency) instead */
export function fmtSek(value) {
  return fmtMoney(value, 'SEK');
}

export function fmtShortDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

export function changeLabel(current, previous) {
  if (!previous) return null;
  const pct = ((current - previous) / previous) * 100;
  const sign = pct >= 0 ? '+' : '';
  return { text: `${sign}${Math.round(pct)}%`, positive: pct >= 0 };
}

export function periodLabel(periodId) {
  return FINANCE_PERIODS.find((period) => period.id === periodId)?.label || 'This period';
}

export function buildFinanceActions({ summary, insights, revenueChange, currency = 'SEK' }) {
  const actions = [];
  const fmt = (v) => fmtMoney(v, currency);

  if (summary?.unpaid_count > 0) {
    actions.push({
      title: `Collect ${fmt(summary.unpaid_amount)} from ${summary.unpaid_count} completed booking${summary.unpaid_count === 1 ? '' : 's'}`,
      badge: 'Cash',
      body: 'The AI should keep providers from forgetting finished work that still has no paid invoice attached.',
    });
  }

  if ((summary?.vat_collected || 0) > 0) {
    actions.push({
      title: `Reserve ${fmt(summary.vat_collected)} for VAT`,
      badge: 'Tax',
      body: 'This is money the provider should mentally treat as already spoken for, not spendable profit.',
    });
  }

  if (revenueChange) {
    actions.push({
      title: revenueChange.positive ? 'Explain what lifted revenue' : 'Explain why revenue softened',
      badge: 'Insight',
      body: revenueChange.positive
        ? 'A good finance agent should connect growth to completed bookings and top services so the provider can repeat it.'
        : 'A good finance agent should point to fewer completions, pricing changes, or payment lag instead of leaving the provider guessing.',
    });
  }

  const topService = summary?.top_services?.[0] || insights?.top_services?.[0];
  if (topService?.name) {
    actions.push({
      title: `Use ${topService.name} as the anchor for pricing and bundles`,
      badge: 'Growth',
      body: 'The most repeated service is usually the best place for margin improvements, package experiments, and upsell logic.',
    });
  }

  if (!actions.length) {
    actions.push({
      title: 'Start with clean booking-to-cash tracking',
      badge: 'Setup',
      body: 'Once completed bookings, payments, and VAT snapshots are flowing reliably, the AI can take on more accountant-like work.',
    });
  }

  return actions.slice(0, 4);
}

export function buildCloseChecklist({ summary, insights, currency = 'SEK' }) {
  const fmt = (v) => fmtMoney(v, currency);
  const items = [
    {
      title: 'Reconcile completed work against paid cash',
      body: 'Every completed booking should move into either paid, awaiting payment, or needs follow-up so the provider never loses track.',
    },
    {
      title: 'Set aside tax money before owner draw',
      body: `Current VAT estimate for the selected range is ${fmt(summary?.vat_collected)}.`,
    },
    {
      title: 'Review service mix and margin signals',
      body: `Top service right now is ${(summary?.top_services?.[0] || insights?.top_services?.[0])?.name || 'not available yet'}, which should shape pricing conversations.`,
    },
  ];

  if (summary?.unpaid_count > 0) {
    items.push({
      title: 'Clear the unpaid queue',
      body: `${summary.unpaid_count} completed booking${summary.unpaid_count === 1 ? '' : 's'} still need payment closure.`,
    });
  }

  return items;
}
