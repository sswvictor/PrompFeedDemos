/**
 * ProgressBar — segmented step indicator for onboarding flows.
 *
 * Design: thin, precise segments with generous spacing between them.
 * Active segments fill with accent. Completed segments stay filled.
 * Upcoming are the soft border colour — present but not distracting.
 * Animates each fill on step change.
 *
 * Usage:
 *   <ProgressBar steps={4} currentStep={1} />
 *   <ProgressBar steps={3} currentStep={2} className="mb-6" />
 */

import { useEffect, useRef } from 'react';
import { Animated, View } from 'react-native';
import { colors } from '@/theme';

interface ProgressBarProps {
  steps: number;
  currentStep: number; // 0-indexed
  className?: string;
}

function Segment({ filled, animated }: { filled: boolean; animated: boolean }) {
  const fillAnim = useRef(new Animated.Value(filled && !animated ? 1 : 0)).current;

  useEffect(() => {
    Animated.timing(fillAnim, {
      toValue: filled ? 1 : 0,
      duration: 340,
      useNativeDriver: false,
    }).start();
  }, [filled, fillAnim]);

  const bgColor = fillAnim.interpolate({
    inputRange:  [0, 1],
    outputRange: [colors.borderSoft, colors.accent],
  });

  return (
    <Animated.View
      style={{ flex: 1, height: 3, borderRadius: 2, backgroundColor: bgColor }}
    />
  );
}

export function ProgressBar({ steps, currentStep, className = '' }: ProgressBarProps) {
  return (
    <View className={`flex-row gap-1.5 px-5 ${className}`}>
      {Array.from({ length: steps }).map((_, i) => (
        <Segment
          key={i}
          filled={i <= currentStep}
          animated={i === currentStep}
        />
      ))}
    </View>
  );
}
