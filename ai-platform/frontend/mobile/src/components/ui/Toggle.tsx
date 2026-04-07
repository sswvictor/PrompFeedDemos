/**
 * Toggle — Switch row with title, optional subtitle, and dark/light theming.
 *
 * Usage:
 *   <Toggle
 *     label="Home visits"
 *     description="Available at client's location"
 *     value={homeAvail}
 *     onValueChange={setHomeAvail}
 *   />
 *   <Toggle label="Active" value={isActive} onValueChange={setIsActive} />
 */

import { Switch, View } from 'react-native';
import { colors } from '@/theme';
import { Caption } from './Caption';

interface ToggleProps {
  label: string;
  description?: string;
  value: boolean;
  onValueChange: (value: boolean) => void;
  disabled?: boolean;
  className?: string;
}

export function Toggle({
  label,
  description,
  value,
  onValueChange,
  disabled = false,
  className = '',
}: ToggleProps) {
  return (
    <View
      className={`
        flex-row items-center
        bg-fixme-light-card dark:bg-fixme-card
        px-[18px] py-4
        ${className}
      `}
      style={{ opacity: disabled ? 0.45 : 1 }}
    >
      <View className="flex-1 mr-3">
        <Caption variant="secondary" className="text-[15px] font-medium">
          {label}
        </Caption>
        {description && (
          <Caption className="mt-0.5">{description}</Caption>
        )}
      </View>

      <Switch
        value={value}
        onValueChange={disabled ? undefined : onValueChange}
        trackColor={{ false: colors.border, true: colors.success }}
        thumbColor={colors.accent}
      />
    </View>
  );
}
