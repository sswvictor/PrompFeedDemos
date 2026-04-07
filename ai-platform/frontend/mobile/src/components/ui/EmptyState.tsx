/**
 * EmptyState — full-screen moment when there's nothing to show yet.
 *
 * Design intent: not a sad error screen — an invitation.
 * Cinematic: large icon, bold headline, generous breathing room,
 * clear single CTA. Think Airbnb's empty search, Uber's empty history.
 *
 * Usage:
 *   <EmptyState
 *     icon="✂️"
 *     title="Your menu is empty"
 *     body="Add your first service and start taking bookings."
 *     action="Add your first service"
 *     onAction={openAdd}
 *   />
 *
 *   // Without a CTA (informational only)
 *   <EmptyState icon="📅" title="No bookings yet" body="Your calendar is clear." />
 *
 *   // Compact variant (inside a tab, not full-screen)
 *   <EmptyState icon="⭐" title="No reviews yet" compact />
 */

import { Text, View } from 'react-native';
import { Button } from './Button';

interface EmptyStateProps {
  icon: string;
  title: string;
  body?: string;
  /** CTA button label */
  action?: string;
  onAction?: () => void;
  /** Compact — less vertical padding, smaller icon (for use inside tabs) */
  compact?: boolean;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  body,
  action,
  onAction,
  compact = false,
  className = '',
}: EmptyStateProps) {
  return (
    <View
      className={`
        flex-1 items-center justify-center
        ${compact ? 'px-8 py-16' : 'px-10 py-24'}
        ${className}
      `}
    >
      {/* Icon — large, cinematic, lots of space below */}
      <Text
        style={{ fontSize: compact ? 48 : 64, lineHeight: compact ? 60 : 76 }}
        className="mb-7"
      >
        {icon}
      </Text>

      {/* Headline — bold, centred, confident */}
      <Text
        className="
          text-center font-bold tracking-tight mb-3
          text-fixme-light-text-primary dark:text-fixme-text-primary
        "
        style={{ fontSize: compact ? 20 : 24, lineHeight: compact ? 26 : 31 }}
      >
        {title}
      </Text>

      {/* Body — soft, generous line-height */}
      {body && (
        <Text
          className="
            text-[15px] text-center leading-[23px] mb-9
            text-fixme-light-text-muted dark:text-fixme-text-muted
          "
        >
          {body}
        </Text>
      )}

      {/* CTA — only rendered when action is provided */}
      {action && onAction && (
        <Button size="lg" onPress={onAction}>
          {action}
        </Button>
      )}
    </View>
  );
}
