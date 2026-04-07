/**
 * LoadingSpinner — elegant loading state. Never jarring, always calm.
 *
 * Variants:
 *   default  → standard ActivityIndicator in accent colour     ← default
 *   fullscreen → centred in flex-1 container (whole screen loading)
 *   inline   → small, sits inline with text or inside a card
 *
 * Usage:
 *   // Full screen — replaces screen content while data loads
 *   <LoadingSpinner fullscreen />
 *
 *   // Inside a card or list
 *   <LoadingSpinner />
 *
 *   // Tiny inline (next to text, inside buttons)
 *   <LoadingSpinner size="small" />
 *
 *   // With a caption below (first load moments)
 *   <LoadingSpinner fullscreen label="Setting things up…" />
 */

import { ActivityIndicator, Text, View } from 'react-native';
import { colors } from '@/theme';

interface LoadingSpinnerProps {
  size?: 'small' | 'large';
  fullscreen?: boolean;
  label?: string;
  className?: string;
}

export function LoadingSpinner({
  size = 'large',
  fullscreen = false,
  label,
  className = '',
}: LoadingSpinnerProps) {
  const spinner = (
    <ActivityIndicator
      size={size}
      color={colors.accent}
    />
  );

  if (fullscreen) {
    return (
      <View
        className={`
          flex-1 items-center justify-center gap-5
          bg-fixme-light-bg dark:bg-fixme-bg
          ${className}
        `}
      >
        {spinner}
        {label && (
          <Text className="
            text-[15px] font-medium tracking-wide
            text-fixme-light-text-muted dark:text-fixme-text-muted
          ">
            {label}
          </Text>
        )}
      </View>
    );
  }

  return (
    <View className={`items-center justify-center py-8 ${className}`}>
      {spinner}
      {label && (
        <Text className="
          text-[13px] mt-3
          text-fixme-light-text-muted dark:text-fixme-text-muted
        ">
          {label}
        </Text>
      )}
    </View>
  );
}
