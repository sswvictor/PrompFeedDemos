/**
 * LoadingScreen — fun animated loading state with a tiny worker dude.
 *
 * Usage:
 *   <LoadingScreen message="Getting your bookings..." />
 *   <LoadingScreen message="Loading your profile..." />
 *
 * The dude swings a hammer and builds blocks while data loads.
 */

export default function LoadingScreen({ message = 'Loading\u2026' }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[55vh] gap-5 select-none">
      <DudeSVG />
      <p className="text-fixme-text-muted text-sm tracking-wide animate-pulse">{message}</p>
    </div>
  );
}

function DudeSVG() {
  return (
    <svg
      viewBox="0 0 80 70"
      width="80"
      height="70"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <style>{`
        @keyframes hammer-swing {
          0%   { transform: rotate(-30deg); transform-origin: 55px 28px; }
          40%  { transform: rotate(20deg);  transform-origin: 55px 28px; }
          55%  { transform: rotate(15deg);  transform-origin: 55px 28px; }
          100% { transform: rotate(-30deg); transform-origin: 55px 28px; }
        }
        @keyframes arm-swing {
          0%   { transform: rotate(-10deg); transform-origin: 40px 32px; }
          40%  { transform: rotate(30deg);  transform-origin: 40px 32px; }
          100% { transform: rotate(-10deg); transform-origin: 40px 32px; }
        }
        @keyframes block-pop {
          0%  { opacity: 0; transform: scaleY(0); transform-origin: bottom; }
          15% { opacity: 1; transform: scaleY(1); transform-origin: bottom; }
          80% { opacity: 1; }
          95% { opacity: 0; }
          100%{ opacity: 0; }
        }
        @keyframes block-pop2 {
          0%  { opacity: 0; } 10% { opacity: 0; }
          25% { opacity: 1; transform: scaleY(1); }
          80% { opacity: 1; }
          95% { opacity: 0; }
          100%{ opacity: 0; }
        }
        @keyframes block-pop3 {
          0%  { opacity: 0; } 35% { opacity: 0; }
          50% { opacity: 1; transform: scaleY(1); }
          80% { opacity: 1; }
          95% { opacity: 0; }
          100%{ opacity: 0; }
        }
        @keyframes body-bob {
          0%,100% { transform: translateY(0); }
          50%     { transform: translateY(-1px); }
        }
        .dude-body  { animation: body-bob 0.7s ease-in-out infinite; }
        .arm-group  { animation: arm-swing 0.7s ease-in-out infinite; }
        .hammer     { animation: hammer-swing 0.7s ease-in-out infinite; }
        .blk1 { animation: block-pop  1.4s ease-out infinite; }
        .blk2 { animation: block-pop2 1.4s ease-out infinite; }
        .blk3 { animation: block-pop3 1.4s ease-out infinite; }
      `}</style>

      {/* Ground */}
      <rect x="8" y="62" width="64" height="3" rx="1.5" fill="#2A2A2A" />

      {/* Stacked blocks being built */}
      <g>
        <rect className="blk1" x="10" y="52" width="14" height="10" rx="2" fill="#2A2A2A" stroke="#3A3A3A" strokeWidth="1" />
        <rect className="blk2" x="10" y="43" width="14" height="10" rx="2" fill="#2A2A2A" stroke="#3A3A3A" strokeWidth="1" />
        <rect className="blk3" x="10" y="34" width="14" height="10" rx="2" fill="#2A2A2A" stroke="#F5F5F0" strokeWidth="1" opacity="0.6" />
      </g>

      {/* Dude */}
      <g className="dude-body">
        {/* Head */}
        <circle cx="42" cy="22" r="7" fill="#F5F5F0" />
        {/* Hard hat brim */}
        <rect x="35" y="16" width="14" height="3" rx="1.5" fill="#F5F5F0" />
        <rect x="37" y="13" width="10" height="5" rx="2.5" fill="#F5F5F0" />

        {/* Body */}
        <rect x="37" y="30" width="10" height="14" rx="3" fill="#3A3A3A" />
        {/* Legs */}
        <rect x="37" y="43" width="4" height="10" rx="2" fill="#2A2A2A" />
        <rect x="43" y="43" width="4" height="10" rx="2" fill="#2A2A2A" />
        {/* Feet */}
        <rect x="35" y="51" width="7" height="3" rx="1.5" fill="#1A1A1A" />
        <rect x="42" y="51" width="7" height="3" rx="1.5" fill="#1A1A1A" />

        {/* Arm holding hammer */}
        <g className="arm-group">
          <rect x="47" y="32" width="4" height="11" rx="2" fill="#3A3A3A" transform="rotate(15 49 32)" />
        </g>

        {/* Hammer */}
        <g className="hammer">
          {/* handle */}
          <rect x="53" y="28" width="2.5" height="14" rx="1.2" fill="#6B4A1E" />
          {/* head */}
          <rect x="50" y="26" width="8.5" height="5" rx="1.5" fill="#888" />
        </g>

        {/* Left arm (resting) */}
        <rect x="33" y="32" width="4" height="10" rx="2" fill="#3A3A3A" transform="rotate(-10 35 32)" />
      </g>
    </svg>
  );
}
