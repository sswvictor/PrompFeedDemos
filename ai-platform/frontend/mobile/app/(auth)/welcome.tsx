/**
 * WelcomeScreen
 * Phase 1: splash — cinematic lines + inline email input + "Send code →"
 * Phase 2: otp   — big digit input, auto-verifies on 6th digit
 *
 * Existing provider → /(tabs)/
 * New provider      → /(auth)/onboarding/scrape
 */
import { useState, useRef, useEffect } from 'react';
import {
  View, Text, TextInput, Pressable,
  ActivityIndicator, KeyboardAvoidingView,
  Platform, Animated,
} from 'react-native';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/stores/auth';
import { sendProviderCode, verifyProviderCode, getProviderSession } from '@/lib/api';
import { registerForPushNotifications, saveTokenToBackend } from '@/lib/notifications';
import { onboardingData } from './onboarding/_state';

type Phase = 'splash' | 'otp';

const LINES = [
  { text: 'More clients booked.',  delay: 700  },
  { text: 'Fewer DMs to answer.',  delay: 1700 },
  { text: "That's the deal.",      delay: 2700 },
];

const isEmail = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);

export default function WelcomeScreen() {
  const { setAuth } = useAuth();
  const [phase,   setPhase]   = useState<Phase>('splash');
  const [email,   setEmail]   = useState('');
  const [code,    setCode]    = useState('');
  const [devCode, setDevCode] = useState('');
  const [busy,    setBusy]    = useState(false);
  const [error,   setError]   = useState<string | null>(null);

  const lineAnims    = useRef(LINES.map(() => new Animated.Value(0))).current;
  const linesOutAnim = useRef(new Animated.Value(1)).current;
  const ctaAnim      = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (phase !== 'splash') return;
    // Lines enter one by one
    LINES.forEach((l, i) =>
      Animated.timing(lineAnims[i], {
        toValue: 1, duration: 900, delay: l.delay, useNativeDriver: true,
      }).start()
    );
    // Lines fade out after they've all settled (last line done at ~3600ms, +400ms settle)
    Animated.timing(linesOutAnim, {
      toValue: 0, duration: 700, delay: 4000, useNativeDriver: true,
    }).start();
    // Email fades in exactly 500ms after lines are gone (4000 + 700 + 500 = 5200ms)
    Animated.timing(ctaAnim, {
      toValue: 1, duration: 800, delay: 5200, useNativeDriver: true,
    }).start();
  }, [phase]);

  function replayIntro() {
    // Reset all animation values and replay the cinematic sequence
    lineAnims.forEach(a => a.setValue(0));
    linesOutAnim.setValue(1);
    ctaAnim.setValue(0);
    setPhase('splash');
    setError(null);
  }

  async function sendCode() {
    const e = email.trim().toLowerCase();
    if (!isEmail(e)) { setError('Enter a valid email'); return; }
    setError(null); setBusy(true);
    try {
      const res = await sendProviderCode(e);
      setDevCode(res.dev_code ?? '');
      setPhase('otp');
    } catch (err: any) {
      setError(err.message || 'Could not send code');
    } finally { setBusy(false); }
  }

  async function verify(val: string) {
    if (val.length !== 6) return;
    setError(null); setBusy(true);
    try {
      const e = email.trim().toLowerCase();
      const res = await verifyProviderCode(e, val);

      if (res.has_provider_profile && res.provider_id) {
        const me = await getProviderSession(res.access_token).catch(() => null);
        await setAuth(
          res.access_token,
          me?.provider_id  ?? res.provider_id,
          me?.provider_name ?? e,
          me?.slug ?? res.slug ?? '',
        );
        const pt = await registerForPushNotifications();
        if (pt) await saveTokenToBackend(pt);
        router.replace('/(tabs)/');
        return;
      }

      // New provider → onboarding
      onboardingData.email              = e;
      onboardingData.pendingAccessToken = res.access_token;
      onboardingData.isEmailVerified    = true;
      router.replace('/(auth)/onboarding/instagram-connect');
    } catch (err: any) {
      setError(err.message || 'Invalid code');
    } finally { setBusy(false); }
  }

  /* ── SPLASH ── */
  if (phase === 'splash') return (
    <SafeAreaView className="flex-1 bg-fixme-bg">
      <View className="flex-1">
        <View className="flex-1 px-6 pt-10 pb-10">

          <Pressable onPress={replayIntro} hitSlop={12}>
            <Text className="text-fixme-text-muted text-[10px] font-bold uppercase tracking-[0.42em]">
              Fixmeapp
            </Text>
          </Pressable>

          {/* Content area — both layers sit at the bottom of this flex-1 space */}
          <View style={{ flex: 1, position: 'relative' }}>

            {/* Layer 1: Cinematic lines — fade OUT after entrance */}
            <Animated.View style={{
              position: 'absolute', top: 0, bottom: 0, left: 0, right: 0,
              justifyContent: 'center', paddingBottom: 80, opacity: linesOutAnim,
            }}>
              {LINES.map((l, i) => (
                <Animated.Text key={i}
                  className="text-fixme-text-primary font-bold leading-tight tracking-tight"
                  style={{ fontSize: 38, opacity: lineAnims[i],
                    transform: [{ translateY: lineAnims[i].interpolate({ inputRange:[0,1], outputRange:[14,0] }) }] }}
                >{l.text}</Animated.Text>
              ))}
            </Animated.View>

            {/* Layer 2: Subtitle + email + button — fade IN after lines are gone */}
            <Animated.View
              style={{
                position: 'absolute', top: 0, bottom: 0, left: 0, right: 0,
                justifyContent: 'center', paddingBottom: 80,
                opacity: ctaAnim,
                transform: [{ translateY: ctaAnim.interpolate({ inputRange:[0,1], outputRange:[12,0] }) }],
              }}
              className="gap-4"
            >
              <Text className="text-fixme-text-muted text-xs uppercase tracking-[0.2em]">
                Login or sign up
              </Text>

              <TextInput
                className="bg-[#222] border border-[#444] rounded-xl px-4 py-4 text-fixme-text-primary text-sm tracking-normal"
                placeholder="your@email.com"
                placeholderTextColor="#555"
                value={email}
                onChangeText={v => { setEmail(v); setError(null); }}
                autoCapitalize="none"
                keyboardType="email-address"
                autoComplete="email"
                returnKeyType="send"
                onSubmitEditing={sendCode}
              />

              {error && <Text className="text-fixme-error text-xs">{error}</Text>}

              <Pressable onPress={sendCode} disabled={busy}
                className="self-end mt-3 bg-fixme-accent rounded-xl px-7 py-3 items-center active:opacity-80 disabled:opacity-50">
                {busy
                  ? <ActivityIndicator color="#131312" />
                  : <Text className="text-fixme-bg font-semibold text-xs">Send code →</Text>}
              </Pressable>

            </Animated.View>

          </View>
        </View>
      </View>
    </SafeAreaView>
  );

  /* ── OTP ── */
  return (
    <SafeAreaView className="flex-1 bg-fixme-bg">
      <KeyboardAvoidingView className="flex-1" behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <View className="flex-1 px-6 pt-10 pb-12">

          <Pressable onPress={() => { setPhase('splash'); setCode(''); setError(null); }}
            className="mb-10 self-start">
            <Text className="text-fixme-text-muted text-lg">←</Text>
          </Pressable>

          <Pressable onPress={() => { setPhase('splash'); setCode(''); setError(null); }} hitSlop={12}>
            <Text className="text-fixme-text-muted text-[10px] font-bold uppercase tracking-[0.42em] mb-10">
              Fixmeapp
            </Text>
          </Pressable>

          <Text className="text-fixme-text-primary font-bold text-2xl mb-2">Check your inbox</Text>
          <Text className="text-fixme-text-secondary text-sm mb-8 leading-relaxed">
            Code sent to <Text className="text-fixme-accent font-medium">{email}</Text>
          </Text>

          {!!devCode && (
            <View className="bg-fixme-card border border-fixme-border rounded-xl px-4 py-3 mb-5 items-center">
              <Text className="text-fixme-text-muted text-[10px] mb-1 uppercase tracking-widest">Dev code</Text>
              <Text className="text-fixme-accent font-bold text-2xl tracking-[0.4em]">{devCode}</Text>
            </View>
          )}

          <TextInput
            className="bg-fixme-card border border-fixme-border rounded-2xl px-4 py-5 text-fixme-text-primary text-center font-bold mb-2"
            style={{ fontSize: 34, letterSpacing: 12 }}
            placeholder="000000"
            placeholderTextColor="rgba(245,245,240,0.15)"
            value={code}
            onChangeText={val => {
              const v = val.replace(/\D/g, '').slice(0, 6);
              setCode(v);
              setError(null);
              if (v.length === 6) setTimeout(() => verify(v), 100);
            }}
            keyboardType="number-pad"
            maxLength={6}
            autoFocus
          />

          <Text className="text-fixme-text-muted text-[11px] text-center mb-5">
            Auto-verifies on the 6th digit
          </Text>

          {error && <Text className="text-fixme-error text-xs text-center mb-4">{error}</Text>}

          <Pressable onPress={() => verify(code)} disabled={busy}
            className="self-center bg-fixme-accent rounded-xl px-10 py-4 items-center active:opacity-80 disabled:opacity-50">
            {busy
              ? <ActivityIndicator color="#131312" />
              : <Text className="text-fixme-bg font-semibold text-sm">Verify →</Text>}
          </Pressable>

          <Pressable onPress={() => { setPhase('splash'); setCode(''); setError(null); }}
            className="py-4 items-center">
            <Text className="text-fixme-text-muted text-xs">Use a different email</Text>
          </Pressable>

        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
