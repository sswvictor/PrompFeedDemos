/**
 * Pill — selectable chip for filter rows, duration pickers, period selectors.
 *
 * Usage (single):
 *   <Pill label="60 min" selected={duration === 60} onPress={() => setDuration(60)} />
 *
 * Usage (group — horizontal scroll):
 *   <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
 *     {DURATIONS.map(d => (
 *       <Pill key={d} label={fmtDuration(d)} selected={duration === d} onPress={() => setDuration(d)} />
 *     ))}
 *   </ScrollView>
 *
 * Sizes:
 *   sm  → compact (filter tags)
 *   md  → standard duration / period picker   ← default
 */

import { Pressable, Text } from 'react-native';

interface PillProps {
  label: string;
  selected: boolean;
  onPress: () => void;
  size?: 'sm' | 'md';
  disabled?: boolean;
  className?: string;
}

export function Pill({
  label,
  selected,
  onPress,
  size = 'md',
  disabled = false,
  className = '',
}: PillProps) {
  const padding = size === 'sm'
    ? 'px-3 py-1.5'
    : 'px-[18px] py-[10px]';

  const textSize = size === 'sm' ? 'text-xs' : 'text-sm';

  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      style={{ opacity: disabled ? 0.45 : 1 }}
      className={`
        ${padding} rounded-full border
        ${selected
          ? 'bg-fixme-light-text-secondary dark:bg-fixme-text-secondary border-fixme-light-text-secondary dark:border-fixme-text-secondary'
          : 'bg-transparent border-fixme-light-border dark:border-fixme-border'
        }
        ${className}
      `}
    >
      <Text
        className={`
          ${textSize} font-semibold
          ${selected
            ? 'text-fixme-light-bg dark:text-fixme-bg'
            : 'text-fixme-light-text-secondary dark:text-fixme-text-secondary'
          }
        `}
      >
        {label}
      </Text>
    </Pressable>
  );
}
