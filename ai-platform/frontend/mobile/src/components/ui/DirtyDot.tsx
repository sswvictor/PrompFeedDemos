/**
 * DirtyDot — tiny pulsing dot that signals unsaved changes.
 *
 * Appears next to screen titles when the user has edited something
 * but not yet saved. Subtle but unmissable — like the one in VS Code
 * or Linear's unsaved indicator.
 *
 * Uses a gentle scale pulse animation on mount so the eye catches it
 * without it being aggressive.
 *
 * Usage:
 *   // In a screen header next to the title
 *   <View className="flex-row items-center gap-2">
 *     <Heading>Bot settings</Heading>
 *     {isDirty && <DirtyDot />}
 *   </View>
 *
 *   // Warning colour (changes are destructive)
 *   {isDirty && <DirtyDot variant="warning" />}
 */

import { useEffect, useRef } from 'react';
import { Animated } from 'react-native';

interface DirtyDotProps {
  variant?: 'default' | 'warning';
  size?: number;
}

export function DirtyDot({ variant = 'default', size = 7 }: DirtyDotProps) {
  const pulse = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    // Gentle breathe — scale 1 → 1.4 → 1, once on mount, then repeat slowly
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1.45,
          duration: 900,
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 1,
          duration: 900,
          useNativeDriver: true,
        }),
      ]),
    ).start();

    return () => pulse.stopAnimation();
  }, [pulse]);

  const color = variant === 'warning'
    ? 'rgb(251,191,36)'   // amber-400
    : 'rgb(99,215,163)';  // success green — softer than pure #34D399

  return (
    <Animated.View
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: color,
        transform: [{ scale: pulse }],
        // Soft glow via shadow (iOS only — Android ignores, which is fine)
        shadowColor: color,
        shadowOpacity: 0.6,
        shadowRadius: 4,
        shadowOffset: { width: 0, height: 0 },
      }}
    />
  );
}
