/**
 * AmenityChip — selectable chip for amenity/tag selection grids.
 *
 * Selected state: green success ring + background tint.
 * Unselected: standard card border.
 *
 * Usage:
 *   <AmenityChip
 *     label="Parking"
 *     icon="🅿️"
 *     selected={amenities.includes('parking')}
 *     onPress={() => toggleAmenity('parking')}
 *   />
 *
 * Usage (grid):
 *   <View className="flex-row flex-wrap gap-2">
 *     {AMENITIES.map(a => (
 *       <AmenityChip key={a.id} {...a} selected={selected.includes(a.id)} onPress={() => toggle(a.id)} />
 *     ))}
 *   </View>
 */

import { Pressable, Text, View } from 'react-native';

interface AmenityChipProps {
  label: string;
  icon?: string;
  selected: boolean;
  onPress: () => void;
  className?: string;
}

export function AmenityChip({
  label,
  icon,
  selected,
  onPress,
  className = '',
}: AmenityChipProps) {
  return (
    <Pressable
      onPress={onPress}
      className={`
        flex-row items-center px-3.5 py-2.5 rounded-2xl border gap-1.5
        ${selected
          ? 'bg-fixme-light-success/10 dark:bg-fixme-success/10 border-fixme-light-success dark:border-fixme-success'
          : 'bg-fixme-light-card dark:bg-fixme-card border-fixme-light-border dark:border-fixme-border'
        }
        ${className}
      `}
    >
      {icon && <Text style={{ fontSize: 15 }}>{icon}</Text>}

      <Text
        className={`
          text-[13px] font-medium
          ${selected
            ? 'text-fixme-light-success dark:text-fixme-success'
            : 'text-fixme-light-text-secondary dark:text-fixme-text-secondary'
          }
        `}
      >
        {label}
      </Text>

      {/* Checkmark — only when selected */}
      {selected && (
        <View className="ml-0.5">
          <Text
            className="text-fixme-light-success dark:text-fixme-success font-bold"
            style={{ fontSize: 11 }}
          >
            ✓
          </Text>
        </View>
      )}
    </Pressable>
  );
}
