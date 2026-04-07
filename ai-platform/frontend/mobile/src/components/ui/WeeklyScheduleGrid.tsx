import { Pressable, ScrollView, Text, View } from 'react-native';

import type { BookingItem, TimeBlock } from '@/lib/api';

const HOUR_SLOTS = Array.from({ length: 13 }, (_, idx) => 8 + idx);
const TIME_LABEL_WIDTH = 48;
const DAY_COLUMN_WIDTH = 84;

interface WeekDayItem {
  key: string;
  weekdayShort: string;
  dayNumber: number;
}

interface WeeklyScheduleGridProps {
  weekDays: WeekDayItem[];
  selectedDay: string;
  bookingsByDay: Record<string, BookingItem[]>;
  timeBlocks: TimeBlock[];
  onSelectSlot: (dayKey: string, options?: { bookingId?: string; hour?: number; blocked?: boolean }) => void;
}

function slotIso(dayKey: string, hour: number) {
  return `${dayKey}T${String(hour).padStart(2, '0')}:00:00`;
}

function overlaps(startsAt: string, endsAt: string, slotStartIso: string, slotEndIso: string) {
  return new Date(startsAt).getTime() < new Date(slotEndIso).getTime()
    && new Date(endsAt).getTime() > new Date(slotStartIso).getTime();
}

function firstWord(value?: string | null) {
  return (value ?? '').trim().split(/\s+/)[0] || 'Booked';
}

function blockLabel(value?: string | null) {
  const cleaned = (value ?? '').trim();
  if (!cleaned) return 'Blocked';
  const [prefix] = cleaned.split(':');
  return prefix || 'Blocked';
}

export function WeeklyScheduleGrid({
  weekDays,
  selectedDay,
  bookingsByDay,
  timeBlocks,
  onSelectSlot,
}: WeeklyScheduleGridProps) {
  return (
    <View className="rounded-2xl border border-fixme-border overflow-hidden bg-fixme-bg">
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View>
          <View className="flex-row border-b border-fixme-border bg-fixme-card">
            <View style={{ width: TIME_LABEL_WIDTH }} className="border-r border-fixme-border px-2 py-3" />
            {weekDays.map((day) => {
              const bookings = bookingsByDay[day.key] ?? [];
              const isSelected = day.key === selectedDay;
              return (
                <Pressable
                  key={day.key}
                  onPress={() => onSelectSlot(day.key)}
                  style={{ width: DAY_COLUMN_WIDTH }}
                  className={`border-r border-fixme-border px-2 py-3 ${isSelected ? 'bg-fixme-text-primary/10' : ''}`}
                >
                  <Text className={`text-[10px] uppercase font-semibold ${isSelected ? 'text-fixme-text-primary' : 'text-fixme-text-muted'}`}>
                    {day.weekdayShort}
                  </Text>
                  <Text className={`text-sm font-bold mt-0.5 ${isSelected ? 'text-fixme-text-primary' : 'text-fixme-text-secondary'}`}>
                    {day.dayNumber}
                  </Text>
                  <Text className="text-[10px] text-fixme-text-muted mt-1">
                    {bookings.length > 0 ? `${bookings.length} booked` : 'Free'}
                  </Text>
                </Pressable>
              );
            })}
          </View>

          {HOUR_SLOTS.map((hour) => (
            <View key={hour} className="flex-row border-b border-fixme-border/70">
              <View
                style={{ width: TIME_LABEL_WIDTH, minHeight: 52 }}
                className="border-r border-fixme-border px-2 py-2 justify-start bg-fixme-card"
              >
                <Text className="text-[10px] font-semibold text-fixme-text-muted">
                  {String(hour).padStart(2, '0')}:00
                </Text>
              </View>

              {weekDays.map((day) => {
                const slotStartIso = slotIso(day.key, hour);
                const slotEndIso = slotIso(day.key, hour + 1);
                const booking = (bookingsByDay[day.key] ?? []).find((item) =>
                  overlaps(item.scheduled_start, item.scheduled_end, slotStartIso, slotEndIso));
                const block = timeBlocks.find((item) =>
                  overlaps(item.starts_at, item.ends_at, slotStartIso, slotEndIso));
                const isSelected = day.key === selectedDay;

                let cellClass = 'bg-fixme-bg';
                let title = 'Free';
                let subtitle = '';

                if (booking) {
                  cellClass = 'bg-fixme-accent/15';
                  title = firstWord(booking.customer_name);
                  subtitle = new Date(booking.scheduled_start).getHours() === hour
                    ? new Date(booking.scheduled_start).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
                    : booking.service_name ?? 'Booked';
                } else if (block) {
                  cellClass = 'bg-fixme-card';
                  title = blockLabel(block.label);
                  subtitle = '';
                }

                return (
                  <Pressable
                    key={`${day.key}-${hour}`}
                    onPress={() => onSelectSlot(day.key, {
                      bookingId: booking?.booking_id,
                      hour,
                      blocked: !!block,
                    })}
                    style={{ width: DAY_COLUMN_WIDTH, minHeight: 52 }}
                    className={`border-r border-fixme-border px-2 py-2 active:opacity-80 ${cellClass} ${isSelected ? 'border-fixme-accent/40' : ''}`}
                  >
                    <Text
                      className={`text-[10px] font-semibold ${
                        booking ? 'text-fixme-text-primary' : block ? 'text-fixme-text-secondary' : 'text-fixme-text-muted'
                      }`}
                      numberOfLines={1}
                    >
                      {title}
                    </Text>
                    {subtitle ? (
                      <Text className="text-[10px] text-fixme-text-muted mt-0.5" numberOfLines={1}>
                        {subtitle}
                      </Text>
                    ) : null}
                  </Pressable>
                );
              })}
            </View>
          ))}
        </View>
      </ScrollView>
    </View>
  );
}
