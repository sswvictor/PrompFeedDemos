import { useState } from 'react';
import { Text, View } from 'react-native';

import type { BookingItem } from '@/lib/api';
import { colors } from '@/theme';

import { Avatar } from './Avatar';
import { Button } from './Button';
import { Card } from './Card';

interface BookingCardProps {
  booking: BookingItem;
  onComplete: (id: string) => void;
  onCancel: (id: string) => void;
  onReschedule: (booking: BookingItem) => void;
  onLateAlert: (id: string) => void;
  onReport: (id: string, customerId?: string) => void;
  expanded?: boolean;
  onToggleExpand?: (next: boolean) => void;
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

function ordinal(n: number) {
  const s = ['th', 'st', 'nd', 'rd'];
  const v = n % 100;
  return s[(v - 20) % 10] ?? s[v] ?? s[0];
}

export function BookingCard({
  booking,
  onComplete,
  onCancel,
  onReschedule,
  onLateAlert,
  onReport,
  expanded,
  onToggleExpand,
}: BookingCardProps) {
  const [internalExpanded, setInternalExpanded] = useState(false);
  const isExpanded = expanded ?? internalExpanded;
  const durationMs = new Date(booking.scheduled_end).getTime() - new Date(booking.scheduled_start).getTime();
  const durationMins = Math.round(durationMs / 60000);
  const visitLabel = (booking.visit_count ?? 0) > 1
    ? `${booking.visit_count}${ordinal(booking.visit_count!)} visit`
    : 'New client';

  function handleToggle() {
    const next = !isExpanded;
    if (expanded === undefined) {
      setInternalExpanded(next);
    }
    onToggleExpand?.(next);
  }

  return (
    <Card onPress={handleToggle} padding="none" className="mb-3">
      <View className="flex-row items-center gap-3 p-4">
        <Avatar name={booking.customer_name ?? '?'} size="sm" />
        <View className="flex-1">
          <Text className="text-fixme-text-primary font-semibold text-base" numberOfLines={1}>
            {booking.customer_name ?? 'Unknown'}
          </Text>
          <Text className="text-fixme-text-muted text-xs mt-0.5">
            {booking.service_name ?? 'Appointment'} · {durationMins} min
          </Text>
        </View>
        <View className="items-end gap-1">
          <Text className="text-fixme-accent font-bold text-base">{fmtTime(booking.scheduled_start)}</Text>
          <View className="bg-fixme-border/60 rounded-full px-2 py-0.5">
            <Text className="text-fixme-text-muted text-xs">{visitLabel}</Text>
          </View>
        </View>
      </View>

      {isExpanded && (
        <View className="border-t border-fixme-border px-4 pt-3 pb-4">
          {booking.customer_notes ? (
            <View className="bg-fixme-bg rounded-xl px-3 py-2 mb-3">
              <Text className="text-fixme-text-muted text-xs mb-1">Note from client</Text>
              <Text className="text-fixme-text-secondary text-sm">{booking.customer_notes}</Text>
            </View>
          ) : null}
          <View className="flex-row gap-2 flex-wrap">
            <Button
              size="xs"
              variant="ghost"
              onPress={() => onComplete(booking.booking_id)}
              className="border-fixme-success/40"
            >
              <Text style={{ color: colors.success }} className="text-xs font-semibold">Complete</Text>
            </Button>
            <Button
              size="xs"
              variant="ghost"
              onPress={() => onCancel(booking.booking_id)}
              className="border-red-800/40"
            >
              <Text className="text-red-400 text-xs font-semibold">Cancel</Text>
            </Button>
            <Button size="xs" variant="ghost" onPress={() => onReschedule(booking)}>
              Reschedule
            </Button>
            <Button size="xs" variant="ghost" onPress={() => onLateAlert(booking.booking_id)}>
              Running late
            </Button>
            <Button
              size="xs"
              variant="ghost"
              onPress={() => onReport(booking.booking_id, booking.customer_id)}
              className="border-orange-800/40"
            >
              <Text className="text-orange-400 text-xs font-semibold">Report</Text>
            </Button>
          </View>
        </View>
      )}
    </Card>
  );
}
