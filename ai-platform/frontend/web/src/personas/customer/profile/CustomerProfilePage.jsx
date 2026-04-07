import { useEffect, useMemo, useRef, useState } from 'react';
import CustomerTabBar from '../navigation/CustomerTabBar';
import {
  getCustomerDashboard,
  uploadCustomerAvatar,
  updateCustomerFavorites,
} from '../../../api/bookingApi';
import { SERVICE_OPTIONS } from '../../../constants/customerPreferences';
import { buildCustomerFavoriteReferralQuery } from '../../../utils/referralTracking';

const FAVORITE_CATEGORY_LABELS = {
  ...Object.fromEntries(SERVICE_OPTIONS.map(({ key, label }) => [key, label])),
  fitness: 'Fitness',
  tattoo: 'Tattoo',
  other: 'Other',
};

const FAVORITE_CATEGORY_ORDER = [
  'hair',
  'barber',
  'nails',
  'spa',
  'massage',
  'lashes',
  'brows',
  'makeup',
  'skincare',
  'waxing',
  'fitness',
  'tattoo',
  'other',
];

function StatItem({ value, label }) {
  return (
    <div className="min-w-[72px] text-center">
      <p className="text-fixme-text-primary font-semibold text-sm leading-none">{value}</p>
      <p className="text-fixme-text-muted text-[11px] mt-0.5">{label}</p>
    </div>
  );
}

const TIER_STYLES = {
  member: { bg: 'rgba(255,255,255,0.06)',  color: 'rgba(255,255,255,0.4)',  glow: 'rgba(255,255,255,0.08)' },
  silver: { bg: 'rgba(255,255,255,0.13)',  color: '#ffffff',                glow: 'rgba(255,255,255,0.22)' },
  gold:   { bg: 'rgba(234,179,8,0.20)',    color: '#fde047',                glow: 'rgba(250,204,21,0.36)'  },
  vip:    { bg: 'rgba(168,85,247,0.24)',   color: '#d8b4fe',                glow: 'rgba(192,132,252,0.40)' },
};

function LevelBadge({ tier, badge }) {
  const s = TIER_STYLES[(tier || 'member').toLowerCase()] || TIER_STYLES.member;
  return (
    <div style={{
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: '86px',
      height: '34px',
      clipPath: 'polygon(18% 0%, 82% 0%, 100% 50%, 82% 100%, 18% 100%, 0% 50%)',
      background: s.bg,
      color: s.color,
      filter: `drop-shadow(0 0 5px ${s.glow})`,
      fontSize: '10px',
      fontWeight: '600',
      letterSpacing: '0.09em',
      textTransform: 'uppercase',
    }}>
      {badge}
    </div>
  );
}

function ProviderAvatar({ name, imageUrl }) {
  if (imageUrl) {
    return <img src={imageUrl} alt={name} className="w-14 h-14 rounded-full object-cover" />;
  }
  return (
    <div className="w-14 h-14 rounded-full bg-fixme-border flex items-center justify-center text-fixme-text-secondary font-semibold text-base">
      {(name || '?')[0].toUpperCase()}
    </div>
  );
}

function providerProfileHref(provider) {
  const query = buildCustomerFavoriteReferralQuery();
  const suffix = query ? `?${query}` : '';
  if (provider?.slug) return `/p/${provider.slug}${suffix}`;
  if (provider?.provider_id) return `/pid/${provider.provider_id}${suffix}`;
  return '#';
}

function providerUsername(provider) {
  if (provider?.instagram_username) return provider.instagram_username;
  if (provider?.slug) return provider.slug;
  return (provider?.name || 'provider').toLowerCase().replace(/\s+/g, '');
}

function normalizeProviderCategories(provider) {
  const raw = Array.isArray(provider?.service_categories) ? provider.service_categories : [];
  const normalized = raw
    .map((value) => String(value || '').trim().toLowerCase())
    .filter((value) => FAVORITE_CATEGORY_LABELS[value]);
  return Array.from(new Set(normalized));
}

function favoriteCategoryLabel(key) {
  return FAVORITE_CATEGORY_LABELS[key] || key;
}

function FavoriteProviderCard({ provider, onRemoveFavorite, favoriteBusy }) {
  const href = providerProfileHref(provider);
  const username = providerUsername(provider);
  const hasRating = typeof provider.rating === 'number' && provider.rating > 0;
  const categories = normalizeProviderCategories(provider);

  return (
    <article className="min-w-[210px] max-w-[210px] rounded-2xl border border-fixme-border bg-fixme-card p-3.5 flex flex-col gap-3 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <a href={href} className="flex items-center gap-3 min-w-0">
          <ProviderAvatar name={provider.name} imageUrl={provider.image_url} />
          <div className="min-w-0">
            <p className="text-fixme-text-primary text-sm font-semibold truncate max-w-[110px]">{provider.name}</p>
            <p className="text-fixme-accent text-xs truncate max-w-[110px]">@{username}</p>
          </div>
        </a>

        <button
          type="button"
          onClick={() => onRemoveFavorite(provider.provider_id)}
          disabled={favoriteBusy}
          className="text-[11px] font-semibold px-2 py-1 rounded-full border border-fixme-border text-fixme-text-muted hover:border-fixme-error hover:text-fixme-error transition-colors"
        >
          Remove
        </button>
      </div>

      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-1.5 text-fixme-text-primary">
          <svg className="w-3.5 h-3.5 text-fixme-accent" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" />
          </svg>
          <span className="font-semibold">{hasRating ? provider.rating.toFixed(1) : 'No rating yet'}</span>
        </div>
        {provider.city ? <span className="text-fixme-text-muted truncate max-w-[90px]">{provider.city}</span> : <span />}
      </div>

      {categories.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {categories.slice(0, 2).map((category) => (
            <span
              key={`${provider.provider_id}-${category}`}
              className="text-[10px] px-2 py-0.5 rounded-full border border-fixme-border bg-fixme-bg text-fixme-text-secondary"
            >
              {favoriteCategoryLabel(category)}
            </span>
          ))}
        </div>
      )}

      <a
        href={href}
        className="w-full text-center rounded-xl bg-fixme-bg border border-fixme-border text-fixme-text-primary text-xs font-semibold py-2.5 hover:border-fixme-accent hover:text-fixme-accent transition-colors"
      >
        View profile
      </a>
    </article>
  );
}

// dev-only: mock favorites so we can preview the UI without real data
const DEV_MOCK_FAVORITES = [
  { provider_id: 'mock-1', name: 'Studio Noir', slug: 'studio-noir', city: 'Stockholm', instagram_username: 'studionoir', rating: 4.9, service_categories: ['hair'], image_url: null },
  { provider_id: 'mock-2', name: 'Hammam & Spa', slug: 'hammam-spa', city: 'Södermalm', instagram_username: 'hammamspa', rating: 4.7, service_categories: ['spa', 'massage'], image_url: null },
  { provider_id: 'mock-3', name: 'Lash Lab', slug: 'lash-lab', city: 'Vasastan', instagram_username: 'lashlabsthlm', rating: 4.8, service_categories: ['lashes', 'brows'], image_url: null },
];

export default function CustomerProfilePage() {
  const token = localStorage.getItem('fixme_token');
  const avatarInputRef = useRef(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [avatarUrl, setAvatarUrl] = useState(null);
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [displayName, setDisplayName] = useState(null);

  const [dashboard, setDashboard] = useState(null);
  const [followedProviders, setFollowedProviders] = useState([]);
  const [favoriteProviderIds, setFavoriteProviderIds] = useState([]);
  const [favoriteBusy, setFavoriteBusy] = useState(false);
  const [favoriteCategoryFilter, setFavoriteCategoryFilter] = useState('all');

  function deriveFavoriteProviders(followed, favoriteIds) {
    const byId = new Map((followed || []).map((p) => [p.provider_id, p]));
    return (favoriteIds || []).map((id) => byId.get(id)).filter(Boolean);
  }

  async function loadProfile() {
    if (!token) {
      setError('not_logged_in');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const dash = await getCustomerDashboard(token);
      const followed = dash.followed_providers || [];
      const favoriteIds = Array.isArray(dash.favorite_provider_ids) ? dash.favorite_provider_ids : [];

      setDashboard(dash);
      setAvatarUrl(dash.image_url || null);
      setDisplayName(dash.display_name || null);
      setFollowedProviders(followed);
      setFavoriteProviderIds(favoriteIds);
    } catch (e) {
      setError(e.message || 'Could not load profile');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProfile();
  }, []);

  const frequentServices = useMemo(() => {
    if (!dashboard) return [];

    if (Array.isArray(dashboard.frequent_services) && dashboard.frequent_services.length > 0) {
      return dashboard.frequent_services;
    }

    const allBookings = [...(dashboard.upcoming_bookings || []), ...(dashboard.past_bookings || [])];

    const map = new Map();
    for (const booking of allBookings) {
      const key = booking.service_name || 'Appointment';
      const existing = map.get(key) || {
        service_name: key,
        count: 0,
        last_scheduled_start: booking.scheduled_start,
      };
      existing.count += 1;
      if (new Date(booking.scheduled_start) > new Date(existing.last_scheduled_start)) {
        existing.last_scheduled_start = booking.scheduled_start;
      }
      map.set(key, existing);
    }

    return Array.from(map.values())
      .sort((a, b) => {
        if (b.count !== a.count) return b.count - a.count;
        return new Date(b.last_scheduled_start) - new Date(a.last_scheduled_start);
      })
      .slice(0, 6);
  }, [dashboard]);

  const levelBadge      = dashboard?.level_badge  || 'Member';
  const loyaltyTier     = dashboard?.loyalty_tier || 'member';
  const followingCount  = Number(dashboard?.following_count ?? followedProviders.length);
  const followersCount  = Number(dashboard?.followers_count ?? 0);
  // Backend returns 0–100; display as 0–5 (÷20). New customers (score=0, confidence=0)
  // start at a perfect 5.0 — they haven't done anything wrong yet.
  const rawScore         = dashboard?.reliability_score   ?? 0;
  const rawConfidence    = dashboard?.reliability_confidence ?? 0;
  const reliabilityScore = (rawScore === 0 && rawConfidence === 0) ? 5.0 : +(rawScore / 20).toFixed(1);
  const reliabilityTier  = dashboard?.reliability_tier ?? 'new';

  const favoriteProviders = useMemo(() => {
    if (Array.isArray(dashboard?.favorite_providers) && dashboard.favorite_providers.length > 0) {
      return dashboard.favorite_providers;
    }
    const derived = deriveFavoriteProviders(followedProviders, favoriteProviderIds);
    // dev fallback: show mock cards so UI is previewable without real data
    if (derived.length === 0) return DEV_MOCK_FAVORITES;
    return derived;
  }, [dashboard, followedProviders, favoriteProviderIds]);

  const favoriteCategoryOptions = useMemo(() => {
    const categories = new Set();
    favoriteProviders.forEach((provider) => {
      normalizeProviderCategories(provider).forEach((category) => categories.add(category));
    });

    const ordered = FAVORITE_CATEGORY_ORDER.filter((category) => categories.has(category));
    const leftovers = Array.from(categories).filter((category) => !FAVORITE_CATEGORY_ORDER.includes(category));

    return ['all', ...ordered, ...leftovers];
  }, [favoriteProviders]);

  useEffect(() => {
    if (!favoriteCategoryOptions.includes(favoriteCategoryFilter)) {
      setFavoriteCategoryFilter('all');
    }
  }, [favoriteCategoryFilter, favoriteCategoryOptions]);

  const filteredFavoriteProviders = useMemo(() => {
    if (favoriteCategoryFilter === 'all') return favoriteProviders;
    return favoriteProviders.filter((provider) => normalizeProviderCategories(provider).includes(favoriteCategoryFilter));
  }, [favoriteProviders, favoriteCategoryFilter]);

  async function handleAvatarChange(e) {
    const file = e.target.files?.[0];
    if (!file || !token) return;
    setAvatarUploading(true);
    try {
      const result = await uploadCustomerAvatar(token, file);
      setAvatarUrl(result.image_url);
    } catch (e2) {
      setError(e2.message || 'Could not upload photo');
    } finally {
      setAvatarUploading(false);
      if (avatarInputRef.current) avatarInputRef.current.value = '';
    }
  }

  async function handleRemoveFavorite(providerId) {
    if (!token || favoriteBusy) return;
    const nextIds = favoriteProviderIds.filter((id) => id !== providerId);

    setFavoriteBusy(true);
    try {
      const updated = await updateCustomerFavorites(token, nextIds);
      const savedIds = updated.provider_ids || [];
      setFavoriteProviderIds(savedIds);
      setDashboard((prev) => {
        if (!prev) return prev;
        const nextProviders = (prev.favorite_providers || []).filter((p) => savedIds.includes(p.provider_id));
        return { ...prev, favorite_provider_ids: savedIds, favorite_providers: nextProviders };
      });
    } catch {
      // no-op
    } finally {
      setFavoriteBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-fixme-bg pb-20 px-4 pt-8 max-w-md mx-auto animate-pulse space-y-4">
        <div className="flex flex-col items-center gap-3 pb-2">
          <div className="w-24 h-24 rounded-full bg-fixme-card" />
          <div className="h-4 bg-fixme-card rounded w-32" />
        </div>
        <div className="h-16 bg-fixme-card rounded-2xl" />
        <div className="h-24 bg-fixme-card rounded-2xl" />
        <div className="h-28 bg-fixme-card rounded-2xl" />
        <CustomerTabBar active="profile" />
      </div>
    );
  }

  if (error === 'not_logged_in') {
    return (
      <div className="min-h-screen bg-fixme-bg pb-20 px-4 pt-10 max-w-md mx-auto text-center space-y-4">
        <h1 className="text-fixme-text-primary text-xl font-semibold">Customer Profile</h1>
        <p className="text-fixme-text-secondary text-sm">Log in to view your profile and preferences.</p>
        <button
          onClick={() => {
            window.location.href = '/customer/login';
          }}
          className="px-6 py-3 bg-fixme-text-primary text-fixme-bg text-sm font-semibold rounded-xl"
        >
          Log in
        </button>
        <CustomerTabBar active="profile" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-fixme-bg pb-24 px-4 pt-8 max-w-md mx-auto space-y-5">
      <div className="flex justify-end -mb-3">
        <button
          type="button"
          onClick={() => {
            window.location.href = '/customer/settings';
          }}
          className="w-9 h-9 flex items-center justify-center rounded-full bg-fixme-card border border-fixme-border text-fixme-text-muted hover:text-fixme-text-primary hover:border-fixme-accent/40 transition-all"
          aria-label="Settings"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.8}>
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
            />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>
      </div>

      <div className="flex items-center gap-5 mt-1 mb-1">
        <LevelBadge tier={loyaltyTier} badge={levelBadge} />
        <StatItem value={followingCount} label="Following" />
        <StatItem value={followersCount} label="Followers" />
      </div>

      <div className="pt-2 pb-1 space-y-3">
        <input
          ref={avatarInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={handleAvatarChange}
        />

        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => avatarInputRef.current?.click()}
            className="relative w-24 h-24 rounded-full overflow-hidden border-2 border-fixme-border bg-fixme-card flex-shrink-0 focus:outline-none group"
            title="Change profile photo"
          >
            {avatarUrl ? (
              <img src={avatarUrl} alt="Profile" className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-fixme-accent text-3xl font-bold">
                {displayName?.charAt(0)?.toUpperCase() || '?'}
              </div>
            )}

            <div className="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
              {avatarUploading ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
                  />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              )}
            </div>
          </button>

          <div className="min-w-0">
            <p className="text-fixme-text-primary text-lg font-semibold leading-tight truncate">
              {displayName || 'Your Profile'}
            </p>
            {/* Uber-style rating */}
            <div className="flex items-center gap-1.5 mt-1">
              <svg className="w-3.5 h-3.5 text-yellow-400 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
              <span className="text-fixme-text-primary text-sm font-semibold">
                {reliabilityScore}
              </span>
            </div>
          </div>
        </div>
      </div>


      {error && (
        <div className="bg-fixme-error/10 border border-fixme-error/30 rounded-xl px-3 py-2 text-xs text-fixme-error">
          {error}
        </div>
      )}

      <section className="bg-fixme-card border border-fixme-border rounded-2xl p-4">
        <h2 className="text-fixme-text-primary text-base font-semibold mb-3">Usually booked</h2>

        {frequentServices.length === 0 ? (
          <p className="text-fixme-text-secondary text-sm">No bookings yet.</p>
        ) : (
          <div className="space-y-2">
            {frequentServices.map((row) => (
              <div
                key={row.service_name}
                className="flex items-center justify-between py-2 border-b border-fixme-border/50 last:border-b-0"
              >
                <div>
                  <p className="text-fixme-text-primary text-sm font-medium">{row.service_name}</p>
                  <p className="text-fixme-text-muted text-xs">
                    Last booked: {new Date(row.last_scheduled_start).toLocaleDateString('en-GB')}
                  </p>
                </div>
                <span className="text-xs text-fixme-text-secondary bg-fixme-bg px-2 py-1 rounded-full">{row.count}x</span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="bg-fixme-card border border-fixme-border rounded-2xl p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-fixme-text-primary text-base font-semibold">Favorite providers</h2>
          <button
            type="button"
            onClick={() => {
              window.location.href = '/customer/settings';
            }}
            className="text-fixme-text-muted text-xs hover:text-fixme-accent transition-colors"
          >
            Manage
          </button>
        </div>

        {favoriteProviders.length === 0 ? (
          <div className="py-4 text-center space-y-1">
            <p className="text-fixme-text-secondary text-sm">No favorites yet</p>
            <p className="text-fixme-text-muted text-xs leading-relaxed">Choose favorites in Settings.</p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
              {favoriteCategoryOptions.map((category) => {
                const active = favoriteCategoryFilter === category;
                const label = category === 'all' ? 'All' : favoriteCategoryLabel(category);
                return (
                  <button
                    key={category}
                    type="button"
                    onClick={() => setFavoriteCategoryFilter(category)}
                    className={`px-3 py-1.5 rounded-full text-xs border whitespace-nowrap transition-colors ${
                      active
                        ? 'border-fixme-accent bg-fixme-accent/10 text-fixme-text-primary'
                        : 'border-fixme-border bg-fixme-bg text-fixme-text-secondary'
                    }`}
                  >
                    {label}
                  </button>
                );
              })}
            </div>

            <div className="flex gap-3 overflow-x-auto pb-1 -mx-1 px-1">
              {filteredFavoriteProviders.length > 0 ? (
                filteredFavoriteProviders.map((provider) => (
                  <FavoriteProviderCard
                    key={provider.provider_id}
                    provider={provider}
                    onRemoveFavorite={handleRemoveFavorite}
                    favoriteBusy={favoriteBusy}
                  />
                ))
              ) : (
                <div className="w-full rounded-xl border border-fixme-border bg-fixme-bg px-3 py-4 text-center">
                  <p className="text-fixme-text-secondary text-sm">No favorite providers in this category yet.</p>
                  <p className="text-fixme-text-muted text-xs mt-1">Only broad categories are shown for privacy.</p>
                </div>
              )}
            </div>
          </div>
        )}
      </section>

      <CustomerTabBar active="profile" />
    </div>
  );
}


