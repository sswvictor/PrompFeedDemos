/**
 * ProviderProfilePage – unified owner + public profile
 *
 * Routes:
 *   /provider/profile  → isOwner=true, provider dashboard shell with edit controls
 *   /p/:slug           → public; isOwner=true when slug + token match localStorage
 */

import { useEffect, useState, useCallback } from 'react';
import {
  getProvider,
  getProviderProfile,
  getProviderProfileById,
  followProvider,
  unfollowProvider,
  getFollowStatus,
} from '../../../api/bookingApi';
import BookingFlowEmbedded from '../../../features/booking/embed/BookingFlowEmbedded';
import VerifiedBadge from '../../../components/verification/VerifiedBadge';
import ProviderTabBar from '../navigation/ProviderTabBar';
import LoadingScreen from '../../../components/LoadingScreen';
import { captureReferralFromSearch, getCapturedReferralSource, normalizeReferralSource } from '../../../utils/referralTracking';

// ── Auth helpers ─────────────────────────────────────────────────────────────
function getCustomerToken() {
  return (
    localStorage.getItem('fixme_token') ||
    localStorage.getItem('fixme_customer_token') ||
    null
  );
}

// ── Amenities (Unicode escapes – safe on all OS/editors) ─────────────────────
const AMENITY_MAP = {
  dog_friendly:          { icon: '\u{1F415}',        label: 'Dogs welcome'    },
  wheelchair_accessible: { icon: '\u267F',            label: 'Accessible'      },
  parking:               { icon: '\u{1F17F}\uFE0F',  label: 'Free parking'    },
  wifi:                  { icon: '\u{1F4F6}',         label: 'Free Wi-Fi'      },
  coffee:                { icon: '\u2615',            label: 'Coffee & tea'    },
  wine:                  { icon: '\u{1F377}',         label: 'Wine & drinks'   },
  eco_friendly:          { icon: '\u{1F33F}',         label: 'Eco-friendly'    },
  home_visits:           { icon: '\u{1F3E0}',         label: 'Home visits'     },
  private_studio:        { icon: '\u{1F512}',         label: 'Private studio'  },
  child_friendly:        { icon: '\u{1F476}',         label: 'Child-friendly'  },
  evening_hours:         { icon: '\u{1F319}',         label: 'Evening hours'   },
  card_payment:          { icon: '\u{1F4B3}',         label: 'Card payment'    },
};

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatCount(n) {
  if (n == null) return '\u2014'; // em dash
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatPolicyText(text) {
  if (!text) return 'Not specified';
  return text;
}

function formatWorkingHours(workingHours) {
  if (!workingHours || typeof workingHours !== 'object') return [];
  const order = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  return order.map((day) => {
    const info = workingHours[day];
    if (!info || !info.open) return { day, text: 'Closed' };
    const start = info.start || '--:--';
    const end = info.end || '--:--';
    return { day, text: `${start} - ${end}` };
  });
}

// ── StatItem ──────────────────────────────────────────────────────────────────
function StatItem({ value, label }) {
  return (
    <div className="flex-1 text-center">
      <p className="text-fixme-text-primary font-bold text-base leading-none">{value}</p>
      <p className="text-fixme-text-muted text-[11px] mt-0.5">{label}</p>
    </div>
  );
}

// ── Stats row ─────────────────────────────────────────────────────────────────
function Stats({ profile, followerDelta = 0 }) {
  const levelBadge = profile?.level_badge || 'Member';
  const followers = (profile?.fixmeapp_followers_count ?? 0) + followerDelta;
  const following = profile?.ig_following_count ?? null;

  return (
    <div className="flex divide-x divide-fixme-border mt-3 mb-4">
      <StatItem value={levelBadge} label="Level" />
      <StatItem value={formatCount(following)} label="Following" />
      <StatItem value={formatCount(followers)} label="Followers" />
    </div>
  );
}

// ── Tabs row ──────────────────────────────────────────────────────────────────
function TabRow({ tab, setTab }) {
  const tabs = [
    { id: 'about',    label: 'About'    },
    { id: 'services', label: 'Services' },
    { id: 'reviews',  label: 'Reviews'  },
  ];
  return (
    <div className="mt-5 border-t border-b border-fixme-border grid grid-cols-3">
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => setTab(t.id)}
          className={`py-3 text-sm font-semibold transition-colors ${
            tab === t.id
              ? 'text-fixme-accent border-b-2 border-fixme-accent'
              : 'text-fixme-text-muted hover:text-fixme-text-secondary'
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

// ── AboutTab ──────────────────────────────────────────────────────────────────
function AboutTab({ profile }) {
  const amenities = profile.amenities || [];
  const hours = formatWorkingHours(profile.working_hours);

  return (
    <div className="px-4 py-5 space-y-5">
      <div>
        <h3 className="text-fixme-text-muted text-xs uppercase tracking-widest mb-2">About</h3>
        <p className="text-fixme-text-secondary text-sm leading-relaxed">
          {profile.bio || 'No bio added yet.'}
        </p>
      </div>

      <div>
        <h3 className="text-fixme-text-muted text-xs uppercase tracking-widest mb-2">Working hours</h3>
        <div className="rounded-2xl border border-fixme-border bg-fixme-card divide-y divide-fixme-border">
          {hours.map((row) => (
            <div key={row.day} className="flex items-center justify-between px-3 py-2.5 text-xs">
              <span className="text-fixme-text-muted">{row.day}</span>
              <span className="text-fixme-text-secondary font-medium">{row.text}</span>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-fixme-text-muted text-xs uppercase tracking-widest mb-2">Policies</h3>
        <div className="rounded-2xl border border-fixme-border bg-fixme-card p-3 space-y-3">
          <div>
            <p className="text-fixme-text-muted text-[11px] uppercase tracking-wider mb-1">Booking policy</p>
            <p className="text-fixme-text-secondary text-xs leading-relaxed">{formatPolicyText(profile.booking_policy)}</p>
          </div>
          <div>
            <p className="text-fixme-text-muted text-[11px] uppercase tracking-wider mb-1">Cancellation policy</p>
            <p className="text-fixme-text-secondary text-xs leading-relaxed">{formatPolicyText(profile.cancellation_policy)}</p>
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-fixme-text-muted text-xs uppercase tracking-widest mb-2">
          Comfort &amp; Convenience
        </h3>
        <div className="flex flex-wrap gap-2">
          {amenities.length > 0 ? (
            amenities.map((key) => {
              const item = AMENITY_MAP[key];
              if (!item) return null;
              return (
                <span
                  key={key}
                  className="inline-flex items-center gap-1.5 rounded-full bg-fixme-card border border-fixme-border px-3 py-1 text-xs text-fixme-text-secondary"
                >
                  <span aria-hidden="true">{item.icon}</span>
                  {item.label}
                </span>
              );
            })
          ) : (
            <span className="text-fixme-text-muted text-xs">No amenities listed.</span>
          )}
        </div>
      </div>

      <div>
        <h3 className="text-fixme-text-muted text-xs uppercase tracking-widest mb-2">Location</h3>
        <p className="text-fixme-text-secondary text-sm">
          {profile.location_salon || profile.city || 'Address not added yet'}
        </p>
        <div className="mt-2 h-28 rounded-xl bg-fixme-card border border-fixme-border flex items-center justify-center">
          <span className="text-fixme-text-muted text-xs">Map coming soon</span>
        </div>
      </div>
    </div>
  );
}

// ── ServicesTab ───────────────────────────────────────────────────────────────
function ServicesTab({ profile, isOwner, bookingReferralSource = null, autoRebookServiceName = null }) {
  const [subTab, setSubTab] = useState('menu');
  const [selectedService, setSelectedService] = useState(null);  // preselected path (1→3→4→5)
  const [rebookService, setRebookService]     = useState(null);  // rebook path (straight to step 3)
  const services = profile.services || [];

  // Auto-start rebook flow when arriving from "Book again" link
  useEffect(() => {
    if (!autoRebookServiceName || services.length === 0) return;
    const nameNorm = autoRebookServiceName.trim().toLowerCase();
    const match = services.find((s) => s.name.trim().toLowerCase() === nameNorm);
    if (match) {
      setRebookService(match);
      setSubTab('book');
    }
  }, [autoRebookServiceName, services]);

  // Derive unique categories from service list
  const categories = ['all', ...new Set(services.map((s) => s.category).filter(Boolean))];
  const [activeCategory, setActiveCategory] = useState('all');
  const [search, setSearch] = useState('');

  const filtered = services.filter(
    (s) =>
      (activeCategory === 'all' || s.category === activeCategory) &&
      s.name.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="pt-1">
      {/* Sub-tab bar: Menu | Book */}
      <div className="flex border-b border-fixme-border mx-4 mb-1">
        {[
          { id: 'menu', label: 'Menu' },
          { id: 'book', label: 'Book' },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setSubTab(t.id)}
            className={`flex-1 py-2.5 text-sm font-semibold transition-colors ${
              subTab === t.id
                ? 'text-fixme-accent border-b-2 border-fixme-accent'
                : 'text-fixme-text-muted hover:text-fixme-text-secondary'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Menu sub-tab ── */}
      {subTab === 'menu' && (
        <div className="px-4 py-4 space-y-4">
          {/* Search input */}
          {services.length > 6 && (
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-fixme-text-muted text-sm pointer-events-none">
                {'\u{1F50D}'}
              </span>
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search services..."
                className="w-full bg-fixme-card border border-fixme-border rounded-xl pl-9 pr-4 py-2.5 text-sm text-fixme-text-primary placeholder:text-fixme-text-muted focus:outline-none focus:border-fixme-accent transition-colors"
              />
            </div>
          )}

          {/* Category filter pills */}
          {categories.length > 2 && (
            <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat)}
                  className={`rounded-full px-3 py-1.5 text-xs font-semibold flex-shrink-0 transition-colors ${
                    activeCategory === cat
                      ? 'bg-fixme-accent text-fixme-bg'
                      : 'bg-fixme-card border border-fixme-border text-fixme-text-muted hover:border-fixme-accent hover:text-fixme-accent'
                  }`}
                >
                  {cat === 'all' ? 'All' : cat.charAt(0).toUpperCase() + cat.slice(1).toLowerCase()}
                </button>
              ))}
            </div>
          )}

          {/* Service cards */}
          {filtered.length > 0 ? (
            <div className="space-y-3">
              {filtered.map((service) => (
                <div
                  key={service.service_id}
                  className="rounded-2xl border border-fixme-border bg-fixme-card px-4 py-3 flex items-center justify-between gap-3"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-fixme-text-primary text-sm font-semibold">{service.name}</p>
                    <p className="text-fixme-text-muted text-xs mt-0.5">
                      {service.duration_minutes} min &middot; {Math.round(service.price_ex_vat)} SEK
                    </p>
                    {service.home_service_available && (
                      <p className="text-[10px] text-fixme-text-muted mt-0.5">
                        {'\u{1F3E0}'} Home visits available
                      </p>
                    )}
                  </div>

                  {isOwner ? (
                    <button
                      onClick={() => { window.location.href = '/provider/settings'; }}
                      className="rounded-full border border-fixme-border text-fixme-text-muted text-xs px-3 py-1.5 hover:border-fixme-accent hover:text-fixme-accent transition-colors flex-shrink-0"
                    >
                      Edit
                    </button>
                  ) : (
                    <button
                      onClick={() => { setSelectedService(service); setSubTab('book'); }}
                      className="rounded-full bg-fixme-accent text-fixme-bg text-xs font-bold px-4 py-2 flex-shrink-0"
                    >
                      Book
                    </button>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-2xl border border-fixme-border bg-fixme-card p-5 text-center">
              {search ? (
                <>
                  <p className="text-fixme-text-secondary text-sm">No services match &ldquo;{search}&rdquo;</p>
                  <button
                    onClick={() => setSearch('')}
                    className="mt-2 text-fixme-accent text-sm font-semibold"
                  >
                    Clear search
                  </button>
                </>
              ) : (
                <>
                  <p className="text-fixme-text-secondary text-sm">No services listed yet.</p>
                  {isOwner && (
                    <button
                      onClick={() => { window.location.href = '/provider/settings'; }}
                      className="mt-3 text-fixme-accent text-sm font-semibold"
                    >
                      Add services in Settings
                    </button>
                  )}
                </>
              )}
            </div>
          )}

          {/* Owner: manage shortcut */}
          {isOwner && services.length > 0 && (
            <button
              onClick={() => { window.location.href = '/provider/settings'; }}
              className="w-full rounded-xl border border-fixme-border text-fixme-text-muted text-sm font-semibold py-2.5 hover:border-fixme-accent hover:text-fixme-accent transition-colors"
            >
              + Add or edit services
            </button>
          )}
        </div>
      )}

      {/* ── Book sub-tab ── */}
      {subTab === 'book' && (
        <div className="px-4 py-4">
          <div className="rounded-2xl bg-fixme-card border border-fixme-border p-3">
            <p className="text-fixme-text-muted text-xs uppercase tracking-widest mb-3">
              {rebookService ? `Book again \u2014 ${rebookService.name}` : selectedService ? 'Choose location & time' : 'Book instantly'}
            </p>
            <div className="rounded-xl border border-fixme-border overflow-hidden">
              <BookingFlowEmbedded
                key={rebookService?.service_id ?? selectedService?.service_id ?? 'no-service'}
                provider={profile}
                rebookService={rebookService ?? null}
                preSelectedService={rebookService ? null : selectedService}
                initialReferralSource={bookingReferralSource}
                onClose={() => { setSubTab('menu'); setSelectedService(null); setRebookService(null); }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── ReviewsTab ────────────────────────────────────────────────────────────────
const MOCK_REVIEWS = [
  {
    id: 'rv1',
    author: 'MajaN',
    ago: '2 days ago',
    stars: 5,
    text: 'Studio was amazing. Friendly staff and the result was exactly what I hoped for.',
  },
  {
    id: 'rv2',
    author: 'Mimmi S.',
    ago: '3 hours ago',
    stars: 5,
    text: 'Great communication and smooth booking. Will come back.',
  },
];

function ReviewsTab() {
  return (
    <div className="px-4 py-4 space-y-4">
      {MOCK_REVIEWS.map((r) => (
        <div key={r.id} className="bg-fixme-card border border-fixme-border rounded-2xl p-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-9 h-9 rounded-full bg-fixme-border flex-shrink-0" />
            <div>
              <p className="text-fixme-text-primary text-sm font-semibold">{r.author}</p>
              <p className="text-fixme-text-muted text-xs">{r.ago}</p>
            </div>
            <span className="ml-auto text-fixme-accent text-xs">
              {'★'.repeat(r.stars)}
            </span>
          </div>
          <p className="text-fixme-text-secondary text-sm leading-relaxed">{r.text}</p>
        </div>
      ))}
      <button className="w-full rounded-full border border-fixme-border text-fixme-text-secondary text-sm font-semibold py-3 hover:border-fixme-accent hover:text-fixme-accent transition-colors">
        Write a review
      </button>
    </div>
  );
}

// ── FollowButton ──────────────────────────────────────────────────────────────
function FollowButton({ providerId, initialFollowing, onFollowChange }) {
  const [following, setFollowing] = useState(initialFollowing);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setFollowing(initialFollowing);
  }, [initialFollowing]);

  const handleClick = useCallback(async () => {
    const token = getCustomerToken();
    if (!token) {
      window.location.href = `/customer/login?redirect=${encodeURIComponent(window.location.pathname)}`;
      return;
    }
    setLoading(true);
    try {
      if (following) {
        await unfollowProvider(token, providerId);
        setFollowing(false);
        onFollowChange?.(-1);
      } else {
        await followProvider(token, providerId);
        setFollowing(true);
        onFollowChange?.(+1);
      }
    } catch {
      // silent – keep original state
    } finally {
      setLoading(false);
    }
  }, [following, providerId, onFollowChange]);

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      className={`flex-1 rounded-xl text-sm font-semibold py-2.5 border transition-colors ${
        following
          ? 'bg-fixme-card border-fixme-border text-fixme-text-primary hover:border-fixme-accent/60'
          : 'bg-fixme-accent border-transparent text-fixme-bg hover:bg-fixme-accent-light'
      } disabled:opacity-50`}
    >
      {loading ? '...' : following ? 'Following' : 'Follow'}
    </button>
  );
}

// ── Avatar placeholder ────────────────────────────────────────────────────────
function Avatar({ url, name, size = 'lg' }) {
  const dim = size === 'lg' ? 'w-20 h-20' : 'w-16 h-16';
  return (
    <div
      className={`${dim} rounded-full overflow-hidden bg-fixme-card border border-fixme-border flex-shrink-0 flex items-center justify-center`}
    >
      {url ? (
        <img src={url} alt={name} className="w-full h-full object-cover" />
      ) : (
        <span className="text-2xl text-fixme-text-muted" aria-hidden="true">
          {'\u{1F9D6}'}
        </span>
      )}
    </div>
  );
}

// ── OwnerProfileShell (/provider/profile) ────────────────────────────────────
function OwnerProfileShell({ profile }) {
  const [tab, setTab] = useState('about');

  const slug = localStorage.getItem('fixme_provider_slug');
  const publicUrl = slug ? `/p/${slug}` : null;
  const avatarUrl = profile?.ig_profile_picture_url || profile?.image_url || null;
  const username = profile?.instagram_username || slug || '';

  const handleShare = () => {
    if (!publicUrl) return;
    const full = `${window.location.origin}${publicUrl}`;
    navigator.clipboard?.writeText(full).catch(() => {});
  };

  // ── No profile yet — AI is building it from onboarding scrape ───────────
  if (!profile) {
    return (
      <div className="min-h-screen bg-fixme-bg pb-24 px-4 pt-8 max-w-md mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-fixme-text-primary text-xl font-bold">Profile</h1>
          <button
            onClick={() => { window.location.href = '/provider/settings'; }}
            className="w-9 h-9 flex items-center justify-center rounded-full bg-fixme-card border border-fixme-border text-fixme-text-secondary hover:border-fixme-accent transition-colors"
            aria-label="Settings"
          >
            {'\u2699'}
          </button>
        </div>
        <div className="rounded-2xl border border-fixme-border bg-fixme-card p-6 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-fixme-accent/10 flex items-center justify-center mx-auto text-2xl">
            {'\u{1F9E0}'}
          </div>
          <p className="text-fixme-text-primary text-sm font-semibold">Your profile is being built</p>
          <p className="text-fixme-text-muted text-xs leading-relaxed">
            Complete onboarding so our AI can scan your Instagram and website
            to auto-fill your profile.
          </p>
          <button
            onClick={() => { window.location.href = '/provider/onboarding'; }}
            className="w-full rounded-xl bg-fixme-accent text-fixme-bg text-sm font-semibold py-3 hover:bg-fixme-accent-light transition-colors"
          >
            Finish onboarding {'\u2192'}
          </button>
        </div>
        <ProviderTabBar active="profile" />
      </div>
    );
  }

  // ── Full owner profile ───────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-fixme-bg pb-24 max-w-md mx-auto">
      {/* Header */}
      <div className="px-4 pt-6 pb-2 flex items-center justify-between">
        <h1 className="text-fixme-text-primary text-xl font-bold">Profile</h1>
        <button
          onClick={() => { window.location.href = '/provider/settings'; }}
          className="w-9 h-9 flex items-center justify-center rounded-full bg-fixme-card border border-fixme-border text-fixme-text-secondary hover:border-fixme-accent transition-colors"
          aria-label="Open settings"
        >
          {'\u2699'}
        </button>
      </div>

      <div className="px-4">
        {/* Avatar + stats */}
        <div className="flex items-center gap-4 mt-3">
          <Avatar url={avatarUrl} name={profile.name} size="lg" />
          <div className="flex-1">
            <Stats profile={profile} />
          </div>
        </div>

        {/* Name + handle + bio */}
        <div className="mt-3">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-fixme-text-primary font-bold text-base">{profile.name || 'Your Name'}</p>
            {profile.is_verified && <VerifiedBadge />}
          </div>
          {username ? (
            <p className="text-fixme-text-muted text-sm mt-0.5">@{username}</p>
          ) : null}
          {profile?.trust?.rating > 0 ? (
            <p className="text-fixme-text-secondary text-xs mt-1">{'\u2B50'} {profile.trust.rating.toFixed(1)}</p>
          ) : (
            <p className="text-fixme-text-muted text-xs mt-1">No rating yet</p>
          )}
          {profile.bio ? (
            <p className="text-fixme-text-secondary text-sm mt-2 leading-relaxed">{profile.bio}</p>
          ) : (
            <p className="text-fixme-text-muted text-sm mt-2 italic">No bio yet — add one in Settings.</p>
          )}
        </div>

        {/* Owner action buttons */}
        <div className="mt-4 grid grid-cols-2 gap-3">
          <button
            onClick={() => { window.location.href = '/provider/settings'; }}
            className="rounded-xl bg-fixme-card border border-fixme-border text-fixme-text-primary text-sm font-semibold py-2.5 hover:border-fixme-accent transition-colors"
          >
            Edit Profile
          </button>
          <button
            onClick={handleShare}
            disabled={!publicUrl}
            className="rounded-xl bg-fixme-card border border-fixme-border text-fixme-text-primary text-sm font-semibold py-2.5 hover:border-fixme-accent transition-colors disabled:opacity-40"
          >
            {'\u{1F517}'} Share
          </button>
        </div>

        {publicUrl && (
          <button
            onClick={() => { window.location.href = publicUrl; }}
            className="mt-2 w-full text-fixme-text-muted text-xs py-1.5 hover:text-fixme-accent transition-colors"
          >
            Preview as customer {'\u2192'}
          </button>
        )}
      </div>

      {/* Tabs + content */}
      <TabRow tab={tab} setTab={setTab} />
      {tab === 'about'    && <AboutTab    profile={profile} />}
      {tab === 'services' && <ServicesTab profile={profile} isOwner bookingReferralSource={null} />}
      {tab === 'reviews'  && <ReviewsTab />}

      <ProviderTabBar active="profile" />
    </div>
  );
}

// ── PublicProfileShell (/p/:slug) ─────────────────────────────────────────────
function PublicProfileShell({ profile, isOwnerPreview }) {
  // Detect "Book again" rebook param: /p/slug?rebook=1&service=ServiceName
  const searchParams = new URLSearchParams(window.location.search);
  const isRebookLink  = searchParams.get('rebook') === '1';
  const rebookServiceName = isRebookLink ? (searchParams.get('service') || null) : null;

  const [tab, setTab] = useState(isRebookLink ? 'services' : 'about');
  const [isFollowing, setIsFollowing] = useState(false);
  const [followerDelta, setFollowerDelta] = useState(0);

  useEffect(() => {
    const token = getCustomerToken();
    if (token && profile?.provider_id) {
      getFollowStatus(token, profile.provider_id)
        .then((res) => setIsFollowing(Boolean(res.is_following)))
        .catch(() => {});
    }
  }, [profile?.provider_id]);

  const avatarUrl = profile.ig_profile_picture_url || profile.image_url || null;
  const slug = window.location.pathname.match(/^\/p\/([a-z0-9-]+)/)?.[1];
  const username = profile.instagram_username || slug || 'profile';
  const location = [profile.business_type, profile.city].filter(Boolean).join(', ');

  const bookingReferralSource = normalizeReferralSource(new URLSearchParams(window.location.search).get('ref'))
    || getCapturedReferralSource({ providerId: profile.provider_id, slug: profile.slug });

  const handleShare = () => {
    navigator.clipboard?.writeText(window.location.href).catch(() => {});
  };

  useEffect(() => {
    captureReferralFromSearch(window.location.search, {
      providerId: profile.provider_id,
      slug: profile.slug,
    });
  }, [profile.provider_id, profile.slug]);

  return (
    <div className="min-h-screen bg-fixme-bg max-w-md mx-auto pb-6">
      {/* Owner preview banner */}
      {isOwnerPreview && (
        <div className="bg-fixme-card border-b border-fixme-border px-4 py-2 flex items-center justify-between">
          <span className="text-fixme-text-muted text-xs">Viewing as customer</span>
          <button
            onClick={() => { window.location.href = '/provider/profile'; }}
            className="text-fixme-accent text-xs font-semibold"
          >
            Back to dashboard
          </button>
        </div>
      )}

      {/* Header */}
      <div className="px-4 pt-5 flex items-center justify-between gap-2">
        <button
          onClick={() => window.history.back()}
          className="w-9 h-9 flex items-center justify-center rounded-full bg-fixme-card border border-fixme-border text-fixme-text-secondary flex-shrink-0"
          aria-label="Back"
        >
          {'\u2190'}
        </button>
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="text-fixme-text-primary text-base font-semibold truncate">
            @{username}
          </span>
          {profile.is_verified && <VerifiedBadge />}
        </div>
        <button
          onClick={handleShare}
          className="w-9 h-9 flex items-center justify-center rounded-full bg-fixme-card border border-fixme-border text-fixme-text-secondary flex-shrink-0"
          aria-label="Share profile"
        >
          {'\u2197'}
        </button>
      </div>

      <div className="px-4">
        {/* Stats */}
        <Stats profile={profile} followerDelta={followerDelta} />

        {/* Avatar + name + Book shortcut */}
        <div className="flex items-start gap-4">
          <Avatar url={avatarUrl} name={profile.name} size="lg" />
          <div className="min-w-0 flex-1 pt-1">
            <div className="flex items-center gap-1.5 flex-wrap">
              <p className="text-fixme-text-primary font-bold text-sm">{profile.name}</p>
              {profile.is_verified && <VerifiedBadge showLabel />}
            </div>
            {location && (
              <p className="text-fixme-text-secondary text-xs mt-0.5">{location}</p>
            )}
            {profile?.trust?.rating > 0 ? (
              <p className="text-fixme-text-secondary text-xs mt-1">{'\u2B50'} {profile.trust.rating.toFixed(1)}</p>
            ) : (
              <p className="text-fixme-text-muted text-xs mt-1">No rating yet</p>
            )}
            {profile.bio && (
              <p className="text-fixme-text-muted text-xs mt-1 line-clamp-2 leading-relaxed">
                {profile.bio}
              </p>
            )}
          </div>
          <button
            onClick={() => setTab('services')}
            className="rounded-full bg-fixme-accent text-fixme-bg text-xs font-bold px-4 py-2 flex-shrink-0 mt-1"
          >
            Book
          </button>
        </div>

        {/* Action buttons – always show customer actions, even in owner-preview */}
        <div className="mt-4 grid grid-cols-2 gap-3">
          <button className="flex-1 rounded-xl bg-fixme-card border border-fixme-border text-fixme-text-primary text-sm font-semibold py-2.5 hover:border-fixme-accent transition-colors">
            Message
          </button>
          <FollowButton
            providerId={profile.provider_id}
            initialFollowing={isFollowing}
            onFollowChange={(delta) => setFollowerDelta((d) => d + delta)}
          />
        </div>
      </div>

      {/* Tabs + content */}
      <TabRow tab={tab} setTab={setTab} />
      {tab === 'about'    && <AboutTab    profile={profile} />}
      {tab === 'services' && (
        <ServicesTab
          profile={profile}
          isOwner={false}
          bookingReferralSource={bookingReferralSource}
          autoRebookServiceName={rebookServiceName}
        />
      )}
      {tab === 'reviews'  && <ReviewsTab />}
    </div>
  );
}

// ── Entry point ───────────────────────────────────────────────────────────────
export default function ProviderProfilePage() {
  const path = window.location.pathname;
  const isOwnerRoute = path === '/provider/profile';

  // /pid/{provider_id} — direct ID-based link (used from search results)
  const urlProviderId = path.match(/^\/pid\/([a-f0-9-]{36})/i)?.[1] || null;

  // Slug resolution for /p/{slug} and /provider/profile
  const urlSlug = path.match(/^\/p\/([a-z0-9-]+)/)?.[1] || null;
  const localSlug = localStorage.getItem('fixme_provider_slug');
  const hasProviderToken = Boolean(localStorage.getItem('fixme_provider_token'));

  // Owner = on own dashboard route, OR visiting own public slug while logged in as provider
  const isOwner = isOwnerRoute || (Boolean(urlSlug) && urlSlug === localSlug && hasProviderToken);
  const slug = isOwnerRoute ? localSlug : urlSlug;

  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function loadProfile() {
      // /pid/{provider_id} route — fetch directly by ID, no slug needed
      if (urlProviderId) {
        getProviderProfileById(urlProviderId)
          .then((data) => setProfile(data))
          .catch((err) => setError(err.message || 'Profile not found'))
          .finally(() => setLoading(false));
        return;
      }

      let resolvedSlug = slug;

      // Auto-resolve slug from provider_id for old sessions that didn't store it
      if (!resolvedSlug && isOwnerRoute) {
        const pid = localStorage.getItem('fixme_provider_id');
        if (pid) {
          try {
            const rec = await getProvider(pid);
            if (rec?.slug) {
              localStorage.setItem('fixme_provider_slug', rec.slug);
              resolvedSlug = rec.slug;
            }
          } catch { /* silently ignore — will show onboarding CTA */ }
        }
      }

      if (!resolvedSlug) {
        setLoading(false);
        return;
      }

      getProviderProfile(resolvedSlug)
        .then((data) => setProfile(data))
        .catch((err) => setError(err.message || 'Profile not found'))
        .finally(() => setLoading(false));
    }

    loadProfile();
  }, [slug, urlProviderId, isOwnerRoute]);

  // ── Loading ──────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="min-h-screen bg-fixme-bg">
        <LoadingScreen message={isOwnerRoute ? 'Building your profile\u2026' : 'Loading profile\u2026'} />
      </div>
    );
  }

  // ── Public error (not owner route) ───────────────────────────────────────
  if (error && !isOwnerRoute) {
    return (
      <div className="min-h-screen bg-fixme-bg flex items-center justify-center px-6 text-center">
        <p className="text-fixme-text-secondary text-sm">{error}</p>
      </div>
    );
  }

  // ── Owner dashboard shell (profile may be null if slug not set yet) ──────
  if (isOwnerRoute) {
    return <OwnerProfileShell profile={profile} />;
  }

  // ── Public /p/:slug – profile must exist ─────────────────────────────────
  if (!profile) {
    return (
      <div className="min-h-screen bg-fixme-bg flex items-center justify-center px-6 text-center">
        <p className="text-fixme-text-secondary text-sm">Profile not found.</p>
      </div>
    );
  }

  return <PublicProfileShell profile={profile} isOwnerPreview={isOwner} />;
}

