import { useState } from 'react';
import { useBooking } from '../../../hooks/useBooking';
import { joinWaitlist } from '../../../api/bookingApi';

const DAYS = [
  { label: 'Mon', value: 0 },
  { label: 'Tue', value: 1 },
  { label: 'Wed', value: 2 },
  { label: 'Thu', value: 3 },
  { label: 'Fri', value: 4 },
  { label: 'Sat', value: 5 },
  { label: 'Sun', value: 6 },
];

const HOURS = Array.from({ length: 16 }, (_, i) => i + 6); // 06:00â€“21:00

function fmtHour(h) {
  return `${String(h).padStart(2, '0')}:00`;
}

export default function WaitlistStep() {
  const { provider, selectedServices, dispatch } = useBooking();

  const [selectedDays, setSelectedDays] = useState([0, 1, 2, 3, 4]); // Monâ€“Fri default
  const [earliestHour, setEarliestHour] = useState(9);
  const [latestHour, setLatestHour] = useState(18);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');

  const toggleDay = (val) => {
    setSelectedDays(prev =>
      prev.includes(val) ? prev.filter(d => d !== val) : [...prev, val]
    );
  };

  const handleSubmit = async () => {
    if (!name.trim() || !email.trim() || selectedDays.length === 0) return;
    setLoading(true);
    setError('');
    try {
      const serviceId = selectedServices[0]?.service_id || null;
      await joinWaitlist({
        providerId: provider.provider_id,
        email: email.trim(),
        name: name.trim(),
        serviceId,
        preferredDays: [...selectedDays].sort((a, b) => a - b),
        earliestHour,
        latestHour,
      });
      setDone(true);
    } catch (e) {
      setError(e.message || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (done) {
    return (
      <div className="animate-fade-in flex flex-col items-center text-center pt-12">
        <div className="w-20 h-20 rounded-full bg-green-500/20 flex items-center justify-center mb-6">
          <svg className="w-10 h-10 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h1 className="text-2xl font-bold text-fixme-text-primary">You're on the waitlist!</h1>
        <p className="text-fixme-text-secondary mt-2 text-sm max-w-xs">
          We'll notify you as soon as a slot matching your preferences opens up.
        </p>
        <button
          onClick={() => dispatch({ type: 'SET_STEP', payload: 0 })}
          className="mt-8 w-full py-3.5 rounded-xl font-semibold text-base bg-fixme-accent text-fixme-bg hover:opacity-90 active:scale-[0.98] transition-all"
        >
          Back to start
        </button>
      </div>
    );
  }

  const canSubmit = name.trim() && email.trim() && selectedDays.length > 0 && !loading;

  return (
    <div className="animate-fade-in pb-24">
      {/* Back to date picker */}
      <button
        onClick={() => dispatch({ type: 'SET_STEP', payload: 3 })}
        className="flex items-center gap-1.5 text-fixme-text-secondary hover:text-fixme-text-primary transition-colors py-2"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        <span className="text-sm">Back</span>
      </button>

      <h1 className="text-xl font-semibold text-fixme-text-primary mt-1">Join the waitlist</h1>
      <p className="text-sm text-fixme-text-secondary mt-1">Tell us when works best â€” we'll notify you first.</p>

      {/* Preferred days */}
      <div className="mt-6">
        <h3 className="text-sm font-medium text-fixme-text-secondary mb-3">Preferred days</h3>
        <div className="grid grid-cols-7 gap-1.5">
          {DAYS.map(({ label, value }) => {
            const active = selectedDays.includes(value);
            return (
              <button
                key={value}
                onClick={() => toggleDay(value)}
                className={`
                  py-2.5 rounded-xl text-sm font-medium transition-all duration-150
                  ${active
                    ? 'bg-fixme-accent text-fixme-bg'
                    : 'bg-fixme-card border border-fixme-border text-fixme-text-secondary hover:border-fixme-accent/50'
                  }
                `}
              >
                {label}
              </button>
            );
          })}
        </div>
        {selectedDays.length === 0 && (
          <p className="text-red-400 text-xs mt-1.5">Pick at least one day</p>
        )}
      </div>

      {/* Preferred time range */}
      <div className="mt-6">
        <h3 className="text-sm font-medium text-fixme-text-secondary mb-3">Preferred time range</h3>
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <label className="text-xs text-fixme-text-muted mb-1 block">From</label>
            <select
              value={earliestHour}
              onChange={(e) => {
                const val = Number(e.target.value);
                setEarliestHour(val);
                if (val >= latestHour) setLatestHour(val + 1);
              }}
              className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-3 text-sm text-fixme-text-primary focus:outline-none focus:border-fixme-accent transition-colors"
            >
              {HOURS.filter(h => h < 21).map(h => (
                <option key={h} value={h}>{fmtHour(h)}</option>
              ))}
            </select>
          </div>
          <div className="text-fixme-text-muted text-sm pt-5">â†’</div>
          <div className="flex-1">
            <label className="text-xs text-fixme-text-muted mb-1 block">To</label>
            <select
              value={latestHour}
              onChange={(e) => setLatestHour(Number(e.target.value))}
              className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-3 text-sm text-fixme-text-primary focus:outline-none focus:border-fixme-accent transition-colors"
            >
              {HOURS.filter(h => h > earliestHour).map(h => (
                <option key={h} value={h}>{fmtHour(h)}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Contact */}
      <div className="mt-6 space-y-3">
        <h3 className="text-sm font-medium text-fixme-text-secondary">Your contact</h3>
        <input
          type="text"
          placeholder="Your name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-4 py-3 text-sm text-fixme-text-primary placeholder-fixme-text-muted focus:outline-none focus:border-fixme-accent transition-colors"
        />
        <input
          type="email"
          placeholder="Email address"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-4 py-3 text-sm text-fixme-text-primary placeholder-fixme-text-muted focus:outline-none focus:border-fixme-accent transition-colors"
        />
      </div>

      {error && <p className="text-red-400 text-xs mt-3">{error}</p>}

      {/* Fixed submit button */}
      <div className="fixed bottom-0 inset-x-0 z-20 flex justify-center">
        <div className="w-full max-w-md px-4 pb-6 pt-3 bg-fixme-bg/95 backdrop-blur-sm border-t border-fixme-border/30">
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="w-full py-3.5 rounded-xl font-semibold text-base bg-fixme-accent text-fixme-bg disabled:opacity-40 hover:opacity-90 active:scale-[0.98] transition-all"
          >
            {loading ? 'Joiningâ€¦' : 'Join waitlist â†’'}
          </button>
        </div>
      </div>
    </div>
  );
}


