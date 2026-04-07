/**
 * ProviderSettings ï¿½ /settings
 *
 * Full provider settings page accessible from profile avatar.
 * Sections:
 *   1. Profile (name, city, bio, phone, instagram)
 *   2. Work Location (salon address, home visits toggle)
 *   3. Services (list with home toggle, price, edit, add new)
 *   4. Amenities (same Airbnb grid from onboarding)
 *
 * Auth: reads JWT from localStorage('fixme_provider_token')
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import ProviderTabBar from '../../personas/provider/navigation/ProviderTabBar';
import SalonTabBar from '../../personas/salon/navigation/SalonTabBar';
import { ROUTES } from '../../app/routeCatalog';

const API_BASE = '/api/v1';

// -- Amenity config ----------------------------------------------------------
const AMENITIES = [
  { key: 'dog_friendly',          emoji: '??', label: 'Dogs welcome' },
  { key: 'wheelchair_accessible', emoji: '?', label: 'Accessible' },
  { key: 'parking',               emoji: '???', label: 'Free parking' },
  { key: 'wifi',                  emoji: '??', label: 'Free Wi-Fi' },
  { key: 'coffee',                emoji: '?', label: 'Coffee & tea' },
  { key: 'wine',                  emoji: '??', label: 'Wine & drinks' },
  { key: 'eco_friendly',          emoji: '??', label: 'Eco-friendly' },
  { key: 'home_visits',           emoji: '??', label: 'Home visits' },
  { key: 'private_studio',        emoji: '??', label: 'Private studio' },
  { key: 'child_friendly',        emoji: '??', label: 'Child-friendly' },
  { key: 'evening_hours',         emoji: '??', label: 'Evening hours' },
  { key: 'card_payment',          emoji: '??', label: 'Card payment' },
];
const CATEGORY_MAP = {
  hair: 'Hair', barber: 'Barber', nails: 'Nails', spa: 'Spa',
  massage: 'Massage', fitness: 'Fitness', makeup: 'Makeup',
  skincare: 'Skincare', lashes: 'Lashes', tattoo: 'Tattoo', other: 'Other',
};



function categoryLabel(category) {
  const key = String(category || 'other').trim().toLowerCase();
  if (CATEGORY_MAP[key]) return CATEGORY_MAP[key];
  return key.replace(/[_-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatDateTime(value) {
  if (!value) return 'Never';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return 'Never';
  return d.toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// -- Auth helpers -----------------------------------------------------------

/** Sentinel values used by the error display to show the right recovery UI. */
const ERR_NO_TOKEN = 'ERR_NO_TOKEN';
const ERR_SESSION_EXPIRED = 'ERR_SESSION_EXPIRED';
const ERR_NO_PROVIDER = 'ERR_NO_PROVIDER';
function getToken() {
  return localStorage.getItem('fixme_provider_token');
}

function clearProviderSession() {
  localStorage.removeItem('fixme_provider_token');
  localStorage.removeItem('fixme_provider_id');
  localStorage.removeItem('fixme_provider_slug');
}

async function authRequest(endpoint, options = {}) {
  const token = getToken();
  if (!token) throw new Error(ERR_NO_TOKEN);

  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      ...options.headers,
    },
    ...options,
  });

  // Token invalid or expired â†’ wipe session so next visit starts fresh.
  if (res.status === 401 || res.status === 403) {
    clearProviderSession();
    throw new Error(ERR_SESSION_EXPIRED);
  }

  // No Provider record linked to this JWT â†’ user skipped or never finished onboarding.
  if (res.status === 404 && endpoint === '/providers/me/settings') {
    throw new Error(ERR_NO_PROVIDER);
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(err.detail || `Error ${res.status}`);
  }
  if (res.status === 204 || options.method === 'DELETE') return {};
  return res.json();
}

// -- Main Component ----------------------------------------------------------
export default function BusinessSettingsPage({ persona = 'provider' }) {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);
  const [activeSection, setActiveSection] = useState('profile');
  const activePersona = persona === 'salon' ? 'salon' : 'provider';
  const loginRoute = activePersona === 'salon' ? ROUTES.salon.login : ROUTES.provider.login;
  const onboardingRoute = activePersona === 'salon' ? ROUTES.salon.onboarding : ROUTES.provider.onboarding;

  // Editable profile state
  const [profile, setProfile] = useState({});
  const [providerEmail, setProviderEmail] = useState('');
  const [editingService, setEditingService] = useState(null);
  const [showAddService, setShowAddService] = useState(false);
  const [newService, setNewService] = useState({ name: '', category: '', duration_minutes: 60, price_ex_vat: 0, home_service_available: false });
  const [scanUploading, setScanUploading] = useState(false);
  const [calendarLoading, setCalendarLoading] = useState(false);
  const [calendarConnections, setCalendarConnections] = useState([]);
  const [icsLink, setIcsLink] = useState({ connected: false, feed_url: null });
  const [calendarBusy, setCalendarBusy] = useState({
    connectGoogle: false,
    connectMicrosoft: false,
    syncConnectionId: null,
    disconnectConnectionId: null,
    rotateIcs: false,
    copyIcs: false,
  });

  // -- Bot settings state -----------------------------------------------------
  const [botSettings, setBotSettings] = useState(null);
  const [botSaving, setBotSaving] = useState(false);
  const [botForm, setBotForm] = useState({
    bot_name: '',
    tone: 'friendly',
    language: 'auto',
    custom_welcome_message: '',
    auto_confirm_bookings: true,
    out_of_hours_behavior: 'show_hours',
    max_advance_booking_days: '',
  });

  const showToast = useCallback((msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  const loadCalendarState = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setCalendarLoading(true);
    try {
      const [connections, ics] = await Promise.all([
        authRequest('/provider/calendar/connections'),
        authRequest('/provider/calendar/ics/link'),
      ]);
      setCalendarConnections(Array.isArray(connections) ? connections : []);
      setIcsLink(ics || { connected: false, feed_url: null });
    } catch (err) {
      if (!silent) showToast(err.message || 'Failed to load calendar sync', 'error');
    } finally {
      if (!silent) setCalendarLoading(false);
    }
  }, [showToast]);

  // -- Load settings -------------------------------------------
  useEffect(() => {
    authRequest('/providers/me/settings')
      .then((data) => {
        setSettings(data);
        setProviderEmail(data.email || localStorage.getItem('fixme_provider_email') || '');
        setProfile({
          name: data.name || '',
          phone: data.phone || '',
          city: data.city || '',
          bio: data.bio || '',
          instagram_username: data.instagram_username || '',
          home_service: data.home_service || false,
          location_salon: data.location_salon || '',
        });
        loadCalendarState({ silent: true });
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [loadCalendarState]);

  // -- Load bot settings when section becomes active ----------
  useEffect(() => {
    if (activeSection === 'bot' && !botSettings) {
      loadBotSettings();
    }
  }, [activeSection, botSettings, loadBotSettings]);

  // -- Save profile --------------------------------------------
  const saveProfile = async () => {
    setSaving(true);
    try {
      const data = await authRequest('/providers/me/settings', {
        method: 'PATCH',
        body: JSON.stringify(profile),
      });
      setSettings(data);
      showToast('Profile saved');
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  // -- Update service ------------------------------------------
  const updateService = async (serviceId, updates) => {
    try {
      const updated = await authRequest(`/providers/me/services/${serviceId}`, {
        method: 'PATCH',
        body: JSON.stringify(updates),
      });
      setSettings(prev => ({
        ...prev,
        services: prev.services.map(s => s.service_id === serviceId ? updated : s),
      }));
      showToast('Service updated');
      setEditingService(null);
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  // -- Toggle home service on a service ------------------------
  const toggleServiceHome = (serviceId, current) => {
    updateService(serviceId, { home_service_available: !current });
  };

  // -- Add new service -----------------------------------------
  const addService = async () => {
    if (!newService.name.trim()) return;
    try {
      const created = await authRequest('/providers/me/services', {
        method: 'POST',
        body: JSON.stringify(newService),
      });
      setSettings(prev => ({
        ...prev,
        services: [...prev.services, created],
      }));
      setNewService({ name: '', category: '', duration_minutes: 60, price_ex_vat: 0, home_service_available: false });
      setShowAddService(false);
      showToast('Service added');
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  // -- Delete (deactivate) service -----------------------------

  // -- Scan screenshot and import services ------------------------------------
  const importScannedServices = async (file) => {
    if (!file) return;
    setScanUploading(true);
    try {
      const token = getToken();
      if (!token) throw new Error('Session expired. Please log in again.');

      const body = new FormData();
      body.append('file', file);

      const scanRes = await fetch(`${API_BASE}/onboarding/scan-price-list`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body,
      });

      if (!scanRes.ok) {
        const err = await scanRes.json().catch(() => ({ detail: 'Scan failed' }));
        throw new Error(err.detail || 'Failed to scan screenshot');
      }

      const scanData = await scanRes.json();
      const scanned = Array.isArray(scanData.services) ? scanData.services : [];
      if (scanned.length === 0) {
        showToast('No services found in screenshot', 'error');
        return;
      }

      const existingNames = new Set(
        (settings.services || [])
          .filter(s => s.is_active)
          .map(s => (s.name || '').trim().toLowerCase())
      );

      const fallbackCategory = Array.isArray(settings.categories) && settings.categories.length > 0
        ? settings.categories[0]
        : null;

      const created = [];
      let skipped = 0;

      for (const svc of scanned) {
        const name = String(svc?.name || '').trim();
        if (!name) {
          skipped += 1;
          continue;
        }
        const nameKey = name.toLowerCase();
        if (existingNames.has(nameKey)) {
          skipped += 1;
          continue;
        }

        try {
          const added = await authRequest('/providers/me/services', {
            method: 'POST',
            body: JSON.stringify({
              name,
              category: fallbackCategory,
              description: svc?.description || null,
              duration_minutes: Number.isFinite(Number(svc?.duration_minutes)) ? Number(svc.duration_minutes) : 60,
              price_ex_vat: Number.isFinite(Number(svc?.price_ex_vat)) ? Number(svc.price_ex_vat) : 0,
              home_service_available: !!settings.home_service,
            }),
          });
          created.push(added);
          existingNames.add(nameKey);
        } catch {
          skipped += 1;
        }
      }

      if (created.length > 0) {
        setSettings(prev => ({
          ...prev,
          services: [...prev.services, ...created],
        }));
      }

      const createdPart = `Imported ${created.length} service${created.length === 1 ? '' : 's'}`;
      const skippedPart = skipped > 0 ? ` (${skipped} skipped)` : '';
      showToast(
        created.length > 0 ? `${createdPart}${skippedPart}` : `No new services imported${skippedPart}`,
        created.length > 0 ? 'success' : 'error'
      );
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setScanUploading(false);
    }
  };

  const deleteService = async (serviceId) => {
    try {
      await authRequest(`/providers/me/services/${serviceId}`, { method: 'DELETE' });
      setSettings(prev => ({
        ...prev,
        services: prev.services.filter(s => s.service_id !== serviceId),
      }));
      showToast('Service removed');
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  // -- Save amenities ------------------------------------------
  const toggleAmenity = async (key) => {
    const current = settings.amenities || [];
    const next = current.includes(key)
      ? current.filter(k => k !== key)
      : [...current, key];
    try {
      await authRequest('/providers/me/amenities', {
        method: 'PUT',
        body: JSON.stringify({ amenity_keys: next }),
      });
      setSettings(prev => ({ ...prev, amenities: next }));
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const connectCalendar = async (connector) => {
    if (connector !== 'google') {
      showToast('Only Google Calendar is supported right now', 'error');
      return;
    }
    setCalendarBusy((prev) => ({ ...prev, connectGoogle: true }));
    try {
      const data = await authRequest(`/provider/calendar/${connector}/connect-url`, { method: 'POST' });
      // Full-page redirect to Google OAuth — browser will return via /provider/calendar/callback
      window.location.href = data.auth_url;
    } catch (err) {
      showToast(err.message, 'error');
      setCalendarBusy((prev) => ({ ...prev, connectGoogle: false }));
    }
    // No finally block — browser navigates away, so busy state stays set during redirect
  };

  const disconnectCalendar = async (connectionId) => {
    setCalendarBusy((prev) => ({ ...prev, disconnectConnectionId: connectionId }));
    try {
      await authRequest(`/provider/calendar/connections/${connectionId}/disconnect`, { method: 'POST' });
      await loadCalendarState({ silent: true });
      showToast('Calendar disconnected');
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setCalendarBusy((prev) => ({ ...prev, disconnectConnectionId: null }));
    }
  };

  const syncCalendarNow = async (connectionId) => {
    setCalendarBusy((prev) => ({ ...prev, syncConnectionId: connectionId }));
    try {
      const result = await authRequest(`/provider/calendar/connections/${connectionId}/sync-now`, {
        method: 'POST',
      });
      await loadCalendarState({ silent: true });
      showToast(result?.message || 'Calendar sync started');
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setCalendarBusy((prev) => ({ ...prev, syncConnectionId: null }));
    }
  };

  const rotateIcsToken = async () => {
    setCalendarBusy((prev) => ({ ...prev, rotateIcs: true }));
    try {
      const link = await authRequest('/provider/calendar/ics/rotate-token', { method: 'POST' });
      setIcsLink(link || { connected: false, feed_url: null });
      showToast('New calendar link created');
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setCalendarBusy((prev) => ({ ...prev, rotateIcs: false }));
    }
  };

  const copyIcsLink = async () => {
    if (!icsLink?.feed_url) return;
    setCalendarBusy((prev) => ({ ...prev, copyIcs: true }));
    try {
      await navigator.clipboard.writeText(icsLink.feed_url);
      showToast('Calendar link copied');
    } catch {
      showToast('Could not copy link, please copy manually', 'error');
    } finally {
      setCalendarBusy((prev) => ({ ...prev, copyIcs: false }));
    }
  };

  // -- Bot settings -------------------------------------------
  const loadBotSettings = useCallback(async () => {
    const providerId = localStorage.getItem('fixme_provider_id');
    if (!providerId) return;
    try {
      const res = await fetch(`${API_BASE}/bot-settings?provider_id=${providerId}`);
      if (!res.ok) return;
      const data = await res.json();
      setBotSettings(data);
      setBotForm({
        bot_name: data.bot_name || '',
        tone: data.tone || 'friendly',
        language: data.language || 'auto',
        custom_welcome_message: data.custom_welcome_message || '',
        auto_confirm_bookings: data.auto_confirm_bookings !== false,
        out_of_hours_behavior: data.out_of_hours_behavior || 'show_hours',
        max_advance_booking_days: data.max_advance_booking_days != null ? String(data.max_advance_booking_days) : '',
      });
    } catch { /* silent */ }
  }, []);

  const saveBotSettings = async () => {
    const providerId = localStorage.getItem('fixme_provider_id');
    if (!providerId) return;
    setBotSaving(true);
    try {
      const payload = {
        bot_name: botForm.bot_name.trim() || null,
        tone: botForm.tone,
        language: botForm.language,
        custom_welcome_message: botForm.custom_welcome_message.trim() || null,
        auto_confirm_bookings: botForm.auto_confirm_bookings,
        out_of_hours_behavior: botForm.out_of_hours_behavior,
        max_advance_booking_days: botForm.max_advance_booking_days ? parseInt(botForm.max_advance_booking_days, 10) : null,
      };
      const res = await fetch(`${API_BASE}/bot-settings?provider_id=${providerId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        const msg = data?.detail?.message || data?.detail || 'Save failed';
        if (data?.detail?.error === 'pro_required') {
          showToast('AI Bot settings require a Pro subscription', 'error');
        } else {
          showToast(msg, 'error');
        }
        return;
      }
      setBotSettings(data);
      showToast('Bot settings saved');
    } catch (err) {
      showToast(err.message || 'Failed to save', 'error');
    } finally {
      setBotSaving(false);
    }
  };

  // -- Loading / Error -----------------------------------------
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-10 h-10 border-2 border-fixme-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    // â”€â”€ No provider profile yet (onboarding was never completed) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if (error === ERR_NO_PROVIDER) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen px-6 text-center gap-4">
          <div className="text-4xl">📋</div>
          <h1 className="text-xl font-bold text-fixme-text-primary">Profile not set up yet</h1>
          <p className="text-fixme-text-secondary text-sm max-w-xs leading-relaxed">
            Complete your onboarding to access your settings dashboard.
          </p>
          <button
            onClick={() => window.location.href = onboardingRoute}
            className="mt-4 px-6 py-3 bg-fixme-accent text-fixme-bg rounded-xl font-semibold"
          >
            Complete setup
          </button>
        </div>
      );
    }

    // â”€â”€ Token missing or expired (ERR_NO_TOKEN / ERR_SESSION_EXPIRED) â”€â”€â”€â”€â”€
    return (
      <div className="flex flex-col items-center justify-center min-h-screen px-6 text-center gap-4">
        <div className="text-4xl">🔐</div>
        <h1 className="text-xl font-bold text-fixme-text-primary">Sign in required</h1>
        <p className="text-fixme-text-secondary text-sm max-w-xs leading-relaxed">
          {error === ERR_SESSION_EXPIRED
            ? 'Your session has expired. Sign in again to continue.'
            : 'Sign in to access your settings.'}
        </p>
        <button
          onClick={() => window.location.href = loginRoute}
          className="mt-4 px-6 py-3 bg-fixme-accent text-fixme-bg rounded-xl font-semibold"
        >
          {activePersona === 'salon' ? 'Go to salon login' : 'Go to provider login'}
        </button>
      </div>
    );
  }

  const SECTIONS = [
    { id: 'profile', label: 'Profile', icon: '\u{1F464}' },
    { id: 'services', label: 'Services', icon: '\u{2728}' },
    { id: 'amenities', label: 'Amenities', icon: '\u{1F4CB}' },
    { id: 'calendar', label: 'Calendar', icon: 'Cal' },
    { id: 'bot', label: 'AI Bot', icon: '\u{1F916}' },
  ];

  const googleConnection = calendarConnections.find((c) => c.connector === 'google');
  const microsoftConnection = calendarConnections.find((c) => c.connector === 'microsoft');

  return (
    <div className="animate-fade-in pb-24">
      {/* -- Header ----------------------------------------------- */}
      <div className="sticky top-0 z-10 bg-fixme-bg/95 backdrop-blur-sm border-b border-fixme-border/50 px-4 py-3">
        <div className="flex items-center justify-between">
          <button
            onClick={() => window.history.back()}
            className="text-fixme-text-secondary hover:text-fixme-text-primary transition-colors text-lg"
          >
            ?
          </button>
          <span className="text-fixme-text-primary font-bold text-lg">Settings</span>
          <div className="w-8" />
        </div>
      </div>

      {/* -- Section tabs ----------------------------------------- */}
      <div className="flex gap-2 px-4 mt-4 overflow-x-auto scrollbar-hide">
        {SECTIONS.map((s) => (
          <button
            key={s.id}
            onClick={() => setActiveSection(s.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 rounded-full text-sm font-medium whitespace-nowrap transition-all ${
              activeSection === s.id
                ? 'bg-fixme-accent text-fixme-bg'
                : 'bg-fixme-card border border-fixme-border text-fixme-text-secondary hover:text-fixme-text-primary'
            }`}
          >
            <span className="text-xs">{s.icon}</span>
            {s.label}
          </button>
        ))}
      </div>

      {/* -- Content ---------------------------------------------- */}
      <div className="px-4 mt-5">
        {activeSection === 'profile' && (
          <ProfileSection
            profile={profile}
            setProfile={setProfile}
            email={providerEmail}
            saving={saving}
            onSave={saveProfile}
            categories={settings.categories || []}
          />
        )}

        {activeSection === 'services' && (
          <ServicesSection
            services={settings.services}
            homeService={settings.home_service}
            editingService={editingService}
            setEditingService={setEditingService}
            onToggleHome={toggleServiceHome}
            onUpdate={updateService}
            onDelete={deleteService}
            showAdd={showAddService}
            setShowAdd={setShowAddService}
            newService={newService}
            setNewService={setNewService}
            onAdd={addService}
            onScanUpload={importScannedServices}
            scanUploading={scanUploading}
          />
        )}

        {activeSection === 'amenities' && (
          <AmenitiesSection
            selected={settings.amenities || []}
            onToggle={toggleAmenity}
          />
        )}

        {activeSection === 'calendar' && (
          <CalendarSection
            loading={calendarLoading}
            googleConnection={googleConnection}
            microsoftConnection={microsoftConnection}
            icsLink={icsLink}
            calendarBusy={calendarBusy}
            onReload={() => loadCalendarState()}
            onConnectGoogle={() => connectCalendar('google')}
            onConnectMicrosoft={() => connectCalendar('microsoft')}
            onDisconnect={disconnectCalendar}
            onSyncNow={syncCalendarNow}
            onRotateIcs={rotateIcsToken}
            onCopyIcs={copyIcsLink}
          />
        )}

        {activeSection === 'bot' && (
          <BotSettingsSection
            botSettings={botSettings}
            botForm={botForm}
            setBotForm={setBotForm}
            saving={botSaving}
            onSave={saveBotSettings}
            onReload={loadBotSettings}
          />
        )}
      </div>

      {/* -- Toast ------------------------------------------------ */}
      {toast && (
        <div className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-5 py-2.5 rounded-full text-sm font-medium shadow-lg animate-slide-up ${
          toast.type === 'error'
            ? 'bg-fixme-error text-fixme-text-primary'
            : 'bg-fixme-accent text-fixme-bg'
        }`}>
          {toast.msg}
        </div>
      )}
      {activePersona === 'salon' ? <SalonTabBar active="settings" /> : <ProviderTabBar active="settings" />}
    </div>
  );
}


// ---------------------------------------------------------------------------
// -- Profile Section -------------------------------------------------------
// ---------------------------------------------------------------------------

function ProfileSection({ profile, setProfile, email, saving, onSave, categories }) {
  const update = (field, value) => setProfile(prev => ({ ...prev, [field]: value }));

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold text-fixme-text-primary">Business profile</h2>


      {/* Service categories from onboarding */}
      <div className="bg-fixme-card border border-fixme-border rounded-xl p-3">
        <p className="text-fixme-text-secondary text-xs font-medium uppercase tracking-wide mb-2">What you offer</p>
        {categories.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {categories.map((cat) => (
              <span
                key={cat}
                className="px-2.5 py-1 rounded-full bg-fixme-accent/10 text-fixme-accent text-xs font-semibold border border-fixme-accent/30"
              >
                {CATEGORY_MAP[cat] || cat}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-fixme-text-muted text-xs">No service categories selected yet.</p>
        )}
      </div>

      {/* Account email (read-only, source of truth for login) */}
      <div>
        <label className="text-fixme-text-secondary text-xs font-medium uppercase tracking-wide mb-1.5 block">Account email</label>
        <input
          type="text"
          value={email || ''}
          readOnly
          className="w-full bg-fixme-card border border-fixme-border rounded-xl px-4 py-3 text-fixme-text-secondary text-sm"
        />
      </div>
      {/* Name */}
      <Field label="Name" value={profile.name} onChange={(v) => update('name', v)} placeholder="Your business name" />

      {/* City */}
      <Field label="City" value={profile.city} onChange={(v) => update('city', v)} placeholder="Miami" />

      {/* Phone */}
      <Field label="Phone" value={profile.phone} onChange={(v) => update('phone', v)} placeholder="+1 305 555 1234" />

      {/* Instagram */}
      <div>
        <label className="text-fixme-text-secondary text-xs font-medium uppercase tracking-wide mb-1.5 block">Instagram</label>
        <div className="flex items-center bg-fixme-card border border-fixme-border rounded-xl overflow-hidden focus-within:border-fixme-accent">
          <span className="text-fixme-text-muted pl-4 pr-1">@</span>
          <input
            type="text"
            value={profile.instagram_username}
            onChange={(e) => update('instagram_username', e.target.value.replace('@', ''))}
            placeholder="yoursalon"
            className="flex-1 bg-transparent px-2 py-3 text-fixme-text-primary placeholder-fixme-text-muted text-sm focus:outline-none"
          />
        </div>
      </div>

      {/* Bio */}
      <div>
        <label className="text-fixme-text-secondary text-xs font-medium uppercase tracking-wide mb-1.5 block">Bio</label>
        <textarea
          rows={3}
          value={profile.bio}
          onChange={(e) => update('bio', e.target.value)}
          placeholder="Tell customers about yourself and your work..."
          className="w-full bg-fixme-card border border-fixme-border rounded-xl px-4 py-3 text-fixme-text-primary placeholder-fixme-text-muted text-sm focus:outline-none focus:border-fixme-accent resize-none"
        />
      </div>

      {/* -- Work Location -------------------------------------- */}
      <div className="pt-2">
        <h3 className="text-sm font-semibold text-fixme-text-primary mb-3">Where do you work?</h3>

        {/* Salon address */}
        <Field
          label="Salon / studio address"
          value={profile.location_salon}
          onChange={(v) => update('location_salon', v)}
          placeholder="123 Main St, Miami"
        />

        {/* Home visits toggle */}
        <div className="mt-3">
          <button
            onClick={() => update('home_service', !profile.home_service)}
            className={`w-full flex items-center gap-3 p-3.5 rounded-xl border-2 transition-all ${
              profile.home_service
                ? 'border-fixme-accent bg-fixme-accent/10'
                : 'border-fixme-border bg-fixme-card'
            }`}
          >
            <span className="text-xl">??</span>
            <div className="flex-1 text-left">
              <div className={`text-sm font-semibold ${profile.home_service ? 'text-fixme-accent' : 'text-fixme-text-secondary'}`}>
                I offer home visits
              </div>
              <div className="text-xs text-fixme-text-muted">Customers can book you to come to them</div>
            </div>
            <Toggle on={profile.home_service} />
          </button>
        </div>
      </div>

      {/* Save button */}
      <button
        onClick={onSave}
        disabled={saving}
        className="w-full mt-4 py-3.5 rounded-xl font-semibold text-base bg-fixme-accent text-fixme-bg hover:bg-fixme-accent-light active:scale-[0.98] transition-all disabled:opacity-50"
      >
        {saving ? 'Saving...' : 'Save changes'}
      </button>
    </div>
  );
}


// ---------------------------------------------------------------------------
// -- Services Section -----------------------------------------------------
// ---------------------------------------------------------------------------

function ServicesSection({
  services, homeService, editingService, setEditingService,
  onToggleHome, onUpdate, onDelete,
  showAdd, setShowAdd, newService, setNewService, onAdd,
  onScanUpload, scanUploading,
}) {
  const activeServices = (services || []).filter((s) => s.is_active);

  const grouped = {};
  activeServices.forEach((s) => {
    const cat = (s.category || 'other').toString().trim().toLowerCase();
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(s);
  });

  const categoryKeys = Object.keys(grouped).sort((a, b) => categoryLabel(a).localeCompare(categoryLabel(b)));
  const [serviceFilter, setServiceFilter] = useState('all');

  useEffect(() => {
    if (serviceFilter !== 'all' && !categoryKeys.includes(serviceFilter)) {
      setServiceFilter('all');
    }
  }, [serviceFilter, categoryKeys.join('|')]);

  const visibleCategoryKeys = serviceFilter === 'all'
    ? categoryKeys
    : categoryKeys.filter((cat) => cat === serviceFilter);

  const visibleServiceCount = visibleCategoryKeys.reduce((sum, cat) => sum + grouped[cat].length, 0);

  const fileInputRef = useRef(null);

  const openScanPicker = () => {
    if (scanUploading) return;
    fileInputRef.current?.click();
  };

  const onScanFileChange = (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file || !onScanUpload) return;
    onScanUpload(file);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-bold text-fixme-text-primary">Services</h2>
        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,.heic,.heif,.png,.jpg,.jpeg,.webp"
            onChange={onScanFileChange}
            className="hidden"
          />
          <button
            onClick={openScanPicker}
            disabled={scanUploading}
            className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-fixme-card border border-fixme-border text-fixme-text-secondary text-xs font-semibold hover:text-fixme-text-primary hover:border-fixme-accent/40 transition-colors disabled:opacity-50"
          >
            {scanUploading ? 'Scanning...' : 'Upload screenshot'}
          </button>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-fixme-accent/10 text-fixme-accent text-xs font-semibold hover:bg-fixme-accent/20 transition-colors"
          >
            <span className="text-sm">+</span> Add service
          </button>
        </div>
      </div>

      {homeService && (
        <p className="text-xs text-fixme-text-muted bg-fixme-card border border-fixme-border rounded-xl px-3 py-2">
          ?? You offer home visits. Toggle the house icon on each service to make it available for home bookings.
        </p>
      )}

      {categoryKeys.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-fixme-text-muted uppercase tracking-wide">Filter by service type</p>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setServiceFilter('all')}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${
                serviceFilter === 'all'
                  ? 'bg-fixme-accent text-fixme-bg border-fixme-accent'
                  : 'bg-fixme-card text-fixme-text-secondary border-fixme-border hover:text-fixme-text-primary'
              }`}
            >
              All ({activeServices.length})
            </button>
            {categoryKeys.map((cat) => {
              const count = grouped[cat]?.length || 0;
              return (
                <button
                  key={cat}
                  onClick={() => setServiceFilter(cat)}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${
                    serviceFilter === cat
                      ? 'bg-fixme-accent text-fixme-bg border-fixme-accent'
                      : 'bg-fixme-card text-fixme-text-secondary border-fixme-border hover:text-fixme-text-primary'
                  }`}
                >
                  {categoryLabel(cat)} ({count})
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Add service form */}
      {showAdd && (
        <div className="bg-fixme-card border border-fixme-accent/30 rounded-xl p-4 space-y-3 animate-fade-in">
          <p className="text-sm font-semibold text-fixme-accent">New service</p>
          <input
            type="text"
            placeholder="Service name"
            value={newService.name}
            onChange={(e) => setNewService(p => ({ ...p, name: e.target.value }))}
            className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2.5 text-sm text-fixme-text-primary placeholder-fixme-text-muted focus:outline-none focus:border-fixme-accent"
          />
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-fixme-text-muted text-xs mb-1 block">Duration (min)</label>
              <input
                type="number"
                value={newService.duration_minutes}
                onChange={(e) => setNewService(p => ({ ...p, duration_minutes: parseInt(e.target.value) || 0 }))}
                className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2.5 text-sm text-fixme-text-primary focus:outline-none focus:border-fixme-accent"
              />
            </div>
            <div>
              <label className="text-fixme-text-muted text-xs mb-1 block">Price (kr ex VAT)</label>
              <input
                type="number"
                value={newService.price_ex_vat}
                onChange={(e) => setNewService(p => ({ ...p, price_ex_vat: parseFloat(e.target.value) || 0 }))}
                className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2.5 text-sm text-fixme-text-primary focus:outline-none focus:border-fixme-accent"
              />
            </div>
          </div>
          <select
            value={newService.category}
            onChange={(e) => setNewService(p => ({ ...p, category: e.target.value }))}
            className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2.5 text-sm text-fixme-text-primary focus:outline-none focus:border-fixme-accent"
          >
            <option value="">Category (optional)</option>
            {Object.entries(CATEGORY_MAP).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          {homeService && (
            <button
              onClick={() => setNewService(p => ({ ...p, home_service_available: !p.home_service_available }))}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition-all ${
                newService.home_service_available
                  ? 'bg-fixme-accent/10 text-fixme-accent'
                  : 'bg-fixme-border/30 text-fixme-text-muted'
              }`}
            >
              ?? Available for home visits
              <Toggle on={newService.home_service_available} small />
            </button>
          )}
          <div className="flex gap-2">
            <button
              onClick={onAdd}
              disabled={!newService.name.trim()}
              className="flex-1 py-2.5 rounded-xl font-semibold text-sm bg-fixme-accent text-fixme-bg disabled:opacity-40"
            >
              Add
            </button>
            <button
              onClick={() => setShowAdd(false)}
              className="px-4 py-2.5 rounded-xl text-sm text-fixme-text-secondary border border-fixme-border"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Service list by category */}
      {visibleCategoryKeys.map((cat) => {
        const catServices = grouped[cat] || [];
        return (
          <div key={cat}>
            <p className="text-xs font-semibold text-fixme-text-muted uppercase tracking-wide mb-2">
              {categoryLabel(cat)}
            </p>
            <div className="space-y-2">
              {catServices.map((svc) => (
                <ServiceCard
                  key={svc.service_id}
                  service={svc}
                  homeService={homeService}
                  isEditing={editingService === svc.service_id}
                  onEdit={() => setEditingService(editingService === svc.service_id ? null : svc.service_id)}
                  onToggleHome={() => onToggleHome(svc.service_id, svc.home_service_available)}
                  onUpdate={(updates) => onUpdate(svc.service_id, updates)}
                  onDelete={() => onDelete(svc.service_id)}
                />
              ))}
            </div>
          </div>
        );
      })}

      {activeServices.length === 0 && !showAdd && (
        <div className="text-center py-10">
          <p className="text-fixme-text-muted text-sm">No services yet</p>
          <button
            onClick={() => setShowAdd(true)}
            className="mt-3 px-4 py-2 bg-fixme-accent text-fixme-bg rounded-xl text-sm font-semibold"
          >
            Add your first service
          </button>
        </div>
      )}

      {activeServices.length > 0 && visibleServiceCount === 0 && !showAdd && (
        <div className="text-center py-10">
          <p className="text-fixme-text-muted text-sm">No services in this category.</p>
          <button
            onClick={() => setServiceFilter('all')}
            className="mt-3 px-4 py-2 bg-fixme-card border border-fixme-border text-fixme-text-secondary rounded-xl text-sm font-semibold"
          >
            Show all services
          </button>
        </div>
      )}
    </div>
  );
}

function ServiceCard({ service, homeService, isEditing, onEdit, onToggleHome, onUpdate, onDelete }) {
  const [name, setName] = useState(service.name);
  const [price, setPrice] = useState(service.price_ex_vat);
  const [duration, setDuration] = useState(service.duration_minutes);

  return (
    <div className={`bg-fixme-card border rounded-xl transition-all ${isEditing ? 'border-fixme-accent' : 'border-fixme-border'}`}>
      <div className="flex items-center gap-3 p-3.5">
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-fixme-text-primary truncate">{service.name}</div>
          <div className="text-xs text-fixme-text-muted mt-0.5">{service.duration_minutes} min</div>
        </div>
        <span className="text-fixme-accent font-semibold text-sm">{Math.round(service.price_ex_vat)} kr</span>

        {/* Home toggle */}
        {homeService && (
          <button
            onClick={onToggleHome}
            title={service.home_service_available ? 'Available for home visits' : 'Salon only'}
            className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm transition-all ${
              service.home_service_available
                ? 'bg-fixme-accent/15 text-fixme-accent'
                : 'bg-fixme-border/30 text-fixme-text-muted opacity-40'
            }`}
          >
            ??
          </button>
        )}

        {/* Edit button */}
        <button
          onClick={onEdit}
          className="w-8 h-8 rounded-lg flex items-center justify-center text-fixme-text-muted hover:text-fixme-text-primary hover:bg-fixme-border/50 transition-all"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
          </svg>
        </button>
      </div>

      {/* Expanded edit form */}
      {isEditing && (
        <div className="border-t border-fixme-border px-3.5 py-3 space-y-2.5 animate-fade-in">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full bg-fixme-bg border border-fixme-border rounded-lg px-3 py-2 text-sm text-fixme-text-primary focus:outline-none focus:border-fixme-accent"
          />
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-fixme-text-muted text-xs mb-1 block">Duration</label>
              <input
                type="number"
                value={duration}
                onChange={(e) => setDuration(parseInt(e.target.value) || 0)}
                className="w-full bg-fixme-bg border border-fixme-border rounded-lg px-3 py-2 text-sm text-fixme-text-primary focus:outline-none focus:border-fixme-accent"
              />
            </div>
            <div>
              <label className="text-fixme-text-muted text-xs mb-1 block">Price (ex VAT)</label>
              <input
                type="number"
                value={price}
                onChange={(e) => setPrice(parseFloat(e.target.value) || 0)}
                className="w-full bg-fixme-bg border border-fixme-border rounded-lg px-3 py-2 text-sm text-fixme-text-primary focus:outline-none focus:border-fixme-accent"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => onUpdate({ name, price_ex_vat: price, duration_minutes: duration })}
              className="flex-1 py-2 rounded-lg text-sm font-semibold bg-fixme-accent text-fixme-bg"
            >
              Save
            </button>
            <button
              onClick={onDelete}
              className="px-3 py-2 rounded-lg text-sm text-fixme-error border border-fixme-error/30 hover:bg-fixme-error/10 transition-colors"
            >
              Remove
            </button>
          </div>
        </div>
      )}
    </div>
  );
}


function CalendarSection({
  loading,
  googleConnection,
  microsoftConnection,
  icsLink,
  calendarBusy,
  onReload,
  onConnectGoogle,
  onConnectMicrosoft,
  onDisconnect,
  onSyncNow,
  onRotateIcs,
  onCopyIcs,
}) {
  const hasIcsLink = !!icsLink?.feed_url;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-bold text-fixme-text-primary">Calendar sync</h2>
        <button
          onClick={onReload}
          className="px-3 py-1.5 rounded-lg border border-fixme-border text-xs text-fixme-text-secondary hover:text-fixme-text-primary"
        >
          Refresh
        </button>
      </div>

      <div className="bg-fixme-card border border-fixme-border rounded-xl p-4 space-y-2">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-fixme-text-primary">Google Calendar</p>
            <p className="text-xs text-fixme-text-muted">
              {googleConnection ? `Connected: ${googleConnection.display_name || googleConnection.external_calendar_id}` : 'Not connected'}
            </p>
            {googleConnection?.last_synced_at && (
              <p className="text-xs text-fixme-text-muted">Last sync: {formatDateTime(googleConnection.last_synced_at)}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {googleConnection ? (
              <>
                <button
                  onClick={() => onSyncNow(googleConnection.connection_id)}
                  disabled={calendarBusy.syncConnectionId === googleConnection.connection_id}
                  className="px-3 py-1.5 rounded-lg bg-fixme-accent text-fixme-bg text-xs font-semibold disabled:opacity-60"
                >
                  {calendarBusy.syncConnectionId === googleConnection.connection_id ? 'Syncing...' : 'Sync now'}
                </button>
                <button
                  onClick={() => onDisconnect(googleConnection.connection_id)}
                  disabled={calendarBusy.disconnectConnectionId === googleConnection.connection_id}
                  className="px-3 py-1.5 rounded-lg border border-fixme-border text-xs text-fixme-text-secondary disabled:opacity-60"
                >
                  Disconnect
                </button>
              </>
            ) : (
              <button
                onClick={onConnectGoogle}
                disabled={calendarBusy.connectGoogle}
                className="px-3 py-1.5 rounded-lg bg-fixme-accent text-fixme-bg text-xs font-semibold disabled:opacity-60"
              >
                {calendarBusy.connectGoogle ? 'Connecting...' : 'Connect'}
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="bg-fixme-card border border-fixme-border rounded-xl p-4 space-y-2">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-fixme-text-primary">Microsoft Calendar</p>
            <p className="text-xs text-fixme-text-muted">
              {microsoftConnection ? `Connected: ${microsoftConnection.display_name || microsoftConnection.external_calendar_id}` : 'Not connected'}
            </p>
            {microsoftConnection?.last_synced_at && (
              <p className="text-xs text-fixme-text-muted">Last sync: {formatDateTime(microsoftConnection.last_synced_at)}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {microsoftConnection ? (
              <>
                <button
                  onClick={() => onSyncNow(microsoftConnection.connection_id)}
                  disabled={calendarBusy.syncConnectionId === microsoftConnection.connection_id}
                  className="px-3 py-1.5 rounded-lg bg-fixme-accent text-fixme-bg text-xs font-semibold disabled:opacity-60"
                >
                  {calendarBusy.syncConnectionId === microsoftConnection.connection_id ? 'Syncing...' : 'Sync now'}
                </button>
                <button
                  onClick={() => onDisconnect(microsoftConnection.connection_id)}
                  disabled={calendarBusy.disconnectConnectionId === microsoftConnection.connection_id}
                  className="px-3 py-1.5 rounded-lg border border-fixme-border text-xs text-fixme-text-secondary disabled:opacity-60"
                >
                  Disconnect
                </button>
              </>
            ) : (
              <button
                onClick={onConnectMicrosoft}
                disabled={calendarBusy.connectMicrosoft}
                className="px-3 py-1.5 rounded-lg bg-fixme-card border border-fixme-border text-xs text-fixme-text-secondary disabled:opacity-60"
              >
                {calendarBusy.connectMicrosoft ? 'Connecting...' : 'Connect'}
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="bg-fixme-card border border-fixme-border rounded-xl p-4 space-y-3">
        <div>
          <p className="text-sm font-semibold text-fixme-text-primary">iCal feed</p>
          <p className="text-xs text-fixme-text-muted">Use this in Apple Calendar, Outlook, or any app that supports ICS subscriptions.</p>
        </div>
        {hasIcsLink ? (
          <div className="space-y-2">
            <input
              readOnly
              value={icsLink.feed_url}
              className="w-full bg-fixme-bg border border-fixme-border rounded-lg px-3 py-2 text-xs text-fixme-text-secondary"
            />
            <div className="flex gap-2">
              <button
                onClick={onCopyIcs}
                disabled={calendarBusy.copyIcs}
                className="flex-1 py-2 rounded-lg bg-fixme-accent text-fixme-bg text-xs font-semibold disabled:opacity-60"
              >
                {calendarBusy.copyIcs ? 'Copying...' : 'Copy link'}
              </button>
              <button
                onClick={onRotateIcs}
                disabled={calendarBusy.rotateIcs}
                className="flex-1 py-2 rounded-lg border border-fixme-border text-xs text-fixme-text-secondary disabled:opacity-60"
              >
                {calendarBusy.rotateIcs ? 'Rotating...' : 'Rotate link'}
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={onRotateIcs}
            disabled={calendarBusy.rotateIcs || loading}
            className="px-3 py-2 rounded-lg bg-fixme-accent text-fixme-bg text-xs font-semibold disabled:opacity-60"
          >
            {calendarBusy.rotateIcs ? 'Creating...' : 'Create iCal link'}
          </button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// -- Amenities Section ----------------------------------------------------
// ---------------------------------------------------------------------------

function AmenitiesSection({ selected, onToggle }) {
  return (
    <div>
      <h2 className="text-lg font-bold text-fixme-text-primary mb-1">What do you offer?</h2>
      <p className="text-fixme-text-muted text-xs mb-4">Tap to toggle. Changes save automatically.</p>

      <div className="grid grid-cols-3 gap-2.5">
        {AMENITIES.map((a) => {
          const isSelected = selected.includes(a.key);
          return (
            <button
              key={a.key}
              onClick={() => onToggle(a.key)}
              className={`relative flex flex-col items-center gap-2 px-2 py-4 rounded-2xl border-2 transition-all duration-150 active:scale-95 ${
                isSelected
                  ? 'border-fixme-accent bg-fixme-accent/10'
                  : 'border-fixme-border bg-fixme-card hover:border-fixme-accent/40'
              }`}
            >
              {isSelected && (
                <span className="absolute top-2 right-2 w-4 h-4 bg-fixme-accent rounded-full flex items-center justify-center">
                  <svg viewBox="0 0 10 8" className="w-2.5 h-2.5 fill-none stroke-fixme-bg stroke-2 stroke-linecap-round stroke-linejoin-round">
                    <polyline points="1,4 3.5,6.5 9,1" />
                  </svg>
                </span>
              )}
              <span className="text-2xl leading-none">{a.emoji}</span>
              <span className={`text-xs font-semibold text-center leading-tight ${isSelected ? 'text-fixme-accent' : 'text-fixme-text-secondary'}`}>
                {a.label}
              </span>
            </button>
          );
        })}
      </div>

      {selected.length > 0 && (
        <div className="mt-4 bg-fixme-card border border-fixme-border rounded-xl px-4 py-3 flex items-center gap-2">
          <span className="text-fixme-accent text-sm">?</span>
          <span className="text-fixme-text-secondary text-sm">
            <span className="text-fixme-text-primary font-semibold">{selected.length}</span>
            {' '}amenit{selected.length === 1 ? 'y' : 'ies'} selected
          </span>
        </div>
      )}
    </div>
  );
}


// ---------------------------------------------------------------------------
// -- Bot Settings Section -------------------------------------------------
// ---------------------------------------------------------------------------

function BotSettingsSection({ botSettings, botForm, setBotForm, saving, onSave, onReload }) {
  const isPro = botSettings?.is_pro === true;
  const update = (field, value) => setBotForm((prev) => ({ ...prev, [field]: value }));

  if (!botSettings) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="w-8 h-8 border-2 border-fixme-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-bold text-fixme-text-primary">AI Booking Bot</h2>
          <p className="text-xs text-fixme-text-muted mt-0.5">Customise how your bot talks to clients in DMs</p>
        </div>
        {isPro ? (
          <span className="px-2.5 py-1 rounded-full bg-fixme-accent/15 text-fixme-accent text-[11px] font-bold uppercase tracking-wide">Pro</span>
        ) : (
          <span className="px-2.5 py-1 rounded-full bg-fixme-border text-fixme-text-muted text-[11px] font-bold uppercase tracking-wide">Free</span>
        )}
      </div>

      {!isPro && (
        <div className="bg-fixme-card border border-fixme-border rounded-xl p-4 flex items-start gap-3">
          <span className="text-xl mt-0.5">{'\uD83D\uDD12'}</span>
          <div>
            <p className="text-sm font-semibold text-fixme-text-primary">Pro feature</p>
            <p className="text-xs text-fixme-text-muted leading-relaxed mt-0.5">
              Customising bot name, tone, and behaviour requires a Pro subscription.
              You can still see the defaults below.
            </p>
          </div>
        </div>
      )}

      {/* Bot name */}
      <div>
        <label className="text-fixme-text-secondary text-xs font-medium uppercase tracking-wide mb-1.5 block">
          Bot name
        </label>
        <input
          type="text"
          value={botForm.bot_name}
          onChange={(e) => update('bot_name', e.target.value)}
          placeholder="Leave blank to use your business name"
          disabled={!isPro}
          className="w-full bg-fixme-card border border-fixme-border rounded-xl px-4 py-3 text-fixme-text-primary placeholder-fixme-text-muted text-sm focus:outline-none focus:border-fixme-accent transition-colors disabled:opacity-50"
        />
      </div>

      {/* Tone */}
      <div>
        <label className="text-fixme-text-secondary text-xs font-medium uppercase tracking-wide mb-2 block">Tone</label>
        <div className="grid grid-cols-3 gap-2">
          {[
            { value: 'friendly', label: 'Friendly', desc: 'Warm & casual' },
            { value: 'professional', label: 'Professional', desc: 'Polished & formal' },
            { value: 'casual', label: 'Casual', desc: 'Relaxed & chatty' },
          ].map((opt) => (
            <button
              key={opt.value}
              onClick={() => isPro && update('tone', opt.value)}
              className={`flex flex-col items-center gap-1 p-3 rounded-xl border-2 transition-all text-center ${
                botForm.tone === opt.value
                  ? 'border-fixme-accent bg-fixme-accent/10'
                  : 'border-fixme-border bg-fixme-card'
              } ${!isPro ? 'opacity-50 cursor-default' : 'cursor-pointer'}`}
            >
              <span className={`text-xs font-semibold ${botForm.tone === opt.value ? 'text-fixme-accent' : 'text-fixme-text-secondary'}`}>{opt.label}</span>
              <span className="text-[10px] text-fixme-text-muted leading-tight">{opt.desc}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Language */}
      <div>
        <label className="text-fixme-text-secondary text-xs font-medium uppercase tracking-wide mb-2 block">Language</label>
        <div className="grid grid-cols-3 gap-2">
          {[
            { value: 'auto', label: 'Auto-detect', desc: 'Matches the client' },
            { value: 'sv', label: 'Swedish', desc: 'Always svenska' },
            { value: 'en', label: 'English', desc: 'Always English' },
          ].map((opt) => (
            <button
              key={opt.value}
              onClick={() => isPro && update('language', opt.value)}
              className={`flex flex-col items-center gap-1 p-3 rounded-xl border-2 transition-all text-center ${
                botForm.language === opt.value
                  ? 'border-fixme-accent bg-fixme-accent/10'
                  : 'border-fixme-border bg-fixme-card'
              } ${!isPro ? 'opacity-50 cursor-default' : 'cursor-pointer'}`}
            >
              <span className={`text-xs font-semibold ${botForm.language === opt.value ? 'text-fixme-accent' : 'text-fixme-text-secondary'}`}>{opt.label}</span>
              <span className="text-[10px] text-fixme-text-muted leading-tight">{opt.desc}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Auto-confirm */}
      <button
        onClick={() => isPro && update('auto_confirm_bookings', !botForm.auto_confirm_bookings)}
        className={`w-full flex items-center gap-3 p-3.5 rounded-xl border-2 transition-all ${
          botForm.auto_confirm_bookings && isPro
            ? 'border-fixme-accent bg-fixme-accent/10'
            : 'border-fixme-border bg-fixme-card'
        } ${!isPro ? 'opacity-50 cursor-default' : ''}`}
      >
        <span className="text-xl">{'\uD83D\uDCC5'}</span>
        <div className="flex-1 text-left">
          <div className={`text-sm font-semibold ${botForm.auto_confirm_bookings && isPro ? 'text-fixme-accent' : 'text-fixme-text-secondary'}`}>
            Auto-confirm bookings
          </div>
          <div className="text-xs text-fixme-text-muted">Bot books without waiting for your approval</div>
        </div>
        <Toggle on={botForm.auto_confirm_bookings && isPro} />
      </button>

      {/* Out-of-hours behaviour */}
      <div>
        <label className="text-fixme-text-secondary text-xs font-medium uppercase tracking-wide mb-2 block">
          Out-of-hours behaviour
        </label>
        <div className="space-y-2">
          {[
            { value: 'show_hours', label: 'Show working hours', desc: 'Bot tells clients when you are next available' },
            { value: 'send_link', label: 'Send booking link', desc: 'Bot shares your direct booking link' },
            { value: 'silent', label: 'Stay silent', desc: 'Bot does not respond outside hours' },
          ].map((opt) => (
            <button
              key={opt.value}
              onClick={() => isPro && update('out_of_hours_behavior', opt.value)}
              className={`w-full flex items-center gap-3 p-3 rounded-xl border-2 transition-all text-left ${
                botForm.out_of_hours_behavior === opt.value
                  ? 'border-fixme-accent bg-fixme-accent/10'
                  : 'border-fixme-border bg-fixme-card'
              } ${!isPro ? 'opacity-50 cursor-default' : ''}`}
            >
              <div className={`w-4 h-4 rounded-full border-2 flex-shrink-0 flex items-center justify-center ${
                botForm.out_of_hours_behavior === opt.value ? 'border-fixme-accent' : 'border-fixme-border'
              }`}>
                {botForm.out_of_hours_behavior === opt.value && (
                  <div className="w-2 h-2 rounded-full bg-fixme-accent" />
                )}
              </div>
              <div>
                <div className={`text-sm font-semibold ${botForm.out_of_hours_behavior === opt.value ? 'text-fixme-accent' : 'text-fixme-text-secondary'}`}>{opt.label}</div>
                <div className="text-xs text-fixme-text-muted">{opt.desc}</div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Custom welcome message */}
      <div>
        <label className="text-fixme-text-secondary text-xs font-medium uppercase tracking-wide mb-1.5 block">
          Custom welcome message
        </label>
        <textarea
          rows={3}
          value={botForm.custom_welcome_message}
          onChange={(e) => update('custom_welcome_message', e.target.value)}
          placeholder="Leave blank to use the default greeting..."
          disabled={!isPro}
          className="w-full bg-fixme-card border border-fixme-border rounded-xl px-4 py-3 text-fixme-text-primary placeholder-fixme-text-muted text-sm focus:outline-none focus:border-fixme-accent resize-none transition-colors disabled:opacity-50"
        />
      </div>

      {/* Max advance days */}
      <div>
        <label className="text-fixme-text-secondary text-xs font-medium uppercase tracking-wide mb-1.5 block">
          Max advance booking (days)
        </label>
        <input
          type="number"
          min="1"
          max="365"
          value={botForm.max_advance_booking_days}
          onChange={(e) => update('max_advance_booking_days', e.target.value)}
          placeholder="No limit"
          disabled={!isPro}
          className="w-full bg-fixme-card border border-fixme-border rounded-xl px-4 py-3 text-fixme-text-primary placeholder-fixme-text-muted text-sm focus:outline-none focus:border-fixme-accent transition-colors disabled:opacity-50"
        />
        <p className="text-fixme-text-muted text-xs mt-1">How far in the future clients can book via DM</p>
      </div>

      {/* Save */}
      <button
        onClick={onSave}
        disabled={saving || !isPro}
        className="w-full py-3.5 rounded-xl font-semibold text-base bg-fixme-accent text-fixme-bg hover:bg-fixme-accent-light active:scale-[0.98] transition-all disabled:opacity-50"
      >
        {saving ? 'Saving...' : isPro ? 'Save bot settings' : 'Pro required to save'}
      </button>
    </div>
  );
}


// ---------------------------------------------------------------------------
// -- Shared UI components -------------------------------------------------
// ---------------------------------------------------------------------------

function Field({ label, value, onChange, placeholder, type = 'text' }) {
  return (
    <div>
      <label className="text-fixme-text-secondary text-xs font-medium uppercase tracking-wide mb-1.5 block">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-fixme-card border border-fixme-border rounded-xl px-4 py-3 text-fixme-text-primary placeholder-fixme-text-muted text-sm focus:outline-none focus:border-fixme-accent transition-colors"
      />
    </div>
  );
}

function Toggle({ on, small = false }) {
  const w = small ? 'w-8 h-4' : 'w-10 h-5';
  const dot = small ? 'w-3 h-3' : 'w-4 h-4';
  const pos = small ? (on ? 'left-4' : 'left-0.5') : (on ? 'left-5' : 'left-0.5');
  return (
    <span className={`${w} rounded-full transition-all relative flex-shrink-0 ${on ? 'bg-fixme-accent' : 'bg-fixme-border'}`}>
      <span className={`absolute top-0.5 ${dot} bg-white rounded-full shadow transition-all ${pos}`} />
    </span>
  );
}








