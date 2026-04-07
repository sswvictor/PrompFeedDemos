import { useBooking, getStepSequence } from '../../../hooks/useBooking';

const PATHS = [
  {
    id: 'when',
    icon: 'ðŸ“…',
    title: 'When',
    subtitle: 'Pick a time that works for you',
  },
  {
    id: 'what',
    icon: 'ðŸ’…',
    title: 'What',
    subtitle: 'Browse services, then find a slot',
  },
  {
    id: 'where',
    icon: 'ðŸ“',
    title: 'Where',
    subtitle: 'Choose location first',
    requiresBoth: true, // only shown if provider has home + salon
  },
];

import ProviderHeader from '../../../components/ProviderHeader';

export default function BookingEntry() {
  const { provider, dispatch, embedded } = useBooking();

  const hasBoth = provider?.home_service === true && provider?.location_salon != null;

  const visiblePaths = PATHS.filter(p => !p.requiresBoth || hasBoth);

  const handleChoose = (pathId) => {
    // Compute step sequence with the NEW path (can't use goNext() here â€” state
    // batching means state.bookingPath is still null when goNext() runs)
    const seq = getStepSequence(pathId, provider);
    const nextStep = seq[1]; // seq[0] is always 0 (this entry screen)

    dispatch({ type: 'SET_BOOKING_PATH', payload: pathId });
    dispatch({ type: 'SET_STEP', payload: nextStep });

    // Auto-set location type for paths that skip the location step
    if (pathId === 'what' || pathId === 'when') {
      if (!hasBoth) {
        const autoType = provider?.home_service === true ? 'home' : 'salon';
        dispatch({ type: 'SET_LOCATION_TYPE', payload: autoType });
      }
    }
  };

  return (
    <div className="animate-fade-in">
      {/* Provider mini-header â€” hidden when embedded in the profile page */}
      {!embedded && <ProviderHeader />}

      <div className="mt-1 mb-7">
        <h1 className="text-xl font-semibold text-fixme-text-primary">How do you want to start?</h1>
        <p className="text-sm text-fixme-text-secondary mt-1">Choose your booking approach</p>
      </div>

      {/* Path cards */}
      <div className="space-y-3">
        {visiblePaths.map((path) => (
          <button
            key={path.id}
            onClick={() => handleChoose(path.id)}
            className="w-full flex items-center gap-4 p-5 rounded-2xl border border-fixme-border bg-fixme-card hover:border-fixme-accent/50 hover:bg-fixme-accent/5 active:scale-[0.98] transition-all duration-200 text-left"
          >
            {/* Icon */}
            <div className="w-12 h-12 rounded-xl bg-fixme-bg border border-fixme-border flex items-center justify-center text-2xl flex-shrink-0">
              {path.icon}
            </div>

            {/* Text */}
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-fixme-text-primary text-base">{path.title}</div>
              <div className="text-sm text-fixme-text-secondary mt-0.5">{path.subtitle}</div>
            </div>

            {/* Chevron */}
            <svg className="w-5 h-5 text-fixme-text-muted flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        ))}
      </div>

      {/* Powered by */}
      <div className="mt-10 text-center">
        <span className="text-xs text-fixme-text-muted">
          Booking powered by{' '}
          <span className="text-fixme-accent font-semibold">Fixmeapp</span>
        </span>
      </div>
    </div>
  );
}


