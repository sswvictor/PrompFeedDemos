/**
 * BackButton — minimal, elegant back navigation.
 *
 * Not just a chevron — has a generous hit area and clear label.
 * Defaults to router.back() but accepts a custom onPress.
 *
 * Usage:
 *   <BackButton />
 *   <BackButton label="Settings" />
 *   <BackButton onPress={() => router.push('/home')} />
 */

import { Pressable, Text } from 'react-native';
import { router } from 'expo-router';

interface BackButtonProps {
  label?: string;
  onPress?: () => void;
  className?: string;
}

export function BackButton({
  label = 'Back',
  onPress,
  className = '',
}: BackButtonProps) {
  return (
    <Pressable
      onPress={onPress ?? (() => router.back())}
      hitSlop={16}
      style={({ pressed }) => ({ opacity: pressed ? 0.5 : 1 })}
      className={`flex-row items-center gap-1.5 ${className}`}
    >
      <Text className="
        text-fixme-light-text-muted dark:text-fixme-text-muted
        text-[17px]
        font-light
      ">
        ‹
      </Text>
      <Text className="
        text-[15px] font-medium
        text-fixme-light-text-muted dark:text-fixme-text-muted
      ">
        {label}
      </Text>
    </Pressable>
  );
}
