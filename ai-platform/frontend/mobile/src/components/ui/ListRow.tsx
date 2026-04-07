/**
 * ListRow — settings-style row: icon container + title + subtitle + chevron.
 *
 * Think iOS Settings or Uber driver settings — clean, airy, clear hierarchy.
 *
 * Usage:
 *   <ListRow
 *     icon="✂️"
 *     title="Services"
 *     subtitle="Manage your menu"
 *     onPress={() => router.push('/settings/services')}
 *   />
 *
 *   <ListRow icon="📅" title="Calendar" onPress={…} />
 *
 *   // Without chevron (informational)
 *   <ListRow icon="📍" title="Stockholm" chevron={false} />
 *
 *   // With a right accessory instead of chevron
 *   <ListRow icon="🌙" title="Dark mode" rightAccessory={<Switch … />} />
 *
 *   // Destructive (logout, delete)
 *   <ListRow icon="🚪" title="Log out" destructive onPress={handleLogout} />
 */

import { Pressable, Text, View } from 'react-native';

interface ListRowProps {
  icon?: string;
  title: string;
  subtitle?: string;
  onPress?: () => void;
  chevron?: boolean;
  rightAccessory?: React.ReactNode;
  destructive?: boolean;
  className?: string;
}

export function ListRow({
  icon,
  title,
  subtitle,
  onPress,
  chevron = true,
  rightAccessory,
  destructive = false,
  className = '',
}: ListRowProps) {
  const Wrapper = onPress ? Pressable : View;
  const wrapperProps = onPress
    ? {
        onPress,
        style: ({ pressed }: { pressed: boolean }) => ({ opacity: pressed ? 0.6 : 1 }),
      }
    : {};

  return (
    <Wrapper
      {...(wrapperProps as object)}
      className={`
        flex-row items-center
        px-5 py-4
        bg-fixme-light-card dark:bg-fixme-card
        ${className}
      `}
    >
      {/* Icon container */}
      {icon && (
        <View
          className="
            w-9 h-9 rounded-xl mr-4
            items-center justify-center
            bg-fixme-light-bg-soft dark:bg-fixme-bg-soft
          "
        >
          <Text style={{ fontSize: 18 }}>{icon}</Text>
        </View>
      )}

      {/* Title + subtitle */}
      <View className="flex-1">
        <Text
          className={`
            text-[15px] font-medium
            ${destructive
              ? 'text-fixme-light-error dark:text-fixme-error'
              : 'text-fixme-light-text-primary dark:text-fixme-text-primary'
            }
          `}
        >
          {title}
        </Text>
        {subtitle && (
          <Text className="text-xs text-fixme-light-text-muted dark:text-fixme-text-muted mt-0.5">
            {subtitle}
          </Text>
        )}
      </View>

      {/* Right side — accessory or chevron */}
      {rightAccessory
        ? rightAccessory
        : chevron && (
            <Text className="text-fixme-light-text-muted dark:text-fixme-text-muted text-lg ml-2">
              ›
            </Text>
          )
      }
    </Wrapper>
  );
}
