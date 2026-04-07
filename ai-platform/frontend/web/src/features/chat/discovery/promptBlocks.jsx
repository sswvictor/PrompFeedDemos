function classNames(...values) {
  return values.filter(Boolean).join(' ');
}

function formatDateLabel(value) {
  if (!value) return '';
  try {
    return new Date(value).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return value;
  }
}

function formatDateTimeLabel(value) {
  if (!value) return '';
  try {
    return new Date(value).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return value;
  }
}

function emphasisClass(field, emphasis) {
  return emphasis.includes(field)
    ? 'border-fixme-accent/60 bg-fixme-accent/10 text-fixme-accent'
    : 'border-white/10 bg-white/5 text-fixme-text-secondary';
}

export function HeroCardBlock({ block }) {
  const { title, subtitle, tone } = block.data;
  const toneStyles = {
    guided: 'from-[#1d1f2e] via-[#0f111a] to-[#121417]',
    decisive: 'from-[#1f3024] via-[#0f1713] to-[#121417]',
    explore: 'from-[#2e2216] via-[#15110f] to-[#121417]',
    returning: 'from-[#251d31] via-[#15111b] to-[#121417]',
  };

  return (
    <section className={classNames(
      'rounded-[30px] border border-white/10 bg-gradient-to-br p-5 shadow-[0_20px_80px_rgba(0,0,0,0.24)] animate-slide-up',
      toneStyles[tone],
    )}>
      <div className="inline-flex items-center rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-fixme-text-secondary">
        Prompt Feed
      </div>
      <h1 className="mt-4 text-3xl font-semibold leading-tight text-white">{title}</h1>
      <p className="mt-3 max-w-xl text-sm leading-6 text-[#d3d7de]">{subtitle}</p>
    </section>
  );
}

export function SearchSummaryCardBlock({ block }) {
  const { query, subtitle, detected_signals, result_count } = block.data;
  return (
    <section className="rounded-[26px] border border-white/10 bg-[linear-gradient(180deg,rgba(21,24,30,0.96),rgba(11,13,16,0.96))] p-4 animate-fade-in">
      <div className="text-xs uppercase tracking-[0.16em] text-fixme-text-secondary">Search understanding</div>
      <p className="mt-2 text-base font-medium text-fixme-text-primary">{subtitle}</p>
      <p className="mt-2 text-sm text-fixme-text-secondary">"{query}" matched {result_count} providers.</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {detected_signals.map((signal) => (
          <span
            key={signal}
            className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-fixme-text-secondary"
          >
            {signal.replaceAll('_', ' ')}
          </span>
        ))}
      </div>
    </section>
  );
}

function ProviderStat({ label, value, emphasized }) {
  return (
    <div className={classNames(
      'rounded-2xl border px-3 py-2',
      emphasized
        ? 'border-fixme-accent/50 bg-fixme-accent/10 text-fixme-accent'
        : 'border-white/10 bg-white/5 text-fixme-text-secondary',
    )}>
      <div className="text-[11px] uppercase tracking-[0.12em]">{label}</div>
      <div className="mt-1 text-sm font-medium">{value}</div>
    </div>
  );
}

function ProviderCard({ provider, emphasis = [] }) {
  return (
    <article className="rounded-[26px] border border-white/10 bg-[linear-gradient(180deg,rgba(20,23,29,0.96),rgba(10,12,15,0.96))] p-4 shadow-[0_12px_40px_rgba(0,0,0,0.18)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-fixme-text-primary">{provider.name}</h3>
          <p className="mt-1 text-sm text-fixme-text-secondary">
            {[provider.city, provider.location_salon].filter(Boolean).join(' / ') || 'Location coming soon'}
          </p>
          {provider.bio ? (
            <p className="mt-3 text-sm leading-6 text-fixme-text-secondary">{provider.bio}</p>
          ) : null}
        </div>
        <div className={classNames(
          'rounded-full border px-3 py-1 text-xs',
          emphasisClass('price_level', emphasis),
        )}>
          {provider.price_level_label}
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <ProviderStat
          label="Rating"
          value={provider.rating?.toFixed?.(1) || provider.rating || 'N/A'}
          emphasized={emphasis.includes('rating')}
        />
        <ProviderStat
          label="Revisit"
          value={`${Math.round((provider.revisit_rate || 0) * 100)}%`}
          emphasized={emphasis.includes('revisit_rate')}
        />
        <ProviderStat
          label="From"
          value={provider.starting_from ? `${Math.round(provider.starting_from)} SEK` : 'Ask provider'}
          emphasized={emphasis.includes('starting_from')}
        />
        <ProviderStat
          label="Next slot"
          value={provider.next_available ? formatDateTimeLabel(provider.next_available) : 'No slots yet'}
          emphasized={emphasis.includes('next_available')}
        />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {provider.matched_services.slice(0, 4).map((service) => (
          <span
            key={service.service_id}
            className={classNames(
              'rounded-full border px-3 py-1 text-xs',
              emphasisClass('matched_services', emphasis),
            )}
          >
            {service.name}
          </span>
        ))}
      </div>

      {provider.vibe_tags?.length ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {provider.vibe_tags.slice(0, 4).map((tag) => (
            <span
              key={tag}
              className={classNames(
                'rounded-full border px-3 py-1 text-xs',
                emphasisClass('vibe_tags', emphasis),
              )}
            >
              {tag}
            </span>
          ))}
        </div>
      ) : null}
    </article>
  );
}

export function ProviderResultsBlock({ block }) {
  return (
    <section className="space-y-3 animate-fade-in">
      <div className="flex items-end justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-[0.16em] text-fixme-text-secondary">Provider matches</div>
          <h2 className="mt-1 text-xl font-semibold text-fixme-text-primary">
            {block.data.total_found} options ranked for this prompt
          </h2>
        </div>
        <div className="text-xs text-fixme-text-secondary">Sort: {block.data.sort_strategy}</div>
      </div>
      <div className="space-y-3">
        {block.data.providers.map((provider) => (
          <ProviderCard key={provider.provider_id} provider={provider} emphasis={block.emphasis || []} />
        ))}
      </div>
    </section>
  );
}

export function AvailabilityPickerBlock({ block }) {
  const { provider_name: providerName, available_dates: availableDates, slots_by_date: slotsByDate } = block.data;
  return (
    <section className="rounded-[26px] border border-white/10 bg-[linear-gradient(180deg,rgba(21,24,30,0.96),rgba(11,13,16,0.96))] p-4 animate-fade-in">
      <div className="text-xs uppercase tracking-[0.16em] text-fixme-text-secondary">Availability preview</div>
      <h2 className="mt-1 text-lg font-semibold text-fixme-text-primary">{providerName}</h2>
      <div className="mt-4 flex flex-wrap gap-2">
        {availableDates.slice(0, 5).map((date) => (
          <div key={date} className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2">
            <div className="text-sm font-medium text-fixme-text-primary">{formatDateLabel(date)}</div>
            <div className="mt-1 text-xs text-fixme-text-secondary">{(slotsByDate[date] || []).length} slots</div>
          </div>
        ))}
      </div>
      {availableDates[0] ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {(slotsByDate[availableDates[0]] || []).slice(0, 6).map((slot) => (
            <span
              key={slot.start}
              className="rounded-full border border-fixme-accent/30 bg-fixme-accent/10 px-3 py-1 text-sm text-fixme-accent"
            >
              {slot.time_label}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  );
}

export function ProfileMemoryCardBlock({ block }) {
  const { display_name: displayName, visit_count: visitCount, last_visit: lastVisit, preferences } = block.data;
  return (
    <section className="rounded-[26px] border border-emerald-400/20 bg-[linear-gradient(180deg,rgba(23,36,30,0.82),rgba(11,15,13,0.95))] p-4 animate-fade-in">
      <div className="text-xs uppercase tracking-[0.16em] text-emerald-300">Returning context</div>
      <h2 className="mt-1 text-lg font-semibold text-white">
        {displayName ? `Welcome back, ${displayName}` : 'Returning customer'}
      </h2>
      <p className="mt-2 text-sm text-[#d9ece0]">
        {visitCount} previous visits{lastVisit ? ` / last booked ${formatDateLabel(lastVisit)}` : ''}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        {preferences.slice(0, 4).map((preference) => (
          <span
            key={`${preference.category}-${preference.key}`}
            className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs text-emerald-200"
          >
            {preference.value}
          </span>
        ))}
      </div>
    </section>
  );
}

export function CTAButtonRowBlock({ block }) {
  return (
    <section className="flex flex-wrap gap-3 animate-fade-in">
      {block.data.buttons.map((button, index) => (
        <button
          key={`${button.label}-${index}`}
          type="button"
          className={classNames(
            'rounded-full border px-4 py-2 text-sm font-medium transition',
            button.style === 'primary' && 'border-fixme-accent bg-fixme-accent text-fixme-bg',
            button.style === 'secondary' && 'border-fixme-accent text-fixme-accent',
            button.style === 'ghost' && 'border-white/10 bg-white/5 text-fixme-text-secondary',
          )}
        >
          {button.label}
        </button>
      ))}
    </section>
  );
}

export function ConversationalFollowUpBlock({ block }) {
  return (
    <section className="rounded-[26px] border border-white/10 bg-[linear-gradient(180deg,rgba(21,24,30,0.96),rgba(11,13,16,0.96))] p-4 animate-fade-in">
      <div className="text-xs uppercase tracking-[0.16em] text-fixme-text-secondary">Refine the search</div>
      <div className="mt-4 flex flex-wrap gap-2">
        {block.data.suggestions.map((suggestion) => (
          <span key={suggestion} className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-sm text-fixme-text-primary">
            {suggestion}
          </span>
        ))}
      </div>
    </section>
  );
}

export function UnsupportedBlock({ block }) {
  return (
    <section className="rounded-[24px] border border-dashed border-fixme-border bg-fixme-card p-4">
      <div className="text-sm text-fixme-text-secondary">Unsupported block type: {block.type}</div>
    </section>
  );
}
