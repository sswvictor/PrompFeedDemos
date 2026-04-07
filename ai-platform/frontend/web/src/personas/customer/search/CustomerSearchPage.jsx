import { useState, useRef } from 'react';
import CustomerTabBar from '../navigation/CustomerTabBar';
import { searchFeed } from '../../../api/bookingApi';

// ── Inspiration chips shown on idle screen ────────────────────────────────────
const INSPIRATION_CHIPS = [
  { label: 'Hair', prompt: 'hair salon' },
  { label: 'Nails', prompt: 'nail studio' },
  { label: 'Lashes', prompt: 'lash extensions' },
  { label: 'Skin', prompt: 'facial skin treatment' },
  { label: 'Massage', prompt: 'massage therapy' },
  { label: 'Brows', prompt: 'eyebrow shaping' },
  { label: 'Makeup', prompt: 'makeup artist' },
  { label: 'Wellness', prompt: 'wellness spa' },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtPrice(startingFrom) {
  if (!startingFrom) return null;
  return `From ${Math.round(startingFrom)} kr`;
}

function fmtAvail(nextAvailable, availableToday) {
  if (availableToday) return 'Available today';
  if (!nextAvailable) return null;
  try {
    const d = new Date(nextAvailable);
    return d.toLocaleDateString('en-GB', { weekday: 'short', month: 'short', day: 'numeric' });
  } catch {
    return null;
  }
}

// ── Provider card ─────────────────────────────────────────────────────────────

function ProviderCard({ provider }) {
  // Prefer the SEO slug URL; fall back to provider_id URL (always available)
  const href = provider.slug
    ? `/p/${provider.slug}`
    : `/pid/${provider.provider_id}`;
  const initial = (provider.name || '?')[0].toUpperCase();
  const price = fmtPrice(provider.starting_from);
  const avail = fmtAvail(provider.next_available, provider.available_today);
  const vibes = (provider.vibe_tags || []).slice(0, 3);

  return (
    <a
      href={href}
      className="block bg-fixme-card border border-fixme-border rounded-2xl p-4 hover:border-fixme-accent/40 active:scale-[0.99] transition-all"
    >
      <div className="flex items-start gap-3">
        {/* Avatar */}
        <div className="flex-shrink-0 w-12 h-12 rounded-full overflow-hidden bg-fixme-border">
          {provider.image_url ? (
            <img src={provider.image_url} alt={provider.name} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-fixme-text-secondary font-bold text-base">
              {initial}
            </div>
          )}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-fixme-text-primary text-sm font-semibold leading-tight truncate">
                {provider.name}
              </p>
              {provider.city && (
                <p className="text-fixme-text-muted text-xs mt-0.5 truncate">{provider.city}</p>
              )}
            </div>
            {price && (
              <span className="flex-shrink-0 text-xs font-semibold text-fixme-text-primary whitespace-nowrap">
                {price}
              </span>
            )}
          </div>

          {/* Availability badge */}
          {avail && (
            <span
              className={`inline-block mt-1.5 text-[11px] px-2 py-0.5 rounded-full font-medium ${
                provider.available_today
                  ? 'bg-fixme-success/10 text-fixme-success'
                  : 'bg-fixme-bg text-fixme-text-muted border border-fixme-border/60'
              }`}
            >
              {avail}
            </span>
          )}

          {/* Vibe tags */}
          {vibes.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {vibes.map((tag) => (
                <span
                  key={tag}
                  className="text-[10px] px-2 py-0.5 rounded-full bg-fixme-bg border border-fixme-border/60 text-fixme-text-muted capitalize"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </a>
  );
}

// ── Loading skeletons ─────────────────────────────────────────────────────────

function SkeletonCards() {
  return (
    <div className="space-y-3 animate-pulse">
      {[0, 1, 2].map((i) => (
        <div key={i} className="bg-fixme-card border border-fixme-border rounded-2xl p-4">
          <div className="flex gap-3">
            <div className="w-12 h-12 rounded-full bg-fixme-border flex-shrink-0" />
            <div className="flex-1 space-y-2 pt-0.5">
              <div className="h-3.5 bg-fixme-border rounded w-3/5" />
              <div className="h-2.5 bg-fixme-border rounded w-2/5" />
              <div className="h-2 bg-fixme-border rounded w-1/3 mt-3" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function CustomerSearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  async function doSearch(prompt) {
    const trimmed = prompt.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const data = await searchFeed(trimmed);
      setResults(data);
    } catch (e) {
      setError(e.message || 'Search failed');
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    doSearch(query);
  }

  function handleChip(prompt) {
    setQuery(prompt);
    doSearch(prompt);
  }

  function clearSearch() {
    setQuery('');
    setResults(null);
    setError(null);
    inputRef.current?.focus();
  }

  // Extract blocks from the feed response
  const summaryBlock = results?.blocks?.find((b) => b.type === 'SearchSummaryCard');
  const resultsBlock = results?.blocks?.find((b) => b.type === 'ProviderResults');
  const providers = resultsBlock?.data?.providers || [];
  const hasResults = results && !loading;

  return (
    <div className="min-h-screen bg-fixme-bg pb-24 px-4 pt-8 max-w-md mx-auto">

      {/* ── Header ──────────────────────────────────────────────────── */}
      <div className="mb-5">
        <h1 className="text-fixme-text-primary text-2xl font-bold">Discover</h1>
        <p className="text-fixme-text-muted text-sm mt-0.5">Find your next appointment</p>
      </div>

      {/* ── Search bar ──────────────────────────────────────────────── */}
      <form onSubmit={handleSubmit} className="mb-5">
        <div className="flex items-center gap-2.5 bg-fixme-card border border-fixme-border rounded-2xl px-4 py-3 focus-within:border-fixme-accent/50 transition-colors">
          {/* Search icon */}
          <svg
            className="w-4 h-4 text-fixme-text-muted flex-shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 115 11a6 6 0 0112 0z" />
          </svg>

          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Hair, massage, nails near me..."
            className="flex-1 bg-transparent text-fixme-text-primary text-sm placeholder-fixme-text-muted outline-none"
            autoComplete="off"
          />

          {/* Clear button */}
          {query && (
            <button
              type="button"
              onClick={clearSearch}
              className="text-fixme-text-muted hover:text-fixme-text-secondary transition-colors flex-shrink-0"
              aria-label="Clear search"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </form>

      {/* ── Error banner ─────────────────────────────────────────────── */}
      {error && (
        <div className="mb-4 bg-fixme-error/10 border border-fixme-error/30 rounded-xl px-3 py-2 text-xs text-fixme-error">
          {error}
        </div>
      )}

      {/* ── Loading ──────────────────────────────────────────────────── */}
      {loading && <SkeletonCards />}

      {/* ── Results ──────────────────────────────────────────────────── */}
      {hasResults && !error && (
        <>
          {/* Summary subtitle */}
          {summaryBlock?.data?.subtitle && (
            <p className="text-fixme-text-muted text-xs mb-3 px-1">
              {summaryBlock.data.subtitle}
            </p>
          )}

          {/* Result count */}
          {summaryBlock?.data?.result_count != null && (
            <p className="text-fixme-text-secondary text-xs font-medium mb-3 px-1">
              {summaryBlock.data.result_count} provider{summaryBlock.data.result_count !== 1 ? 's' : ''} found
            </p>
          )}

          {providers.length === 0 ? (
            <div className="text-center py-12 space-y-2">
              <p className="text-fixme-text-secondary text-sm font-medium">No providers found</p>
              <p className="text-fixme-text-muted text-xs">Try a different search term</p>
              <button
                type="button"
                onClick={clearSearch}
                className="mt-3 text-xs text-fixme-accent underline"
              >
                Clear search
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {providers.map((p) => (
                <ProviderCard key={p.provider_id} provider={p} />
              ))}
            </div>
          )}
        </>
      )}

      {/* ── Idle state — inspiration grid ────────────────────────────── */}
      {!loading && !results && !error && (
        <div className="space-y-6">
          <div>
            <p className="text-fixme-text-muted text-xs font-semibold uppercase tracking-widest mb-3">
              Browse by category
            </p>
            <div className="grid grid-cols-4 gap-2">
              {INSPIRATION_CHIPS.map((chip) => (
                <button
                  key={chip.label}
                  type="button"
                  onClick={() => handleChip(chip.prompt)}
                  className="py-3 rounded-xl bg-fixme-card border border-fixme-border text-fixme-text-secondary text-xs font-semibold hover:border-fixme-accent/40 hover:text-fixme-text-primary active:scale-95 transition-all"
                >
                  {chip.label}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-2xl bg-fixme-card border border-fixme-border p-4 space-y-1.5">
            <p className="text-fixme-text-primary text-sm font-semibold">Try asking naturally</p>
            <p className="text-fixme-text-muted text-xs leading-relaxed">
              {'"Hair colour near Södermalm"'}
            </p>
            <p className="text-fixme-text-muted text-xs leading-relaxed">
              {'"Relaxing massage available this week"'}
            </p>
            <p className="text-fixme-text-muted text-xs leading-relaxed">
              {'"Affordable nail studio in Stockholm"'}
            </p>
          </div>
        </div>
      )}

      <CustomerTabBar active="search" />
    </div>
  );
}
