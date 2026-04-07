/**
 * ReviewScreen — Step 3 of onboarding.
 *
 * Dynamic progressive steps:
 *   1. Identity      — Instagram profile
 *   2. Business      — name, city, hours, policies, amenities
 *   3…N. [Category]  — one step per service category found by AI
 *
 * Cinematic slide + fade transition between every step.
 */
import { useState, useRef, useMemo } from 'react';
import {
  View, Text, Pressable, Image, TextInput,
  ScrollView, ActivityIndicator, Switch, Animated, Easing,
  KeyboardAvoidingView, Platform,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useAuth } from '@/stores/auth';
import {
  createOnboardingProvider,
  applyScanToProviderProfile,
  getProviderSession,
} from '@/lib/api';
import { registerForPushNotifications, saveTokenToBackend } from '@/lib/notifications';
import { onboardingData } from './_state';
import * as SecureStore from 'expo-secure-store';

// ── Design tokens ──────────────────────────────────────────────────────

const C = {
  bg:     '#181A20',
  card:   '#1E2028',
  border: 'rgba(255,255,255,0.10)',
  text:   '#F2F2F7',
  text2:  '#C2C7D2',
  muted:  '#98A0AF',
  green:  '#4ade80',
  accent: '#C8A97E',
  error:  '#ef4444',
} as const;

const BTN = {
  primary: {
    gradient: ['#FFFBF5', '#EEECEA'] as const,
    text:     '#0D0D0D',
    radius:   20,
  },
  secondary: {
    gradient: ['#252830', '#1E2028'] as const,
    text:     '#F2F2F7',
    border:   'rgba(255,255,255,0.18)',
    radius:   20,
  },
} as const;

// ── Types ──────────────────────────────────────────────────────────────

interface ServiceRow {
  name:     string;
  category: string;
  price:    string;
  duration: string;
}

interface DayHours {
  enabled: boolean;
  open:    string;
  close:   string;
}

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const DAY_SHORT: Record<string, string> = {
  Monday: 'Mon', Tuesday: 'Tue', Wednesday: 'Wed',
  Thursday: 'Thu', Friday: 'Fri', Saturday: 'Sat', Sunday: 'Sun',
};

const KNOWN_AMENITIES = [
  { key: 'parking',      label: 'Parking nearby' },
  { key: 'dogs_allowed', label: 'Dogs allowed' },
  { key: 'private_room', label: 'Private room' },
  { key: 'wifi',         label: 'WiFi' },
  { key: 'card_payment', label: 'Card payment' },
  { key: 'coffee',       label: 'Coffee & drinks' },
  { key: 'accessible',   label: 'Wheelchair accessible' },
  { key: 'music',        label: 'Music' },
];

// ── Helpers ────────────────────────────────────────────────────────────

function fmtFollowers(n?: number | null): string {
  if (!n) return '0';
  if (n >= 1000) return (n / 1000).toFixed(1).replace('.0', '') + 'k';
  return String(n);
}

function toInitials(s: string): string {
  return s.split(' ').map(w => w[0] ?? '').join('').toUpperCase().slice(0, 2) || '?';
}

// Strip duration suffix from service names — e.g. "Klassisk massage 75min" → "Klassisk massage"
function cleanServiceName(name: string): string {
  return name
    .replace(/\s*[\-–|,]?\s*\d+\s*(min(uter?|utes?)?|h(rs?|ours?)?|tim(mar|me)?)\b\.?/gi, '')
    .replace(/\s*\(\d+\s*(min|h)\)/gi, '')
    .trim();
}

const DEFAULT_HOURS: Record<string, DayHours> = {
  Monday:    { enabled: true,  open: '09:00', close: '18:00' },
  Tuesday:   { enabled: true,  open: '09:00', close: '18:00' },
  Wednesday: { enabled: true,  open: '09:00', close: '18:00' },
  Thursday:  { enabled: true,  open: '09:00', close: '18:00' },
  Friday:    { enabled: true,  open: '09:00', close: '18:00' },
  Saturday:  { enabled: false, open: '10:00', close: '16:00' },
  Sunday:    { enabled: false, open: '10:00', close: '16:00' },
};

function parseScanHours(raw: Record<string, any>): Record<string, DayHours> {
  const result: Record<string, DayHours> = {};
  const hasAny = Object.keys(raw).length > 0;

  DAYS.forEach(day => {
    // Backend returns 3-letter keys: Mon, Tue, Wed, Thu, Fri, Sat, Sun
    const v = raw[DAY_SHORT[day]] ?? raw[day] ?? raw[day.toLowerCase()] ?? null;

    if (!v) {
      // Fall back to sensible defaults rather than all-closed
      result[day] = hasAny
        ? { enabled: false, open: '09:00', close: '18:00' }
        : DEFAULT_HOURS[day];
      return;
    }

    if (typeof v === 'string') {
      const [open = '09:00', close = '18:00'] = v.split(/[-–]/);
      result[day] = { enabled: true, open: open.trim(), close: close.trim() };
    } else {
      // { open: bool, start: 'HH:MM', end: 'HH:MM' }
      result[day] = {
        enabled: v.open !== false,
        open:    v.start ?? v.open_time  ?? '09:00',
        close:   v.end   ?? v.close_time ?? '18:00',
      };
    }
  });
  return result;
}

// ── Sub-components ─────────────────────────────────────────────────────

function StepLabel({ label, muted }: { label: string; muted?: string }) {
  return (
    <View style={{ marginBottom: 32 }}>
      {muted && (
        <Text style={{ color: C.muted, fontSize: 11, fontWeight: '700', letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 10 }}>
          {muted}
        </Text>
      )}
      <Text style={{ color: C.text, fontSize: 28, fontWeight: '800', letterSpacing: -0.5, lineHeight: 34 }}>
        {label}
      </Text>
    </View>
  );
}

function EditableRow({
  label, value, onChange, multiline, placeholder,
}: {
  label: string; value: string; onChange: (v: string) => void;
  multiline?: boolean; placeholder?: string;
}) {
  const [editing, setEditing] = useState(false);
  return (
    <View style={{ marginBottom: 22 }}>
      <Text style={{ color: C.muted, fontSize: 11, fontWeight: '600', letterSpacing: 0.6, textTransform: 'uppercase', marginBottom: 6 }}>
        {label}
      </Text>
      {editing ? (
        <TextInput
          autoFocus
          style={{
            color: C.text, fontSize: 16,
            backgroundColor: 'rgba(255,255,255,0.06)',
            borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.18)',
            borderRadius: 14, paddingHorizontal: 14, paddingVertical: 12,
            ...(multiline ? { minHeight: 80, textAlignVertical: 'top' } : {}),
          }}
          value={value}
          onChangeText={onChange}
          multiline={multiline}
          onBlur={() => setEditing(false)}
          placeholder={placeholder}
          placeholderTextColor={C.muted}
        />
      ) : (
        <Pressable onPress={() => setEditing(true)} style={{ flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
          <Text style={{ color: value ? C.text : C.muted, fontSize: 16, flex: 1, lineHeight: 24 }}>
            {value || (placeholder ?? 'Not found — tap to add')}
          </Text>
          <Text style={{ color: C.muted, fontSize: 13, marginTop: 2 }}>Edit</Text>
        </Pressable>
      )}
    </View>
  );
}

function AmenityChip({ label, active, onToggle }: { label: string; active: boolean; onToggle: () => void }) {
  return (
    <Pressable
      onPress={onToggle}
      style={({ pressed }) => ({
        paddingHorizontal: 14, paddingVertical: 8, borderRadius: 999,
        borderWidth: 1,
        borderColor: active ? 'rgba(74,222,128,0.40)' : C.border,
        backgroundColor: active ? 'rgba(74,222,128,0.10)' : 'rgba(255,255,255,0.04)',
        opacity: pressed ? 0.75 : 1,
      })}
    >
      <Text style={{ color: active ? C.green : C.muted, fontSize: 13, fontWeight: active ? '600' : '400' }}>
        {label}
      </Text>
    </Pressable>
  );
}

function ServiceEditRow({ service, index, onChange }: {
  service: ServiceRow; index: number; onChange: (i: number, s: ServiceRow) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const field = {
    color: C.text, fontSize: 14,
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 1, borderColor: C.border,
    borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8,
  };
  return (
    <View style={{ borderBottomWidth: 1, borderBottomColor: C.border, paddingVertical: 14 }}>
      <Pressable onPress={() => setExpanded(e => !e)} style={{ flexDirection: 'row', alignItems: 'center' }}>
        <View style={{ flex: 1 }}>
          <Text style={{ color: C.text, fontSize: 15, fontWeight: '500' }}>
            {service.name || 'Unnamed service'}
          </Text>
          <Text style={{ color: C.muted, fontSize: 12, marginTop: 2 }}>
            {[service.price ? service.price + '' : null, service.duration ? service.duration + ' min' : null].filter(Boolean).join('  ·  ') || 'No details'}
          </Text>
        </View>
        <Text style={{ color: C.muted, fontSize: 12 }}>{expanded ? 'Done' : 'Edit'}</Text>
      </Pressable>
      {expanded && (
        <View style={{ marginTop: 12, gap: 8 }}>
          <TextInput style={field} value={service.name} onChangeText={v => onChange(index, { ...service, name: v })} placeholder="Service name" placeholderTextColor={C.muted} />
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <TextInput style={[field, { flex: 1 }]} value={service.price}    onChangeText={v => onChange(index, { ...service, price: v })}    placeholder="Price" placeholderTextColor={C.muted} keyboardType="numeric" />
            <TextInput style={[field, { flex: 1 }]} value={service.duration} onChangeText={v => onChange(index, { ...service, duration: v })} placeholder="Duration (min)" placeholderTextColor={C.muted} keyboardType="numeric" />
          </View>
        </View>
      )}
    </View>
  );
}

function HoursRow({ day, hours, onChange }: {
  day: string; hours: DayHours; onChange: (d: string, h: DayHours) => void;
}) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: C.border, gap: 12 }}>
      <Text style={{ color: hours.enabled ? C.text : C.muted, fontSize: 14, width: 36 }}>{DAY_SHORT[day]}</Text>
      <Switch
        value={hours.enabled}
        onValueChange={v => onChange(day, { ...hours, enabled: v })}
        trackColor={{ false: 'rgba(255,255,255,0.12)', true: 'rgba(74,222,128,0.45)' }}
        thumbColor={hours.enabled ? C.green : '#555'}
        style={{ transform: [{ scaleX: 0.8 }, { scaleY: 0.8 }] }}
      />
      {hours.enabled ? (
        <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <TextInput
            style={{ flex: 1, color: C.text, fontSize: 14, backgroundColor: 'rgba(255,255,255,0.06)', borderWidth: 1, borderColor: C.border, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 6, textAlign: 'center' }}
            value={hours.open}
            onChangeText={v => onChange(day, { ...hours, open: v })}
            placeholder="09:00"
            placeholderTextColor={C.muted}
          />
          <Text style={{ color: C.muted, fontSize: 13 }}>–</Text>
          <TextInput
            style={{ flex: 1, color: C.text, fontSize: 14, backgroundColor: 'rgba(255,255,255,0.06)', borderWidth: 1, borderColor: C.border, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 6, textAlign: 'center' }}
            value={hours.close}
            onChangeText={v => onChange(day, { ...hours, close: v })}
            placeholder="18:00"
            placeholderTextColor={C.muted}
          />
        </View>
      ) : (
        <Text style={{ color: C.muted, fontSize: 14 }}>Closed</Text>
      )}
    </View>
  );
}

// ── Main screen ────────────────────────────────────────────────────────

export default function ReviewScreen() {
  const { setAuth } = useAuth();
  const scan   = (onboardingData.scanResult   ?? {}) as Record<string, any>;
  const ig     = onboardingData.igStatus;
  const handle = onboardingData.igHandle;

  // ── Build dynamic step list ──────────────────────────────────────
  const { steps, servicesByCategory } = useMemo(() => {
    const rawServices: any[] = Array.isArray(scan.services) ? scan.services : [];
    const catMap: Record<string, ServiceRow[]> = {};
    rawServices.forEach(s => {
      const cat = (s.category || 'Other').trim();
      if (!catMap[cat]) catMap[cat] = [];
      catMap[cat].push({
        name:     cleanServiceName(s.name ?? ''),
        category: cat,
        price:    String(s.price_ex_vat     ?? s.price    ?? ''),
        duration: String(s.duration_minutes  ?? s.duration ?? ''),
      });
    });
    const cats = Object.keys(catMap);
    const stepList = ['identity', 'business', ...cats.map(c => `cat:${c}`)];
    return { steps: stepList, servicesByCategory: catMap };
  }, []);

  const [stepIdx,  setStepIdx]  = useState(0);
  const [busy,     setBusy]     = useState(false);
  const [error,    setError]    = useState<string | null>(null);

  // ── Animation ────────────────────────────────────────────────────
  const slideAnim = useRef(new Animated.Value(0)).current;
  const fadeAnim  = useRef(new Animated.Value(1)).current;

  function transition(nextIdx: number, direction: 'forward' | 'back') {
    const outX = direction === 'forward' ? -24 : 24;
    const inX  = direction === 'forward' ?  24 : -24;

    Animated.parallel([
      Animated.timing(slideAnim, { toValue: outX, duration: 140, useNativeDriver: true, easing: Easing.in(Easing.quad) }),
      Animated.timing(fadeAnim,  { toValue: 0,    duration: 140, useNativeDriver: true }),
    ]).start(() => {
      setStepIdx(nextIdx);
      slideAnim.setValue(inX);
      Animated.parallel([
        Animated.timing(slideAnim, { toValue: 0, duration: 300, useNativeDriver: true, easing: Easing.out(Easing.cubic) }),
        Animated.timing(fadeAnim,  { toValue: 1, duration: 300, useNativeDriver: true }),
      ]).start();
    });
  }

  function goNext() { transition(stepIdx + 1, 'forward'); }
  function goBack() { transition(stepIdx - 1, 'back'); }

  // ── Business state ───────────────────────────────────────────────
  const [name,          setName]          = useState<string>(scan.name    ?? '');
  const [city,          setCity]          = useState<string>(scan.city    ?? '');
  const [address,       setAddress]       = useState<string>(scan.address ?? '');
  const [cancelPolicy,  setCancelPolicy]  = useState<string>(scan.cancellation_policy ?? '');
  const [bookingPolicy, setBookingPolicy] = useState<string>(scan.booking_policy      ?? '');
  const [homeVisits,    setHomeVisits]    = useState(false);
  const [amenities,     setAmenities]     = useState<Set<string>>(() =>
    new Set(Array.isArray(scan.amenity_keys) ? scan.amenity_keys : [])
  );
  const [hours, setHours] = useState<Record<string, DayHours>>(() =>
    parseScanHours(typeof scan.working_hours === 'object' && scan.working_hours ? scan.working_hours : {})
  );

  // ── Service state (mutable copy per category) ────────────────────
  const [serviceMap, setServiceMap] = useState<Record<string, ServiceRow[]>>(servicesByCategory);

  function updateService(cat: string, i: number, updated: ServiceRow) {
    setServiceMap(prev => ({
      ...prev,
      [cat]: prev[cat].map((s, idx) => idx === i ? updated : s),
    }));
  }

  function toggleAmenity(key: string) {
    setAmenities(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  // ── Finish ───────────────────────────────────────────────────────
  async function handleFinish() {
    const token = onboardingData.pendingAccessToken;
    if (!token) { setError('Session expired — please log in again.'); return; }
    setError(null);
    setBusy(true);
    try {
      const fallback = onboardingData.email?.split('@')[0] || 'New Provider';
      const allServices = Object.values(serviceMap).flat();

      const result = await createOnboardingProvider({
        name:                name || fallback,
        city:                city || null,
        bio:                 scan.bio ?? null,
        instagram_username:  handle || null,
        home_service:        homeVisits,
        amenity_keys:        Array.from(amenities),
        scanned_services:    allServices.map(s => ({
          name:              s.name,
          category:          s.category         || null,
          price_ex_vat:      s.price    ? parseFloat(s.price)  : null,
          duration_minutes:  s.duration ? parseInt(s.duration) : null,
        })),
        booking_policy:      bookingPolicy || null,
        cancellation_policy: cancelPolicy  || null,
        ig_user_id:          ig?.instagram_user_id ?? null,
        ig_access_token:     null,
      }, token);

      // Convert DayHours → { Mon: { open: bool, start: 'HH:MM', end: 'HH:MM' } }
      const workingHours: Record<string, any> = {};
      DAYS.forEach(day => {
        const h = hours[day];
        const shortDay = DAY_SHORT[day];
        workingHours[shortDay] = {
          open:  h?.enabled ?? false,
          start: h?.enabled ? (h.open  || '09:00') : null,
          end:   h?.enabled ? (h.close || '18:00') : null,
        };
      });
      if (Object.keys(workingHours).length > 0) {
        await applyScanToProviderProfile({ working_hours: workingHours }, token).catch(() => {});
      }

      const me = await getProviderSession(token).catch(() => null);
      await setAuth(token, result.provider_id, me?.provider_name ?? result.name, result.slug ?? '');

      // Hide the "Build your profile" scrape card on the home screen —
      // provider already went through onboarding so they don't need it.
      await SecureStore.setItemAsync('fixme_setup_import_done', '1');

      const pt = await registerForPushNotifications();
      if (pt) await saveTokenToBackend(pt);

      router.replace('/(tabs)/');
    } catch (err: any) {
      setError(err.message || 'Something went wrong. Try again.');
      setBusy(false);
    }
  }

  // ── Step content ──────────────────────────────────────────────────
  const currentStep = steps[stepIdx] ?? 'identity';
  const isLast      = stepIdx === steps.length - 1;
  const catKey      = currentStep.startsWith('cat:') ? currentStep.slice(4) : null;
  const catServices = catKey ? (serviceMap[catKey] ?? []) : [];

  // ── Render ────────────────────────────────────────────────────────
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: C.bg }}>

      {/* ── Sticky header + progress ── */}
      <View style={{ paddingHorizontal: 24, paddingTop: 16, paddingBottom: 4, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <Text style={{ color: C.muted, fontSize: 10, fontWeight: '700', letterSpacing: 5, textTransform: 'uppercase' }}>
          Fixmeapp
        </Text>
        <Text style={{ color: C.muted, fontSize: 12 }}>{stepIdx + 1} / {steps.length}</Text>
      </View>

      {/* Progress bar — dynamic segments */}
      <View style={{ flexDirection: 'row', gap: 5, paddingHorizontal: 24, paddingVertical: 14 }}>
        {steps.map((_, i) => (
          <View
            key={i}
            style={{
              flex: 1, height: 3, borderRadius: 99,
              backgroundColor: i <= stepIdx ? C.text : 'rgba(255,255,255,0.12)',
            }}
          />
        ))}
      </View>

      {/* ── Animated content area ── */}
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ paddingHorizontal: 24, paddingBottom: 120 }}
        keyboardShouldPersistTaps="handled"
      >
        <Animated.View style={{ opacity: fadeAnim, transform: [{ translateX: slideAnim }] }}>

          {/* ── Step: Identity ── */}
          {currentStep === 'identity' && (
            <View style={{ paddingTop: 8 }}>
              <StepLabel label={'Your Instagram\nprofile'} muted="This is you" />
              <View style={{
                backgroundColor: C.card, borderWidth: 1, borderColor: C.border,
                borderRadius: 24, padding: 28, alignItems: 'center', gap: 16,
              }}>
                <View style={{
                  width: 90, height: 90, borderRadius: 45, overflow: 'hidden',
                  backgroundColor: 'rgba(200,169,126,0.15)',
                  alignItems: 'center', justifyContent: 'center',
                  borderWidth: 2, borderColor: 'rgba(200,169,126,0.25)',
                }}>
                  {ig?.profile_picture_url
                    ? <Image source={{ uri: ig.profile_picture_url }} style={{ width: 90, height: 90 }} resizeMode="cover" />
                    : <Text style={{ color: C.accent, fontSize: 28, fontWeight: '700' }}>{toInitials(handle || 'U')}</Text>
                  }
                </View>
                <View style={{ alignItems: 'center', gap: 4 }}>
                  <Text style={{ color: C.text, fontSize: 20, fontWeight: '700' }}>
                    @{ig?.instagram_username || handle || '—'}
                  </Text>
                  {(ig?.followers_count ?? 0) > 0 && (
                    <Text style={{ color: C.muted, fontSize: 13 }}>
                      {fmtFollowers(ig?.followers_count)} followers
                    </Text>
                  )}
                </View>
              </View>
            </View>
          )}

          {/* ── Step: Business ── */}
          {currentStep === 'business' && (
            <View style={{ paddingTop: 8 }}>
              <StepLabel label="Your business" muted="From your website" />
              <EditableRow label="Business name"  value={name}          onChange={setName}          placeholder="Your business name" />
              <EditableRow label="Street address" value={address}       onChange={setAddress}       placeholder="Street address" />
              <EditableRow label="City"            value={city}          onChange={setCity}          placeholder="City" />
              <EditableRow label="Cancellation"    value={cancelPolicy}  onChange={setCancelPolicy}  placeholder="e.g. 24h notice required" multiline />
              <EditableRow label="Booking policy"  value={bookingPolicy} onChange={setBookingPolicy} placeholder="e.g. Pay on arrival" multiline />

              {/* Home visits */}
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
                <View>
                  <Text style={{ color: C.muted, fontSize: 11, fontWeight: '600', letterSpacing: 0.6, textTransform: 'uppercase', marginBottom: 4 }}>Home visits</Text>
                  <Text style={{ color: homeVisits ? C.green : C.muted, fontSize: 15 }}>{homeVisits ? 'Yes — you visit clients' : 'No'}</Text>
                </View>
                <Switch
                  value={homeVisits}
                  onValueChange={setHomeVisits}
                  trackColor={{ false: 'rgba(255,255,255,0.12)', true: 'rgba(74,222,128,0.45)' }}
                  thumbColor={homeVisits ? C.green : '#555'}
                />
              </View>

              {/* Working hours */}
              <Text style={{ color: C.muted, fontSize: 11, fontWeight: '600', letterSpacing: 0.6, textTransform: 'uppercase', marginBottom: 4 }}>
                Working hours
              </Text>
              <View style={{ backgroundColor: C.card, borderWidth: 1, borderColor: C.border, borderRadius: 20, paddingHorizontal: 16, marginBottom: 28 }}>
                {DAYS.map(day => (
                  <HoursRow
                    key={day}
                    day={day}
                    hours={hours[day]}
                    onChange={(d, h) => setHours(prev => ({ ...prev, [d]: h }))}
                  />
                ))}
              </View>

              {/* Amenities */}
              <Text style={{ color: C.muted, fontSize: 11, fontWeight: '600', letterSpacing: 0.6, textTransform: 'uppercase', marginBottom: 12 }}>
                Amenities
              </Text>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                {KNOWN_AMENITIES.map(a => (
                  <AmenityChip key={a.key} label={a.label} active={amenities.has(a.key)} onToggle={() => toggleAmenity(a.key)} />
                ))}
              </View>
            </View>
          )}

          {/* ── Step: Service category ── */}
          {catKey && (
            <View style={{ paddingTop: 8 }}>
              <StepLabel label={catKey} muted={`${catServices.length} service${catServices.length !== 1 ? 's' : ''} found`} />
              {catServices.length > 0 ? (
                <View style={{ backgroundColor: C.card, borderWidth: 1, borderColor: C.border, borderRadius: 20, paddingHorizontal: 16 }}>
                  {catServices.map((s, i) => (
                    <ServiceEditRow
                      key={i}
                      service={s}
                      index={i}
                      onChange={(idx, updated) => updateService(catKey, idx, updated)}
                    />
                  ))}
                </View>
              ) : (
                <Text style={{ color: C.muted, fontSize: 15 }}>No services found — add them from settings after launch.</Text>
              )}
            </View>
          )}

          {error && (
            <Text style={{ color: C.error, fontSize: 13, textAlign: 'center', marginTop: 16 }}>
              {error}
            </Text>
          )}

        </Animated.View>
      </ScrollView>

      {/* ── Sticky bottom nav — inside KeyboardAvoidingView so it rises with keyboard ── */}
      <View style={{
        paddingHorizontal: 24, paddingBottom: 24, paddingTop: 12,
        flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
      }}>
        {stepIdx > 0
          ? <Pressable onPress={goBack} disabled={busy}><Text style={{ color: C.muted, fontSize: 13 }}>← Back</Text></Pressable>
          : <View />
        }

        {!isLast ? (
          <Pressable
            onPress={goNext}
            style={({ pressed }) => ({ borderRadius: BTN.primary.radius, overflow: 'hidden', opacity: pressed ? 0.85 : 1 })}
          >
            <LinearGradient
              colors={BTN.primary.gradient}
              start={{ x: 0, y: 0 }} end={{ x: 0, y: 1 }}
              style={{ borderRadius: BTN.primary.radius, paddingVertical: 13, paddingHorizontal: 28, alignItems: 'center' }}
            >
              <Text style={{ color: BTN.primary.text, fontWeight: '700', fontSize: 15 }}>
                {currentStep === 'identity' ? 'Looks right →' : 'Approve →'}
              </Text>
            </LinearGradient>
          </Pressable>
        ) : (
          <Pressable
            onPress={handleFinish}
            disabled={busy}
            style={({ pressed }) => ({ borderRadius: BTN.primary.radius, overflow: 'hidden', opacity: busy ? 0.45 : pressed ? 0.85 : 1 })}
          >
            <LinearGradient
              colors={BTN.primary.gradient}
              start={{ x: 0, y: 0 }} end={{ x: 0, y: 1 }}
              style={{ borderRadius: BTN.primary.radius, paddingVertical: 13, paddingHorizontal: 28, alignItems: 'center' }}
            >
              {busy
                ? <ActivityIndicator color={BTN.primary.text} size="small" />
                : <Text style={{ color: BTN.primary.text, fontWeight: '700', fontSize: 15 }}>Finish →</Text>
              }
            </LinearGradient>
          </Pressable>
        )}
      </View>
      </KeyboardAvoidingView>

    </SafeAreaView>
  );
}
