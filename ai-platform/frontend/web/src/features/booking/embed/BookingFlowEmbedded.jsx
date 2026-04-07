import { BookingProvider, useBooking } from '../../../hooks/useBooking';
import StepProgress from '../../../components/StepProgress';
import BookingEntry from '../flow/BookingEntry';
import LocationStep from '../flow/LocationStep';
import ServicesStep from '../flow/ServicesStep';
import DateTimeStep from '../flow/DateTimeStep';
import ConfirmStep from '../flow/ConfirmStep';
import BookingConfirmed from '../flow/BookingConfirmed';

function EmbeddedSteps() {
  const { currentStep } = useBooking();
  switch (currentStep) {
    case 0: return <BookingEntry />;
    case 1: return <LocationStep />;
    case 2: return <ServicesStep />;
    case 3: return <DateTimeStep />;
    case 4: return <ConfirmStep />;
    case 5: return <BookingConfirmed />;
    default: return <BookingEntry />;
  }
}

/**
 * Renders the full booking flow inline inside another page (e.g. ProviderProfile Book tab).
 * Accepts a pre-loaded `provider` object so no additional network fetch is needed.
 *
 * Props:
 *   provider            – already-loaded provider object from the profile
 *   onClose             – called when the user wants to exit (e.g. “Back to profile”)
 *   rebookService       – optional { service_id, service_name, duration_minutes, price_ex_vat }
 *                         pre-fills service AND location (salon), starts at DateTimeStep (step 3)
 *   preSelectedService  – optional { service_id, name, duration_minutes, price_ex_vat }
 *                         pre-fills service only, starts at LocationStep (step 1) so the
 *                         customer still picks where and when
 */
export default function BookingFlowEmbedded({ provider, onClose, rebookService = null, preSelectedService = null, initialReferralSource = null }) {
  const isRebook = Boolean(rebookService);
  const hasPreSelected = Boolean(preSelectedService);

  const initialStep = isRebook ? 3 : hasPreSelected ? 1 : 0;

  const initialServices = isRebook
    ? [{ service_id: rebookService.service_id,       name: rebookService.service_name,    duration_minutes: rebookService.duration_minutes, price_ex_vat: rebookService.price_ex_vat }]
    : hasPreSelected
    ? [{ service_id: preSelectedService.service_id,  name: preSelectedService.name,        duration_minutes: preSelectedService.duration_minutes, price_ex_vat: preSelectedService.price_ex_vat }]
    : [];

  return (
    <BookingProvider
      initialProvider={provider}
      initialStep={initialStep}
      initialServices={initialServices}
      initialBookingPath={isRebook ? 'rebook' : hasPreSelected ? 'preselected' : null}
      initialLocationType={isRebook ? 'salon' : null}
      initialReferralSource={initialReferralSource}
      onExit={onClose}
      embedded
    >
      <div className="min-h-[60vh]">
        <StepProgress />
        <div className="px-4 pb-8">
          <EmbeddedSteps />
        </div>
      </div>
    </BookingProvider>
  );
}

