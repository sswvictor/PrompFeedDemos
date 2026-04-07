/**
 * SectionHeader — category divider between groups of content.
 *
 * Uppercase, tracked, muted — creates clear visual sections without
 * heavy lines or boxes. Think Notion sections or Linear group headers.
 *
 * Usage:
 *   <SectionHeader label="Hair" />
 *   <SectionHeader label="Services" count={5} />
 *   <SectionHeader label="Amenities" count={3} onAction={() => clearAll()} actionLabel="Clear all" />
 *   <SectionHeader label="Account" className="mt-8" />
 */

import { Pressable, Text, View } from 'react-native';

interface SectionHeaderProps {
  label: string;
  count?: number;
  /** Optional right-side action (e.g. "Clear all") */
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

export function SectionHeader({
  label,
  count,
  actionLabel,
  onAction,
  className = '',
}: SectionHeaderProps) {
  return (
    <View className={`flex-row items-center mt-8 mb-3 px-1 ${className}`}>

      {/* Label */}
      <Text className="
        flex-1
        text-xs font-semibold uppercase tracking-widest
        text-fixme-light-text-muted dark:text-fixme-text-muted
      ">
        {label}
      </Text>

      {/* Count bubble */}
      {count !== undefined && (
        <View className="
          bg-fixme-light-bg-soft dark:bg-fixme-bg-soft
          border border-fixme-light-border dark:border-fixme-border
          rounded-full px-2 py-0.5 mr-2
        ">
          <Text className="text-[11px] font-semibold text-fixme-light-text-muted dark:text-fixme-text-muted">
            {count}
          </Text>
        </View>
      )}

      {/* Optional action */}
      {actionLabel && onAction && (
        <Pressable onPress={onAction} hitSlop={8}>
          <Text className="
            text-xs font-medium
            text-fixme-light-text-secondary dark:text-fixme-text-secondary
            underline
          ">
            {actionLabel}
          </Text>
        </Pressable>
      )}
    </View>
  );
}
