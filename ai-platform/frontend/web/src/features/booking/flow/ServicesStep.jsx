import { useState, useEffect } from 'react';
import { useBooking } from '../../../hooks/useBooking';
import { getServices } from '../../../api/bookingApi';
import BackButton from '../../../components/BackButton';

// Category display config matching the design
const CATEGORY_CONFIG = {
  nails: { label: 'Nails', icon: 'ðŸ’…' },
  hair: { label: 'Hair', icon: 'ðŸ’‡' },
  lashes: { label: 'Lashes', icon: 'ðŸ‘ï¸' },
  brows: { label: 'Brows', icon: 'âœ¨' },
  spa: { label: 'Spa', icon: 'ðŸ§–' },
  makeup: { label: 'Makeup', icon: 'ðŸ’„' },
  skincare: { label: 'Skincare', icon: 'ðŸ§´' },
  massage: { label: 'Massage', icon: 'ðŸ’†' },
  other: { label: 'Other', icon: 'â­' },
};

export default function ServicesStep() {
  const { provider, selectedServices, locationType, dispatch, goNext } = useBooking();
  const [services, setServices] = useState([]);
  const [activeCategory, setActiveCategory] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!provider) return;
    setLoading(true);
    getServices(provider.provider_id)
      .then((data) => {
        // Filter by home_service if user chose home visit
        const filtered = locationType === 'home'
          ? data.filter(s => s.home_service_available)
          : data;
        setServices(filtered);
        // Set first category as active
        if (filtered.length > 0) {
          const cats = [...new Set(filtered.map(s => s.category))];
          setActiveCategory(cats[0]);
        }
      })
      .catch((err) => dispatch({ type: 'SET_ERROR', payload: err.message }))
      .finally(() => setLoading(false));
  }, [provider, locationType]);

  const categories = [...new Set(services.map(s => s.category))];
  const filteredServices = services.filter(s => s.category === activeCategory);

  const isSelected = (serviceId) => selectedServices.some(s => s.service_id === serviceId);

  const totalDuration = selectedServices.reduce((sum, s) => sum + (s.duration_minutes || 0), 0);
  const totalPrice = selectedServices.reduce((sum, s) => sum + (s.price_ex_vat || 0), 0);

  const handleContinue = () => {
    if (selectedServices.length > 0) {
      goNext();
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-fixme-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className={`animate-fade-in ${selectedServices.length > 0 ? 'pb-28' : 'pb-4'}`}>
      <BackButton />

      <h1 className="text-xl font-semibold text-fixme-text-primary mt-1">Select services</h1>
      <p className="text-sm text-fixme-text-secondary mt-1">Choose what you'd like to book</p>

      {/* Category tabs */}
      <div className="flex gap-2 mt-4 overflow-x-auto pb-2 -mx-1 px-1 scrollbar-hide">
        {categories.map((cat) => {
          const config = CATEGORY_CONFIG[cat] || CATEGORY_CONFIG.other;
          return (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`
                flex items-center gap-1.5 px-3.5 py-2 rounded-full text-sm font-medium whitespace-nowrap
                transition-all duration-200
                ${activeCategory === cat
                  ? 'bg-fixme-accent text-fixme-bg'
                  : 'bg-fixme-card border border-fixme-border text-fixme-text-secondary hover:text-fixme-text-primary'
                }
              `}
            >
              <span className="text-xs">{config.icon}</span>
              {config.label}
            </button>
          );
        })}
      </div>

      {/* Service list */}
      <div className="mt-4 space-y-2">
        {filteredServices.map((service) => (
          <button
            key={service.service_id}
            onClick={() => dispatch({ type: 'TOGGLE_SERVICE', payload: service })}
            className={`
              w-full flex items-center justify-between p-4 rounded-xl border transition-all duration-200
              ${isSelected(service.service_id)
                ? 'bg-fixme-accent/10 border-fixme-accent'
                : 'bg-fixme-card border-fixme-border hover:border-fixme-text-muted'
              }
            `}
          >
            <div className="text-left flex-1 min-w-0">
              <div className="font-medium text-fixme-text-primary">{service.name}</div>
              <div className="text-sm text-fixme-text-secondary mt-0.5">
                {service.duration_minutes} min
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-fixme-accent font-semibold">
                {Math.round(service.price_ex_vat)} kr
              </span>
              <div className={`
                w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all
                ${isSelected(service.service_id)
                  ? 'bg-fixme-accent border-fixme-accent'
                  : 'border-fixme-text-muted'
                }
              `}>
                {isSelected(service.service_id) && (
                  <svg className="w-3 h-3 text-fixme-bg" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* Fixed summary + continue */}
      {selectedServices.length > 0 && (
        <div className="fixed bottom-0 inset-x-0 z-20 flex justify-center animate-slide-up">
          <div className="w-full max-w-md px-4 pb-6 pt-3 bg-fixme-bg/95 backdrop-blur-sm border-t border-fixme-border/30">
            <div className="flex justify-between text-sm mb-3">
              <span className="text-fixme-text-secondary">
                {selectedServices.length} service{selectedServices.length > 1 ? 's' : ''} Â· {totalDuration} min
              </span>
              <span className="text-fixme-accent font-semibold">{Math.round(totalPrice)} kr</span>
            </div>
            <button
              onClick={handleContinue}
              className="w-full py-3.5 rounded-xl font-semibold text-base bg-fixme-accent text-fixme-bg hover:opacity-90 active:scale-[0.98] transition-all duration-200"
            >
              Continue
            </button>
          </div>
        </div>
      )}
    </div>
  );
}



