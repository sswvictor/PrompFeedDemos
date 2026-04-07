import { useBooking } from '../hooks/useBooking';

export default function BackButton() {
  const { currentStep, goBack } = useBooking();

  // Hide on entry screen (step 0)
  if (currentStep <= 0) return null;

  return (
    <button
      onClick={goBack}
      className="flex items-center gap-1.5 text-fixme-text-secondary hover:text-fixme-text-primary transition-colors py-2"
    >
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
      </svg>
      <span className="text-sm">Back</span>
    </button>
  );
}
