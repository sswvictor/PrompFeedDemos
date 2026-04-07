import { useEffect, useMemo, useState } from 'react';
import { ROUTES } from '../../app/routeCatalog';
import { getAdminReportStats } from '../../api/bookingApi';

const SESSION_TOKEN_KEY = 'fixme_admin_token';
const SESSION_ACTOR_KEY = 'fixme_admin_actor';
const ENV_TOKEN = import.meta.env.VITE_ADMIN_TOKEN || '';
const ENV_ACTOR = import.meta.env.VITE_ADMIN_ACTOR || 'johanna@fixmeapp.ai';

const MENU_ITEMS = [
  { key: 'operations', label: 'Operations', href: ROUTES.admin.operations },
  { key: 'bookings', label: 'Bookings', href: ROUTES.admin.bookings },
  { key: 'reports', label: 'Reports', href: ROUTES.admin.reports },
  { key: 'accounts', label: 'Accounts', href: ROUTES.admin.accounts },
  { key: 'levels', label: 'Levels', href: ROUTES.admin.levels },
  { key: 'audit', label: 'History', href: ROUTES.admin.audit },
  { key: 'verifications', label: 'Verifications', href: ROUTES.admin.verifications },
  { key: 'gdpr', label: 'GDPR', href: ROUTES.admin.gdprRequests },
];

function LoginCard({ onLogin }) {
  const [tokenInput, setTokenInput] = useState(ENV_TOKEN);
  const [actorInput, setActorInput] = useState(ENV_ACTOR);

  return (
    <div className="min-h-screen bg-[#0D0D0D] text-white px-4 flex items-center justify-center">
      <div className="w-full max-w-sm bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-5 space-y-4">
        <div>
          <p className="text-base font-semibold">Fixmeapp Admin</p>
          <p className="text-xs text-gray-400 mt-1">Use ADMIN_SECRET_TOKEN and admin email to continue.</p>
        </div>
        <input
          type="email"
          value={actorInput}
          onChange={(e) => setActorInput(e.target.value)}
          placeholder="Admin email"
          className="w-full bg-[#0D0D0D] border border-[#2A2A2A] rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-[#F5F5F0]/40"
        />
        <input
          type="password"
          value={tokenInput}
          onChange={(e) => setTokenInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && tokenInput.trim() && actorInput.trim()) {
              onLogin(tokenInput.trim(), actorInput.trim());
            }
          }}
          placeholder="Admin token"
          className="w-full bg-[#0D0D0D] border border-[#2A2A2A] rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-[#F5F5F0]/40"
        />
        <button
          type="button"
          onClick={() => onLogin(tokenInput.trim(), actorInput.trim())}
          disabled={!tokenInput.trim() || !actorInput.trim()}
          className="w-full bg-[#F5F5F0] text-[#0D0D0D] rounded-xl py-2.5 text-sm font-semibold disabled:opacity-40"
        >
          Enter admin
        </button>
      </div>
    </div>
  );
}

export default function AdminShell({ title, activeKey, children }) {
  const [token, setToken] = useState(() => sessionStorage.getItem(SESSION_TOKEN_KEY) || '');
  const [reportOpenCount, setReportOpenCount] = useState(0);

  const activeHref = useMemo(
    () => MENU_ITEMS.find((item) => item.key === activeKey)?.href || ROUTES.admin.operations,
    [activeKey],
  );

  useEffect(() => {
    if (!token) {
      setReportOpenCount(0);
      return;
    }

    let cancelled = false;
    async function loadStats() {
      try {
        const stats = await getAdminReportStats(token);
        if (!cancelled) setReportOpenCount(Number(stats?.open_total || 0));
      } catch {
        if (!cancelled) setReportOpenCount(0);
      }
    }

    loadStats();
    const timer = setInterval(loadStats, 30000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [token]);

  if (!token) {
    return (
      <LoginCard
        onLogin={(nextToken, actorEmail) => {
          if (!nextToken || !actorEmail) return;
          sessionStorage.setItem(SESSION_TOKEN_KEY, nextToken);
          sessionStorage.setItem(SESSION_ACTOR_KEY, actorEmail.trim().toLowerCase());
          setToken(nextToken);
        }}
      />
    );
  }

  return (
    <div className="min-h-screen bg-[#0D0D0D] text-white">
      <header className="sticky top-0 z-20 bg-[#0D0D0D]/95 backdrop-blur border-b border-[#2A2A2A] px-4 py-3">
        <div className="max-w-6xl mx-auto flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold">Fixmeapp Admin</p>
            <p className="text-[11px] text-gray-400">{title}</p>
          </div>
          <button
            type="button"
            onClick={() => {
              sessionStorage.removeItem(SESSION_TOKEN_KEY);
              sessionStorage.removeItem(SESSION_ACTOR_KEY);
              setToken('');
            }}
            className="text-xs text-gray-400 hover:text-red-400 transition-colors"
          >
            Sign out
          </button>
        </div>
      </header>

      <nav className="sticky top-[61px] z-10 bg-[#111111] border-b border-[#222222]">
        <div className="max-w-6xl mx-auto px-4 py-2 flex gap-2 overflow-x-auto">
          {MENU_ITEMS.map((item) => {
            const active = activeHref === item.href;
            const isReports = item.key === 'reports';
            return (
              <a
                key={item.key}
                href={item.href}
                className={[
                  'px-3 py-1.5 rounded-full text-xs whitespace-nowrap border transition-colors inline-flex items-center gap-1.5',
                  active
                    ? 'border-[#F5F5F0]/50 text-white bg-[#F5F5F0]/10'
                    : 'border-[#2A2A2A] text-gray-400 hover:text-white hover:border-[#4A4A4A]',
                ].join(' ')}
              >
                <span>{item.label}</span>
                {isReports && reportOpenCount > 0 && (
                  <span className="inline-flex items-center justify-center min-w-4 h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-semibold">
                    {reportOpenCount > 99 ? '99+' : reportOpenCount}
                  </span>
                )}
              </a>
            );
          })}
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-4 py-4">{children}</main>
    </div>
  );
}

export function getAdminToken() {
  return sessionStorage.getItem(SESSION_TOKEN_KEY) || '';
}

export function getAdminActor() {
  return (
    (sessionStorage.getItem(SESSION_ACTOR_KEY) || ENV_ACTOR || '').trim().toLowerCase()
  );
}
