/**
 * ScrapeWebsiteScreen — Step 2 of onboarding.
 * Provider pastes their website / booking site URL.
 * AI scrapes it and navigates to the review screen.
 */
import { useState } from 'react';
import {
  View, Text, TextInput, Pressable,
  ActivityIndicator, KeyboardAvoidingView,
  Platform, ScrollView,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { scanWebsite } from '@/lib/api';
import { onboardingData } from './_state';

// ── Design tokens (matches instagram-connect) ─────────────────────────

const C = {
  bg:     '#181A20',
  card:   '#262A33',
  border: '#454B58',
  text:   '#F2F2F7',
  text2:  '#C2C7D2',
  muted:  '#98A0AF',
  error:  '#ef4444',
} as const;

const BTN = {
  primary: {
    gradient:  ['#FFFBF5', '#EEECEA'] as const,
    bgPressed: '#D8D6D3',
    text:      '#0D0D0D',
    radius:    20,
  },
  secondary: {
    gradient:  ['#252830', '#1E2028'] as const,
    text:      '#F2F2F7',
    border:    'rgba(255,255,255,0.18)',
    radius:    20,
  },
} as const;

export default function ScrapeWebsiteScreen() {
  const [url,   setUrl]   = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy,  setBusy]  = useState(false);

  async function handleGo() {
    const clean = url.trim();
    if (!clean) { setError('Add your website URL first'); return; }

    setError(null);
    setBusy(true);
    try {
      const token = onboardingData.pendingAccessToken || undefined;
      const scanData = await scanWebsite(clean.replace(/^https?:\/\//i, ''), token);
      onboardingData.websiteUrl  = clean;
      onboardingData.scanResult  = scanData;
      router.push('/(auth)/onboarding/review' as any);
    } catch (err: any) {
      // Still navigate — review screen handles missing data gracefully
      onboardingData.websiteUrl = clean;
      onboardingData.scanResult = null;
      router.push('/(auth)/onboarding/review' as any);
    } finally {
      setBusy(false);
    }
  }

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

          {/* Logo */}
          <Text style={{
            color: C.muted, fontSize: 10, fontWeight: '700',
            letterSpacing: 5, textTransform: 'uppercase',
            marginTop: 24, marginBottom: 36,
          }}>
            Fixmeapp
          </Text>

          {/* Main content — flex: 1 so bottom row pins to bottom */}
          <View style={{ flex: 1, paddingTop: 48 }}>

            {/* Top content */}
            <View>
              {/* Headline */}
              <Text style={{
                color: C.text, fontSize: 36, fontWeight: '800',
                letterSpacing: -0.8, lineHeight: 43, marginBottom: 16,
              }}>
                Get your services{'\n'}in seconds
              </Text>

              {/* Subline */}
              <Text style={{
                color: C.text2, fontSize: 16, lineHeight: 26,
                maxWidth: 300, marginBottom: 32,
              }}>
                Our AI will collect only relevant information about your services and working hours.
              </Text>

              {/* URL input + Go button */}
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <TextInput
                  style={{
                    flex: 1,
                    height: 50,
                    backgroundColor: 'rgba(255,255,255,0.06)',
                    borderColor: 'rgba(255,255,255,0.14)',
                    borderWidth: 1.5,
                    borderRadius: 16,
                    paddingHorizontal: 16,
                    paddingVertical: 0,
                    color: C.text,
                    fontSize: 15,
                    letterSpacing: 0,
                  }}
                  placeholder="Add website here"
                  placeholderTextColor={C.muted}
                  value={url}
                  onChangeText={v => { setUrl(v); setError(null); }}
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="url"
                  returnKeyType="go"
                  onSubmitEditing={handleGo}
                />

                {/* Go — primary button */}
                <Pressable
                  onPress={handleGo}
                  disabled={busy}
                  style={({ pressed }) => ({
                    borderRadius: BTN.primary.radius,
                    overflow: 'hidden',
                    opacity: busy ? 0.35 : pressed ? 0.82 : 1,
                  })}
                >
                  <LinearGradient
                    colors={BTN.primary.gradient}
                    start={{ x: 0, y: 0 }}
                    end={{ x: 0, y: 1 }}
                    style={{
                      height: 50,
                      borderRadius: BTN.primary.radius,
                      paddingHorizontal: 22,
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {busy
                      ? <ActivityIndicator color={BTN.primary.text} size="small" />
                      : <Text style={{ color: BTN.primary.text, fontWeight: '700', fontSize: 15 }}>Go</Text>}
                  </LinearGradient>
                </Pressable>
              </View>

              {!!error && (
                <Text style={{ color: C.error, fontSize: 12, marginTop: 12 }}>
                  {error}
                </Text>
              )}
            </View>

            {/* Flex spacer — pins bottom row to screen bottom */}
            <View style={{ flex: 1 }} />

            {/* Bottom row — Skip left, back right */}
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingBottom: 8 }}>
              <Pressable onPress={() => router.back()} disabled={busy}>
                <Text style={{ color: C.muted, fontSize: 13 }}>← Back</Text>
              </Pressable>
              <Pressable onPress={() => router.push('/(auth)/onboarding/review' as any)} disabled={busy}>
                <Text style={{ color: C.muted, fontSize: 13 }}>Skip for now</Text>
              </Pressable>
            </View>

          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
