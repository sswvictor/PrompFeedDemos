/**
 * AiCommandSheet — cinematic bottom sheet for provider AI commands.
 *
 * Provider types a natural-language instruction:
 *   "Block tomorrow 2–4pm, dentist"
 *   "Tell my next client I'm running 20 min late"
 *   "I'm sick, cancel today's bookings"
 *
 * Slides up from the bottom with a spring animation + dim overlay.
 */

import { useEffect, useRef, useState } from 'react';
import {
  Animated,
  Easing,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  Text,
  TextInput,
  View,
} from 'react-native';
import { sendAiCommand, type AiCommandResult } from '@/lib/api';
import { colors } from '@/theme';
import { Button } from '@/components/ui';

const QUICK_COMMANDS = [
  'Block next hour',
  "I'm running 15 min late",
  "I'm sick, cancel today",
  'Block tomorrow afternoon',
];

interface Props {
  visible: boolean;
  onClose: () => void;
  onDone?: (result: AiCommandResult) => void;
}

export function AiCommandSheet({ visible, onClose, onDone }: Props) {
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AiCommandResult | null>(null);

  // Slide + fade animations
  const slideY = useRef(new Animated.Value(600)).current;
  const opacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (visible) {
      setResult(null);
      setMessage('');
      Animated.parallel([
        Animated.spring(slideY, {
          toValue: 0,
          useNativeDriver: true,
          tension: 65,
          friction: 11,
        }),
        Animated.timing(opacity, {
          toValue: 1,
          duration: 220,
          easing: Easing.out(Easing.ease),
          useNativeDriver: true,
        }),
      ]).start();
    } else {
      Animated.parallel([
        Animated.spring(slideY, {
          toValue: 600,
          useNativeDriver: true,
          tension: 80,
          friction: 14,
        }),
        Animated.timing(opacity, {
          toValue: 0,
          duration: 180,
          useNativeDriver: true,
        }),
      ]).start();
    }
  }, [visible]);

  async function handleSend() {
    const cmd = message.trim();
    if (!cmd) return;
    setLoading(true);
    try {
      const res = await sendAiCommand(cmd);
      setResult(res);
      onDone?.(res);
    } catch (err: unknown) {
      setResult({
        action: 'error',
        message: (err as Error).message || 'Something went wrong. Try again.',
      });
    } finally {
      setLoading(false);
    }
  }

  function handleQuick(cmd: string) {
    setMessage(cmd);
  }

  if (!visible) return null;

  return (
    <View style={{ position: 'absolute', inset: 0, zIndex: 999 }}>
      {/* Backdrop */}
      <Animated.View style={{ flex: 1, opacity }}>
        <Pressable style={{ flex: 1 }} onPress={onClose}>
          <View style={{ flex: 1, backgroundColor: 'rgba(7, 10, 18, 0.74)' }} />
        </Pressable>
      </Animated.View>

      {/* Sheet */}
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'position' : 'height'}
        style={{ position: 'absolute', bottom: 0, left: 0, right: 0 }}
      >
        <Animated.View
          style={{ transform: [{ translateY: slideY }] }}
          className="bg-fixme-card rounded-t-3xl px-5 pt-5 pb-10 border-t border-fixme-border"
        >
          {/* Handle */}
          <View className="w-10 h-1 rounded-full bg-fixme-border self-center mb-5" />

          {/* Header */}
          <View className="flex-row items-center gap-3 mb-4">
            <View className="w-9 h-9 rounded-2xl bg-fixme-accent/15 items-center justify-center">
              <Text style={{ fontSize: 18 }}>✦</Text>
            </View>
            <View className="flex-1">
              <Text className="text-fixme-text-primary font-bold text-base">AI Assistant</Text>
              <Text className="text-fixme-text-muted text-xs mt-0.5">Tell me what to do</Text>
            </View>
            <Pressable
              onPress={onClose}
              className="w-8 h-8 rounded-full bg-fixme-bg items-center justify-center active:opacity-60"
            >
              <Text className="text-fixme-text-muted text-lg leading-none">✕</Text>
            </Pressable>
          </View>

          {/* Result */}
          {result ? (
            <View className={`rounded-2xl p-4 mb-4 ${result.action === 'error' ? 'bg-red-900/20 border border-red-800/30' : 'bg-fixme-accent/10 border border-fixme-accent/30'}`}>
              <Text className={`text-sm font-semibold mb-1 ${result.action === 'error' ? 'text-red-400' : 'text-fixme-accent'}`}>
                {result.action === 'error' ? 'Hmm…' : 'Done ✓'}
              </Text>
              <Text className="text-fixme-text-primary text-sm leading-relaxed">{result.message}</Text>
              <Button variant="ghost" size="xs" onPress={() => { setResult(null); setMessage(''); }} className="mt-3 self-start">
                Try another
              </Button>
            </View>
          ) : (
            <>
              {/* Quick commands */}
              <View className="flex-row flex-wrap gap-2 mb-4">
                {QUICK_COMMANDS.map((cmd) => (
                  <Pressable
                    key={cmd}
                    onPress={() => handleQuick(cmd)}
                    className="bg-fixme-bg border border-fixme-border rounded-full px-3 py-1.5 active:opacity-70"
                  >
                    <Text className="text-fixme-text-secondary text-xs">{cmd}</Text>
                  </Pressable>
                ))}
              </View>

              {/* Input row */}
              <View className="flex-row items-end gap-2">
                <TextInput
                  value={message}
                  onChangeText={setMessage}
                  placeholder="Block tomorrow 2–4pm…"
                  placeholderTextColor={colors.textMuted}
                  multiline
                  style={{ color: colors.textPrimary, maxHeight: 100 }}
                  className="flex-1 bg-fixme-bg border border-fixme-border rounded-2xl px-4 py-3 text-sm"
                  onSubmitEditing={handleSend}
                  returnKeyType="send"
                />
                <Button
                  onPress={handleSend}
                  loading={loading}
                  disabled={!message.trim()}
                  size="sm"
                  className="mb-0.5"
                >
                  Send
                </Button>
              </View>
            </>
          )}
        </Animated.View>
      </KeyboardAvoidingView>
    </View>
  );
}
