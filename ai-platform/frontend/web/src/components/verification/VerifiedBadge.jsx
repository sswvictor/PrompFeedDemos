/**
 * VerifiedBadge — shared verified business badge.
 *
 * Usage:
 *   <VerifiedBadge />              — icon only (default, for compact spaces)
 *   <VerifiedBadge showLabel />    — icon + "Verified" text
 *   <VerifiedBadge size="lg" />    — larger icon
 *
 * AGENTS.md §9: badge display must use this component, never re-implemented per persona.
 */

export default function VerifiedBadge({ showLabel = false, size = 'sm', className = '' }) {
  const iconSize = size === 'lg' ? 'w-5 h-5' : 'w-3.5 h-3.5';

  return (
    <span
      className={`inline-flex items-center gap-1 ${className}`}
      title="Verified business"
      aria-label="Verified business"
    >
      {/* Blue circle with white checkmark — universally recognised */}
      <svg
        className={`${iconSize} flex-shrink-0`}
        viewBox="0 0 20 20"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <circle cx="10" cy="10" r="10" fill="#1D6EF5" />
        <path
          d="M5.5 10.5L8.5 13.5L14.5 7"
          stroke="white"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      {showLabel && (
        <span className="text-xs font-medium text-blue-600">Verified</span>
      )}
    </span>
  );
}
