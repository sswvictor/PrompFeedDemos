/**
 * ScreenHeader — top bar used on every settings and detail screen.
 *
 * Layout:
 *   [‹]  Title                    [action]   ← single row, always
 *        Subtitle (optional)
 *
 * The back chevron sits flush top-left, the title grows into the
 * available space, and the optional action anchors to the right.
 * Clean, airy, one glance reads the whole header.
 *
 * Usage:
 *   <ScreenHeader title="Services" showBack />
 *   <ScreenHeader title="Services" showBack action={<Button size="sm" onPress={openAdd}>+ Add</Button>} />
 *   <ScreenHeader title="Bot settings" showBack dirty={isDirty} />
 *   <ScreenHeader title="Settings" subtitle="Provider account" />
 *   <ScreenHeader title="Edit service" showBack backLabel="Services" />
 */

import React from 'react';
import { Pressable, Text, View } from 'react-native';
import { router } from 'expo-router';
import { DirtyDot } from './DirtyDot';

interface ScreenHeaderProps {
  title: string;
  subtitle?: string;
  showBack?: boolean;
  backLabel?: string;
  onBack?: () => void;
  /** Right-side element — Button, IconButton, any node */
  action?: React.ReactNode;
  /** Show pulsing dirty dot next to the title */
  dirty?: boolean;
  className?: string;
}

export function ScreenHeader({
  title,
  subtitle,
  showBack = false,
  backLabel,
  onBack,
  action,
  dirty = false,
  className = '',
}: ScreenHeaderProps) {
  return (
    <View className={`px-5 pt-6 pb-5 ${className}`}>

      {/* ── Single title row ─────────────────────────────────────────── */}
      <View className="flex-row items-center gap-3">

        {/* Back chevron — top-left, compact, generous hit area */}
        {showBack && (
          <Pressable
            onPress={onBack ?? (() => router.back())}
            hitSlop={16}
            style={({ pressed }) => ({ opacity: pressed ? 0.4 : 1 })}
            className="-ml-1"
          >
            <Text className="
              text-[26px] font-light leading-[34px]
              text-fixme-light-text-muted dark:text-fixme-text-muted
            ">
              ‹
            </Text>
          </Pressable>
        )}

        {/* Title + dirty dot — grows to fill available width */}
        <View className="flex-1 flex-row items-center gap-2">
          <Text
            className="
              text-[26px] font-bold tracking-tight leading-[34px]
              text-fixme-light-text-primary dark:text-fixme-text-primary
            "
            numberOfLines={1}
          >
            {title}
          </Text>
          {dirty && <DirtyDot />}
        </View>

        {/* Right action — e.g. "+ Add" button */}
        {action && <View>{action}</View>}

      </View>

      {/* ── Subtitle ─────────────────────────────────────────────────── */}
      {subtitle && (
        <Text className="
          text-[13px] mt-1.5 leading-[19px]
          text-fixme-light-text-muted dark:text-fixme-text-muted
        ">
          {subtitle}
        </Text>
      )}

    </View>
  );
}
