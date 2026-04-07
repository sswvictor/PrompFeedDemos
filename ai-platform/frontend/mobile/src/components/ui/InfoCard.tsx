/**
 * InfoCard — notification-style card for tips, warnings, and status messages.
 *
 * Think Stripe's info banners or Linear's hint cards — clean, airy, never alarming.
 *
 * Variants:
 *   info     → neutral tint (tips, instructions)       ← default
 *   success  → green tint (connected, confirmed)
 *   warning  → amber tint (attention needed)
 *   error    → red tint (failed, blocked)
 *
 * Usage:
 *   <InfoCard title="Connect your calendar" description="Sync bookings automatically." icon="📅" />
 *   <InfoCard variant="success" title="Calendar connected" icon="✅" />
 *   <InfoCard variant="warning" title="Unpaid invoices" description="3 bookings need payment." icon="⚠️" />
 *   <InfoCard variant="error" title="Connection failed" description="Try again later." icon="❌" />
 */

import { Text, View } from 'react-native';

interface InfoCardProps {
  title: string;
  description?: string;
  icon?: string;
  variant?: 'info' | 'success' | 'warning' | 'error';
  className?: string;
}

const variantStyles = {
  info: {
    container: 'bg-fixme-light-card dark:bg-fixme-card border border-fixme-light-border dark:border-fixme-border',
    title:     'text-fixme-light-text-primary dark:text-fixme-text-primary',
    body:      'text-fixme-light-text-muted dark:text-fixme-text-muted',
  },
  success: {
    container: 'bg-green-400/8 border border-green-400/25',
    title:     'text-fixme-light-success dark:text-fixme-success',
    body:      'text-fixme-light-text-secondary dark:text-fixme-text-secondary',
  },
  warning: {
    container: 'bg-amber-400/8 border border-amber-400/25',
    title:     'text-amber-500 dark:text-amber-400',
    body:      'text-fixme-light-text-secondary dark:text-fixme-text-secondary',
  },
  error: {
    container: 'bg-red-400/8 border border-red-400/25',
    title:     'text-fixme-light-error dark:text-fixme-error',
    body:      'text-fixme-light-text-secondary dark:text-fixme-text-secondary',
  },
} as const;

export function InfoCard({
  title,
  description,
  icon,
  variant = 'info',
  className = '',
}: InfoCardProps) {
  const s = variantStyles[variant];

  return (
    <View
      className={`
        flex-row items-start
        rounded-2xl px-5 py-5 gap-4
        ${s.container}
        ${className}
      `}
    >
      {/* Icon — large, centred with first line of text */}
      {icon && (
        <Text style={{ fontSize: 24, lineHeight: 28, marginTop: 1 }}>
          {icon}
        </Text>
      )}

      {/* Text block */}
      <View className="flex-1">
        <Text className={`text-[15px] font-semibold leading-snug ${s.title}`}>
          {title}
        </Text>
        {description && (
          <Text className={`text-[13px] leading-[19px] mt-1.5 ${s.body}`}>
            {description}
          </Text>
        )}
      </View>
    </View>
  );
}
