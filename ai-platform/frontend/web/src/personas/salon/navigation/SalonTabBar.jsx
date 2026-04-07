export default function SalonTabBar({ active = 'home' }) {
  const Item = ({ id, label, href }) => (
    <button
      onClick={() => { window.location.href = href; }}
      className={`flex-1 py-3 text-xs font-semibold ${active === id ? 'text-fixme-accent' : 'text-fixme-text-muted'}`}
    >
      {label}
    </button>
  );

  return (
    <div className="fixed bottom-0 left-0 right-0 border-t border-fixme-border bg-fixme-bg/95 backdrop-blur-sm">
      <div className="max-w-md mx-auto flex">
        <Item id="home" label="Home" href="/salon/home" />
        <Item id="profile" label="Profile" href="/salon/profile" />
        <Item id="settings" label="Settings" href="/salon/settings" />
      </div>
    </div>
  );
}
