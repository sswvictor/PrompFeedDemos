/**
 * CustomerSettingsPage — /customer/settings
 *
 * Account + preferences hub.
 *   - Account: avatar, display name (editable), real name (GDPR, providers only), email (editable)
 *   - Preferences: service interests + lifestyle (used by AI discovery)
 *   - My Locations: preferred spots the AI uses for DM booking + search (up to 10)
 *   - Privacy: public/private profile toggle
 *   - Sign out
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  getCustomerDashboard,
  getCustomerPreferences,
  followProvider,
  searchProviders,
  updateCustomerPreferences,
  updateCustomerFavorites,
  updateCustomerProfile,
  uploadCustomerAvatar,
} from '../../../api/bookingApi';
import { SERVICE_OPTIONS, LIFESTYLE_OPTIONS } from '../../../constants/customerPreferences';

function normalize(arr) {
  return [...(arr || [])].sort((a, b) => a.localeCompare(b));
}

function arraysEqual(a, b) {
  const aa = normalize(a);
  const bb = normalize(b);
  if (aa.length !== bb.length) return false;
  return aa.every((v, i) => v === bb[i]);
}

function orderedArraysEqual(a, b) {
  if (a.length !== b.length) return false;
  return a.every((v, i) => v === b[i]);
}

function toggleChoice(values, key) {
  return values.includes(key) ? values.filter((v) => v !== key) : [...values, key];
}

function providerLocationLabel(provider) {
  return provider?.city || provider?.location_salon || '';
}

function ChoiceChips({ title, subtitle, options, selected, onToggle }) {
  return (
    <div className="space-y-2.5">
      <div>
        <h3 className="text-fixme-text-primary text-sm font-semibold">{title}</h3>
        {subtitle && <p className="text-fixme-text-muted text-xs mt-0.5">{subtitle}</p>}
      </div>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => {
          const active = selected.includes(opt.key);
          return (
            <button
              key={opt.key}
              type="button"
              onClick={() => onToggle(opt.key)}
              className={`px-3 py-1.5 rounded-full text-xs border transition-all ${
                active
                  ? 'border-fixme-accent bg-fixme-accent/10 text-fixme-text-primary'
                  : 'border-fixme-border bg-fixme-card text-fixme-text-secondary'
              }`}
            >
              {opt.emoji && <span className="mr-1">{opt.emoji}</span>}{opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function CustomerSettingsPage() {
  const token = localStorage.getItem('fixme_token');
  const avatarInputRef = useRef(null);

  const [loading, setLoading] = useState(true);
  const [avatarUrl, setAvatarUrl] = useState(null);
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [toast, setToast] = useState(null);

  // ── Account / Profile fields ─────────────────────────────
  const [serverProfile, setServerProfile] = useState({ display_name: '', full_name: '', email: '' });
  const [displayName, setDisplayName] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [profileSaving, setProfileSaving] = useState(false);

  // ── Preferences ─────────────────────────────────────────
  const [serverPreferences, setServerPreferences] = useState({ service_interests: [], lifestyle_preferences: [] });
  const [serviceInterests, setServiceInterests] = useState([]);
  const [lifestylePreferences, setLifestylePreferences] = useState([]);
  const [prefSaving, setPrefSaving] = useState(false);

  const [followedProviders, setFollowedProviders] = useState([]);
  const [serverFavoriteProviderIds, setServerFavoriteProviderIds] = useState([]);
  const [favoriteProviderIds, setFavoriteProviderIds] = useState([]);
  const [favoriteSaving, setFavoriteSaving] = useState(false);
  const [providerSearchLocation, setProviderSearchLocation] = useState('');
  const [providerSearchCategory, setProviderSearchCategory] = useState('');
  const [providerSearchResults, setProviderSearchResults] = useState([]);
  const [providerSearchLoading, setProviderSearchLoading] = useState(false);
  const [providerSearchError, setProviderSearchError] = useState('');
  const [favoriteAddBusyProviderId, setFavoriteAddBusyProviderId] = useState(null);

  // ── Preferred Locations ──────────────────────────────────
  const [serverLocations, setServerLocations] = useState([]);
  const [preferredLocations, setPreferredLocations] = useState([]);
  const [locationInput, setLocationInput] = useState('');
  const [locationSaving, setLocationSaving] = useState(false);

  // ── Privacy ──────────────────────────────────────────────
  const [isProfilePublic, setIsProfilePublic] = useState(true);
  const [privacySaving, setPrivacySaving] = useState(false);

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 2800);
  };

  useEffect(() => {
    if (!token) { setLoading(false); return; }
    Promise.all([getCustomerDashboard(token), getCustomerPreferences(token)])
      .then(([dash, prefs]) => {
        setAvatarUrl(dash.image_url || null);

        const dn = dash.display_name || '';
        const fn = dash.full_name || '';
        const em = dash.email || localStorage.getItem('fixme_customer_email') || '';
        setDisplayName(dn);
        setFullName(fn);
        setEmail(em);
        setServerProfile({ display_name: dn, full_name: fn, email: em });

        const locs = dash.preferred_locations || [];
        setPreferredLocations(locs);
        setServerLocations(locs);

        setIsProfilePublic(dash.is_profile_public !== false);
        setServerPreferences(prefs);
        setServiceInterests(prefs.service_interests || []);
        setLifestylePreferences(prefs.lifestyle_preferences || []);

        const followed = dash.followed_providers || [];
        const favorites = Array.isArray(dash.favorite_provider_ids) ? dash.favorite_provider_ids : [];
        setFollowedProviders(followed);
        setServerFavoriteProviderIds(favorites);
        setFavoriteProviderIds(favorites);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // ── Dirty checks ────────────────────────────────────────
  const hasProfileChanges = useMemo(
    () =>
      (displayName || '') !== (serverProfile.display_name || '') ||
      (fullName || '') !== (serverProfile.full_name || '') ||
      (email || '') !== (serverProfile.email || ''),
    [displayName, fullName, email, serverProfile],
  );

  const hasPrefChanges = useMemo(
    () =>
      !arraysEqual(serviceInterests, serverPreferences.service_interests) ||
      !arraysEqual(lifestylePreferences, serverPreferences.lifestyle_preferences),
    [serviceInterests, lifestylePreferences, serverPreferences],
  );

  const hasLocationChanges = useMemo(
    () => !orderedArraysEqual(preferredLocations, serverLocations),
    [preferredLocations, serverLocations],
  );

  const hasFavoriteChanges = useMemo(
    () => !arraysEqual(favoriteProviderIds, serverFavoriteProviderIds),
    [favoriteProviderIds, serverFavoriteProviderIds],
  );

  const followedProviderIdSet = useMemo(
    () => new Set((followedProviders || []).map((p) => p.provider_id)),
    [followedProviders],
  );

  const favoriteSearchCategoryOptions = useMemo(
    () => [
      { key: '', label: 'All categories' },
      ...SERVICE_OPTIONS.map((opt) => ({ key: opt.key, label: opt.label })),
    ],
    [],
  );

  // ── Handlers ────────────────────────────────────────────
  async function handleAvatarChange(e) {
    const file = e.target.files?.[0];
    if (!file || !token) return;
    setAvatarUploading(true);
    try {
      const result = await uploadCustomerAvatar(token, file);
      setAvatarUrl(result.image_url);
      showToast('Photo updated');
    } catch (err) {
      showToast(err.message || 'Could not upload photo', 'error');
    } finally {
      setAvatarUploading(false);
      if (avatarInputRef.current) avatarInputRef.current.value = '';
    }
  }

  async function saveProfile() {
    if (!token || !hasProfileChanges || profileSaving) return;
    setProfileSaving(true);
    try {
      // Only send fields that actually changed
      const body = {};
      if ((displayName || '') !== (serverProfile.display_name || ''))
        body.display_name = displayName.trim() || null;
      if ((fullName || '') !== (serverProfile.full_name || ''))
        body.full_name = fullName.trim() || null;
      if ((email || '') !== (serverProfile.email || '') && email.trim())
        body.email = email.trim();

      const updated = await updateCustomerProfile(token, body);

      const newDn = updated.display_name !== undefined ? (updated.display_name || '') : displayName;
      const newFn = updated.full_name !== undefined ? (updated.full_name || '') : fullName;
      const newEm = updated.email || email;
      setDisplayName(newDn);
      setFullName(newFn);
      setEmail(newEm);
      setServerProfile({ display_name: newDn, full_name: newFn, email: newEm });
      if (updated.email) localStorage.setItem('fixme_customer_email', updated.email);
      showToast('Profile saved');
    } catch (err) {
      showToast(err.message || 'Could not save', 'error');
    } finally {
      setProfileSaving(false);
    }
  }

  async function savePreferences() {
    if (!token || !hasPrefChanges || prefSaving) return;
    setPrefSaving(true);
    try {
      const updated = await updateCustomerPreferences(
        token,
        normalize(serviceInterests),
        normalize(lifestylePreferences),
      );
      setServerPreferences(updated);
      setServiceInterests(updated.service_interests || []);
      setLifestylePreferences(updated.lifestyle_preferences || []);
      showToast('Preferences saved');
    } catch (err) {
      showToast(err.message || 'Could not save', 'error');
    } finally {
      setPrefSaving(false);
    }
  }

  function toggleFavoriteProvider(providerId) {
    setFavoriteProviderIds((prev) => (
      prev.includes(providerId)
        ? prev.filter((id) => id !== providerId)
        : [...prev, providerId]
    ));
  }

  async function saveFavorites() {
    if (!token || !hasFavoriteChanges || favoriteSaving) return;
    setFavoriteSaving(true);
    try {
      const updated = await updateCustomerFavorites(token, normalize(favoriteProviderIds));
      const ids = updated.provider_ids || [];
      setServerFavoriteProviderIds(ids);
      setFavoriteProviderIds(ids);
      showToast('Favorite providers saved');
    } catch (err) {
      showToast(err.message || 'Could not save favorites', 'error');
    } finally {
      setFavoriteSaving(false);
    }
  }

  async function runProviderSearch() {
    const location = providerSearchLocation.trim();
    const serviceCategory = providerSearchCategory || '';
    if (!location && !serviceCategory) {
      setProviderSearchError('Add location or category before searching.');
      setProviderSearchResults([]);
      return;
    }

    setProviderSearchLoading(true);
    setProviderSearchError('');
    try {
      const results = await searchProviders({ location, serviceCategory });
      setProviderSearchResults(Array.isArray(results) ? results : []);
      if (!results || results.length === 0) {
        setProviderSearchError('No providers found for this search.');
      }
    } catch (err) {
      setProviderSearchResults([]);
      setProviderSearchError(err.message || 'Could not search providers.');
    } finally {
      setProviderSearchLoading(false);
    }
  }

  async function addProviderAsFavorite(provider) {
    if (!token || !provider?.provider_id || favoriteAddBusyProviderId) return;

    const providerId = provider.provider_id;
    setFavoriteAddBusyProviderId(providerId);
    try {
      if (!followedProviderIdSet.has(providerId)) {
        await followProvider(token, providerId);
        setFollowedProviders((prev) => {
          if (prev.some((p) => p.provider_id === providerId)) return prev;
          return [
            ...prev,
            {
              provider_id: provider.provider_id,
              name: provider.name || 'Provider',
              image_url: provider.image_url || null,
              city: provider.city || null,
              rating: provider.rating || 0,
            },
          ];
        });
      }

      const nextFavorites = Array.from(new Set([...favoriteProviderIds, providerId]));
      const updated = await updateCustomerFavorites(token, normalize(nextFavorites));
      const ids = updated.provider_ids || [];
      setServerFavoriteProviderIds(ids);
      setFavoriteProviderIds(ids);
      showToast('Added to favorite providers');
    } catch (err) {
      showToast(err.message || 'Could not add favorite provider', 'error');
    } finally {
      setFavoriteAddBusyProviderId(null);
    }
  }

  function addLocation() {
    const val = locationInput.trim();
    if (!val || preferredLocations.length >= 10) return;
    if (preferredLocations.some((l) => l.toLowerCase() === val.toLowerCase())) return;
    setPreferredLocations((prev) => [...prev, val]);
    setLocationInput('');
  }

  async function saveLocations() {
    if (!token || !hasLocationChanges || locationSaving) return;
    setLocationSaving(true);
    try {
      await updateCustomerProfile(token, { preferred_locations: preferredLocations });
      setServerLocations([...preferredLocations]);
      showToast('Locations saved');
    } catch (err) {
      showToast(err.message || 'Could not save', 'error');
    } finally {
      setLocationSaving(false);
    }
  }

  async function togglePrivacy(newValue) {
    if (!token || privacySaving) return;
    setPrivacySaving(true);
    const previous = isProfilePublic;
    setIsProfilePublic(newValue); // optimistic
    try {
      await updateCustomerProfile(token, { is_profile_public: newValue });
      showToast(newValue ? 'Profile is now public' : 'Profile is now private');
    } catch (err) {
      setIsProfilePublic(previous); // rollback
      showToast(err.message || 'Could not update privacy', 'error');
    } finally {
      setPrivacySaving(false);
    }
  }

  function signOut() {
    localStorage.removeItem('fixme_token');
    localStorage.removeItem('fixme_customer_email');
    localStorage.removeItem('fixme_customer_id');
    window.location.href = '/customer/welcome';
  }

  if (!token) {
    return (
      <div className="min-h-screen bg-fixme-bg px-4 pt-10 max-w-md mx-auto text-center space-y-4">
        <p className="text-fixme-text-secondary text-sm">Sign in to access your settings.</p>
        <button
          onClick={() => { window.location.href = '/customer/login'; }}
          className="px-6 py-3 bg-fixme-accent text-fixme-bg text-sm font-semibold rounded-xl"
        >
          Sign in
        </button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-fixme-bg px-4 pt-8 max-w-md mx-auto animate-pulse space-y-4">
        <div className="h-6 bg-fixme-card rounded w-24" />
        <div className="h-48 bg-fixme-card rounded-2xl" />
        <div className="h-48 bg-fixme-card rounded-2xl" />
        <div className="h-36 bg-fixme-card rounded-2xl" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-fixme-bg pb-12 px-4 pt-4 max-w-md mx-auto space-y-5">

      {/* Header */}
      <div className="flex items-center gap-3 pt-2 pb-1">
        <button
          onClick={() => window.history.back()}
          className="text-fixme-text-muted hover:text-fixme-text-secondary transition-colors text-lg leading-none w-7"
          aria-label="Back"
        >
          {'\u2190'}
        </button>
        <h1 className="text-fixme-text-primary font-bold text-lg flex-1">Settings</h1>
      </div>

      {/* ── Account ─────────────────────────────────────────── */}
      <section className="bg-fixme-card border border-fixme-border rounded-2xl p-4 space-y-4">
        <h2 className="text-fixme-text-primary text-sm font-semibold uppercase tracking-wide">Account</h2>

        {/* Avatar */}
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
            className="relative w-16 h-16 rounded-full overflow-hidden border-2 border-fixme-border bg-fixme-bg flex-shrink-0 group focus:outline-none"
            title="Change profile photo"
          >
            {avatarUrl ? (
              <img src={avatarUrl} alt="Avatar" className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-fixme-accent text-2xl font-bold">
                {displayName?.charAt(0)?.toUpperCase() || '\u{1F464}'}
              </div>
            )}
            <div className="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
              {avatarUploading ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              )}
            </div>
          </button>
          <button
            type="button"
            onClick={() => avatarInputRef.current?.click()}
            className="text-fixme-accent text-xs font-medium hover:underline"
          >
            {avatarUploading ? 'Uploading\u2026' : 'Change photo'}
          </button>
        </div>

        {/* Display name */}
        <div className="space-y-1">
          <label className="text-fixme-text-secondary text-xs font-medium block">
            Username / Display name
          </label>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="How you appear publicly"
            maxLength={80}
            className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2.5 text-sm text-fixme-text-primary placeholder-fixme-text-muted focus:outline-none focus:border-fixme-accent/60 transition-colors"
          />
          <p className="text-fixme-text-muted text-[11px]">Visible on your public profile</p>
        </div>

        {/* Real name (GDPR) */}
        <div className="space-y-1">
          <label className="text-fixme-text-secondary text-xs font-medium block">
            Real name
          </label>
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Your full name"
            maxLength={120}
            className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2.5 text-sm text-fixme-text-primary placeholder-fixme-text-muted focus:outline-none focus:border-fixme-accent/60 transition-colors"
          />
          <p className="text-fixme-text-muted text-[11px]">
            Only visible to providers you have booked with
          </p>
        </div>

        {/* Email */}
        <div className="space-y-1">
          <label className="text-fixme-text-secondary text-xs font-medium block">
            Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="your@email.com"
            className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2.5 text-sm text-fixme-text-primary placeholder-fixme-text-muted focus:outline-none focus:border-fixme-accent/60 transition-colors"
          />
        </div>

        <button
          type="button"
          onClick={saveProfile}
          disabled={profileSaving || !hasProfileChanges}
          className="w-full rounded-xl px-4 py-3 text-sm font-semibold bg-fixme-accent text-fixme-bg disabled:opacity-50 transition-all active:scale-[0.98]"
        >
          {profileSaving ? 'Saving\u2026' : hasProfileChanges ? 'Save account' : 'Up to date'}
        </button>
      </section>

      {/* ── Preferences ─────────────────────────────────────── */}
      <section className="bg-fixme-card border border-fixme-border rounded-2xl p-4 space-y-5">
        <div>
          <h2 className="text-fixme-text-primary text-sm font-semibold uppercase tracking-wide">Preferences</h2>
          <p className="text-fixme-text-muted text-xs mt-0.5">Used by the AI to match you to the right providers</p>
        </div>

        <ChoiceChips
          title="Services you love"
          subtitle="Tap to select your interests"
          options={SERVICE_OPTIONS}
          selected={serviceInterests}
          onToggle={(key) => setServiceInterests((prev) => toggleChoice(prev, key))}
        />

        <ChoiceChips
          title="Your vibe"
          subtitle="What makes a great session for you"
          options={LIFESTYLE_OPTIONS}
          selected={lifestylePreferences}
          onToggle={(key) => setLifestylePreferences((prev) => toggleChoice(prev, key))}
        />

        <button
          type="button"
          onClick={savePreferences}
          disabled={prefSaving || !hasPrefChanges}
          className="w-full rounded-xl px-4 py-3 text-sm font-semibold bg-fixme-accent text-fixme-bg disabled:opacity-50 transition-all active:scale-[0.98]"
        >
          {prefSaving ? 'Saving\u2026' : hasPrefChanges ? 'Save preferences' : 'Up to date'}
        </button>
      </section>

      {/* ── My Locations ────────────────────────────────────── */}
      <section className="bg-fixme-card border border-fixme-border rounded-2xl p-4 space-y-4">
        <div>
          <h2 className="text-fixme-text-primary text-sm font-semibold uppercase tracking-wide">My locations</h2>
          <p className="text-fixme-text-muted text-xs mt-0.5">
            The AI uses these to suggest nearby providers and time slots
          </p>
        </div>

        {/* Add location row */}
        <div className="flex gap-2">
          <input
            type="text"
            value={locationInput}
            onChange={(e) => setLocationInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addLocation(); } }}
            placeholder={'e.g. Gym \u2013 Hammarby'}
            maxLength={100}
            disabled={preferredLocations.length >= 10}
            className="flex-1 bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2.5 text-sm text-fixme-text-primary placeholder-fixme-text-muted focus:outline-none focus:border-fixme-accent/60 transition-colors disabled:opacity-40"
          />
          <button
            type="button"
            onClick={addLocation}
            disabled={!locationInput.trim() || preferredLocations.length >= 10}
            className="px-4 py-2.5 rounded-xl bg-fixme-accent text-fixme-bg text-sm font-semibold disabled:opacity-40 transition-all active:scale-[0.97]"
          >
            Add
          </button>
        </div>

        {/* Location chips */}
        {preferredLocations.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {preferredLocations.map((loc, i) => (
              <div
                key={i}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-fixme-border bg-fixme-bg text-xs text-fixme-text-primary"
              >
                <span className="text-fixme-accent">{'\u{1F4CD}'}</span>
                <span>{loc}</span>
                <button
                  type="button"
                  onClick={() => setPreferredLocations((prev) => prev.filter((_, idx) => idx !== i))}
                  className="ml-0.5 text-fixme-text-muted hover:text-fixme-error transition-colors leading-none font-bold"
                  aria-label={'Remove ' + loc}
                >
                  {'\u00D7'}
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-fixme-text-muted text-xs text-center py-1">
            No locations added yet
          </p>
        )}

        <button
          type="button"
          onClick={saveLocations}
          disabled={locationSaving || !hasLocationChanges}
          className="w-full rounded-xl px-4 py-3 text-sm font-semibold bg-fixme-accent text-fixme-bg disabled:opacity-50 transition-all active:scale-[0.98]"
        >
          {locationSaving ? 'Saving\u2026' : hasLocationChanges ? 'Save locations' : 'Up to date'}
        </button>
      </section>

      {/* Favorite providers */}


      <section className="bg-fixme-card border border-fixme-border rounded-2xl p-4 space-y-4">
        <div>
          <h2 className="text-fixme-text-primary text-sm font-semibold uppercase tracking-wide">Favorite providers</h2>
          <p className="text-fixme-text-muted text-xs mt-0.5">
            Choose favorites and add new providers to your list
          </p>
        </div>

        {followedProviders.length > 0 ? (
          <div className="space-y-2">
            {followedProviders.map((provider) => {
              const checked = favoriteProviderIds.includes(provider.provider_id);
              const location = providerLocationLabel(provider);
              return (
                <button
                  type="button"
                  key={provider.provider_id}
                  onClick={() => toggleFavoriteProvider(provider.provider_id)}
                  className={checked
                    ? 'w-full text-left rounded-xl border px-3 py-2.5 transition-colors border-fixme-accent bg-fixme-accent/10'
                    : 'w-full text-left rounded-xl border px-3 py-2.5 transition-colors border-fixme-border bg-fixme-bg'}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={checked
                        ? 'w-5 h-5 rounded border flex items-center justify-center text-[11px] border-fixme-accent bg-fixme-accent text-fixme-bg'
                        : 'w-5 h-5 rounded border flex items-center justify-center text-[11px] border-fixme-border text-transparent'}
                    >
                      {'\u2713'}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-fixme-text-primary text-sm font-medium truncate">{provider.name || 'Provider'}</p>
                      <p className="text-fixme-text-muted text-xs truncate">
                        {location || 'Location not set'}
                      </p>
                    </div>
                    {typeof provider.rating === 'number' && provider.rating > 0 && (
                      <p className="text-fixme-text-secondary text-xs whitespace-nowrap">{provider.rating.toFixed(1)} / 5.0</p>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          <p className="text-fixme-text-muted text-xs">
            You are not following any providers yet. Add some below.
          </p>
        )}

        <button
          type="button"
          onClick={saveFavorites}
          disabled={favoriteSaving || !hasFavoriteChanges}
          className="w-full rounded-xl px-4 py-3 text-sm font-semibold bg-fixme-accent text-fixme-bg disabled:opacity-50 transition-all active:scale-[0.98]"
        >
          {favoriteSaving ? 'Saving\u2026' : hasFavoriteChanges ? 'Save favorite providers' : 'Up to date'}
        </button>

        <div className="pt-2 border-t border-fixme-border space-y-3">
          <div>
            <h3 className="text-fixme-text-primary text-sm font-semibold">Add more providers</h3>
            <p className="text-fixme-text-muted text-xs mt-0.5">
              Search, follow, and add to favorites in one step
            </p>
          </div>

          <div className="space-y-2">
            <input
              type="text"
              value={providerSearchLocation}
              onChange={(e) => setProviderSearchLocation(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); runProviderSearch(); } }}
              placeholder="Location (e.g. Stockholm)"
              className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2.5 text-sm text-fixme-text-primary placeholder-fixme-text-muted focus:outline-none focus:border-fixme-accent/60 transition-colors"
            />
            <select
              value={providerSearchCategory}
              onChange={(e) => setProviderSearchCategory(e.target.value)}
              className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2.5 text-sm text-fixme-text-primary focus:outline-none focus:border-fixme-accent/60 transition-colors"
            >
              {favoriteSearchCategoryOptions.map((opt) => (
                <option key={opt.key || 'all'} value={opt.key}>
                  {opt.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={runProviderSearch}
              disabled={providerSearchLoading}
              className="w-full rounded-xl px-4 py-3 text-sm font-semibold border border-fixme-border bg-fixme-bg text-fixme-text-primary disabled:opacity-50 transition-all active:scale-[0.98]"
            >
              {providerSearchLoading ? 'Searching\u2026' : 'Search providers'}
            </button>
          </div>

          {providerSearchError && (
            <p className="text-fixme-error text-xs">{providerSearchError}</p>
          )}

          {providerSearchResults.length > 0 && (
            <div className="space-y-2">
              {providerSearchResults.slice(0, 8).map((provider) => {
                const providerId = provider.provider_id;
                const alreadyFavorite = favoriteProviderIds.includes(providerId);
                const busy = favoriteAddBusyProviderId === providerId;
                return (
                  <div
                    key={providerId}
                    className="flex items-center gap-3 rounded-xl border border-fixme-border bg-fixme-bg px-3 py-2.5"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-fixme-text-primary text-sm font-medium truncate">{provider.name || 'Provider'}</p>
                      <p className="text-fixme-text-muted text-xs truncate">
                        {[providerLocationLabel(provider), provider?.home_service ? 'Home visits' : null]
                          .filter(Boolean)
                          .join(' - ') || 'No location details'}
                      </p>
                    </div>
                    <button
                      type="button"
                      disabled={alreadyFavorite || busy}
                      onClick={() => addProviderAsFavorite(provider)}
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-fixme-border text-fixme-text-primary disabled:opacity-50"
                    >
                      {alreadyFavorite ? 'Added' : busy ? 'Adding...' : 'Add'}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </section>
      {/* Privacy */}
      <section className="bg-fixme-card border border-fixme-border rounded-2xl p-4 space-y-3">
        <div>
          <h2 className="text-fixme-text-primary text-sm font-semibold uppercase tracking-wide">Privacy</h2>
          <p className="text-fixme-text-muted text-xs mt-0.5">Control who can see your profile</p>
        </div>

        <button
          type="button"
          onClick={() => togglePrivacy(!isProfilePublic)}
          disabled={privacySaving}
          className="w-full flex items-center gap-4 p-3.5 rounded-xl border-2 transition-all disabled:opacity-60 border-fixme-border bg-fixme-bg hover:border-fixme-accent/30"
        >
          {/* Icon */}
          <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 transition-colors ${
            isProfilePublic ? 'bg-fixme-accent/15' : 'bg-fixme-border/60'
          }`}>
            {isProfilePublic ? (
              <svg className="w-5 h-5 text-fixme-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
            ) : (
              <svg className="w-5 h-5 text-fixme-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
              </svg>
            )}
          </div>

          {/* Text */}
          <div className="flex-1 text-left">
            <p className={`text-sm font-semibold ${isProfilePublic ? 'text-fixme-text-primary' : 'text-fixme-text-secondary'}`}>
              {isProfilePublic ? 'Public profile' : 'Private profile'}
            </p>
            <p className="text-xs text-fixme-text-muted leading-snug mt-0.5">
              {isProfilePublic
                ? 'Providers can see your name, avatar and rating'
                : 'Only providers you have booked can see your profile'}
            </p>
          </div>

          {/* Toggle */}
          <div className={`w-12 h-6 rounded-full relative transition-colors flex-shrink-0 ${
            isProfilePublic ? 'bg-fixme-accent' : 'bg-fixme-border'
          }`}>
            <div className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-all ${
              isProfilePublic ? 'left-7' : 'left-1'
            }`} />
          </div>
        </button>
      </section>

      {/* ── My data & privacy ───────────────────────────────── */}
      <section className="bg-fixme-card border border-fixme-border rounded-2xl p-4">
        <button
          type="button"
          onClick={() => { window.location.href = '/customer/my-data'; }}
          className="w-full flex items-center justify-between py-1 group"
        >
          <div className="flex items-center gap-3">
            <span className="text-lg">{'\u{1F512}'}</span>
            <div className="text-left">
              <p className="text-fixme-text-primary text-sm font-semibold">My data &amp; privacy</p>
              <p className="text-fixme-text-muted text-xs">GDPR rights, data export, account deletion</p>
            </div>
          </div>
          <span className="text-fixme-text-muted group-hover:text-fixme-text-secondary transition-colors">{'\u203A'}</span>
        </button>
      </section>

      {/* ── Sign out ─────────────────────────────────────────── */}
      <section className="bg-fixme-card border border-fixme-border rounded-2xl p-4">
        <button
          type="button"
          onClick={signOut}
          className="w-full text-center text-sm font-semibold text-fixme-error py-1 hover:opacity-80 transition-opacity"
        >
          Sign out
        </button>
      </section>

      {/* Toast */}
      {toast && (
        <div className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-5 py-2.5 rounded-full text-sm font-medium shadow-lg animate-slide-up ${
          toast.type === 'error' ? 'bg-fixme-error text-fixme-text-primary' : 'bg-fixme-accent text-fixme-bg'
        }`}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}
