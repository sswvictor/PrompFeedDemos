import { useState } from 'react';
import { useBooking } from '../../../hooks/useBooking';
import { createBooking, createCustomer } from '../../../api/bookingApi';
import BackButton from '../../../components/BackButton';

// â”€â”€â”€ Session preference chips â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// These are lightweight signals the customer sends to the provider before the visit.
// Think: Uber Quiet Mode, Airbnb special requests.
const SESSION_PREFERENCES = [
  { key: 'quiet_session',   emoji: 'ðŸ¤«', label: 'Quiet session'     },
  { key: 'bringing_dog',    emoji: 'ðŸ•', label: 'Bringing my dog'   },
  { key: 'coffee_please',   emoji: 'â˜•', label: 'Coffee please'     },
  { key: 'wine_please',     emoji: 'ðŸ·', label: 'Wine please'       },
  { key: 'private_room',    emoji: 'ðŸ”’', label: 'Private room'      },
  { key: 'eco_products',    emoji: 'ðŸŒ¿', label: 'Eco products'      },
  { key: 'bringing_child',  emoji: 'ðŸ‘¶', label: 'Bringing a child'  },
  { key: 'need_accessible', emoji: 'â™¿', label: 'Need accessible'   },
  { key: 'pay_by_card',     emoji: 'ðŸ’³', label: 'Pay by card'       },
];
// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function formatTimeSlot(slot) {
  if (!slot) return 'â€”';
  if (typeof slot === 'string' && slot.includes('T')) {
    return slot.split('T')[1].substring(0, 5);
  }
  if (typeof slot === 'object' && slot !== null && slot.start) {
    const s = slot.start;
    return s.includes('T') ? s.split('T')[1].substring(0, 5) : s;
  }
  return String(slot).substring(0, 5);
}

function formatDateDisplay(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  const options = { weekday: 'long', day: 'numeric', month: 'long' };
  return d.toLocaleDateString('en-US', options);
}

export default function ConfirmStep() {
  const {
    provider, selectedServices, selectedDate, selectedTime,
    locationType, totalDuration, totalPrice, referralSource, dispatch
  } = useBooking();

  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [notes, setNotes] = useState('');
  const [selectedPrefs, setSelectedPrefs] = useState([]);
  const [gdprConsent, setGdprConsent] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const togglePref = (key) => {
    setSelectedPrefs((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  };

  const canSubmit = name.trim() && phone.trim() && email.trim() && gdprConsent && !isSubmitting;

  const handleBook = async () => {
    if (!canSubmit) return;
    setIsSubmitting(true);
    setError(null);

    try {
      // 1. Create customer
      const customerData = {
        provider_id: provider.provider_id,
        display_name: name.trim(),
        phone: phone.trim(),
        source_channel: 'web',
      };
      if (email.trim()) {
        customerData.customer_email = email.trim();
      }
      const customer = await createCustomer(customerData);

      // 2. Build booking start/end times (naive local datetimes â€” backend uses Europe/Stockholm)
      const timeStr = formatTimeSlot(selectedTime);
      const [hours, minutes] = timeStr.split(':').map(Number);
      const startDatetime = `${selectedDate}T${timeStr}:00`;
      const endTotalMinutes = hours * 60 + minutes + totalDuration;
      const endH = String(Math.floor(endTotalMinutes / 60)).padStart(2, '0');
      const endM = String(endTotalMinutes % 60).padStart(2, '0');
      const endDatetime = `${selectedDate}T${endH}:${endM}:00`;

      // 3. Create booking with line items + session preferences
      const bookingData = {
        provider_id: provider.provider_id,
        customer_id: customer.customer_id,
        scheduled_start: startDatetime,
        scheduled_end: endDatetime,
        customer_notes: notes.trim() || null,
        session_preferences: selectedPrefs,
        referral_source: referralSource || null,
        status: "confirmed",
        line_items: selectedServices.map(s => ({
          service_type: s.name,
          quantity: 1,
          unit_price_ex_vat: s.price_ex_vat,
          vat_percent: s.vat_percent || provider.vat_percent || 25,
        })),
      };

      const booking = await createBooking(bookingData);

      // Save to context and go to confirmation
      dispatch({ type: 'SET_CONTACT', payload: { customerName: name, customerPhone: phone, customerEmail: email } });
      dispatch({ type: 'SET_BOOKING', payload: booking });
      dispatch({ type: 'SET_STEP', payload: 5 });
    } catch (err) {
      const msg = err.message || '';
      if (msg.toLowerCase().includes('time slot') || msg.toLowerCase().includes('no longer available')) {
        setError('This time slot was just taken. Let\u2019s pick another time.');
        // Go back to DateTime step after a short delay so user sees the message
        setTimeout(() => dispatch({ type: 'SET_STEP', payload: 3 }), 2500);
      } else {
        setError(msg || 'Something went wrong. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="animate-fade-in">
      <BackButton />

      <h1 className="text-xl font-semibold text-fixme-text-primary mt-1">Confirm your booking</h1>
      <p className="text-sm text-fixme-text-secondary mt-1">Review details and fill in your info</p>

      {/* Booking summary */}
      <div className="mt-4 bg-fixme-card border border-fixme-border rounded-xl p-4 space-y-3">
        {/* Provider */}
        <div className="flex items-center gap-3 pb-3 border-b border-fixme-border">
          <div className="w-10 h-10 rounded-full bg-fixme-border flex items-center justify-center text-fixme-accent font-semibold">
            {provider?.name?.charAt(0)}
          </div>
          <div>
            <div className="text-fixme-text-primary font-medium text-sm">{provider?.name}</div>
            <div className="text-xs text-fixme-text-muted">
              {locationType === 'home' ? 'Home visit' : provider?.city || 'At location'}
            </div>
          </div>
        </div>

        {/* Services */}
        <div className="space-y-2">
          {selectedServices.map((s) => (
            <div key={s.service_id} className="flex justify-between text-sm">
              <span className="text-fixme-text-secondary">{s.name}</span>
              <span className="text-fixme-text-primary">{Math.round(s.price_ex_vat)} kr</span>
            </div>
          ))}
        </div>

        {/* Date & time */}
        <div className="pt-3 border-t border-fixme-border flex items-center gap-2 text-sm">
          <svg className="w-4 h-4 text-fixme-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <span className="text-fixme-text-primary">{formatDateDisplay(selectedDate)}</span>
          <span className="text-fixme-text-muted">at</span>
          <span className="text-fixme-text-primary">{formatTimeSlot(selectedTime)}</span>
        </div>

        {/* Total */}
        <div className="pt-3 border-t border-fixme-border flex justify-between">
          <span className="text-fixme-text-secondary font-medium">Total</span>
          <span className="text-fixme-accent font-bold text-lg">{Math.round(totalPrice)} kr</span>
        </div>
      </div>

      {/* Payment method */}
      <div className="mt-4 bg-fixme-card border border-fixme-border rounded-xl p-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-fixme-accent/20 flex items-center justify-center">
          <svg className="w-4 h-4 text-fixme-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
          </svg>
        </div>
        <div>
          <div className="text-fixme-text-primary text-sm font-medium">Pay at place</div>
          <div className="text-xs text-fixme-text-muted">Pay when you arrive</div>
        </div>
      </div>

      {/* â”€â”€ Preferences â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      <div className="mt-5">
        <h3 className="text-sm font-medium text-fixme-text-secondary mb-1">Any preferences?</h3>
        <p className="text-xs text-fixme-text-muted mb-3">Optional â€” lets the provider prepare for your visit</p>

        <div className="flex flex-wrap gap-2">
          {SESSION_PREFERENCES.map((pref) => {
            const active = selectedPrefs.includes(pref.key);
            return (
              <button
                key={pref.key}
                type="button"
                onClick={() => togglePref(pref.key)}
                className={`
                  flex items-center gap-1.5 px-3 py-2 rounded-full border text-sm font-medium
                  transition-all duration-150 active:scale-95 select-none
                  ${active
                    ? 'border-fixme-accent bg-fixme-accent/15 text-fixme-accent'
                    : 'border-fixme-border bg-fixme-card text-fixme-text-secondary hover:border-fixme-accent/50'
                  }
                `}
              >
                <span className="text-base leading-none">{pref.emoji}</span>
                <span>{pref.label}</span>
                {active && (
                  <span className="ml-0.5 text-fixme-accent text-xs">âœ“</span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Contact form */}
      <div className="mt-5 space-y-3">
        <h3 className="text-sm font-medium text-fixme-text-secondary">Your contact info</h3>

        <div>
          <input
            type="text"
            placeholder="Full name *"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full bg-fixme-card border border-fixme-border rounded-xl px-4 py-3 text-fixme-text-primary placeholder-fixme-text-muted text-sm focus:outline-none focus:border-fixme-accent transition-colors"
          />
        </div>

        <div>
          <input
            type="tel"
            placeholder="Phone number *"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="w-full bg-fixme-card border border-fixme-border rounded-xl px-4 py-3 text-fixme-text-primary placeholder-fixme-text-muted text-sm focus:outline-none focus:border-fixme-accent transition-colors"
          />
        </div>

        <div>
          <input
            type="email"
            placeholder="Email address *"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full bg-fixme-card border border-fixme-border rounded-xl px-4 py-3 text-fixme-text-primary placeholder-fixme-text-muted text-sm focus:outline-none focus:border-fixme-accent transition-colors"
          />
        </div>

        <div>
          <textarea
            placeholder="Anything else for the provider? (optional)"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className="w-full bg-fixme-card border border-fixme-border rounded-xl px-4 py-3 text-fixme-text-primary placeholder-fixme-text-muted text-sm focus:outline-none focus:border-fixme-accent transition-colors resize-none"
          />
        </div>
      </div>

      {/* GDPR consent â€” required before booking */}
      <div className="mt-5">
        <button
          type="button"
          onClick={() => setGdprConsent((v) => !v)}
          className="flex items-start gap-3 w-full text-left group"
        >
          {/* Custom checkbox */}
          <div className={`
            mt-0.5 w-5 h-5 rounded-md flex-shrink-0 border-2 flex items-center justify-center
            transition-all duration-150
            ${gdprConsent
              ? 'bg-fixme-accent border-fixme-accent'
              : 'border-fixme-border bg-fixme-card group-hover:border-fixme-accent/60'
            }
          `}>
            {gdprConsent && (
              <svg viewBox="0 0 10 8" className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--color-fixme-bg, #0d0d0d)' }}>
                <polyline points="1,4 3.5,6.5 9,1" />
              </svg>
            )}
          </div>
          <p className="text-xs text-fixme-text-muted leading-relaxed">
            I agree that{' '}
            <span className="text-fixme-text-secondary font-medium">{provider?.name}</span>
            {' '}may store my contact details to manage this booking, in accordance with GDPR.
          </p>
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="mt-3 bg-fixme-error/10 border border-fixme-error/30 rounded-xl px-4 py-3 text-fixme-error text-sm">
          {error}
        </div>
      )}

      {/* Book button */}
      <div className="mt-6 mb-8">
        <button
          onClick={handleBook}
          disabled={!canSubmit}
          className={`
            w-full py-3.5 rounded-xl font-semibold text-base transition-all duration-200 flex items-center justify-center gap-2
            ${canSubmit
              ? 'bg-fixme-accent text-fixme-bg hover:bg-fixme-accent-light active:scale-[0.98]'
              : 'bg-fixme-card text-fixme-text-muted cursor-not-allowed'
            }
          `}
        >
          {isSubmitting ? (
            <>
              <div className="w-5 h-5 border-2 border-fixme-bg border-t-transparent rounded-full animate-spin" />
              Booking...
            </>
          ) : (
            'Complete Booking'
          )}
        </button>
      </div>
    </div>
  );
}



