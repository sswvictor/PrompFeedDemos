/**
 * ScrapeScreen â€” combined Instagram + website scan, 6 section confirmation rows.
 *
 * Three phases:
 *   input     â†’ Clean form: IG connect + website URL + Analyze button
 *   analyzing â†’ Sections slide in, each resolving staggered
 *   done      â†’ All sections resolved; "Continue â†’" when â‰¥1 approved, else "Launch my account â†’"
 */
import { useState, useMemo, useEffect, useRef } from 'react';
import {
  View, Text, TextInput, Pressable,
  ActivityIndicator, KeyboardAvoidingView,
  Platform, ScrollView, Animated,
} from 'react-native';
import Svg, { Rect, Circle } from 'react-native-svg';
import { LinearGradient } from 'expo-linear-gradient';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as WebBrowser from 'expo-web-browser';

import { useAuth } from '@/stores/auth';
import {
  scanWebsite,
  createOnboardingProvider,
  applyScanToProviderProfile,
  getInstagramConnectStatus,
  getProviderSession,
  startInstagramConnect,
  type InstagramConnectStatus,
} from '@/lib/api';
import { registerForPushNotifications, saveTokenToBackend } from '@/lib/notifications';
import { onboardingData } from './_state';

WebBrowser.maybeCompleteAuthSession();
const REDIRECT_URI = 'fixmeapp://instagram-callback';

// â”€â”€ Design tokens â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const C = {
  bg:     '#181A20',
  card:   '#262A33',
  deep:   '#343944',
  border: '#454B58',
  text:   '#F2F2F7',
  text2:  '#C2C7D2',
  muted:  '#98A0AF',
  accent: '#C8A97E',
  green:  '#4ade80',
  ig:     '#C13584',
  error:  '#ef4444',
} as const;

// ── Button system (dark mode) ─────────────────────────────────────────
// Primary   — solid light, single most important action on screen
// Secondary — glass fill, clearly visible supporting action
// Tertiary  — ghost, low-friction dismiss / skip
const BTN = {
  primary: {
    gradient:   ['#FFFBF5', '#EEECEA'] as const,
    bgPressed:  '#D8D6D3',
    text:       '#0D0D0D',
    border:     'transparent',
    radius:     20,
  },
  secondary: {
    gradient:   ['#252830', '#1E2028'] as const,
    bgPressed:  '#2C3040',
    text:       '#F2F2F7',
    border:     'rgba(255,255,255,0.18)',
    radius:     20,
  },
  tertiary: {
    bg:         'transparent',
    bgPressed:  'transparent',
    text:       'rgba(242,242,247,0.45)',
    border:     'transparent',
    radius:     20,
  },
} as const;

// â”€â”€ Types â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

type Phase = 'input' | 'analyzing' | 'done';
type ReviewDesign = 'luxury' | 'cinematic' | 'editorial' | 'streamlined';

type SectionKey =
  | 'instagram'
  | 'business_name'
  | 'address'
  | 'working_hours'
  | 'services'
  | 'cancellation';

type SectionStatus = 'loading' | 'found' | 'review';

interface Draft {
  source_url: string;
  name: string;
  city: string;
  bio: string;
  services: any[];
  working_hours: Record<string, any>;
  amenity_keys: string[];
  booking_policy: string;
  cancellation_policy: string;
  instagram_username: string;
  ig_profile_picture_url: string;
  ig_user_id: string | null;
  ig_access_token: null;
  ai_vibe_tags: string[];
  vibe_summary: string | null;
}

// â”€â”€ Constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const SECTION_ORDER: SectionKey[] = [
  'instagram', 'business_name', 'address',
  'working_hours', 'services', 'cancellation',
];

const SECTION_TITLES: Record<SectionKey, string> = {
  instagram:     'Instagram profile',
  business_name: 'Business name',
  address:       'Location',
  working_hours: 'Working hours',
  services:      'Services & pricing',
  cancellation:  'Cancellation policy',
};

const LOADING_STATUS: Record<SectionKey, SectionStatus> = {
  instagram: 'loading', business_name: 'loading', address: 'loading',
  working_hours: 'loading', services: 'loading', cancellation: 'loading',
};

const INITIAL_APPROVED: Record<SectionKey, boolean> = {
  instagram: false, business_name: false, address: false,
  working_hours: false, services: false, cancellation: false,
};

const INITIAL_DISMISSED: Record<SectionKey, boolean> = {
  instagram: false, business_name: false, address: false,
  working_hours: false, services: false, cancellation: false,
};

const sleep = (ms: number) => new Promise<void>(r => setTimeout(r, ms));

const REVIEW_VARIANTS: Array<{ key: ReviewDesign; label: string; caption: string }> = [
  { key: 'luxury', label: 'A', caption: 'Minimal luxury' },
  { key: 'cinematic', label: 'B', caption: 'Cinematic AI reveal' },
  { key: 'editorial', label: 'C', caption: 'Calm editorial review' },
  { key: 'streamlined', label: 'D', caption: 'Trust & launch' },
];

const STEP_H1 = {
  color: C.text,
  fontSize: 30,
  lineHeight: 37,
  fontWeight: '800' as const,
};

const STEP_H2 = {
  color: C.text,
  fontSize: 22,
  lineHeight: 28,
  fontWeight: '500' as const,
};

const GLASS_INPUT_SHELL = {
  backgroundColor: 'rgba(255,255,255,0.06)',
  borderColor: 'rgba(255,255,255,0.14)',
  borderWidth: 1.5,
  borderRadius: 16,
  paddingHorizontal: 16,
  shadowColor: '#000',
  shadowOpacity: 0.16,
  shadowRadius: 12,
  shadowOffset: { width: 0, height: 6 },
};

const GLASS_INPUT_TEXT = {
  color: C.text,
  fontSize: 16,
  letterSpacing: 0,
};

const REVIEW_CARD = {
  backgroundColor: '#21252D',
  borderColor: 'rgba(255,255,255,0.08)',
  borderRadius: 24,
  borderWidth: 1,
  shadowColor: '#000',
  shadowOpacity: 0.18,
  shadowRadius: 16,
  shadowOffset: { width: 0, height: 8 },
} as const;

const REVIEW_FIELD = {
  backgroundColor: 'rgba(255,255,255,0.045)',
  borderColor: 'rgba(255,255,255,0.08)',
  borderWidth: 1,
  borderRadius: 16,
  paddingHorizontal: 14,
  paddingVertical: 12,
  color: C.text,
  fontSize: 14,
} as const;

// Helpers

function buildDraft(scanData: any, igData: any, handle: string): Draft {
  return {
    source_url:             scanData?.source_url ?? '',
    name:                   scanData?.name ?? igData?.name ?? '',
    city:                   scanData?.city ?? '',
    bio:                    scanData?.bio ?? igData?.biography ?? '',
    services:               Array.isArray(scanData?.services) ? scanData.services : [],
    working_hours:          scanData?.working_hours ?? {},
    amenity_keys:           Array.isArray(scanData?.amenity_keys) ? scanData.amenity_keys : [],
    booking_policy:         scanData?.booking_policy ?? '',
    cancellation_policy:    scanData?.cancellation_policy ?? '',
    instagram_username:     igData?.username ?? igData?.instagram_username ?? handle,
    ig_profile_picture_url: igData?.profile_picture_url ?? '',
    ig_user_id:             igData?.ig_user_id ?? igData?.instagram_user_id ?? null,
    ig_access_token:        null,
    ai_vibe_tags:           Array.isArray(scanData?.ai_vibe_tags) ? scanData.ai_vibe_tags : [],
    vibe_summary:           scanData?.vibe_summary ?? null,
  };
}

function resolveSection(draft: Draft, key: SectionKey): SectionStatus {
  if (key === 'instagram')     return draft.instagram_username || draft.ig_profile_picture_url ? 'found' : 'review';
  if (key === 'business_name') return draft.name ? 'found' : 'review';
  if (key === 'address')       return draft.city ? 'found' : 'review';
  if (key === 'working_hours') return Object.keys(draft.working_hours).length > 0 ? 'found' : 'review';
  if (key === 'services')      return draft.services.length > 0 ? 'found' : 'review';
  if (key === 'cancellation')  return draft.cancellation_policy || draft.booking_policy ? 'found' : 'review';
  return 'review';
}

function sectionHint(key: SectionKey, draft: Draft | null): string {
  if (!draft) return '';
  if (key === 'instagram')     return draft.instagram_username ? '@' + draft.instagram_username : 'Not found';
  if (key === 'business_name') return draft.name || 'Not found';
  if (key === 'address')       return draft.city || 'Not found';
  if (key === 'working_hours') {
    const n = Object.keys(draft.working_hours).length;
    return n > 0 ? n + ' day' + (n !== 1 ? 's' : '') + ' detected' : 'Not found';
  }
  if (key === 'services') {
    const n = draft.services.length;
    return n + ' service' + (n !== 1 ? 's' : '') + ' found';
  }
  if (key === 'cancellation') {
    const text = draft.cancellation_policy || draft.booking_policy;
    if (!text) return 'Not found';
    return text.length > 52 ? text.slice(0, 52) + '...' : text;
  }
  return '';
}

// Instagram icon (SVG)

function InstagramIcon({ size = 18, color = '#C13584' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Rect x="2" y="2" width="20" height="20" rx="6" stroke={color} strokeWidth="1.8" />
      <Circle cx="12" cy="12" r="4.5" stroke={color} strokeWidth="1.8" />
      <Circle cx="17.5" cy="6.5" r="1.2" fill={color} />
    </Svg>
  );
}

// StatusPill

function StatusPill({ status }: { status: SectionStatus }) {
  if (status === 'loading') {
    return <ActivityIndicator size="small" color={C.accent} style={{ width: 18, height: 18 }} />;
  }
  if (status === 'found') {
    return (
      <View style={{
        backgroundColor: 'rgba(74,222,128,0.10)',
        borderColor: 'rgba(74,222,128,0.22)',
        borderWidth: 1,
        paddingHorizontal: 11,
        paddingVertical: 6,
        borderRadius: 999,
      }}>
        <Text style={{ color: C.green, fontSize: 11, fontWeight: '700' }}>Found</Text>
      </View>
    );
  }
  return (
    <View style={{
      backgroundColor: 'rgba(255,255,255,0.04)',
      borderColor: 'rgba(255,255,255,0.08)',
      borderWidth: 1,
      paddingHorizontal: 11,
      paddingVertical: 6,
      borderRadius: 999,
    }}>
      <Text style={{ color: C.muted, fontSize: 11, fontWeight: '600' }}>Needs review</Text>
    </View>
  );
}

// SectionDetail

function SectionDetail({
  sectionKey,
  draft,
  onDraftChange,
}: {
  sectionKey: SectionKey;
  draft: Draft;
  onDraftChange: (nextDraft: Draft) => void;
}) {
  const body  = { color: C.text2, fontSize: 13, lineHeight: 20 };
  const label = {
    color: C.muted,
    fontSize: 10,
    fontWeight: '600' as const,
    width: 80,
    textTransform: 'capitalize' as const,
  };
  const row   = { flexDirection: 'row' as const, paddingVertical: 8, alignItems: 'center' as const, gap: 10 };
  const content = { paddingHorizontal: 6, paddingBottom: 2 };
  const input = {
    ...REVIEW_FIELD,
  } as const;
  const textarea = {
    ...input,
    minHeight: 108,
    textAlignVertical: 'top' as const,
  };

  if (sectionKey === 'instagram') {
    return (
      <View style={content}>
        <Text style={[body, { marginBottom: 8 }]}>Instagram handle</Text>
        <TextInput
          style={input}
          value={draft.instagram_username ?? ''}
          onChangeText={(value) => onDraftChange({
            ...draft,
            instagram_username: value.replace(/^@/, ''),
          })}
          placeholder="yourusername"
          placeholderTextColor={C.muted}
          autoCapitalize="none"
          autoCorrect={false}
        />
      </View>
    );
  }

  if (sectionKey === 'business_name') {
    return (
      <View style={content}>
        <Text style={[body, { marginBottom: 8 }]}>Business name</Text>
        <TextInput
          style={input}
          value={draft.name ?? ''}
          onChangeText={(value) => onDraftChange({ ...draft, name: value })}
          placeholder="Business name"
          placeholderTextColor={C.muted}
        />
      </View>
    );
  }

  if (sectionKey === 'address') {
    return (
      <View style={content}>
        <Text style={[body, { marginBottom: 8 }]}>City</Text>
        <TextInput
          style={input}
          value={draft.city ?? ''}
          onChangeText={(value) => onDraftChange({ ...draft, city: value })}
          placeholder="City"
          placeholderTextColor={C.muted}
        />
      </View>
    );
  }

  if (sectionKey === 'working_hours') {
    const entries = Object.entries(draft.working_hours);
    if (!entries.length) {
      return (
        <View style={content}>
          <Text style={body}>No hours detected. You can set them after launch.</Text>
        </View>
      );
    }
    return (
      <View style={content}>
        {entries.map(([day, hours]) => (
          <View key={day} style={row}>
            <Text style={label}>{day}</Text>
            {typeof hours === 'string' ? (
              <TextInput
                style={[input, { flex: 1 }]}
                value={hours}
                onChangeText={(value) => onDraftChange({
                  ...draft,
                  working_hours: {
                    ...draft.working_hours,
                    [day]: value,
                  },
                })}
                placeholder="09:00-17:00"
                placeholderTextColor={C.muted}
              />
            ) : (
              <View style={{ flex: 1, flexDirection: 'row', gap: 8 }}>
                <TextInput
                  style={[input, { flex: 1 }]}
                  value={String((hours).open ?? '')}
                  onChangeText={(value) => onDraftChange({
                    ...draft,
                    working_hours: {
                      ...draft.working_hours,
                      [day]: {
                        ...(hours),
                        open: value,
                      },
                    },
                  })}
                  placeholder="09:00"
                  placeholderTextColor={C.muted}
                />
                <TextInput
                  style={[input, { flex: 1 }]}
                  value={String((hours).close ?? '')}
                  onChangeText={(value) => onDraftChange({
                    ...draft,
                    working_hours: {
                      ...draft.working_hours,
                      [day]: {
                        ...(hours),
                        close: value,
                      },
                    },
                  })}
                  placeholder="17:00"
                  placeholderTextColor={C.muted}
                />
              </View>
            )}
          </View>
        ))}
      </View>
    );
  }

  if (sectionKey === 'services') {
    if (!draft.services.length) {
      return (
        <View style={content}>
          <Text style={body}>No services detected. Add them in settings after launch.</Text>
        </View>
      );
    }
    return (
      <View style={content}>
        {draft.services.slice(0, 8).map((s: any, i: number) => (
          <View key={i} style={{ marginBottom: 10 }}>
            <TextInput
              style={input}
              value={String(s.name || s.service_name || '')}
              onChangeText={(value) => {
                const nextServices = [...draft.services];
                nextServices[i] = {
                  ...nextServices[i],
                  name: value,
                  service_name: value,
                };
                onDraftChange({ ...draft, services: nextServices });
              }}
              placeholder="Service name"
              placeholderTextColor={C.muted}
            />
            <View style={{ flexDirection: 'row', gap: 8, marginTop: 8, marginBottom: 4 }}>
              <Text style={[body, { flex: 1, fontSize: 10 }]}>Minutes</Text>
              <Text style={[body, { flex: 1, fontSize: 10 }]}>Price</Text>
            </View>
            <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
              <TextInput
                style={[input, { flex: 1 }]}
                value={String(s.duration_minutes ?? s.duration ?? '')}
                onChangeText={(value) => {
                  const nextServices = [...draft.services];
                  nextServices[i] = {
                    ...nextServices[i],
                    duration_minutes: value === '' ? null : Number(value),
                  };
                  onDraftChange({ ...draft, services: nextServices });
                }}
                placeholder="Minutes"
                placeholderTextColor={C.muted}
                keyboardType="number-pad"
              />
              <TextInput
                style={[input, { flex: 1 }]}
                value={String(s.price ?? s.price_sek ?? '')}
                onChangeText={(value) => {
                  const nextServices = [...draft.services];
                  nextServices[i] = {
                    ...nextServices[i],
                    price: value === '' ? null : Number(value),
                  };
                  onDraftChange({ ...draft, services: nextServices });
                }}
                placeholder="Price"
                placeholderTextColor={C.muted}
                keyboardType="decimal-pad"
              />
            </View>
          </View>
        ))}
        {draft.services.length > 8 && (
          <Text style={{ color: C.muted, fontSize: 11, marginTop: 4 }}>
            +{draft.services.length - 8} more
          </Text>
        )}
      </View>
    );
  }

  if (sectionKey === 'cancellation') {
    return (
      <View style={content}>
        <Text style={[body, { marginBottom: 8 }]}>Cancellation policy</Text>
        <TextInput
          style={textarea}
          value={draft.cancellation_policy || draft.booking_policy || ''}
          onChangeText={(value) => onDraftChange({
            ...draft,
            cancellation_policy: value,
            booking_policy: value,
          })}
          placeholder="Write your cancellation policy"
          placeholderTextColor={C.muted}
          multiline
        />
      </View>
    );
  }

  return null;
}
function SectionRow({
  title, sectionKey, hint, status, approved, skipped, onApprove, onSkip, expanded, onToggle, draft, onDraftChange, variant, spotlight,
}: {
  title: string;
  sectionKey: SectionKey;
  hint: string;
  status: SectionStatus;
  approved: boolean;
  skipped: boolean;
  onApprove: () => void;
  onSkip: () => void;
  expanded: boolean;
  onToggle: () => void;
  draft: Draft | null;
  onDraftChange: (nextDraft: Draft) => void;
  variant: ReviewDesign;
  spotlight?: boolean;
}) {
  const isLoading = status === 'loading';
  const tone = approved ? 'Approved' : skipped ? 'Skipped' : status === 'review' ? 'Needs review' : 'Ready';
  const variantCard =
    variant === 'cinematic'
      ? {
          backgroundColor: '#1B1A20',
          borderColor: approved ? 'rgba(74,222,128,0.28)' : expanded ? 'rgba(193,53,132,0.30)' : 'rgba(255,255,255,0.08)',
          borderRadius: 28,
          shadowOpacity: 0.28,
          shadowRadius: 22,
        }
      : variant === 'editorial'
      ? {
          backgroundColor: '#23262E',
          borderColor: approved ? 'rgba(74,222,128,0.22)' : 'rgba(255,255,255,0.06)',
          borderRadius: 22,
          shadowOpacity: 0.10,
          shadowRadius: 10,
        }
      : {
          backgroundColor: '#21252D',
          borderColor: approved ? 'rgba(74,222,128,0.24)' : expanded ? 'rgba(200,169,126,0.24)' : 'rgba(255,255,255,0.08)',
          borderRadius: 24,
          shadowOpacity: 0.18,
          shadowRadius: 16,
        };
  const toneColor = approved ? C.green : skipped ? C.muted : variant === 'cinematic' ? '#E17BC1' : status === 'review' ? C.accent : C.muted;
  const titleSize = variant === 'cinematic' ? 19 : variant === 'editorial' ? 17 : 18;

  // ── Streamlined variant ─────────────────────────────────────────────
  if (variant === 'streamlined') {
    // Loading state
    if (isLoading) {
      return (
        <View style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 16, paddingHorizontal: 4, gap: 12, borderBottomWidth: 1, borderBottomColor: 'rgba(255,255,255,0.06)' }}>
          <ActivityIndicator size="small" color={C.accent} />
          <Text style={{ color: C.muted, fontSize: 15 }}>{title}</Text>
        </View>
      );
    }
    // Compact confirmed row (approved or found, not expanded for editing)
    if ((approved || status === 'found') && !expanded) {
      return (
        <Pressable
          onPress={onToggle}
          style={({ pressed }) => ({
            flexDirection: 'row', alignItems: 'center', paddingVertical: 15,
            paddingHorizontal: 4, gap: 14, opacity: pressed ? 0.7 : 1,
            borderBottomWidth: 1, borderBottomColor: 'rgba(255,255,255,0.06)',
          })}
        >
          <View style={{ width: 24, height: 24, borderRadius: 12, backgroundColor: 'rgba(74,222,128,0.12)', borderWidth: 1, borderColor: 'rgba(74,222,128,0.28)', alignItems: 'center', justifyContent: 'center' }}>
            <Text style={{ color: C.green, fontSize: 11, fontWeight: '800' }}>✓</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ color: C.text, fontSize: 15, fontWeight: '500' }}>{title}</Text>
            {!!hint && <Text style={{ color: C.muted, fontSize: 12, marginTop: 2 }} numberOfLines={1}>{hint}</Text>}
          </View>
          <Text style={{ color: C.muted, fontSize: 12 }}>Edit</Text>
        </Pressable>
      );
    }
    // Attention card for review sections, or expanded found section
    const isAttention = status === 'review' && !approved;
    return (
      <View style={{
        backgroundColor: isAttention ? '#1E1B13' : '#21252D',
        borderColor: isAttention ? 'rgba(200,169,126,0.35)' : 'rgba(74,222,128,0.22)',
        borderWidth: isAttention ? 1.5 : 1,
        borderRadius: 20, marginBottom: 16, overflow: 'hidden',
      }}>
        <Pressable
          onPress={isAttention ? undefined : onToggle}
          style={{ paddingHorizontal: 20, paddingTop: 18, paddingBottom: isAttention ? 4 : 14 }}
        >
          <Text style={{ color: isAttention ? C.accent : C.green, fontSize: 11, fontWeight: '700', letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 6 }}>
            {isAttention ? 'Needs your input' : 'Confirmed — tap to collapse'}
          </Text>
          <Text style={{ color: C.text, fontSize: 17, fontWeight: '600' }}>{title}</Text>
        </Pressable>
        {draft && (
          <View style={{ paddingHorizontal: 20, paddingBottom: 20 }}>
            <SectionDetail sectionKey={sectionKey} draft={draft} onDraftChange={onDraftChange} />
            <Pressable
              onPress={onApprove}
              style={({ pressed }) => ({
                borderRadius: BTN.primary.radius,
                overflow: 'hidden',
                marginTop: 16,
                borderWidth: approved ? 1 : 0,
                borderColor: 'rgba(74,222,128,0.35)',
                opacity: pressed ? 0.85 : 1,
              })}
            >
              {approved ? (
                <View style={{ backgroundColor: 'rgba(74,222,128,0.10)', paddingVertical: 13, alignItems: 'center' }}>
                  <Text style={{ color: C.green, fontWeight: '700', fontSize: 14 }}>✓ Confirmed</Text>
                </View>
              ) : (
                <LinearGradient
                  colors={BTN.primary.gradient}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 0, y: 1 }}
                  style={{ paddingVertical: 13, alignItems: 'center', borderRadius: BTN.primary.radius }}
                >
                  <Text style={{ color: BTN.primary.text, fontWeight: '700', fontSize: 14 }}>Looks good</Text>
                </LinearGradient>
              )}
            </Pressable>
            {isAttention && !approved && (
              <Pressable onPress={onSkip} style={{ paddingTop: 12, alignItems: 'center' }}>
                <Text style={{ color: C.muted, fontSize: 12 }}>Skip — I'll fill in later</Text>
              </Pressable>
            )}
          </View>
        )}
      </View>
    );
  }
  // ── End streamlined ──────────────────────────────────────────────────

  return (
    <View style={{
      ...REVIEW_CARD,
      ...variantCard,
      borderWidth: 1,
      marginBottom: variant === 'cinematic' ? 18 : 16,
      overflow: 'hidden',
    }}>
      <Pressable
        onPress={isLoading ? undefined : onToggle}
        style={({ pressed }) => ({
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingHorizontal: variant === 'editorial' ? 20 : 22,
          paddingVertical: variant === 'editorial' ? 18 : 20,
          minHeight: variant === 'cinematic' ? 96 : 88,
          opacity: pressed && !isLoading ? 0.84 : 1,
        })}
      >
        <View style={{ flex: 1, marginRight: 14 }}>
          <Text style={{
            color: toneColor,
            fontSize: 11,
            fontWeight: '700',
            letterSpacing: variant === 'editorial' ? 0.3 : 0.8,
            textTransform: variant === 'editorial' ? 'none' : 'uppercase',
            marginBottom: 8,
          }}>
            {variant === 'editorial' ? tone : tone}
          </Text>
          <Text style={{ color: C.text, fontSize: titleSize, fontWeight: variant === 'editorial' ? '500' : '600' }}>{title}</Text>
          {variant === 'cinematic' && spotlight && (
            <Text style={{ color: '#F2A1D0', fontSize: 12, lineHeight: 18, marginTop: 8 }}>
              AI staged this section for review now
            </Text>
          )}
          {!!hint && !expanded && (
            <Text style={{ color: C.text2, fontSize: variant === 'editorial' ? 13 : 12, lineHeight: 18, marginTop: 8 }} numberOfLines={2}>
              {hint}
            </Text>
          )}
        </View>

        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <StatusPill status={approved ? 'found' : status} />
          {!isLoading && (
            <Text style={{ color: C.muted, fontSize: 12 }}>
              {expanded ? '^' : 'v'}
            </Text>
          )}
        </View>
      </Pressable>

      {expanded && !isLoading && draft && (
        <View style={{
          borderTopWidth: 1,
          borderTopColor: variant === 'cinematic' ? 'rgba(193,53,132,0.16)' : 'rgba(255,255,255,0.06)',
          paddingHorizontal: variant === 'editorial' ? 20 : 24,
          paddingTop: 18,
          paddingBottom: 22,
          backgroundColor: variant === 'cinematic' ? 'rgba(255,255,255,0.01)' : 'transparent',
        }}>
          <SectionDetail sectionKey={sectionKey} draft={draft} onDraftChange={onDraftChange} />

          <View style={{ flexDirection: variant === 'cinematic' ? 'row' : 'column', justifyContent: 'space-between', alignItems: variant === 'editorial' ? 'stretch' : 'flex-end', gap: 10, marginTop: 16 }}>
            {variant === 'cinematic' && (
              <Pressable
                onPress={onToggle}
                style={({ pressed }) => ({
                  paddingHorizontal: 18,
                  paddingVertical: 11,
                  borderRadius: 999,
                  borderWidth: 1,
                  borderColor: 'rgba(255,255,255,0.10)',
                  backgroundColor: 'rgba(255,255,255,0.03)',
                  opacity: pressed ? 0.78 : 1,
                })}
              >
                <Text style={{ color: C.text2, fontSize: 12, fontWeight: '700' }}>
                  {expanded ? 'Close editor' : 'Edit section'}
                </Text>
              </Pressable>
            )}
            <View style={{ flexDirection: variant === 'cinematic' ? 'row' : 'column', gap: 10 }}>
              {variant === 'cinematic' && !approved && !skipped && (
                <Pressable
                  onPress={onSkip}
                  style={({ pressed }) => ({
                    paddingHorizontal: 18,
                    paddingVertical: 11,
                    borderRadius: 999,
                    alignItems: 'center',
                    backgroundColor: 'rgba(255,255,255,0.03)',
                    borderWidth: 1,
                    borderColor: 'rgba(255,255,255,0.10)',
                    opacity: pressed ? 0.78 : 1,
                  })}
                >
                  <Text style={{ fontSize: 12, fontWeight: '700', color: C.text2 }}>Skip section</Text>
                </Pressable>
              )}
            <Pressable
              onPress={onApprove}
              style={({ pressed }) => ({
                paddingHorizontal: 18,
                paddingVertical: 11,
                borderRadius: variant === 'editorial' ? 14 : 999,
                alignItems: 'center',
                backgroundColor: approved
                  ? 'rgba(74,222,128,0.10)'
                  : variant === 'cinematic'
                  ? 'rgba(193,53,132,0.14)'
                  : 'rgba(200,169,126,0.10)',
                borderWidth: 1,
                borderColor: approved
                  ? 'rgba(74,222,128,0.35)'
                  : variant === 'cinematic'
                  ? 'rgba(193,53,132,0.30)'
                  : 'rgba(200,169,126,0.35)',
                opacity: pressed ? 0.78 : 1,
              })}
            >
              <Text style={{
                fontSize: 12,
                fontWeight: '700',
                color: approved ? C.green : variant === 'cinematic' ? '#F2A1D0' : C.accent,
              }}>
                {approved ? 'Approved' : 'Approve section'}
              </Text>
            </Pressable>
            </View>
          </View>

          {status === 'review' && (
            <Text style={{ color: C.muted, fontSize: 12, lineHeight: 18, marginTop: 14 }}>
              Nothing useful was detected here. You can edit it now or finish it later in settings.
            </Text>
          )}
        </View>
      )}
    </View>
  );
}

// Main screen

export default function ScrapeScreen() {
  const { setAuth } = useAuth();

  const [phase,            setPhase]            = useState<Phase>('input');
  const [instagramHandle,  setInstagramHandle]  = useState('');
  const [igStatus,         setIgStatus]         = useState<InstagramConnectStatus | null>(null);
  const [connectingIg,     setConnectingIg]     = useState(false);
  const [websiteUrl,       setWebsiteUrl]       = useState('');
  const [draft,            setDraft]            = useState<Draft | null>(null);
  const [sectionStatus,    setSectionStatus]    = useState<Record<SectionKey, SectionStatus>>(LOADING_STATUS);
  const [approvedSections, setApprovedSections] = useState<Record<SectionKey, boolean>>(INITIAL_APPROVED);
  const [dismissedSections, setDismissedSections] = useState<Record<SectionKey, boolean>>(INITIAL_DISMISSED);
  const [expandedSection,  setExpandedSection]  = useState<SectionKey | null>(null);
  const [error,            setError]            = useState<string | null>(null);
  const [busy,             setBusy]             = useState(false);
  const [reviewDesign,     setReviewDesign]     = useState<ReviewDesign>('luxury');

  const sectionsAnim  = useRef(new Animated.Value(0)).current;
  const inputFadeAnim = useRef(new Animated.Value(1)).current;

  const readyForConfirm = useMemo(() => {
    if (phase !== 'done') return false;
    return Object.values(sectionStatus).every(v => v !== 'loading');
  }, [phase, sectionStatus]);

  const anyApproved = useMemo(
    () => Object.values(approvedSections).some(Boolean),
    [approvedSections],
  );
  const approvedCount = useMemo(
    () => Object.values(approvedSections).filter(Boolean).length,
    [approvedSections],
  );
  const foundCount = useMemo(
    () => Object.values(sectionStatus).filter((value) => value === 'found').length,
    [sectionStatus],
  );
  const reviewCount = useMemo(
    () => Object.values(sectionStatus).filter((value) => value === 'review').length,
    [sectionStatus],
  );
  const completedCount = useMemo(
    () => Object.values(approvedSections).filter(Boolean).length + Object.values(dismissedSections).filter(Boolean).length,
    [approvedSections, dismissedSections],
  );
  const currentCinematicSection = useMemo(
    () => SECTION_ORDER.find((key) => !approvedSections[key] && !dismissedSections[key]) ?? null,
    [approvedSections, dismissedSections],
  );
  const pendingCinematicCount = useMemo(
    () => SECTION_ORDER.filter((key) => !approvedSections[key] && !dismissedSections[key]).length,
    [approvedSections, dismissedSections],
  );

  function focusNextSection(nextApproved = approvedSections, nextDismissed = dismissedSections) {
    const nextKey = SECTION_ORDER.find((key) => !nextApproved[key] && !nextDismissed[key]) ?? null;
    setExpandedSection(nextKey);
  }

  function handleApproveSection(sectionKey: SectionKey) {
    const nextApproved = { ...approvedSections, [sectionKey]: true };
    const nextDismissed = { ...dismissedSections, [sectionKey]: false };
    setApprovedSections(nextApproved);
    setDismissedSections(nextDismissed);
    if (reviewDesign === 'cinematic') focusNextSection(nextApproved, nextDismissed);
  }

  function handleSkipSection(sectionKey: SectionKey) {
    const nextDismissed = { ...dismissedSections, [sectionKey]: true };
    setDismissedSections(nextDismissed);
    if (reviewDesign === 'cinematic') focusNextSection(approvedSections, nextDismissed);
  }

  function handleSectionDraftChange(sectionKey: SectionKey, nextDraft: Draft) {
    setDraft(nextDraft);
    setSectionStatus((prev) => ({
      ...prev,
      [sectionKey]: resolveSection(nextDraft, sectionKey),
    }));
  }

  const igConnected = !!igStatus?.connected;

  useEffect(() => {
    if (phase !== 'done' || reviewDesign !== 'cinematic') return;
    if (!currentCinematicSection) return;
    if (expandedSection === currentCinematicSection) return;
    setExpandedSection(currentCinematicSection);
  }, [phase, reviewDesign, currentCinematicSection, expandedSection]);

  // On mount: check if Instagram already linked for this session
  useEffect(() => {
    const token = onboardingData.pendingAccessToken;
    if (!token) return;
    getInstagramConnectStatus(token)
      .then(s => {
        if (!s?.connected) return;
        setIgStatus(s);
        if (s.instagram_username) setInstagramHandle(s.instagram_username.replace(/^@/, ''));
      })
      .catch(() => {});
  }, []);

  function revealSections() {
    Animated.spring(sectionsAnim, {
      toValue: 1,
      useNativeDriver: true,
      tension: 60,
      friction: 9,
    }).start();
  }

  // â”€â”€ Instagram OAuth â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  async function connectInstagram() {
    const token = onboardingData.pendingAccessToken;
    if (!token) { setError('Session expired â€” please log in again.'); return; }

    setError(null);
    setConnectingIg(true);
    try {
      const { auth_url } = await startInstagramConnect(REDIRECT_URI, token);
      const result = await WebBrowser.openAuthSessionAsync(auth_url, REDIRECT_URI);

      if (result.type === 'cancel' || result.type === 'dismiss') return;
      if (result.type !== 'success' || !result.url) throw new Error('Instagram connection did not complete.');

      const redirectUrl = new URL(result.url);
      if (redirectUrl.searchParams.get('ok') !== '1') {
        throw new Error(redirectUrl.searchParams.get('error') || 'Instagram connection failed.');
      }

      const s = await getInstagramConnectStatus(token);
      setIgStatus(s);
      if (s.instagram_username) {
        const handle = s.instagram_username.replace(/^@/, '');
        setInstagramHandle(handle);
        onboardingData.igStatus = s;
        onboardingData.igHandle = handle;
      }
    } catch (err: any) {
      setError(err?.message || 'Could not connect Instagram right now.');
    } finally {
      setConnectingIg(false);
    }
  }

  // â”€â”€ Analyze â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  async function handleAnalyze() {
    const cleanUrl = websiteUrl.trim();

    setError(null);
    setDraft(null);
    setApprovedSections({ ...INITIAL_APPROVED });
    setDismissedSections({ ...INITIAL_DISMISSED });
    setSectionStatus({ ...LOADING_STATUS });
    setExpandedSection(null);
    sectionsAnim.setValue(0);
    inputFadeAnim.setValue(1); // reset in case of re-analyze
    setPhase('analyzing');
    revealSections();
    // Fade out the input cards as sections appear
    Animated.timing(inputFadeAnim, {
      toValue: 0,
      duration: 280,
      useNativeDriver: true,
    }).start();

    try {
      const handle = instagramHandle.replace('@', '').trim();
      let igData: any = {};
      if (igConnected && igStatus) {
        igData = {
          ...igStatus,
          username:   igStatus.instagram_username || handle,
          ig_user_id: (igStatus as any).instagram_user_id ?? null,
        };
      } else if (handle) {
        igData = { username: handle };
      }

      const token = onboardingData.pendingAccessToken || undefined;
      const scanData = cleanUrl
        ? await scanWebsite(cleanUrl.replace(/^https?:\/\//i, ''), token)
        : {};

      const nextDraft = buildDraft(scanData, igData, handle);
      setDraft(nextDraft);

      // Stagger reveals â€” 170 ms apart
      for (const key of SECTION_ORDER) {
        await sleep(170);
        setSectionStatus(prev => ({ ...prev, [key]: resolveSection(nextDraft, key) }));
      }

      setPhase('done');
    } catch (err: any) {
      setSectionStatus({
        instagram: 'review', business_name: 'review', address: 'review',
        working_hours: 'review', services: 'review', cancellation: 'review',
      });
      setPhase('done');
      setError(err.message || 'Could not analyze the page â€” check the URL and try again.');
    }
  }

  // â”€â”€ Shared provider create + navigate â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  async function createAndGo(
    payload: Parameters<typeof createOnboardingProvider>[0],
    workingHours?: Record<string, any>,
  ) {
    const token = onboardingData.pendingAccessToken;
    if (!token) throw new Error('Session expired â€” please log in again.');

    const result = await createOnboardingProvider(payload, token);

    if (workingHours && Object.keys(workingHours).length > 0) {
      await applyScanToProviderProfile({ working_hours: workingHours }, token).catch(() => {});
    }

    const me = await getProviderSession(token).catch(() => null);
    await setAuth(
      token,
      result.provider_id,
      me?.provider_name ?? result.name,
      result.slug ?? '',
    );

    const pt = await registerForPushNotifications();
    if (pt) await saveTokenToBackend(pt);

    router.replace('/(tabs)/');
  }

  // â”€â”€ Launch â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  async function handleLaunch() {
    setError(null);
    setBusy(true);
    try {
      const fallback = onboardingData.email?.split('@')[0] || 'New Provider';
      await createAndGo(
        {
          name:                draft?.name || fallback,
          city:                draft?.city ?? null,
          bio:                 draft?.bio ?? null,
          instagram_username:  draft?.instagram_username || null,
          amenity_keys:        draft?.amenity_keys ?? [],
          scanned_services:    draft?.services ?? [],
          booking_policy:      draft?.booking_policy ?? null,
          cancellation_policy: draft?.cancellation_policy ?? null,
          ig_user_id:          draft?.ig_user_id ?? null,
          ig_access_token:     null,
        },
        draft?.working_hours,
      );
    } catch (err: any) {
      setError(err.message || 'Something went wrong. Try again.');
      setBusy(false);
    }
  }

  // â”€â”€ Skip â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  async function handleSkip() {
    setError(null);
    setBusy(true);
    try {
      const fallback = onboardingData.email?.split('@')[0] || 'New Provider';
      await createAndGo({
        name:                fallback,
        city:                null,
        bio:                 null,
        instagram_username:  instagramHandle.trim() || null,
        amenity_keys:        [],
        scanned_services:    [],
        booking_policy:      null,
        cancellation_policy: null,
        ig_user_id:          (igStatus as any)?.instagram_user_id ?? null,
        ig_access_token:     null,
      });
    } catch (err: any) {
      setError(err.message || 'Something went wrong. Try again.');
      setBusy(false);
    }
  }

  // â”€â”€ Render â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: C.bg }}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ flexGrow: 1, paddingHorizontal: 24, paddingBottom: 40 }}
          keyboardShouldPersistTaps="handled"
        >

          {/* â”€â”€ Logo â”€â”€ */}
          <Text style={{
            color: C.muted, fontSize: 10, fontWeight: '700',
            letterSpacing: 5, textTransform: 'uppercase',
            marginTop: 24, marginBottom: 36,
          }}>
            Fixmeapp
          </Text>

          {/* ── Heading — analyzing + done phases only ── */}
          {phase !== 'input' && (
            <>
              <Text style={[STEP_H1, { marginBottom: 10 }]}>
                {phase === 'done' ? 'Review your profile' : 'Getting to know you…'}
              </Text>
              <Text style={{ color: C.text2, fontSize: 17, lineHeight: 27, marginBottom: 32 }}>
                {phase === 'done'
                  ? 'Approve what looks right — nothing is saved until you continue.'
                  : 'Reading your Instagram. This takes 10–20 seconds.'}
              </Text>
            </>
          )}

          {/* â”€â”€ Compact scanned-URL bar (done phase only) â”€â”€ */}
          {phase === 'done' && !!websiteUrl && (
            <View style={{
              flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
              backgroundColor: C.card, borderColor: C.border, borderWidth: 1,
              borderRadius: 14, paddingHorizontal: 16, paddingVertical: 12, marginBottom: 24,
            }}>
              <Text style={{ color: C.text2, fontSize: 13, flex: 1 }} numberOfLines={1}>
                {websiteUrl.replace(/^https?:\/\//i, '')}
              </Text>
              <Pressable
                onPress={() => { inputFadeAnim.setValue(1); setPhase('input'); }}
                style={{ marginLeft: 12 }}
              >
                <Text style={{ color: C.accent, fontSize: 13, fontWeight: '600' }}>Change</Text>
              </Pressable>
            </View>
          )}

          {/* ── Input phase — cinematic Instagram connect ── */}
          {phase === 'input' && (
          <Animated.View style={{ opacity: inputFadeAnim, flex: 1, paddingTop: 48 }}>

            {/* ⚡ FILE CHECK — remove after confirming */}
            <Text style={{ color: 'red', fontSize: 11, marginBottom: 8 }}>✅ scrape.tsx v2 loaded</Text>

            {/* Top content */}
            <View>
              {/* Headline */}
              <Text style={{
                color: C.text, fontSize: 36, fontWeight: '800',
                letterSpacing: -0.8, lineHeight: 43, marginBottom: 16,
              }}>
                Connect your{'\n'}Instagram
              </Text>

              {/* Subline */}
              <Text style={{
                color: C.text2, fontSize: 16, lineHeight: 26,
                maxWidth: 300, marginBottom: 52,
              }}>
                This way the AI bot will be able to handle your booking requests in your DMs.
              </Text>

              {/* Not connected — connect button */}
              {!igConnected && (
                <Pressable
                  onPress={connectInstagram}
                  disabled={connectingIg}
                  style={({ pressed }) => ({
                    alignSelf: 'center',
                    backgroundColor: 'rgba(193,53,132,0.10)',
                    borderWidth: 1, borderColor: 'rgba(193,53,132,0.28)',
                    borderRadius: BTN.secondary.radius,
                    paddingVertical: 16, paddingHorizontal: 24,
                    opacity: connectingIg ? 0.55 : pressed ? 0.78 : 1,
                  })}
                >
                  {connectingIg
                    ? <ActivityIndicator color={C.ig} />
                    : <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                        <InstagramIcon size={20} color={C.ig} />
                        <Text style={{ color: C.ig, fontWeight: '700', fontSize: 16 }}>
                          Connect Instagram
                        </Text>
                      </View>}
                </Pressable>
              )}

              {/* Connected state */}
              {igConnected && (
                <View style={{
                  flexDirection: 'row', alignItems: 'center', gap: 14,
                  alignSelf: 'flex-start',
                  backgroundColor: 'rgba(74,222,128,0.06)',
                  borderWidth: 1, borderColor: 'rgba(74,222,128,0.18)',
                  borderRadius: BTN.secondary.radius,
                  paddingVertical: 16, paddingHorizontal: 18,
                }}>
                  <View style={{
                    width: 28, height: 28, borderRadius: 14,
                    backgroundColor: 'rgba(74,222,128,0.14)',
                    borderWidth: 1, borderColor: 'rgba(74,222,128,0.28)',
                    alignItems: 'center', justifyContent: 'center',
                  }}>
                    <Text style={{ color: C.green, fontSize: 13, fontWeight: '800' }}>✓</Text>
                  </View>
                  <View>
                    <Text style={{ color: C.green, fontSize: 11, fontWeight: '700', letterSpacing: 0.6, textTransform: 'uppercase', marginBottom: 3 }}>Connected</Text>
                    <Text style={{ color: C.text, fontSize: 15, fontWeight: '500' }}>
                      @{igStatus?.instagram_username || instagramHandle}
                    </Text>
                  </View>
                </View>
              )}

              {!!error && (
                <Text style={{ color: C.error, fontSize: 12, marginTop: 16 }}>
                  {error}
                </Text>
              )}
            </View>

            {/* Flex spacer — pushes bottom row to the bottom of the screen */}
            <View style={{ flex: 1 }} />

            {/* Bottom row — Skip left, Continue right */}
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingBottom: 8 }}>
              <Pressable onPress={handleSkip} disabled={busy}>
                <Text style={{ color: C.muted, fontSize: 13 }}>Skip for now</Text>
              </Pressable>
              <Pressable
                onPress={() => router.push('/(auth)/onboarding/scrape-website' as any)}
                disabled={busy}
                style={({ pressed }) => ({
                  borderRadius: BTN.secondary.radius,
                  borderWidth: 1, borderColor: BTN.secondary.border,
                  overflow: 'hidden',
                  opacity: busy ? 0.35 : pressed ? 0.80 : 1,
                })}
              >
                <LinearGradient
                  colors={BTN.secondary.gradient}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 0, y: 1 }}
                  style={{ borderRadius: BTN.secondary.radius, paddingVertical: 12, paddingHorizontal: 22, alignItems: 'center' }}
                >
                  <Text style={{ color: BTN.secondary.text, fontWeight: '500', fontSize: 15 }}>Continue</Text>
                </LinearGradient>
              </Pressable>
            </View>

          </Animated.View>
          )} {/* end input phase */}

          {/* Analyzing card */}
          {phase === 'analyzing' && (
            <View style={{
              backgroundColor: C.card, borderColor: C.border, borderWidth: 1,
              borderRadius: 24, padding: 30,
              alignItems: 'center', marginBottom: 24,
            }}>
              <ActivityIndicator color={C.accent} size="large" />
              <Text style={{
                color: C.text, fontSize: 26, fontWeight: '800',
                marginTop: 18, marginBottom: 8,
              }}>
                Getting to know you...
              </Text>
              <Text style={{
                color: C.text2, fontSize: 16, lineHeight: 25,
                textAlign: 'center',
              }}>
                We're reading your services, hours, prices and cancellation policy. Nothing is saved until you approve it.
              </Text>
            </View>
          )}

          {/* Review cards */}
          {phase !== 'input' && (
            <Animated.View style={{
              opacity: sectionsAnim,
              transform: [{
                translateY: sectionsAnim.interpolate({
                  inputRange: [0, 1], outputRange: [24, 0],
                }),
              }],
              marginBottom: 8,
            }}>
              {__DEV__ && phase === 'done' && (
                <View style={{ marginBottom: 20 }}>
                  <Text style={{ color: C.muted, fontSize: 11, fontWeight: '700', letterSpacing: 0.8, marginBottom: 10 }}>
                    REVIEW DESIGN
                  </Text>
                  <View style={{ flexDirection: 'row', gap: 8 }}>
                    {REVIEW_VARIANTS.map((variant) => {
                      const active = reviewDesign === variant.key;
                      return (
                        <Pressable
                          key={variant.key}
                          onPress={() => setReviewDesign(variant.key)}
                          style={{
                            paddingHorizontal: 12,
                            paddingVertical: 9,
                            borderRadius: 999,
                            backgroundColor: active ? 'rgba(200,169,126,0.16)' : 'rgba(255,255,255,0.04)',
                            borderWidth: 1,
                            borderColor: active ? 'rgba(200,169,126,0.32)' : 'rgba(255,255,255,0.08)',
                          }}
                        >
                          <Text style={{ color: active ? C.accent : C.text2, fontSize: 12, fontWeight: '700' }}>
                            {variant.label}
                          </Text>
                        </Pressable>
                      );
                    })}
                  </View>
                  <Text style={{ color: C.muted, fontSize: 12, lineHeight: 18, marginTop: 10 }}>
                    {REVIEW_VARIANTS.find((variant) => variant.key === reviewDesign)?.caption}
                  </Text>
                </View>
              )}

              <Text style={{
                color: C.text,
                fontSize: reviewDesign === 'cinematic' ? 30 : reviewDesign === 'editorial' ? 24 : reviewDesign === 'streamlined' ? 28 : 26,
                fontWeight: reviewDesign === 'editorial' ? '700' : '800',
                marginBottom: 6,
                letterSpacing: reviewDesign === 'cinematic' ? -0.6 : reviewDesign === 'streamlined' ? -0.4 : 0,
              }}>
                {reviewDesign === 'cinematic'
                  ? 'Your profile signal'
                  : reviewDesign === 'editorial'
                  ? 'Review the extracted profile'
                  : reviewDesign === 'streamlined'
                  ? (foundCount >= 4 ? 'Your profile is ready.' : foundCount >= 2 ? 'Almost there.' : "Let's build your profile.")
                  : "Here's what we found"}
              </Text>
              <Text style={{
                color: C.text2,
                fontSize: reviewDesign === 'editorial' ? 15 : 14,
                lineHeight: reviewDesign === 'editorial' ? 24 : 22,
                marginBottom: reviewDesign === 'streamlined' ? 24 : 18,
                maxWidth: reviewDesign === 'editorial' ? 320 : undefined,
              }}>
                {reviewDesign === 'cinematic'
                  ? 'AI is staging one section at a time. Edit, approve, or skip each result to move the profile forward.'
                  : reviewDesign === 'editorial'
                  ? 'Read through each section in calm order. Edit if needed, approve what is correct, and continue when the profile feels right.'
                  : reviewDesign === 'streamlined'
                  ? 'AI scanned your Instagram and website. Anything highlighted needs a quick look — the rest is already confirmed.'
                  : 'Open each card, edit what looks off, then approve the parts you want to keep.'}
              </Text>

              {phase === 'done' && reviewDesign === 'streamlined' && (
                <Text style={{ color: C.muted, fontSize: 13, lineHeight: 20, marginBottom: 24 }}>
                  {foundCount} of {SECTION_ORDER.length} sections confirmed
                  {reviewCount > 0 ? ` · ${reviewCount} need${reviewCount === 1 ? 's' : ''} your input` : ' · all ready'}
                </Text>
              )}

              {phase === 'done' && reviewDesign !== 'streamlined' && (
                <View style={{
                  ...REVIEW_CARD,
                  backgroundColor: reviewDesign === 'cinematic' ? '#19171F' : reviewDesign === 'editorial' ? '#252932' : REVIEW_CARD.backgroundColor,
                  borderColor: reviewDesign === 'cinematic' ? 'rgba(193,53,132,0.20)' : reviewDesign === 'editorial' ? 'rgba(255,255,255,0.06)' : REVIEW_CARD.borderColor,
                  flexDirection: reviewDesign === 'editorial' ? 'column' : 'row',
                  flexWrap: 'wrap',
                  gap: 10,
                  paddingHorizontal: 16,
                  paddingVertical: reviewDesign === 'cinematic' ? 16 : 14,
                  marginBottom: 20,
                }}>
                  <View style={{
                    backgroundColor: 'rgba(255,255,255,0.04)',
                    borderColor: 'rgba(255,255,255,0.08)',
                    borderWidth: 1,
                    borderRadius: reviewDesign === 'editorial' ? 14 : 999,
                    paddingHorizontal: 12,
                    paddingVertical: 7,
                  }}>
                    <Text style={{ color: C.text, fontSize: 12, fontWeight: '700' }}>{reviewDesign === 'cinematic' ? completedCount + ' reviewed' : approvedCount + ' approved'}</Text>
                  </View>
                  <View style={{
                    backgroundColor: 'rgba(74,222,128,0.10)',
                    borderColor: 'rgba(74,222,128,0.18)',
                    borderWidth: 1,
                    borderRadius: reviewDesign === 'editorial' ? 14 : 999,
                    paddingHorizontal: 12,
                    paddingVertical: 7,
                  }}>
                    <Text style={{ color: C.green, fontSize: 12, fontWeight: '700' }}>{reviewDesign === 'cinematic' ? (currentCinematicSection ? SECTION_ORDER.indexOf(currentCinematicSection) + 1 : SECTION_ORDER.length) + '/' + SECTION_ORDER.length + ' now' : foundCount + ' found'}</Text>
                  </View>
                  <View style={{
                    backgroundColor: reviewDesign === 'cinematic' ? 'rgba(193,53,132,0.12)' : 'rgba(200,169,126,0.10)',
                    borderColor: reviewDesign === 'cinematic' ? 'rgba(193,53,132,0.20)' : 'rgba(200,169,126,0.18)',
                    borderWidth: 1,
                    borderRadius: reviewDesign === 'editorial' ? 14 : 999,
                    paddingHorizontal: 12,
                    paddingVertical: 7,
                  }}>
                    <Text style={{ color: reviewDesign === 'cinematic' ? '#F2A1D0' : C.accent, fontSize: 12, fontWeight: '700' }}>{reviewDesign === 'cinematic' ? pendingCinematicCount + ' left' : reviewCount + ' to review'}</Text>
                  </View>
                </View>
              )}

              {(reviewDesign === 'cinematic'
                ? SECTION_ORDER.filter((key) => approvedSections[key] || dismissedSections[key] || key === currentCinematicSection)
                : reviewDesign === 'streamlined'
                ? [...SECTION_ORDER].sort((a, b) => {
                    const aNeedsInput = sectionStatus[a] === 'review' && !approvedSections[a] ? 0 : 1;
                    const bNeedsInput = sectionStatus[b] === 'review' && !approvedSections[b] ? 0 : 1;
                    return aNeedsInput - bNeedsInput;
                  })
                : SECTION_ORDER
              ).map(key => (
                <SectionRow
                  key={key}
                  title={SECTION_TITLES[key]}
                  sectionKey={key}
                  hint={sectionHint(key, draft)}
                  status={sectionStatus[key]}
                  approved={approvedSections[key]}
                  skipped={dismissedSections[key]}
                  onApprove={() => handleApproveSection(key)}
                  onSkip={() => handleSkipSection(key)}
                  expanded={reviewDesign === 'cinematic' ? expandedSection === key || key === currentCinematicSection : expandedSection === key}
                  onToggle={() => setExpandedSection(prev => prev === key ? null : key)}
                  draft={draft}
                  onDraftChange={(nextDraft) => handleSectionDraftChange(key, nextDraft)}
                  variant={reviewDesign}
                  spotlight={reviewDesign === 'cinematic' && key === currentCinematicSection}
                />
              ))}
            </Animated.View>
          )}

          {/* Continue card */}
          {phase === 'done' && anyApproved && reviewDesign !== 'streamlined' && (
            <View style={{
              ...REVIEW_CARD,
              backgroundColor: reviewDesign === 'cinematic' ? '#18171D' : reviewDesign === 'editorial' ? '#252932' : REVIEW_CARD.backgroundColor,
              borderColor: reviewDesign === 'cinematic' ? 'rgba(193,53,132,0.20)' : reviewDesign === 'editorial' ? 'rgba(255,255,255,0.06)' : REVIEW_CARD.borderColor,
              paddingHorizontal: 18,
              paddingTop: 18,
              paddingBottom: 16,
              marginTop: 4,
              marginBottom: 12,
            }}>
              <Text style={{ color: C.text, fontSize: reviewDesign === 'cinematic' ? 17 : 15, fontWeight: reviewDesign === 'editorial' ? '500' : '600', marginBottom: 6 }}>
                {reviewDesign === 'cinematic' ? 'Lock this profile in' : reviewDesign === 'editorial' ? 'Continue when this feels right' : 'Ready to continue'}
              </Text>
              <Text style={{ color: C.text2, fontSize: 13, lineHeight: 20, marginBottom: 14 }}>
                {reviewDesign === 'cinematic'
                  ? 'You are about to use these approved sections as the starting profile. Nothing is saved before you continue.'
                  : reviewDesign === 'editorial'
                  ? 'Take one final look. You can still edit before continuing, and nothing is saved until you do.'
                  : 'Nothing is saved until you continue. You can still change everything here.'}
              </Text>
              <Pressable
                onPress={handleLaunch}
                disabled={busy || !readyForConfirm || !anyApproved}
                style={({ pressed }) => ({
                  backgroundColor: reviewDesign === 'cinematic' ? '#F2A1D0' : C.accent,
                  borderRadius: reviewDesign === 'editorial' ? 14 : 18,
                  paddingVertical: 16,
                  alignItems: 'center',
                  opacity: busy || !readyForConfirm || !anyApproved ? 0.45 : pressed ? 0.85 : 1,
                })}
              >
                {busy
                  ? <ActivityIndicator color="#0D0D0D" />
                  : <Text style={{ color: '#0D0D0D', fontWeight: '700', fontSize: 16 }}>
                      Continue
                    </Text>}
              </Pressable>
            </View>
          )}

          {/* Streamlined continue — right-aligned compact pill */}
          {phase === 'done' && anyApproved && reviewDesign === 'streamlined' && (
            <View style={{ marginTop: 16, marginBottom: 12, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text style={{ color: C.muted, fontSize: 12, lineHeight: 18, flex: 1, marginRight: 16 }}>
                Nothing is saved until you continue.
              </Text>
              <Pressable
                onPress={handleLaunch}
                disabled={busy || !readyForConfirm || !anyApproved}
                style={({ pressed }) => ({
                  borderRadius: 20,
                  borderWidth: 1,
                  borderColor: BTN.secondary.border,
                  overflow: 'hidden',
                  opacity: busy || !readyForConfirm || !anyApproved ? 0.35 : pressed ? 0.80 : 1,
                })}
              >
                <LinearGradient
                  colors={BTN.secondary.gradient}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 0, y: 1 }}
                  style={{ paddingVertical: 12, paddingHorizontal: 22, alignItems: 'center', borderRadius: 20 }}
                >
                  {busy
                    ? <ActivityIndicator color={C.text} size="small" />
                    : <Text style={{ color: BTN.secondary.text, fontWeight: '500', fontSize: 15, letterSpacing: -0.1 }}>
                        Continue
                      </Text>}
                </LinearGradient>
              </Pressable>
            </View>
          )}

          {/* Skip — shown during done phase only */}
          {phase === 'done' && (
            <Pressable
              onPress={handleSkip}
              disabled={busy}
              style={{ paddingVertical: 14, alignItems: 'center' }}
            >
              <Text style={{ color: C.muted, fontSize: 12 }}>
                Skip for now — I'll fill in details later
              </Text>
            </Pressable>
          )}

        </ScrollView>

      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
