/**
 * Badge — compact status pill.
 *
 * Variants:
 *   success  → green  (Active, Paid, Verified, Connected)
 *   error    → red    (Failed, Overdue, Blocked)
 *   warning  → amber  (Unpaid, Pending, Attention)
 *   neutral  → muted  (Hidden, Inactive, Draft)
 *   default  → soft bg + border                          ← default
 *
 * Sizes:
 *   sm  → 11px  (inside cards, tight spaces)             ← default
 *   md  → 13px  (standalone, prominent)
 *
 * Usage:
 *   <Badge variant="success">Active</Badge>
 *   <Badge variant="neutral">Hidden</Badge>
 *   <Badge variant="warning">Unpaid</Badge>
 *   <Badge variant="success" dot>Connected</Badge>
 *   <Badge variant="default" size="md">Beta</Badge>
 */

import { Text, View } from 'react-native';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'success' | 'error' | 'warning' | 'neutral' | 'default';
  size?: 'sm' | 'md';
  /** Show a coloured dot before the label */
  dot?: boolean;
  className?: string;
}

const variantStyles = {
  success: {
    container: 'bg-green-400/10 border border-green-400/20',
    text:      'text-green-400',
    dot:       'bg-green-400',
  },
  error: {
    container: 'bg-red-400/10 border border-red-400/20',
    text:      'text-red-400',
    dot:       'bg-red-400',
  },
  warning: {
    container: 'bg-amber-400/10 border border-amber-400/20',
    text:      'text-amber-400',
    dot:       'bg-amber-400',
  },
  neutral: {
    container: 'bg-white/5 dark:bg-white/5 bg-black/5 border border-fixme-light-border dark:border-fixme-border',
    text:      'text-fixme-light-text-muted dark:text-fixme-text-muted',
    dot:       'bg-fixme-light-text-muted dark:bg-fixme-text-muted',
  },
  default: {
    container: 'bg-fixme-light-card dark:bg-fixme-card border border-fixme-light-border dark:border-fixme-border',
    text:      'text-fixme-light-text-secondary dark:text-fixme-text-secondary',
    dot:       'bg-fixme-light-text-secondary dark:bg-fixme-text-secondary',
  },
} as const;

const sizeStyles = {
  sm: { text: 'text-[11px]', px: 'px-2.5 py-[3px]', dot: 5 },
  md: { text: 'text-[13px]', px: 'px-3 py-1',        dot: 6 },
} as const;

export function Badge({
  children,
  variant = 'default',
  size = 'sm',
  dot = false,
  className = '',
}: BadgeProps) {
  const v = variantStyles[variant];
  const s = sizeStyles[size];

  return (
    <View
      className={`
        flex-row items-center self-start rounded-full gap-1.5
        ${v.container}
        ${s.px}
        ${className}
      `}
    >
      {dot && (
        <View
          style={{ width: s.dot, height: s.dot, borderRadius: s.dot / 2 }}
          className={v.dot}
        />
      )}
      <Text className={`${s.text} font-semibold`}>
        {children}
      </Text>
    </View>
  );
}
