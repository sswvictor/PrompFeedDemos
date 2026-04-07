import { useBooking } from '../../../hooks/useBooking';
import ProviderHeader from '../../../components/ProviderHeader';

const LOCATION_OPTIONS = [
  {
    id: 'salon',
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
      </svg>
    ),
    title: 'At location',
    subtitle: 'Visit the salon',
  },
  {
    id: 'home',
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
    ),
    title: 'Home visit',
    subtitle: 'Provider comes to you',
  },
];

export default function LocationStep() {
  const { locationType, provider, selectedServices, dispatch, goNext } = useBooking();

  const handleSelect = (id) => {
    dispatch({ type: 'SET_LOCATION_TYPE', payload: locationType === id ? null : id });
  };

  const handleContinue = () => {
    if (locationType) {
      goNext();
    }
  };

  // Filter options based on provider capabilities
  const availableOptions = LOCATION_OPTIONS.filter(opt => {
    if (opt.id === 'salon') return provider?.location_salon !== false;
    if (opt.id === 'home') return provider?.home_service === true;
    return true;
  });

  return (
    <div className="animate-fade-in">
      <ProviderHeader />

      <div className="mt-2 mb-6">
        <h1 className="text-xl font-semibold text-fixme-text-primary">Where would you like your appointment?</h1>
        <p className="text-sm text-fixme-text-secondary mt-1">Choose a location type</p>
      </div>

      <div className="space-y-3">
        {availableOptions.map((option) => (
          <button
            key={option.id}
            onClick={() => handleSelect(option.id)}
            className={`
              w-full flex items-center gap-4 p-4 rounded-xl border transition-all duration-200
              ${locationType === option.id
                ? 'bg-fixme-accent/10 border-fixme-accent'
                : 'bg-fixme-card border-fixme-border hover:border-fixme-text-muted'
              }
            `}
          >
            <div className={`
              p-2.5 rounded-lg
              ${locationType === option.id ? 'bg-fixme-accent/20 text-fixme-accent' : 'bg-fixme-border/50 text-fixme-text-secondary'}
            `}>
              {option.icon}
            </div>
            <div className="text-left">
              <div className={`font-medium ${locationType === option.id ? 'text-fixme-text-primary' : 'text-fixme-text-primary'}`}>
                {option.title}
              </div>
              <div className="text-sm text-fixme-text-secondary">{option.subtitle}</div>
            </div>
            {locationType === option.id && (
              <div className="ml-auto">
                <svg className="w-5 h-5 text-fixme-accent" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
              </div>
            )}
          </button>
        ))}
      </div>

      {/* Selected service summary */}
      {selectedServices && selectedServices.length > 0 && (
        <div className="mt-8 rounded-xl bg-fixme-card border border-fixme-border px-4 py-3 flex items-center gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-fixme-text-muted text-[10px] uppercase tracking-widest mb-0.5">Selected service</p>
            <p className="text-fixme-text-primary text-sm font-semibold truncate">{selectedServices[0].name}</p>
            <p className="text-fixme-text-muted text-xs">
              {selectedServices[0].duration_minutes} min &middot; {Math.round(selectedServices[0].price_ex_vat)} SEK
            </p>
          </div>
        </div>
      )}

      {/* Continue button */}
      <div className="mt-4">
        <button
          onClick={handleContinue}
          disabled={!locationType}
          className={`
            w-full py-3.5 rounded-xl font-semibold text-base transition-all duration-200
            ${locationType
              ? 'bg-fixme-accent text-fixme-bg hover:bg-fixme-accent-light active:scale-[0.98]'
              : 'bg-fixme-card text-fixme-text-muted cursor-not-allowed'
            }
          `}
        >
          Continue
        </button>
      </div>
    </div>
  );
}


