/**
 * RadioCard — card-style radio option with title, description, and checkmark.
 *
 * Used for: tone selection, language selection, after-hours mode (bot settings).
 *
 * Usage:
 *   <RadioCard
 *     selected={tone === 'friendly'}
 *     onPress={() => setTone('friendly')}
 *     title="Friendly"
 *     description="Warm and approachable — great for beauty & wellness"
 *     icon="😊"
 *   />
 *
 * Usage (group):
 *   <View className="gap-2">
 *     {TONES.map(t => (
 *       <RadioCard key={t.value} selected={tone === t.value} onPress={() => setTone(t.value)} {...t} />
 *     ))}
 *   </View>
 */

import { Pressable, Text, View } from 'react-native';

interface RadioCardProps {
  selected: boolean;
  onPress: () => void;
  title: string;
  description?: string;
  /** Emoji or short string shown on the left */
  icon?: string;
  className?: string;
}

export function RadioCard({
  selected,
  onPress,
  title,
  description,
  icon,
  className = '',
}: RadioCardProps) {
  return (
    <Pressable
      onPress={onPress}
      className={`
        flex-row items-center px-4 py-4 rounded-2xl border
        ${selected
          ? 'bg-fixme-light-card dark:bg-fixme-card border-fixme-light-accent dark:border-fixme-accent'
          : 'bg-fixme-light-card dark:bg-fixme-card border-fixme-light-border dark:border-fixme-border'
        }
        ${className}
      `}
    >
      {/* Icon */}
      {icon && (
        <Text className="text-[22px] mr-3">{icon}</Text>
      )}

      {/* Title + description */}
      <View className="flex-1 mr-3">
        <Text
          className={`
            text-[15px] font-semibold
            ${selected
              ? 'text-fixme-light-text-primary dark:text-fixme-text-primary'
              : 'text-fixme-light-text-secondary dark:text-fixme-text-secondary'
            }
          `}
        >
          {title}
        </Text>
        {description && (
          <Text className="text-xs text-fixme-light-text-muted dark:text-fixme-text-muted mt-0.5 leading-[18px]">
            {description}
          </Text>
        )}
      </View>

      {/* Checkmark indicator */}
      <View
        className={`
          w-5 h-5 rounded-full border-2 items-center justify-center
          ${selected
            ? 'border-fixme-light-accent dark:border-fixme-accent bg-fixme-light-accent dark:bg-fixme-accent'
            : 'border-fixme-light-border dark:border-fixme-border bg-transparent'
          }
        `}
      >
        {selected && (
          <Text
            className="text-fixme-light-bg dark:text-fixme-bg font-bold"
            style={{ fontSize: 11, lineHeight: 14 }}
          >
            ✓
          </Text>
        )}
      </View>
    </Pressable>
  );
}
