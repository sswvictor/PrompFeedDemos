import { useState, useEffect } from 'react';
import {
  View, Text, Pressable, ScrollView,
  ActivityIndicator, Alert, Switch,
} from 'react-native';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getBotSettings, updateBotSettings, type BotSettings } from '@/lib/api';
import { colors } from '@/theme';

// ─── Option pill ──────────────────────────────────────────────────────────────

function OptionPill({
  label, selected, onPress,
}: { label: string; selected: boolean; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      className={`px-4 py-2 rounded-xl border mr-2 mb-2 ${selected ? 'bg-fixme-accent border-fixme-accent' : 'bg-fixme-card border-fixme-border'}`}
    >
      <Text className={`text-sm font-semibold ${selected ? 'text-fixme-bg' : 'text-fixme-text-secondary'}`}>
        {label}
      </Text>
    </Pressable>
  );
}

// ─── Section wrapper ──────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View className="mb-6">
      <Text className="text-fixme-text-secondary text-xs font-semibold mb-3 uppercase tracking-wider">
        {title}
      </Text>
      {children}
    </View>
  );
}

// ─── Main screen ─────────────────────────────────────────────────────────────

const TONES: Array<{ value: string; label: string; description: string }> = [
  { value: 'friendly',     label: '\uD83D\uDE0A Friendly',    description: 'Warm & approachable' },
  { value: 'professional', label: '\uD83D\uDC54 Professional', description: 'Formal & polished' },
  { value: 'playful',      label: '\uD83C\uDF89 Playful',     description: 'Fun & expressive' },
];

const LANGUAGES: Array<{ value: string; label: string }> = [
  { value: 'en', label: '\uD83C\uDDEC\uD83C\uDDE7 English' },
  { value: 'sv', label: '\uD83C\uDDF8\uD83C\uDDEA Svenska' },
  { value: 'de', label: '\uD83C\uDDE9\uD83C\uDDEA Deutsch' },
  { value: 'fr', label: '\uD83C\uDDEB\uD83C\uDDF7 Français' },
  { value: 'es', label: '\uD83C\uDDEA\uD83C\uDDF8 Español' },
  { value: 'ar', label: '\uD83C\uDDF8\uD83C\uDDE6 \u0639\u0631\u0628\u064A' },
];

const AFTER_HOURS: Array<{ value: string; label: string; description: string }> = [
  { value: 'reply',   label: 'Auto-reply',   description: 'Bot responds 24/7' },
  { value: 'collect', label: 'Collect lead',  description: 'Capture name + service, you follow up' },
  { value: 'off',     label: 'Silent',        description: 'No response outside hours' },
];

export default function BotSettingsScreen() {
  const queryClient = useQueryClient();

  const { data: settings, isLoading } = useQuery({
    queryKey: ['bot-settings'],
    queryFn: getBotSettings,
  });

  const [enabled,    setEnabled]    = useState(false);
  const [tone,       setTone]       = useState('friendly');
  const [language,   setLanguage]   = useState('en');
  const [afterHours, setAfterHours] = useState('reply');
  const [dirty,      setDirty]      = useState(false);

  useEffect(() => {
    if (!settings) return;
    setEnabled(settings.bot_enabled);
    setTone(settings.tone ?? 'friendly');
    setLanguage(settings.language ?? 'en');
    setAfterHours(settings.after_hours_mode ?? 'reply');
    setDirty(false);
  }, [settings]);

  function markDirty() { setDirty(true); }

  const mutation = useMutation({
    mutationFn: () => updateBotSettings({
      bot_enabled: enabled,
      tone,
      language,
      after_hours_mode: afterHours,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-settings'] });
      setDirty(false);
      Alert.alert('Saved', 'Bot settings updated.');
    },
    onError: (err: Error) => Alert.alert('Error', err.message),
  });

  if (isLoading) {
    return (
      <SafeAreaView className="flex-1 bg-fixme-bg items-center justify-center">
        <ActivityIndicator color={colors.accent} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView className="flex-1 bg-fixme-bg" edges={['top']}>
      <ScrollView className="flex-1 px-5" keyboardShouldPersistTaps="handled">
        {/* Header */}
        <View className="flex-row items-center gap-3 pt-6 mb-6">
          <Pressable onPress={() => router.back()}>
            <Text className="text-fixme-text-muted text-sm">\u2190</Text>
          </Pressable>
          <Text className="text-fixme-text-primary font-bold text-xl flex-1">AI Bot</Text>
          {dirty && (
            <View className="w-2 h-2 rounded-full bg-fixme-accent" />
          )}
        </View>

        {/* Hero toggle */}
        <View className="bg-fixme-card border border-fixme-border rounded-2xl px-4 py-4 mb-6">
          <View className="flex-row items-center justify-between">
            <View className="flex-1 mr-4">
              <Text className="text-fixme-text-primary font-semibold text-base">\uD83E\uDD16 Instagram AI Bot</Text>
              <Text className="text-fixme-text-muted text-xs mt-1 leading-relaxed">
                Automatically handles DMs, answers questions, and books appointments on Instagram.
              </Text>
            </View>
            <Switch
              value={enabled}
              onValueChange={(v) => { setEnabled(v); markDirty(); }}
              trackColor={{ false: '#2A2A2A', true: colors.accent }}
              thumbColor="#F5F5F0"
            />
          </View>
        </View>

        {/* Tone */}
        <Section title="Bot personality">
          <View className="gap-2">
            {TONES.map(t => (
              <Pressable
                key={t.value}
                onPress={() => { setTone(t.value); markDirty(); }}
                className={`bg-fixme-card border rounded-xl px-4 py-3 flex-row items-center justify-between ${tone === t.value ? 'border-fixme-accent' : 'border-fixme-border'}`}
              >
                <View>
                  <Text className="text-fixme-text-primary text-sm font-semibold">{t.label}</Text>
                  <Text className="text-fixme-text-muted text-xs mt-0.5">{t.description}</Text>
                </View>
                {tone === t.value && (
                  <View className="w-5 h-5 rounded-full bg-fixme-accent items-center justify-center">
                    <Text className="text-fixme-bg text-xs font-bold">\u2713</Text>
                  </View>
                )}
              </Pressable>
            ))}
          </View>
        </Section>

        {/* Language */}
        <Section title="Response language">
          <View className="flex-row flex-wrap">
            {LANGUAGES.map(l => (
              <OptionPill
                key={l.value}
                label={l.label}
                selected={language === l.value}
                onPress={() => { setLanguage(l.value); markDirty(); }}
              />
            ))}
          </View>
        </Section>

        {/* After hours */}
        <Section title="After hours behaviour">
          <View className="gap-2">
            {AFTER_HOURS.map(a => (
              <Pressable
                key={a.value}
                onPress={() => { setAfterHours(a.value); markDirty(); }}
                className={`bg-fixme-card border rounded-xl px-4 py-3 flex-row items-center justify-between ${afterHours === a.value ? 'border-fixme-accent' : 'border-fixme-border'}`}
              >
                <View>
                  <Text className="text-fixme-text-primary text-sm font-semibold">{a.label}</Text>
                  <Text className="text-fixme-text-muted text-xs mt-0.5">{a.description}</Text>
                </View>
                {afterHours === a.value && (
                  <View className="w-5 h-5 rounded-full bg-fixme-accent items-center justify-center">
                    <Text className="text-fixme-bg text-xs font-bold">\u2713</Text>
                  </View>
                )}
              </Pressable>
            ))}
          </View>
        </Section>

        {/* Info card */}
        <View className="bg-fixme-card border border-fixme-border rounded-2xl px-4 py-3 mb-6 flex-row gap-3">
          <Text className="text-lg">\uD83D\uDCA1</Text>
          <Text className="text-fixme-text-muted text-xs leading-relaxed flex-1">
            The bot uses your services catalogue, working hours, and bio to answer questions accurately. Keep your profile up to date for best results.
          </Text>
        </View>

        {/* Save */}
        <Pressable
          onPress={() => mutation.mutate()}
          disabled={mutation.isPending || !dirty}
          className="bg-fixme-accent rounded-2xl py-4 items-center mb-10 active:opacity-80 disabled:opacity-40"
        >
          {mutation.isPending
            ? <ActivityIndicator color="#0D0D0D" />
            : <Text className="text-fixme-bg font-bold text-base">Save changes</Text>
          }
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}
