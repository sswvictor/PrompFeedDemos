import { useBooking } from '../../../hooks/useBooking';

function formatTimeSlot(slot) {
  if (!slot) return '-';
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
  const options = { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' };
  return d.toLocaleDateString('en-US', options);
}

export default function BookingConfirmed() {
  const { provider, selectedServices, selectedDate, selectedTime, booking, totalPrice, customerEmail, onExit } = useBooking();

  // Persist rebook shortcut - powers the one-tap chip on the profile page
  if (provider && selectedServices.length > 0) {
    const s = selectedServices[0];
    try {
      localStorage.setItem(`fixme_rebook_${provider.provider_id}`, JSON.stringify({
        service_id: s.service_id,
        service_name: s.name,
        duration_minutes: s.duration_minutes,
        price_ex_vat: s.price_ex_vat,
        booked_at: new Date().toISOString(),
      }));
    } catch {}
  }

  return (
    <div className="animate-fade-in flex flex-col items-center text-center pt-8">
      {/* Success icon */}
      <div className="w-20 h-20 rounded-full bg-fixme-success/20 flex items-center justify-center mb-6 animate-checkmark">
        <svg className="w-10 h-10 text-fixme-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
        </svg>
      </div>

      <h1 className="text-2xl font-bold text-fixme-text-primary">Booking Confirmed!</h1>
      <p className="text-fixme-text-secondary mt-2 text-sm">
        Your appointment has been booked
      </p>

      {/* Booking reference */}
      {booking?.booking_number && (
        <div className="mt-3 inline-flex items-center gap-1.5 bg-fixme-card border border-fixme-border rounded-full px-4 py-1.5">
          <span className="text-xs text-fixme-text-muted">Booking #</span>
          <span className="text-sm font-semibold text-fixme-accent">{booking.booking_number}</span>
        </div>
      )}

      {/* Booking details card */}
      <div className="mt-6 w-full bg-fixme-card border border-fixme-border rounded-xl p-5 text-left space-y-4">
        {/* Provider */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-fixme-border flex items-center justify-center text-fixme-accent font-semibold">
            {provider?.name?.charAt(0)}
          </div>
          <div>
            <div className="text-fixme-text-primary font-medium">{provider?.name}</div>
            <div className="text-xs text-fixme-text-muted">{provider?.city}</div>
          </div>
        </div>

        {/* Date & time */}
        <div className="flex items-center gap-2 text-sm pt-3 border-t border-fixme-border">
          <svg className="w-4 h-4 text-fixme-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <span className="text-fixme-text-primary">{formatDateDisplay(selectedDate)}</span>
        </div>

        <div className="flex items-center gap-2 text-sm">
          <svg className="w-4 h-4 text-fixme-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-fixme-text-primary">{formatTimeSlot(selectedTime)}</span>
        </div>

        {/* Services */}
        <div className="pt-3 border-t border-fixme-border space-y-2">
          {selectedServices.map((s) => (
            <div key={s.service_id} className="flex justify-between text-sm">
              <span className="text-fixme-text-secondary">{s.name}</span>
              <span className="text-fixme-text-primary">{Math.round(s.price_ex_vat)} kr</span>
            </div>
          ))}
          <div className="flex justify-between pt-2 border-t border-fixme-border">
            <span className="text-fixme-text-primary font-medium">Total</span>
            <span className="text-fixme-accent font-bold">{Math.round(totalPrice)} kr</span>
          </div>
        </div>

        {/* Payment note */}
        <div className="flex items-center gap-2 text-xs text-fixme-text-muted pt-2">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Payment at place
        </div>
      </div>

      {/* Actions */}
      <div className="mt-6 w-full space-y-3 mb-8">
        {/* Create account CTA — takes customer to onboarding with email pre-filled */}
        <button
          className="w-full py-3.5 rounded-xl font-semibold text-base bg-fixme-accent text-fixme-bg hover:bg-fixme-accent-light active:scale-[0.98] transition-all duration-200"
          onClick={() => {
            const dest = customerEmail
              ? `/customer/welcome?email=${encodeURIComponent(customerEmail)}`
              : '/customer/welcome';
            window.location.href = dest;
          }}
        >
          Create account on Fixmeapp
        </button>

        {/* Back to Instagram */}
        <button
          className="w-full py-3 rounded-xl text-sm font-medium text-fixme-text-secondary border border-fixme-border hover:border-fixme-text-muted transition-colors"
          onClick={() => { onExit ? onExit() : (window.location.href = 'instagram://'); }}
        >
          {onExit ? 'Back to profile' : 'Back to Instagram'}
        </button>
      </div>
    </div>
  );
}


