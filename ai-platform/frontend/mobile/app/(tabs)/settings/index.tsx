import { View, Text, Pressable, ScrollView, Alert } from 'react-native';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/stores/auth';
import { removeTokenFromBackend } from '@/lib/notifications';
import { onboardingData } from '../../(auth)/onboarding/_state';

type SettingsRow = {
  icon: string;
  label: string;
  sub?: string;
  route: string;
};

type SettingsSection = {
  title: string;
  subtitle: string;
  rows: SettingsRow[];
};

const SECTIONS: SettingsSection[] = [
  {
    title: 'Business profile',
    subtitle: 'How your studio appears to customers',
    rows: [
      {
        icon: '\u{1F464}',
        label: 'Profile details',
        sub: 'Name, bio, Instagram, location',
        route: '/settings/profile',
      },
      {
        icon: '\u{1F4F2}',
        label: 'Booking QR code',
        sub: 'Show on your counter or tablet',
        route: '/settings/qrcode',
      },
      {
        icon: '\u2728',
        label: 'Services',
        sub: 'Categories, prices, duration',
        route: '/settings/services',
      },
      {
        icon: '\u{1F4CB}',
        label: 'Amenities',
        sub: 'Accessibility, coffee, home visits',
        route: '/settings/amenities',
      },
    ],
  },
  {
    title: 'Operations',
    subtitle: 'Calendar and AI booking behavior',
    rows: [
      {
        icon: '\u{1F4C5}',
        label: 'Calendar',
        sub: 'Availability and sync settings',
        route: '/settings/calendar',
      },
      {
        icon: '\u{1F916}',
        label: 'AI bot',
        sub: 'Tone, language, automation rules',
        route: '/settings/bot',
      },
    ],
  },
];

const LEGAL: SettingsRow[] = [
  { icon: '\u{1F4DC}', label: 'Terms of Service', route: '/legal/terms' },
  { icon: '\u{1F512}', label: 'Privacy Policy', route: '/legal/privacy' },
];

function Row({ icon, label, sub, onPress }: { icon: string; label: string; sub?: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} className="flex-row items-center gap-4 px-4 py-4 active:opacity-70">
      <View className="w-10 h-10 rounded-xl bg-fixme-border/60 items-center justify-center">
        <Text className="text-base">{icon}</Text>
      </View>
      <View className="flex-1">
        <Text className="text-fixme-text-primary font-medium text-base">{label}</Text>
        {sub ? <Text className="text-fixme-text-muted text-xs mt-0.5">{sub}</Text> : null}
      </View>
      <Text className="text-fixme-text-muted text-lg">{'\u203A'}</Text>
    </Pressable>
  );
}

function Divider() {
  return <View className="h-px bg-fixme-border mx-4" />;
}

export default function SettingsScreen() {
  const { providerName, clearAuth, token } = useAuth();

  function handleLogout() {
    Alert.alert('Log out?', 'You will need to log in again.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Log out',
        style: 'destructive',
        onPress: async () => {
          await removeTokenFromBackend();
          await clearAuth();
          router.replace('/(auth)/welcome');
        },
      },
    ]);
  }

  function handleDevScrape() {
    // Pre-fill the pending token so scrape screen can make API calls
    if (token) {
      onboardingData.pendingAccessToken = token;
      onboardingData.isEmailVerified    = true;
    }
    router.push('/(auth)/onboarding/instagram-connect' as any);
  }

  return (
    <SafeAreaView className="flex-1 bg-fixme-bg" edges={['top']}>
      <ScrollView className="flex-1" contentContainerStyle={{ paddingBottom: 40 }}>
        <View className="px-5 pt-6 pb-4">
          <View className="flex-row items-center gap-4">
            <Pressable
              onPress={() => router.push('/(tabs)/profile' as any)}
              hitSlop={16}
              style={({ pressed }) => ({ opacity: pressed ? 0.4 : 1 })}
            >
              <Text style={{ fontSize: 26, lineHeight: 26, color: '#888' }}>‹</Text>
            </Pressable>
            <Text className="flex-1 text-fixme-text-primary font-bold text-2xl">Settings</Text>
          </View>
        </View>

        {SECTIONS.map((section) => (
          <View key={section.title} className="mx-5 mb-4">
            <Text className="text-fixme-text-secondary text-[11px] font-semibold uppercase tracking-widest mb-2 px-1">
              {section.title}
            </Text>
            <Text className="text-fixme-text-muted text-xs mb-3 px-1">{section.subtitle}</Text>

            <View className="bg-fixme-card border border-fixme-border rounded-2xl overflow-hidden">
              {section.rows.map((row, index) => (
                <View key={row.route}>
                  {index > 0 && <Divider />}
                  <Row {...row} onPress={() => router.push(row.route as any)} />
                </View>
              ))}
            </View>
          </View>
        ))}

        <View className="mx-5 mb-4">
          <Text className="text-fixme-text-secondary text-[11px] font-semibold uppercase tracking-widest mb-2 px-1">
            Legal
          </Text>
          <View className="bg-fixme-card border border-fixme-border rounded-2xl overflow-hidden">
            {LEGAL.map((row, index) => (
              <View key={row.route}>
                {index > 0 && <Divider />}
                <Row {...row} onPress={() => router.push(row.route as any)} />
              </View>
            ))}
          </View>
        </View>

        {/* ── Dev shortcut — only visible in dev builds ── */}
        {__DEV__ && (
          <Pressable
            onPress={handleDevScrape}
            className="mx-5 mb-3 py-4 rounded-2xl border border-fixme-accent/30 bg-fixme-accent/10 items-center active:opacity-70"
          >
            <Text className="text-fixme-accent font-semibold text-sm">
              {'\u{1F6E0}'} Test onboarding scrape screen
            </Text>
          </Pressable>
        )}

        {/* ── Log out ── */}
        <Pressable
          onPress={handleLogout}
          className="mx-5 py-4 rounded-2xl border border-fixme-error/30 bg-fixme-error/10 items-center active:opacity-70"
        >
          <Text className="text-fixme-error font-semibold text-base">Log out</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}
