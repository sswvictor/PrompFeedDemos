/**
 * CalendarCard — connect / disconnect a calendar integration.
 *
 * Two states:
 *   connected    → shows green dot, connected label, disconnect button
 *   disconnected → shows connect prompt and connect button
 *
 * Design: clean card, generous padding, clear status at a glance.
 * The status dot pulses when connected (uses DirtyDot logic).
 * Think Notion's integration cards or Linear's connection settings.
 *
 * Usage:
 *   <CalendarCard
 *     icon="📅"
 *     title="Google Calendar"
 *     description="Sync bookings automatically. New bookings appear instantly."
 *     connected={isConnected}
 *     onConnect={handleConnect}
 *     onDisconnect={handleDisconnect}
 *     loading={isLoading}
 *   />
 */

import { ActivityIndicator, Text, View } from 'react-native';
import { colors } from '@/theme';
import { Button } from './Button';

interface CalendarCardProps {
  icon?: string;
  title: string;
  description?: string;
  connected: boolean;
  onConnect?: () => void;
  onDisconnect?: () => void;
  loading?: boolean;
  className?: string;
}

export function CalendarCard({
  icon = '📅',
  title,
  description,
  connected,
  onConnect,
  onDisconnect,
  loading = false,
  className = '',
}: CalendarCardProps) {
  return (
    <View
      className={`
        rounded-2xl border px-5 py-5
        bg-fixme-light-card dark:bg-fixme-card
        border-fixme-light-border dark:border-fixme-border
        ${className}
      `}
    >

      {/* Top row — icon + title + status */}
      <View className="flex-row items-start mb-3">

        {/* Icon */}
        <View className="
          w-11 h-11 rounded-xl mr-4
          items-center justify-center
          bg-fixme-light-bg-soft dark:bg-fixme-bg-soft
        ">
          <Text style={{ fontSize: 22 }}>{icon}</Text>
        </View>

        {/* Title + status */}
        <View className="flex-1 pt-0.5">
          <Text className="
            text-[15px] font-semibold mb-1
            text-fixme-light-text-primary dark:text-fixme-text-primary
          ">
            {title}
          </Text>

          {/* Status indicator */}
          <View className="flex-row items-center gap-1.5">
            {loading ? (
              <ActivityIndicator size="small" color={colors.textMuted} />
            ) : (
              <>
                <View
                  style={{ width: 7, height: 7, borderRadius: 3.5 }}
                  className={connected
                    ? 'bg-fixme-light-success dark:bg-fixme-success'
                    : 'bg-fixme-light-border dark:bg-fixme-border'
                  }
                />
                <Text className={`
                  text-[13px] font-medium
                  ${connected
                    ? 'text-fixme-light-success dark:text-fixme-success'
                    : 'text-fixme-light-text-muted dark:text-fixme-text-muted'
                  }
                `}>
                  {connected ? 'Connected' : 'Not connected'}
                </Text>
              </>
            )}
          </View>
        </View>
      </View>

      {/* Description */}
      {description && (
        <Text className="
          text-[13px] leading-[19px] mb-5
          text-fixme-light-text-muted dark:text-fixme-text-muted
        ">
          {description}
        </Text>
      )}

      {/* Action */}
      {!loading && (
        connected ? (
          <Button
            variant="ghost"
            size="sm"
            onPress={onDisconnect}
          >
            Disconnect
          </Button>
        ) : (
          <Button
            size="sm"
            onPress={onConnect}
          >
            Connect
          </Button>
        )
      )}

    </View>
  );
}
