import { useState } from 'react';

import { getPromptFeed } from '../../../api/bookingApi';
import PromptFeedRenderer from './PromptFeedRenderer';

const QUICK_PROMPTS = [
  'Balayage in Stockholm this Friday',
  'I want balayage but I am not sure who to choose',
  'Show me the best rated nail places near me',
  'Something more natural and premium for summer',
];

const LOCATION_OPTIONS = ['Stockholm', 'Sodermalm', 'Ostermalm', 'Gothenburg'];
const TIME_OPTIONS = ['Today', 'This week', 'Friday afternoon', 'Next week'];
const BUDGET_OPTIONS = ['Affordable', 'Best value', 'Premium'];
const VIBE_OPTIONS = ['Natural', 'Minimal', 'Luxury', 'Bold'];

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5">
      <path
        d="M10.5 4.5a6 6 0 1 0 0 12a6 6 0 0 0 0-12Zm0 0l8.5 8.5"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.6"
      />
    </svg>
  );
}

function FilterIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5">
      <path
        d="M4 7h16M7 12h10M10 17h4"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.6"
      />
    </svg>
  );
}

function SparkIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4">
      <path
        d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z"
        fill="currentColor"
      />
    </svg>
  );
}

function CertaintyBadge({ label, value }) {
  const tone = {
    high: 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300',
    medium: 'border-amber-400/40 bg-amber-400/10 text-amber-200',
    low: 'border-white/10 bg-white/5 text-fixme-text-secondary',
  }[value] || 'border-white/10 bg-white/5 text-fixme-text-secondary';

  return (
    <span className={`rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.14em] ${tone}`}>
      {label} {value}
    </span>
  );
}

function FilterChip({ label, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'rounded-full border px-3 py-2 text-xs transition',
        active
          ? 'border-fixme-accent bg-fixme-accent text-fixme-bg'
          : 'border-white/10 bg-white/5 text-fixme-text-secondary hover:border-fixme-accent/60 hover:text-fixme-text-primary',
      ].join(' ')}
    >
      {label}
    </button>
  );
}

function PromptIntel({ response, isLoggedIn }) {
  const { intent_profile: intentProfile, recipe } = response || {};
  if (!intentProfile || !recipe) return null;

  return (
    <section className="rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(24,27,34,0.94),rgba(14,16,20,0.94))] p-5 shadow-[0_18px_60px_rgba(0,0,0,0.25)] animate-fade-in">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-fixme-accent/30 bg-fixme-accent/10 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-fixme-accent">
          {intentProfile.goal}
        </span>
        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-fixme-text-secondary">
          {recipe.template}
        </span>
        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-fixme-text-secondary">
          {recipe.primary_action}
        </span>
        {isLoggedIn ? (
          <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-emerald-300">
            Personalized
          </span>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <CertaintyBadge label="service" value={intentProfile.service_certainty} />
        <CertaintyBadge label="provider" value={intentProfile.provider_certainty} />
        <CertaintyBadge label="time" value={intentProfile.time_certainty} />
        <CertaintyBadge label="location" value={intentProfile.location_certainty} />
        <CertaintyBadge label="budget" value={intentProfile.budget_certainty} />
      </div>

      <p className="mt-4 text-sm leading-6 text-fixme-text-secondary">
        {intentProfile.needs_clarification?.length
          ? `Still missing: ${intentProfile.needs_clarification.join(', ')}. The feed should guide the next best decision.`
          : 'The user is specific enough that the feed can lean into stronger provider and booking decisions.'}
      </p>
    </section>
  );
}

function EmptyDiscoveryState({ setInput }) {
  return (
    <section className="rounded-[28px] border border-dashed border-white/10 bg-[linear-gradient(180deg,rgba(18,21,27,0.96),rgba(11,12,15,0.96))] p-6 text-fixme-text-secondary animate-fade-in">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-[#f0c38c]">
        <SparkIcon />
        Search direction
      </div>
      <h2 className="mt-4 text-2xl font-semibold text-white">
        Start with a natural request. Let the feed decide whether the user needs inspiration, comparison, or booking.
      </h2>
      <p className="mt-4 max-w-2xl text-sm leading-7">
        This layout is intentionally not a classic results page. It keeps discovery above, a persistent composer below,
        and lets the search become more specific as the user interacts.
      </p>
      <div className="mt-6 flex flex-wrap gap-2">
        {QUICK_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => setInput(prompt)}
            className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-fixme-text-primary transition hover:border-fixme-accent/60 hover:text-white"
          >
            {prompt}
          </button>
        ))}
      </div>
    </section>
  );
}

export default function FixmeappChat() {
  const [sessionId] = useState(() => {
    const existing = sessionStorage.getItem('fixme_prompt_feed_session_id');
    if (existing) return existing;
    const next = `prompt_feed_${Date.now()}`;
    sessionStorage.setItem('fixme_prompt_feed_session_id', next);
    return next;
  });
  const [input, setInput] = useState('');
  const [response, setResponse] = useState(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [filterPanelOpen, setFilterPanelOpen] = useState(false);
  const [filters, setFilters] = useState({
    location: '',
    when: '',
    budget: '',
    vibe: '',
  });

  const customerId = localStorage.getItem('fixme_customer_id') || null;
  const customerUserId = localStorage.getItem('fixme_user_id') || null;
  const customerName = localStorage.getItem('fixme_customer_email') || 'Logged-in customer';
  const isLoggedIn = Boolean(customerId || customerUserId);

  function toggleFilterValue(key, value) {
    setFilters((current) => ({
      ...current,
      [key]: current[key] === value ? '' : value,
    }));
  }

  function buildPromptWithFilters(basePrompt) {
    const parts = [basePrompt.trim()];

    if (filters.location && !basePrompt.toLowerCase().includes(filters.location.toLowerCase())) {
      parts.push(`in ${filters.location}`);
    }
    if (filters.when && !basePrompt.toLowerCase().includes(filters.when.toLowerCase())) {
      parts.push(filters.when);
    }
    if (filters.budget && !basePrompt.toLowerCase().includes(filters.budget.toLowerCase())) {
      parts.push(filters.budget);
    }
    if (filters.vibe && !basePrompt.toLowerCase().includes(filters.vibe.toLowerCase())) {
      parts.push(`${filters.vibe} vibe`);
    }

    return parts.filter(Boolean).join(', ');
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const prompt = input.trim();
    if (!prompt) return;

    setSending(true);
    setError('');

    try {
      const nextResponse = await getPromptFeed(buildPromptWithFilters(prompt), {
        customerId,
        sessionId,
      });
      setResponse(nextResponse);
    } catch (err) {
      setError(err.message || 'Failed to build prompt feed');
    } finally {
      setSending(false);
    }
  }

  const activeFilterCount = Object.values(filters).filter(Boolean).length;

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(211,155,94,0.08),_transparent_24%),linear-gradient(180deg,#090a0d_0%,#0f1217_52%,#090a0d_100%)] text-fixme-text-primary">
      <div className="mx-auto max-w-6xl px-4 pb-48 pt-4">
        <header className="sticky top-0 z-30 rounded-[26px] border border-white/10 bg-[rgba(9,10,13,0.82)] px-4 py-3 backdrop-blur-xl">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="text-[11px] uppercase tracking-[0.2em] text-[#f0c38c]">Fixmeapp Search</div>
              <h1 className="mt-1 text-lg font-semibold text-white">Prompt feed UX experiment</h1>
            </div>
            <button
              type="button"
              onClick={() => setFilterPanelOpen((open) => !open)}
              className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-fixme-text-primary transition hover:border-fixme-accent/50"
            >
              <FilterIcon />
              Filters
              {activeFilterCount ? (
                <span className="rounded-full bg-fixme-accent px-2 py-0.5 text-[11px] text-fixme-bg">{activeFilterCount}</span>
              ) : null}
            </button>
          </div>

          <div
            className={[
              'grid overflow-hidden transition-all duration-300',
              filterPanelOpen ? 'mt-4 grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0',
            ].join(' ')}
          >
            <div className="min-h-0 overflow-hidden">
              <div className="rounded-[22px] border border-white/10 bg-[rgba(255,255,255,0.03)] p-4">
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  <div>
                    <div className="text-[11px] uppercase tracking-[0.16em] text-fixme-text-secondary">Location</div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {LOCATION_OPTIONS.map((option) => (
                        <FilterChip key={option} label={option} active={filters.location === option} onClick={() => toggleFilterValue('location', option)} />
                      ))}
                    </div>
                  </div>
                  <div>
                    <div className="text-[11px] uppercase tracking-[0.16em] text-fixme-text-secondary">When</div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {TIME_OPTIONS.map((option) => (
                        <FilterChip key={option} label={option} active={filters.when === option} onClick={() => toggleFilterValue('when', option)} />
                      ))}
                    </div>
                  </div>
                  <div>
                    <div className="text-[11px] uppercase tracking-[0.16em] text-fixme-text-secondary">Budget</div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {BUDGET_OPTIONS.map((option) => (
                        <FilterChip key={option} label={option} active={filters.budget === option} onClick={() => toggleFilterValue('budget', option)} />
                      ))}
                    </div>
                  </div>
                  <div>
                    <div className="text-[11px] uppercase tracking-[0.16em] text-fixme-text-secondary">Vibe</div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {VIBE_OPTIONS.map((option) => (
                        <FilterChip key={option} label={option} active={filters.vibe === option} onClick={() => toggleFilterValue('vibe', option)} />
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </header>

        <main className="space-y-5 pt-5">
          <section className="rounded-[34px] border border-white/10 bg-[radial-gradient(circle_at_top_left,_rgba(245,190,110,0.15),_transparent_38%),linear-gradient(135deg,#151922_0%,#0a0a0a_50%,#141823_100%)] p-6 shadow-[0_30px_120px_rgba(0,0,0,0.35)] animate-slide-up">
            <div className="max-w-3xl">
              <div className="text-[11px] uppercase tracking-[0.22em] text-[#f0c38c]">Website Prompt Feed</div>
              <h2 className="mt-3 text-3xl font-semibold leading-tight text-white">
                Search should feel like describing your ideal result, not filling a form.
              </h2>
              <p className="mt-4 text-sm leading-7 text-[#d5d8df]">
                This experiment keeps the composer at the bottom like ChatGPT, lets filters slide down from the top,
                and leaves the center of the screen free for an adaptive discovery feed.
              </p>

              <div className="mt-6 flex flex-wrap gap-2">
                {QUICK_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => setInput(prompt)}
                    className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-fixme-text-primary transition hover:border-fixme-accent/60 hover:text-white"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          </section>

          {isLoggedIn ? (
            <section className="rounded-[24px] border border-emerald-400/20 bg-[linear-gradient(180deg,rgba(30,48,39,0.45),rgba(14,18,17,0.7))] p-4 animate-fade-in">
              <div className="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-emerald-300">
                <SparkIcon />
                Personalized for this customer
              </div>
              <p className="mt-3 text-sm leading-6 text-[#d9ece0]">
                The feed can use saved preferences, previous behavior, and ranking personalization for {customerName}.
                When `fixme_customer_id` is present, customer-memory blocks can also appear inline.
              </p>
            </section>
          ) : null}

          {response ? (
            <>
              <PromptIntel response={response} isLoggedIn={isLoggedIn} />
              <PromptFeedRenderer response={response} />
            </>
          ) : (
            <EmptyDiscoveryState setInput={setInput} />
          )}
        </main>
      </div>

      <div className="fixed inset-x-0 bottom-0 z-40 px-3 pb-4">
        <div className="mx-auto max-w-5xl rounded-[30px] border border-white/10 bg-[rgba(12,14,18,0.9)] p-3 shadow-[0_-12px_80px_rgba(0,0,0,0.42)] backdrop-blur-2xl">
          <form onSubmit={handleSubmit}>
            <div className="rounded-[24px] border border-white/10 bg-[rgba(255,255,255,0.04)] px-4 py-3">
              <div className="flex items-start gap-3">
                <div className="mt-1 text-[#f0c38c]">
                  <SearchIcon />
                </div>
                <textarea
                  className="min-h-[56px] flex-1 resize-none bg-transparent text-sm leading-6 text-white outline-none placeholder:text-fixme-text-secondary"
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder="Ask naturally: balayage this Friday in Stockholm, or something softer for summer if I am not sure yet"
                />
                <button
                  type="submit"
                  disabled={sending}
                  className="rounded-full bg-fixme-accent px-5 py-3 text-sm font-medium text-fixme-bg transition disabled:opacity-60"
                >
                  {sending ? 'Thinking...' : 'Search'}
                </button>
              </div>
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-2">
              {Object.entries(filters).map(([key, value]) => (
                value ? (
                  <span key={key} className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-fixme-text-secondary">
                    {key}: {value}
                  </span>
                ) : null
              ))}
              {error ? <span className="text-xs text-red-400">{error}</span> : null}
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
