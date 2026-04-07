/**
 * StatCard — a single metric displayed with a large value and a label.
 *
 * Designed with lots of air — think Uber driver earnings, LTK analytics.
 *
 * Sizes:
 *   sm   → compact (profile grid: followers, level)
 *   md   → standard (finance sidebar stats)           ← default
 *   lg   → hero (revenue hero card, big number)
 *
 * Usage:
 *   <StatCard label="Revenue" value="24 500 kr" />
 *   <StatCard label="Bookings" value="12" change="+3" positive />
 *   <StatCard label="Followers" value="4.2k" size="sm" />
 *   <StatCard label="Total revenue" value="124 800 kr" size="lg" hero />
 */

import { Text, View } from 'react-native';

interface StatCardProps {
  label: string;
  value: string;
  /** Optional change indicator e.g. "+12%" */
  change?: string;
  /** Green if true, red if false, neutral if undefined */
  positive?: boolean;
  size?: 'sm' | 'md' | 'lg';
  /** Hero variant — no card bg, full-bleed for finance hero */
  hero?: boolean;
  className?: string;
}

const valueSize = {
  sm: 'text-[22px] leading-[28px]',
  md: 'text-[28px] leading-[34px]',
  lg: 'text-[38px] leading-[44px]',
} as const;

const labelSize = {
  sm: 'text-xs',
  md: 'text-[13px]',
  lg: 'text-sm',
} as const;

export function StatCard({
  label,
  value,
  change,
  positive,
  size = 'md',
  hero = false,
  className = '',
}: StatCardProps) {
  const changeColor =
    positive === true  ? 'text-fixme-light-success dark:text-fixme-success' :
    positive === false ? 'text-fixme-light-error dark:text-fixme-error' :
                         'text-fixme-light-text-muted dark:text-fixme-text-muted';

  const wrapper = hero
    ? `px-6 py-7 ${className}`
    : `bg-fixme-light-card dark:bg-fixme-card border border-fixme-light-border dark:border-fixme-border rounded-2xl px-5 py-5 ${className}`;

  return (
    <View className={wrapper}>
      {/* Label — sits above the value, small + muted */}
      <Text
        className={`
          ${labelSize[size]} font-medium mb-2
          text-fixme-light-text-muted dark:text-fixme-text-muted
          uppercase tracking-wider
        `}
      >
        {label}
      </Text>

      {/* Value row */}
      <View className="flex-row items-end gap-2">
        <Text
          className={`
            ${valueSize[size]} font-bold tracking-tight
            text-fixme-light-text-primary dark:text-fixme-text-primary
          `}
        >
          {value}
        </Text>

        {change && (
          <Text className={`text-sm font-semibold mb-1 ${changeColor}`}>
            {change}
          </Text>
        )}
      </View>
    </View>
  );
}
