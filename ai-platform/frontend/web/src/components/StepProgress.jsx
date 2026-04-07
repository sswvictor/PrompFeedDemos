import { useBooking, getStepSequence } from '../hooks/useBooking';

export default function StepProgress() {
  const { currentStep, bookingPath, provider } = useBooking();

  const seq = getStepSequence(bookingPath, provider);

  // Working steps = everything between entry (0) and confirmed (5)
  const workingSeq = seq.filter(s => s > 0 && s < 5);

  const position = workingSeq.indexOf(currentStep);

  // Hide on entry screen (step 0) and confirmed screen (step 5)
  if (position === -1) return null;

  return (
    <div className="flex gap-1.5 px-2 py-3">
      {workingSeq.map((_, i) => (
        <div
          key={i}
          className={`
            h-1 flex-1 rounded-full transition-all duration-300
            ${i <= position ? 'bg-fixme-accent' : 'bg-fixme-border'}
          `}
        />
      ))}
    </div>
  );
}
