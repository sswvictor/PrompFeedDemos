const TAB_ITEMS = [
  { id: 'home', icon: '\u{1F3E0}', label: 'Home', href: '/provider/home' },
  { id: 'finance', icon: '\u{1F4B0}', label: 'Finance', href: '/provider/finance' },
  { id: 'profile', icon: '\u{1F464}', label: 'Profile', href: '/provider/profile' },
];

export default function ProviderTabBar({ active = 'home', profileAttention = false }) {
  return (
    <div className="fixed bottom-0 left-0 right-0 border-t border-fixme-border bg-fixme-bg/95 backdrop-blur-sm">
      <div className="max-w-md mx-auto flex">
        {TAB_ITEMS.map(({ id, icon, label, href }) => {
          const isActive = active === id || (id === 'profile' && active === 'settings');
          const showDot = id === 'profile' && profileAttention && !isActive;
          return (
            <button
              key={id}
              onClick={() => {
                window.location.href = href;
              }}
              className={`flex-1 flex flex-col items-center gap-0.5 py-2.5 transition-colors ${
                isActive ? 'text-fixme-accent' : 'text-fixme-text-muted hover:text-fixme-text-secondary'
              }`}
            >
              <span className="relative text-lg leading-none" aria-hidden="true">
                {icon}
                {showDot && (
                  <span className="absolute -top-0.5 -right-1 w-2 h-2 bg-amber-400 rounded-full border border-fixme-bg" />
                )}
              </span>
              <span className={`text-[10px] font-semibold ${isActive ? 'text-fixme-accent' : ''}`}>
                {label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
