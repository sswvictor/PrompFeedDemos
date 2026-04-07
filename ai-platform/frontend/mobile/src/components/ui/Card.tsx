/**
 * Card — base surface component. The building block for everything.
 *
 * Variants:
 *   default  → standard card bg + border                         ← default
 *   soft     → slightly elevated bg, no border (inner sections)
 *   ghost    → transparent, border only
 *
 * Usage:
 *   <Card>…content…</Card>
 *   <Card onPress={handlePress}>…pressable card…</Card>
 *   <Card variant="ghost" className="mt-4">…</Card>
 *   <Card padding="lg">…more breathing room…</Card>
 */

import React from 'react';
import { Pressable, View } from 'react-native';

interface CardProps {
  children: React.ReactNode;
  onPress?: () => void;
  onLongPress?: () => void;
  variant?: 'default' | 'soft' | 'ghost';
  /** Internal padding preset */
  padding?: 'none' | 'sm' | 'md' | 'lg';
  className?: string;
}

const variantClass = {
  default: 'bg-fixme-light-card dark:bg-fixme-card border border-fixme-light-border dark:border-fixme-border',
  soft:    'bg-fixme-light-bg-soft dark:bg-fixme-bg-soft border border-fixme-light-border-soft dark:border-fixme-border-soft',
  ghost:   'bg-transparent border border-fixme-light-border dark:border-fixme-border',
} as const;

const paddingClass = {
  none: '',
  sm:   'px-4 py-3.5',
  md:   'px-5 py-5',
  lg:   'px-6 py-6',
} as const;

export function Card({
  children,
  onPress,
  onLongPress,
  variant = 'default',
  padding = 'md',
  className = '',
}: CardProps) {
  const base = `
    rounded-2xl overflow-hidden
    ${variantClass[variant]}
    ${paddingClass[padding]}
    ${className}
  `;

  if (onPress || onLongPress) {
    return (
      <Pressable
        onPress={onPress}
        onLongPress={onLongPress}
        className={base}
        style={({ pressed }) => ({ opacity: pressed ? 0.75 : 1 })}
      >
        {children}
      </Pressable>
    );
  }

  return <View className={base}>{children}</View>;
}
