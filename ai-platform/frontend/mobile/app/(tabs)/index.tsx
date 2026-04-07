import { useState, useCallback, useEffect } from 'react';
import {
  View, Text, ScrollView, Pressable, RefreshControl,
  Alert, Modal, TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as SecureStore from 'expo-secure-store';
import { removeTokenFromBackend } from '@/lib/notifications';
import {
  getHomeDashboard,
  getProviderProfileById,
  rescheduleBooking,
  updateBookingStatus,
  sendProviderLateAlert,
  submitCustomerReliabilityReport,
  getInboxConversations,
  getBookingUpdateRequests,
  respondToBookingUpdate,
  getProviderTimeBlocks,
  createProviderTimeBlock,
  deleteProviderTimeBlock,
  importUrl,
  applyImport,
  type BookingItem,
  type ImportPreview,
  type BookingUpdateRequest,
  type ProviderPublicService,
  type TimeBlock,
} from '@/lib/api';
import { useAuth } from '@/stores/auth';
import { colors } from '@/theme';
import { BookingFlow } from './booking-flow';
import {
  Avatar, BookingCard as SharedBookingCard, Button, Card, EmptyState, LoadingSpinner,
  SegmentedControl, SectionHeader, StatCard, WeeklyScheduleGrid,
} from '@/components/ui';
import { useProviderHomeUi } from '@/stores/providerHomeUi';
import { formatPrice } from '@/utils/currency';

// ─── Mock data (shown when API has no data yet) ───────────────────────────────

const _now = Date.now();
const _h = (hours: number) => new Date(_now + hours * 3_600_000).toISOString();

const MOCK_BOOKINGS: BookingItem[] = [
  {
    booking_id: 'mock-1',
    customer_id: 'cust-1',
    customer_name: 'Sophie Laurent',
    service_name: 'Balayage + Toning',
    scheduled_start: _h(1.5),
    scheduled_end: _h(4),
    status: 'confirmed',
    visit_count: 3,
    price_ex_vat: 2800,
    customer_notes: 'Please use Olaplex this time 🙏',
  },
  {
    booking_id: 'mock-2',
    customer_id: 'cust-2',
    customer_name: 'Elena Marchetti',
    service_name: 'Cut & Blowdry',
    scheduled_start: _h(5),
    scheduled_end: _h(6),
    status: 'confirmed',
    visit_count: 1,
    price_ex_vat: 1200,
    customer_notes: null,
  },
  {
    booking_id: 'mock-3',
    customer_id: 'cust-3',
    customer_name: 'Anna Bergström',
    service_name: 'Full Color',
    scheduled_start: _h(7),
    scheduled_end: _h(9),
    status: 'confirmed',
    visit_count: 7,
    price_ex_vat: 2200,
    customer_notes: null,
  },
];

const MOCK_UPDATE_REQUESTS: BookingUpdateRequest[] = [
  {
    request_id: 'req-mock-1',
    booking_id: 'mock-1',
    customer_name: 'Sophie Laurent',
    service_name: 'Balayage + Toning',
    original_start: _h(1.5),
    requested_start: _h(25),
    customer_message: 'Something came up — can we move to tomorrow?',
  },
];

const MOCK_DASHBOARD = {
  bookings_today: MOCK_BOOKINGS,
  bookings_upcoming: [],
  next_booking: MOCK_BOOKINGS[0],
  revenue_today: 6200,
  revenue_this_week: 18400,
  currency: 'SEK',
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
}

function fmtSek(value: number | undefined, currency = 'SEK') {
  if (value == null) return `— ${currency}`;
  return formatPrice(value, currency);
}

function dayKey(iso: string) {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function dayKeyFromDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function dateFromDayKey(day: string) {
  const [y, m, d] = day.split('-').map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
}

function shiftDayKey(day: string, deltaDays: number) {
  const next = dateFromDayKey(day);
  next.setDate(next.getDate() + deltaDays);
  return dayKeyFromDate(next);
}

function startOfWeek(anchor: Date) {
  const d = new Date(anchor);
  const weekdayMon = (d.getDay() + 6) % 7;
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - weekdayMon);
  return d;
}

function buildWeekDays(weekStartDate: Date) {
  return Array.from({ length: 7 }, (_, idx) => {
    const date = new Date(weekStartDate);
    date.setDate(weekStartDate.getDate() + idx);
    return {
      date,
      key: dayKeyFromDate(date),
      dayNumber: date.getDate(),
      weekdayShort: date.toLocaleDateString('en-GB', { weekday: 'short' }),
    };
  });
}

function buildCalendarDays(monthDate: Date) {
  const year = monthDate.getFullYear();
  const month = monthDate.getMonth();
  const first = new Date(year, month, 1);
  const firstWeekdayMon = (first.getDay() + 6) % 7;
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrevMonth = new Date(year, month, 0).getDate();

  return Array.from({ length: 42 }, (_, i) => {
    const dayOffset = i - firstWeekdayMon + 1;
    let date: Date;
    let inMonth = true;
    if (dayOffset <= 0) {
      date = new Date(year, month - 1, daysInPrevMonth + dayOffset);
      inMonth = false;
    } else if (dayOffset > daysInMonth) {
      date = new Date(year, month + 1, dayOffset - daysInMonth);
      inMonth = false;
    } else {
      date = new Date(year, month, dayOffset);
    }
    return { date, key: dayKeyFromDate(date), dayNumber: date.getDate(), inMonth };
  });
}

function formatWeekRange(weekStartDate: Date) {
  const from = new Date(weekStartDate);
  const to = new Date(weekStartDate);
  to.setDate(to.getDate() + 6);
  const fromLabel = from.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  const toLabel = to.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  return `${fromLabel} – ${toLabel}`;
}

function localDateTimeIso(day: string, hhmm: string) {
  return `${day}T${hhmm}:00`;
}

function dayRangeIso(day: string) {
  return { fromAt: `${day}T00:00:00`, toAt: `${day}T23:59:59` };
}

function weekRangeIso(weekStartDate: Date) {
  const from = dayKeyFromDate(weekStartDate);
  const to = dayKeyFromDate(new Date(weekStartDate.getFullYear(), weekStartDate.getMonth(), weekStartDate.getDate() + 6));
  return { fromAt: `${from}T00:00:00`, toAt: `${to}T23:59:59` };
}

function inputDateValue(iso: string) {
  return dayKey(iso);
}

function hourToLabel(hour: number) {
  return `${String(hour).padStart(2, '0')}:00`;
}

// ─── Calendar day dot color ───────────────────────────────────────────────────
// Returns a Tailwind bg class or null (no dot = free day)

function dayDotClass(
  bookingCount: number,
  hasBlock: boolean,
  isPast: boolean,
): string | null {
  if (isPast) return null;
  if (hasBlock && bookingCount === 0) return 'bg-fixme-border'; // blocked, grey
  if (bookingCount === 0) return null;                           // free, no dot
  if (bookingCount <= 2) return 'bg-amber-400';                 // partially booked
  return 'bg-fixme-accent';                                     // heavily booked
}

// ─── Setup wizard cards ───────────────────────────────────────────────────────

function SetupImportCard({ onDone }: { onDone: () => void }) {
  const [dismissed, setDismissed] = useState(false);
  const [done, setDone]           = useState(false);
  const [url, setUrl]             = useState('');
  const [scanning, setScanning]   = useState(false);
  const [preview, setPreview]     = useState<ImportPreview | null>(null);
  const [applying, setApplying]   = useState(false);

  useEffect(() => {
    SecureStore.getItemAsync('fixme_setup_import_done').then(v => {
      if (v === '1') setDone(true);
    });
  }, []);

  if (dismissed || done) return null;

  async function handleScan() {
    if (!url.trim()) {
      Alert.alert('Enter a URL', 'Paste your Instagram or website URL first.');
      return;
    }
    setScanning(true);
    try {
      const data = await importUrl(url.trim());
      setPreview(data);
    } catch (err: unknown) {
      Alert.alert('Scan failed', (err as Error).message || 'Could not scan that URL.');
    } finally {
      setScanning(false);
    }
  }

  async function handleApply() {
    if (!preview) return;
    setApplying(true);
    try {
      await applyImport(preview);
      await SecureStore.setItemAsync('fixme_setup_import_done', '1');
      setDone(true);
      onDone();
    } catch (err: unknown) {
      Alert.alert('Error', (err as Error).message || 'Could not apply import.');
    } finally {
      setApplying(false);
    }
  }

  return (
    <Card className="mx-5 mb-3">
      <View className="flex-row items-start justify-between mb-3">
        <View className="flex-1 mr-3">
          <Text className="text-fixme-text-primary font-bold text-sm">Build your profile</Text>
          <Text className="text-fixme-text-muted text-xs mt-0.5">
            Paste your Instagram or website — we'll auto-fill your services
          </Text>
        </View>
        <Pressable onPress={() => setDismissed(true)} className="w-7 h-7 items-center justify-center active:opacity-60">
          <Text style={{ color: '#666', fontSize: 18, lineHeight: 18 }}>✕</Text>
        </Pressable>
      </View>

      {!preview ? (
        <>
          <TextInput
            value={url}
            onChangeText={setUrl}
            placeholder="https://instagram.com/yoursalon"
            placeholderTextColor={colors.textMuted}
            autoCapitalize="none"
            keyboardType="url"
            style={{ color: colors.textPrimary }}
            className="bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2.5 text-sm mb-3"
          />
          <Button onPress={handleScan} loading={scanning} fullWidth>
            Scan profile
          </Button>
        </>
      ) : (
        <>
          <View className="bg-fixme-bg rounded-xl p-3 mb-3 gap-1">
            {preview.bio ? (
              <Text className="text-fixme-text-muted text-xs">✓ Bio found</Text>
            ) : null}
            {(preview.services?.length ?? 0) > 0 ? (
              <Text className="text-fixme-text-muted text-xs">
                ✓ {preview.services!.length} service{preview.services!.length !== 1 ? 's' : ''} found
              </Text>
            ) : null}
            {(preview.working_hours?.length ?? 0) > 0 ? (
              <Text className="text-fixme-text-muted text-xs">✓ Working hours found</Text>
            ) : null}
            {(preview.amenities?.length ?? 0) > 0 ? (
              <Text className="text-fixme-text-muted text-xs">
                ✓ {preview.amenities!.length} amenities found
              </Text>
            ) : null}
          </View>
          <View className="flex-row gap-2">
            <Button variant="ghost" onPress={() => setPreview(null)} className="flex-1">
              Back
            </Button>
            <Button onPress={handleApply} loading={applying} className="flex-1">
              Apply
            </Button>
          </View>
        </>
      )}
    </Card>
  );
}

function SetupVerifyCard() {
  const [dismissed, setDismissed] = useState(false);
  const [done, setDone]           = useState(false);

  useEffect(() => {
    SecureStore.getItemAsync('fixme_setup_verify_done').then(v => {
      if (v === '1') setDone(true);
    });
  }, []);

  if (dismissed || done) return null;

  function handleVerify() {
    Alert.alert(
      'Verify your business',
      'Business verification unlocks your trust badge and higher booking limits. Complete verification at fixmeapp.se/provider/settings.',
      [
        {
          text: 'Done — I verified',
          onPress: async () => {
            await SecureStore.setItemAsync('fixme_setup_verify_done', '1');
            setDone(true);
          },
        },
        { text: 'Later', style: 'cancel' },
      ],
    );
  }

  return (
    <Card className="mx-5 mb-3">
      <View className="flex-row items-start justify-between mb-3">
        <View className="flex-1 mr-3">
          <Text className="text-fixme-text-primary font-bold text-sm">Verify your business</Text>
          <Text className="text-fixme-text-muted text-xs mt-0.5">
            Get a trust badge and unlock higher booking limits
          </Text>
        </View>
        <Pressable onPress={() => setDismissed(true)} className="w-7 h-7 items-center justify-center active:opacity-60">
          <Text style={{ color: '#666', fontSize: 18, lineHeight: 18 }}>✕</Text>
        </Pressable>
      </View>
      <Button variant="ghost" onPress={handleVerify} fullWidth>
        Verify now →
      </Button>
    </Card>
  );
}

// ─── Booking update request card ──────────────────────────────────────────────

function BookingUpdateCard({
  req, onRespond, responding,
}: {
  req:        BookingUpdateRequest;
  onRespond:  (requestId: string, action: 'accept' | 'decline') => void;
  responding: boolean;
}) {
  return (
    <Card className="mb-3 border-fixme-accent/30">
      <View className="flex-row items-center gap-2 mb-2">
        <View className="w-2 h-2 rounded-full bg-fixme-accent" />
        <Text className="text-fixme-accent text-xs font-semibold uppercase tracking-wider">
          Reschedule request
        </Text>
      </View>
      <Text className="text-fixme-text-primary font-semibold text-sm">
        {req.customer_name ?? 'Customer'}
      </Text>
      {req.service_name ? (
        <Text className="text-fixme-text-muted text-xs mt-0.5">{req.service_name}</Text>
      ) : null}
      <View className="bg-fixme-bg rounded-xl px-3 py-2 mt-2 gap-0.5">
        <Text className="text-fixme-text-muted text-xs">Current</Text>
        <Text className="text-fixme-text-secondary text-xs">
          {fmtDate(req.original_start)} · {fmtTime(req.original_start)}
        </Text>
        <Text className="text-fixme-text-muted text-xs mt-1">Requested</Text>
        <Text className="text-fixme-accent text-xs font-semibold">
          {fmtDate(req.requested_start)} · {fmtTime(req.requested_start)}
        </Text>
      </View>
      {req.customer_message ? (
        <View className="bg-fixme-bg rounded-xl px-3 py-2 mt-2">
          <Text className="text-fixme-text-secondary text-xs italic">
            "{req.customer_message}"
          </Text>
        </View>
      ) : null}
      <View className="flex-row gap-2 mt-3">
        <Button
          variant="ghost"
          size="sm"
          onPress={() => onRespond(req.request_id, 'decline')}
          disabled={responding}
          className="flex-1 border-red-800/40"
        >
          <Text className="text-red-400 text-sm font-semibold">Decline</Text>
        </Button>
        <Button
          size="sm"
          onPress={() => onRespond(req.request_id, 'accept')}
          disabled={responding}
          loading={responding}
          className="flex-1"
        >
          Accept
        </Button>
      </View>
    </Card>
  );
}
 

// ─── Main screen ──────────────────────────────────────────────────────────────

export default function HomeScreen() {
  const { providerName, token, isHydrated, clearAuth } = useAuth();
  const canQuery = isHydrated && !!token;
  const queryClient = useQueryClient();

  const [calendarOpen, setCalendarOpen] = useState(false);
  const [calendarView, setCalendarView] = useState<'week' | 'month'>('week');
  const [calendarMonth, setCalendarMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [weekStartDate, setWeekStartDate] = useState(() => startOfWeek(new Date()));
  const [selectedDay, setSelectedDay] = useState(() => dayKey(new Date().toISOString()));
  const [focusedBookingId, setFocusedBookingId] = useState<string | null>(null);
  const [rescheduleBookingTarget, setRescheduleBookingTarget] = useState<BookingItem | null>(null);
  const [rescheduleDate, setRescheduleDate] = useState('');
  const [rescheduleStartTime, setRescheduleStartTime] = useState('');
  const [rescheduleEndTime, setRescheduleEndTime] = useState('');
  const [bookingFlowVisible, setBookingFlowVisible] = useState(false);
  const [bookingFlowService, setBookingFlowService] = useState<ProviderPublicService | null>(null);
  const [bookingFlowInitialDate, setBookingFlowInitialDate] = useState<Date | null>(null);
  const activeView = useProviderHomeUi((state) => state.activeView);
  const setActiveView = useProviderHomeUi((state) => state.setActiveView);

  const [timeBlocks, setTimeBlocks] = useState<TimeBlock[]>([]);
  const [blocksLoading, setBlocksLoading] = useState(false);
  const [blockSaving, setBlockSaving] = useState(false);
  const [blockKind, setBlockKind] = useState<'lunch' | 'private'>('lunch');
  const [blockStartTime, setBlockStartTime] = useState('12:00');
  const [blockEndTime, setBlockEndTime] = useState('12:30');
  const [blockReason, setBlockReason] = useState('');

  const weekDays = buildWeekDays(weekStartDate);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['home-dashboard'],
    queryFn:  getHomeDashboard,
    enabled: canQuery,
    refetchInterval: canQuery ? 60_000 : false,
  });

  const { data: conversations = [] } = useQuery({
    queryKey: ['inbox-conversations'],
    queryFn:  getInboxConversations,
    enabled: canQuery,
    staleTime: 60_000,
  });

  const { data: updateRequests = [] } = useQuery({
    queryKey: ['booking-update-requests'],
    queryFn:  getBookingUpdateRequests,
    enabled: canQuery,
    staleTime: 30_000,
    retry: false,
  });

  // Use mock data when real data isn't loaded yet
  const dashboard = data ?? MOCK_DASHBOARD;
  const liveUpdateRequests = updateRequests.length > 0 ? updateRequests : MOCK_UPDATE_REQUESTS;
  const isMock = !data;
  const providerId = dashboard.provider_id;

  const { data: providerProfile } = useQuery({
    queryKey: ['provider-public-profile', providerId],
    queryFn: () => getProviderProfileById(providerId!),
    enabled: canQuery && !!providerId,
    staleTime: 5 * 60_000,
  });

  const needsHumanConversations = conversations.filter((conv) => conv.needs_human);

  const [refreshing, setRefreshing] = useState(false);
  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  }, [refetch]);

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateBookingStatus(id, status),
    onSuccess:  () => queryClient.invalidateQueries({ queryKey: ['home-dashboard'] }),
  });

  const updateRespondMut = useMutation({
    mutationFn: ({ requestId, action }: { requestId: string; action: 'accept' | 'decline' }) =>
      respondToBookingUpdate(requestId, action),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['booking-update-requests'] }),
    onError:   (err: Error) => Alert.alert('Error', err.message),
  });

  const rescheduleMut = useMutation({
    mutationFn: ({ bookingId, newStart, newEnd }: { bookingId: string; newStart: string; newEnd: string }) =>
      rescheduleBooking(bookingId, newStart, newEnd),
    onSuccess: (booking) => {
      queryClient.invalidateQueries({ queryKey: ['home-dashboard'] });
      const nextDay = dayKey(booking.scheduled_start);
      setSelectedDay(nextDay);
      setWeekStartDate(startOfWeek(dateFromDayKey(nextDay)));
      setCalendarMonth(new Date(new Date(booking.scheduled_start).getFullYear(), new Date(booking.scheduled_start).getMonth(), 1));
      setFocusedBookingId(booking.booking_id);
      setRescheduleBookingTarget(null);
      Alert.alert('Booking rescheduled', 'The customer booking view is updated and the customer has been notified by email.');
    },
    onError: (err: Error) => Alert.alert('Could not reschedule', err.message || 'Try another slot.'),
  });

  async function fetchTimeBlocks() {
    if (!token) return;
    const { fromAt, toAt } = calendarView === 'week'
      ? weekRangeIso(weekStartDate)
      : dayRangeIso(selectedDay);
    try {
      setBlocksLoading(true);
      const rows = await getProviderTimeBlocks(fromAt, toAt);
      setTimeBlocks(Array.isArray(rows) ? rows : []);
    } catch {
      setTimeBlocks([]);
    } finally {
      setBlocksLoading(false);
    }
  }

  useEffect(() => {
    if (!calendarOpen || !token) return;
    fetchTimeBlocks();
  }, [calendarOpen, calendarView, selectedDay, token, weekStartDate]);

  async function handleAddTimeBlock() {
    if (!/^\d{2}:\d{2}$/.test(blockStartTime) || !/^\d{2}:\d{2}$/.test(blockEndTime)) {
      Alert.alert('Invalid time', 'Use HH:MM format.');
      return;
    }
    if (blockEndTime <= blockStartTime) {
      Alert.alert('Invalid time range', 'End must be after start.');
      return;
    }
    try {
      setBlockSaving(true);
      await createProviderTimeBlock({
        label: blockReason?.trim() ? `${blockKind}: ${blockReason.trim()}` : blockKind,
        starts_at: localDateTimeIso(selectedDay, blockStartTime),
        ends_at: localDateTimeIso(selectedDay, blockEndTime),
      });
      setBlockReason('');
      await fetchTimeBlocks();
    } catch (err: unknown) {
      Alert.alert('Could not add blocker', (err as Error).message || 'Try again.');
    } finally {
      setBlockSaving(false);
    }
  }

  async function handleDeleteTimeBlock(blockId: string) {
    try {
      setBlockSaving(true);
      await deleteProviderTimeBlock(blockId);
      await fetchTimeBlocks();
    } catch (err: unknown) {
      Alert.alert('Could not delete blocker', (err as Error).message || 'Try again.');
    } finally {
      setBlockSaving(false);
    }
  }

  function handleSelectDay(nextDay: string) {
    setSelectedDay(nextDay);
    const nextDate = dateFromDayKey(nextDay);
    setWeekStartDate(startOfWeek(nextDate));
    setCalendarMonth(new Date(nextDate.getFullYear(), nextDate.getMonth(), 1));
    setFocusedBookingId(null);
  }

  function handleCreateBookingFromSlot(dayKeyValue: string, hour: number) {
    const services = providerProfile?.services ?? [];
    if (!providerId || services.length === 0) {
      Alert.alert('No services available', 'Add a service first before creating a booking from the calendar.');
      return;
    }

    const nextDate = dateFromDayKey(dayKeyValue);
    nextDate.setHours(hour, 0, 0, 0);
    setBookingFlowInitialDate(nextDate);

    if (services.length === 1) {
      setBookingFlowService(services[0]);
      setBookingFlowVisible(true);
      return;
    }

    Alert.alert(
      'Choose service',
      'Select which service you want to book into this free slot.',
      [
        ...services.slice(0, 6).map((service) => ({
          text: service.name,
          onPress: () => {
            setBookingFlowService(service);
            setBookingFlowVisible(true);
          },
        })),
        { text: 'Cancel', style: 'cancel' as const },
      ],
    );
  }

  function handleSelectCalendarSlot(
    nextDay: string,
    options?: { bookingId?: string; hour?: number; blocked?: boolean },
  ) {
    setSelectedDay(nextDay);
    const nextDate = dateFromDayKey(nextDay);
    setWeekStartDate(startOfWeek(nextDate));
    setCalendarMonth(new Date(nextDate.getFullYear(), nextDate.getMonth(), 1));
    setFocusedBookingId(options?.bookingId ?? null);

    if (options?.bookingId || options?.blocked || options?.hour == null) {
      return;
    }

    const slotLabel = hourToLabel(options.hour);
    Alert.alert(
      'Free slot',
      `${selectedDay === nextDay ? 'This' : 'Selected'} slot at ${slotLabel} is free. What would you like to do?`,
      [
        {
          text: 'Block time',
          onPress: () => {
            setCalendarOpen(true);
            setBlockStartTime(slotLabel);
            setBlockEndTime(hourToLabel(Math.min(options.hour! + 1, 23)));
            setBlockReason('');
          },
        },
        {
          text: 'New booking',
          onPress: () => handleCreateBookingFromSlot(nextDay, options.hour!),
        },
        { text: 'Cancel', style: 'cancel' },
      ],
    );
  }

  function handleCalendarStep(delta: number) {
    if (calendarView === 'month') {
      setCalendarMonth((prev) => new Date(prev.getFullYear(), prev.getMonth() + delta, 1));
      return;
    }
    const shifted = shiftDayKey(selectedDay, delta * 7);
    setSelectedDay(shifted);
    setWeekStartDate(startOfWeek(dateFromDayKey(shifted)));
  }

  function handleComplete(bookingId: string) {
    Alert.alert('Mark complete?', 'This will complete the booking and trigger loyalty tracking.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Complete', onPress: () => statusMutation.mutate({ id: bookingId, status: 'completed' }) },
    ]);
  }

  function handleCancel(bookingId: string) {
    Alert.alert('Cancel booking?', 'The client will be notified by email.', [
      { text: 'Keep it', style: 'cancel' },
      { text: 'Cancel booking', style: 'destructive', onPress: () => statusMutation.mutate({ id: bookingId, status: 'cancelled' }) },
    ]);
  }

  function handleOpenReschedule(booking: BookingItem) {
    setRescheduleBookingTarget(booking);
    setRescheduleDate(inputDateValue(booking.scheduled_start));
    setRescheduleStartTime(fmtTime(booking.scheduled_start));
    setRescheduleEndTime(fmtTime(booking.scheduled_end));
  }

  function handleSubmitReschedule() {
    if (!rescheduleBookingTarget) return;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(rescheduleDate)) {
      Alert.alert('Invalid date', 'Use YYYY-MM-DD format.');
      return;
    }
    if (!/^\d{2}:\d{2}$/.test(rescheduleStartTime) || !/^\d{2}:\d{2}$/.test(rescheduleEndTime)) {
      Alert.alert('Invalid time', 'Use HH:MM format.');
      return;
    }
    if (rescheduleEndTime <= rescheduleStartTime) {
      Alert.alert('Invalid time range', 'End must be after start.');
      return;
    }

    rescheduleMut.mutate({
      bookingId: rescheduleBookingTarget.booking_id,
      newStart: `${rescheduleDate}T${rescheduleStartTime}:00`,
      newEnd: `${rescheduleDate}T${rescheduleEndTime}:00`,
    });
  }

  function handleLateAlert(bookingId: string) {
    sendProviderLateAlert(bookingId, 15).catch(() => {});
    Alert.alert('Alert sent', "Your client has been notified you're running 15 min late.");
  }

  function handleReport(bookingId: string, customerId?: string) {
    if (!customerId) {
      Alert.alert('Cannot report', 'No customer ID linked to this booking.');
      return;
    }
    const CATEGORIES = [
      { label: 'No-show',           value: 'no_show' },
      { label: 'Very late',         value: 'very_late' },
      { label: 'Policy violation',  value: 'policy_violation' },
      { label: 'Abusive behaviour', value: 'abusive_behavior' },
      { label: 'Payment issue',     value: 'payment_issue' },
    ];
    Alert.alert('Report customer', 'What happened?', [
      ...CATEGORIES.map(cat => ({
        text: cat.label,
        onPress: () =>
          submitCustomerReliabilityReport(customerId, { category: cat.value })
            .then(() => Alert.alert('Reported', 'Thank you. This helps keep the platform safe.'))
            .catch((err: Error) => Alert.alert('Error', err.message || 'Report failed')),
      })),
      { text: 'Cancel', style: 'cancel' as const },
    ]);
  }

  function handleUpdateResponse(requestId: string, action: 'accept' | 'decline') {
    const label = action === 'accept' ? 'Accept' : 'Decline';
    Alert.alert(
      `${label} reschedule?`,
      action === 'accept'
        ? 'The booking will be moved to the requested time.'
        : 'The customer will be notified the reschedule was declined.',
      [
        { text: 'Go back', style: 'cancel' },
        {
          text: label,
          style: action === 'decline' ? 'destructive' : 'default',
          onPress: () => updateRespondMut.mutate({ requestId, action }),
        },
      ],
    );
  }

  function handleAccountMenu() {
    Alert.alert(
      providerName ?? 'Account',
      'What would you like to do?',
      [
        { text: 'Settings', onPress: () => router.push('/(tabs)/settings' as any) },
        {
          text: 'Sign out',
          style: 'destructive',
          onPress: () =>
            Alert.alert('Sign out?', 'You will need to log in again.', [
              { text: 'Cancel', style: 'cancel' },
              {
                text: 'Sign out',
                style: 'destructive',
                onPress: async () => {
                  await removeTokenFromBackend();
                  await clearAuth();
                  router.replace('/(auth)/welcome');
                },
              },
            ]),
        },
        { text: 'Cancel', style: 'cancel' },
      ],
    );
  }

  // Calendar data
  const allBookings = [...(dashboard.bookings_today ?? []), ...(dashboard.bookings_upcoming ?? [])];
  const bookingsByDay = allBookings.reduce<Record<string, BookingItem[]>>((acc, booking) => {
    const k = dayKey(booking.scheduled_start);
    if (!acc[k]) acc[k] = [];
    acc[k].push(booking);
    return acc;
  }, {});
  const timeBlocksByDay = timeBlocks.reduce<Record<string, TimeBlock[]>>((acc, block) => {
    const k = dayKey(block.starts_at);
    if (!acc[k]) acc[k] = [];
    acc[k].push(block);
    return acc;
  }, {});
  const todayKey = dayKey(new Date().toISOString());
  const dayBookings = (bookingsByDay[selectedDay] ?? [])
    .slice()
    .sort((a, b) => new Date(a.scheduled_start).getTime() - new Date(b.scheduled_start).getTime());
  const selectedDayLabel = dateFromDayKey(selectedDay).toLocaleDateString('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  });
  const selectedDayCountLabel = dayBookings.length === 1 ? '1 booking' : `${dayBookings.length} bookings`;

  const calendarMonthLabel = calendarMonth.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });
  const weekLabel = formatWeekRange(weekStartDate);
  const monthCells = buildCalendarDays(calendarMonth);
  const selectedDayBlocks = (timeBlocksByDay[selectedDay] ?? [])
    .slice()
    .sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime());

  // ── Inbox view ────────────────────────────────────────────────────────────

  if (activeView === 1) {
    return (
      <SafeAreaView className="flex-1 bg-fixme-bg" edges={['top']}>
        <ScrollView className="flex-1" showsVerticalScrollIndicator={false}>
          {/* Header */}
          <View className="flex-row items-center justify-between px-5 pt-6 pb-4">
            <View>
              <Text className="text-fixme-text-muted text-sm">{getGreeting()}</Text>
              <Text className="text-fixme-text-primary font-bold text-2xl mt-0.5">{providerName ?? 'Provider'}</Text>
            </View>
            <Pressable
              onPress={handleAccountMenu}
              className="w-9 h-9 rounded-full bg-fixme-card border border-fixme-border items-center justify-center active:opacity-70"
            >
              <Text className="text-base">⚙️</Text>
            </Pressable>
          </View>

          {/* Tab switcher */}
          <View className="px-5 mb-5">
            <SegmentedControl
              options={['Bookings', 'Inbox']}
              activeIndex={activeView}
              onChange={(i) => setActiveView(i as 0 | 1)}
            />
          </View>

          <View className="px-5 pb-8">
            {needsHumanConversations.length === 0 ? (
              <EmptyState
                icon="✅"
                title="All caught up"
                body="No messages need your attention right now. Fixmeapp is handling the active conversations."
                compact
              />
            ) : (
              <View className="gap-3">
                <SectionHeader label="Messages needing your attention" />
                {needsHumanConversations.map((conv) => (
                  <Card key={conv.conversation_id} className="border-amber-500/40">
                    <View className="flex-row items-start">
                      <Avatar name={conv.customer_name ?? 'U'} size="sm" className="mr-3" />
                      <View className="flex-1">
                        <View className="flex-row items-center justify-between">
                          <Text className="text-fixme-text-primary text-sm font-semibold">{conv.customer_name ?? 'Unknown'}</Text>
                          <Text className="text-fixme-text-muted text-[10px]">{conv.last_message_at ? fmtDate(conv.last_message_at) : ''}</Text>
                        </View>
                        {conv.last_message ? (
                          <Text className="text-fixme-text-muted text-xs mt-1">{conv.last_message}</Text>
                        ) : null}
                      </View>
                    </View>
                  </Card>
                ))}
              </View>
            )}
          </View>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ── Bookings view ─────────────────────────────────────────────────────────

  return (
    <SafeAreaView className="flex-1 bg-fixme-bg" edges={['top']}>
      <ScrollView
        className="flex-1"
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
      >
        {/* Header */}
        <View className="flex-row items-center justify-between px-5 pt-6 pb-4">
          <View>
            <Text className="text-fixme-text-muted text-sm">{getGreeting()}</Text>
            <Text className="text-fixme-text-primary font-bold text-2xl mt-0.5">{providerName ?? 'Provider'}</Text>
          </View>
          <Pressable
            onPress={handleAccountMenu}
            className="w-9 h-9 rounded-full bg-fixme-card border border-fixme-border items-center justify-center active:opacity-70"
          >
            <Text className="text-base">⚙️</Text>
          </Pressable>
        </View>

        {/* Tab switcher */}
        <View className="px-5 mb-4">
          <SegmentedControl
            options={['Bookings', 'Inbox']}
            activeIndex={activeView}
            onChange={(i) => setActiveView(i as 0 | 1)}
          />
        </View>

        {/* ── Week strip calendar ── always visible ── */}
        <View className="px-5 mb-2">
          {/* Row: week label + expand button */}
          <View className="flex-row items-center justify-between mb-3">
            <Text className="text-fixme-text-secondary text-xs font-semibold uppercase tracking-wider">
              {calendarView === 'month' ? calendarMonthLabel : weekLabel}
            </Text>
            <View className="flex-row items-center gap-2">
              <Pressable onPress={() => handleCalendarStep(-1)} className="w-7 h-7 rounded-lg border border-fixme-border items-center justify-center active:opacity-70">
                <Text className="text-fixme-text-secondary text-xs">‹</Text>
              </Pressable>
              <Pressable onPress={() => handleCalendarStep(1)} className="w-7 h-7 rounded-lg border border-fixme-border items-center justify-center active:opacity-70">
                <Text className="text-fixme-text-secondary text-xs">›</Text>
              </Pressable>
              <Pressable
                onPress={() => setCalendarOpen(v => !v)}
                className={`w-7 h-7 rounded-lg border items-center justify-center active:opacity-70 ${calendarOpen ? 'border-fixme-text-primary bg-fixme-text-primary/10' : 'border-fixme-border'}`}
              >
                <Text className={`text-xs ${calendarOpen ? 'text-fixme-text-primary' : 'text-fixme-text-muted'}`}>⊞</Text>
              </Pressable>
            </View>
          </View>

          {/* Week strip */}
          <View className="flex-row gap-1.5">
            {weekDays.map((day) => {
              const count = bookingsByDay[day.key]?.length ?? 0;
              const hasBlock = (timeBlocksByDay[day.key]?.length ?? 0) > 0;
              const isPast = day.key < todayKey;
              const isToday = day.key === todayKey;
              const isSelected = day.key === selectedDay;
              const dotClass = dayDotClass(count, hasBlock, isPast);

              return (
                <Pressable
                  key={day.key}
                  onPress={() => handleSelectDay(day.key)}
                  className={`
                    flex-1 rounded-2xl px-1 py-2.5 items-center gap-1
                    ${isSelected ? 'bg-fixme-text-primary' : isToday ? 'bg-fixme-card border border-fixme-accent/40' : 'bg-fixme-card border border-fixme-border'}
                  `}
                >
                  <Text className={`text-[10px] uppercase font-medium ${isSelected ? 'text-fixme-bg' : isPast ? 'text-fixme-text-muted/50' : 'text-fixme-text-muted'}`}>
                    {day.weekdayShort.slice(0, 3)}
                  </Text>
                  <Text className={`text-sm font-bold ${isSelected ? 'text-fixme-bg' : isPast ? 'text-fixme-text-muted/50' : isToday ? 'text-fixme-accent' : 'text-fixme-text-primary'}`}>
                    {day.dayNumber}
                  </Text>
                  {/* Color dot */}
                  {dotClass ? (
                    <View className={`w-1.5 h-1.5 rounded-full ${isSelected ? 'bg-fixme-bg/70' : dotClass}`} />
                  ) : (
                    <View className="w-1.5 h-1.5" />
                  )}
                </Pressable>
              );
            })}
          </View>
        </View>

        {/* ── Expanded calendar (month view) ── */}
        {calendarOpen && (
          <View className="mx-5 mb-4">
            <Card padding="sm">
              {/* View toggle */}
              <View className="flex-row rounded-xl border border-fixme-border overflow-hidden self-start mb-3">
                {(['week', 'month'] as const).map((view) => (
                  <Pressable
                    key={view}
                    onPress={() => setCalendarView(view)}
                    className={`px-4 py-1.5 ${calendarView === view ? 'bg-fixme-text-primary' : 'bg-transparent'}`}
                  >
                    <Text className={`text-xs font-semibold capitalize ${calendarView === view ? 'text-fixme-bg' : 'text-fixme-text-secondary'}`}>{view}</Text>
                  </Pressable>
                ))}
              </View>

              {calendarView === 'month' && (
                <>
                  <View className="flex-row mb-2">
                    {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((wd) => (
                      <View key={wd} style={{ width: '14.2857%' }}>
                        <Text className="text-fixme-text-muted text-[10px] text-center uppercase">{wd}</Text>
                      </View>
                    ))}
                  </View>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap' }}>
                    {monthCells.map((cell) => {
                      const count = bookingsByDay[cell.key]?.length ?? 0;
                      const isPast = cell.key < todayKey;
                      const isToday = cell.key === todayKey;
                      const isSelected = cell.key === selectedDay;
                      const dotClass = dayDotClass(count, (timeBlocksByDay[cell.key]?.length ?? 0) > 0, isPast);
                      return (
                        <View key={cell.key} style={{ width: '14.2857%', paddingHorizontal: 2, paddingVertical: 2 }}>
                          <Pressable
                            onPress={() => handleSelectDay(cell.key)}
                            className={`h-10 rounded-xl border items-center justify-center gap-0.5
                              ${isSelected ? 'border-fixme-text-primary bg-fixme-text-primary/15' : isToday ? 'border-fixme-accent/60' : cell.inMonth ? 'border-fixme-border' : 'border-transparent'}`}
                          >
                            <Text className={`text-xs font-medium
                              ${isSelected ? 'text-fixme-text-primary font-bold' : isPast ? 'text-fixme-text-muted/40' : cell.inMonth ? 'text-fixme-text-secondary' : 'text-fixme-text-muted/20'}`}>
                              {cell.dayNumber}
                            </Text>
                            {dotClass && cell.inMonth ? (
                              <View className={`w-1 h-1 rounded-full ${dotClass}`} />
                            ) : null}
                          </Pressable>
                        </View>
                      );
                    })}
                  </View>
                </>
              )}

              {calendarView === 'week' && (
                <View className="mt-1">
                  <WeeklyScheduleGrid
                    weekDays={weekDays}
                    selectedDay={selectedDay}
                    bookingsByDay={bookingsByDay}
                    timeBlocks={timeBlocks}
                    onSelectSlot={handleSelectCalendarSlot}
                  />
                </View>
              )}

              {/* Selected day detail */}
              <View className="border-t border-fixme-border/60 mt-3 pt-3 gap-2">
                <Text className="text-fixme-text-primary text-xs font-semibold">{selectedDayLabel}</Text>
                <Text className="text-fixme-text-muted text-xs">
                  {selectedDayCountLabel} scheduled. Tap a day above to update the booking cards and blockers.
                </Text>

                {/* Block time */}
                <View className="mt-2 pt-3 border-t border-fixme-border/60 gap-2">
                  <Text className="text-fixme-text-primary text-xs font-semibold">Block time</Text>
                  <View className="flex-row rounded-lg border border-fixme-border overflow-hidden self-start">
                    {(['lunch', 'private'] as const).map((kind) => (
                      <Pressable key={kind} onPress={() => setBlockKind(kind)} className={`px-3 py-1.5 ${blockKind === kind ? 'bg-fixme-text-primary' : 'bg-transparent'}`}>
                        <Text className={`text-xs font-semibold capitalize ${blockKind === kind ? 'text-fixme-bg' : 'text-fixme-text-secondary'}`}>{kind}</Text>
                      </Pressable>
                    ))}
                  </View>
                  <View className="flex-row gap-2">
                    <View className="flex-1">
                      <Text className="text-[11px] text-fixme-text-muted mb-1">Start</Text>
                      <TextInput value={blockStartTime} onChangeText={setBlockStartTime} placeholder="12:00" placeholderTextColor={colors.textMuted} className="bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2 text-xs text-fixme-text-primary" />
                    </View>
                    <View className="flex-1">
                      <Text className="text-[11px] text-fixme-text-muted mb-1">End</Text>
                      <TextInput value={blockEndTime} onChangeText={setBlockEndTime} placeholder="12:30" placeholderTextColor={colors.textMuted} className="bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2 text-xs text-fixme-text-primary" />
                    </View>
                  </View>
                  <TextInput value={blockReason} onChangeText={setBlockReason} placeholder="Optional note" placeholderTextColor={colors.textMuted} className="bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2 text-xs text-fixme-text-primary" />
                  <Button onPress={handleAddTimeBlock} loading={blockSaving} fullWidth size="sm">
                    Add blocker
                  </Button>
                  {blocksLoading ? (
                    <LoadingSpinner size="sm" />
                  ) : selectedDayBlocks.length > 0 ? (
                    <View className="gap-1.5">
                      {selectedDayBlocks.map((block) => (
                        <View key={block.block_id} className="bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2 flex-row items-center justify-between">
                          <Text className="text-fixme-text-primary text-xs font-semibold flex-1">
                            {block.label || 'Block'} - {fmtTime(block.starts_at)} - {fmtTime(block.ends_at)}
                          </Text>
                          <Button size="xs" variant="ghost" onPress={() => handleDeleteTimeBlock(block.block_id)} disabled={blockSaving} className="border-fixme-error/30 ml-2">
                            <Text className="text-fixme-error text-xs">Remove</Text>
                          </Button>
                        </View>
                      ))}
                    </View>
                  ) : (
                    <Text className="text-fixme-text-muted text-xs">No blockers saved for this day.</Text>
                  )}
                </View>
              </View>
            </Card>
          </View>
        )}

        <View className="px-5 mb-4">
          <View className="flex-row items-center justify-between mb-2">
            <SectionHeader label={selectedDay === todayKey ? "Today's bookings" : selectedDayLabel} />
            <Text className="text-fixme-text-muted text-xs">{selectedDayCountLabel}</Text>
          </View>
          {dayBookings.length === 0 ? (
            <Card>
              <Text className="text-fixme-text-muted text-sm">No bookings scheduled for this day yet.</Text>
            </Card>
          ) : (
            <View>
              {dayBookings.map((booking) => (
                <SharedBookingCard
                  key={booking.booking_id}
                  booking={booking}
                  onComplete={handleComplete}
                  onCancel={handleCancel}
                  onReschedule={handleOpenReschedule}
                  onLateAlert={handleLateAlert}
                  onReport={handleReport}
                  expanded={focusedBookingId === booking.booking_id}
                  onToggleExpand={(next) => setFocusedBookingId(next ? booking.booking_id : null)}
                />
              ))}
            </View>
          )}
        </View>


        {/* ── Revenue stats ── */}
        <View className="flex-row gap-3 px-5 mb-4">
          <StatCard
            label="Today"
            value={fmtSek(dashboard.revenue_today, dashboard.currency)}
            size="sm"
            className="flex-1"
          />
          <StatCard
            label="This week"
            value={fmtSek(dashboard.revenue_this_week, dashboard.currency)}
            size="sm"
            className="flex-1"
          />
        </View>

        {/* ── Reschedule requests ── */}
        {liveUpdateRequests.length > 0 && (
          <View className="px-5 mb-2">
            {isMock && (
              <Text className="text-fixme-text-muted text-[10px] uppercase tracking-wider mb-2">Preview — mock data</Text>
            )}
            {liveUpdateRequests.map((req) => (
              <BookingUpdateCard
                key={req.request_id}
                req={req}
                onRespond={handleUpdateResponse}
                responding={updateRespondMut.isPending}
              />
            ))}
          </View>
        )}


        {/* ── Setup wizard ── shown until completed or dismissed ── */}
        <SetupImportCard onDone={() => queryClient.invalidateQueries({ queryKey: ['home-dashboard'] })} />
        <SetupVerifyCard />

        {/* ── Inbox preview ── */}
        {conversations.length > 0 && (
          <View className="px-5 mb-6">
            <View className="flex-row items-center justify-between mb-2">
              <SectionHeader label="Messages" />
              <Text className="text-fixme-accent text-xs">
                {conversations.filter(c => (c.unread_count ?? 0) > 0 || c.needs_human).length > 0
                  ? `${conversations.filter(c => (c.unread_count ?? 0) > 0 || c.needs_human).length} need attention`
                  : 'All read'}
              </Text>
            </View>
            <Card padding="none">
              {conversations.slice(0, 3).map((conv, i) => (
                <View key={conv.conversation_id}>
                  {i > 0 && <View className="h-px bg-fixme-border mx-4" />}
                  <Pressable className="flex-row items-center px-4 py-3 active:opacity-70">
                    <Avatar name={conv.customer_name ?? 'U'} size="xs" className="mr-3" />
                    <View className="flex-1 mr-2">
                      <Text className="text-fixme-text-primary text-sm font-semibold" numberOfLines={1}>
                        {conv.customer_name ?? 'Unknown'}
                      </Text>
                      {conv.last_message ? (
                        <Text className="text-fixme-text-muted text-xs mt-0.5" numberOfLines={1}>
                          {conv.last_message}
                        </Text>
                      ) : null}
                    </View>
                    {(conv.unread_count ?? 0) > 0 && (
                      <View className="w-5 h-5 rounded-full bg-fixme-accent items-center justify-center">
                        <Text className="text-[10px] font-bold text-fixme-bg">{conv.unread_count}</Text>
                      </View>
                    )}
                  </Pressable>
                </View>
              ))}
            </Card>
          </View>
        )}
      </ScrollView>

      <Modal
        visible={!!rescheduleBookingTarget}
        animationType="slide"
        transparent
        onRequestClose={() => setRescheduleBookingTarget(null)}
      >
        <View className="flex-1 bg-black/50 justify-end">
          <View className="bg-fixme-card rounded-t-3xl px-5 pt-5 pb-8 border-t border-fixme-border">
            <Text className="text-fixme-text-primary text-lg font-bold">Reschedule booking</Text>
            <Text className="text-fixme-text-muted text-sm mt-1">
              {rescheduleBookingTarget?.customer_name ?? 'Customer'} · {rescheduleBookingTarget?.service_name ?? 'Appointment'}
            </Text>

            <View className="mt-4 gap-3">
              <View>
                <Text className="text-[11px] text-fixme-text-muted mb-1">Date</Text>
                <TextInput
                  value={rescheduleDate}
                  onChangeText={setRescheduleDate}
                  placeholder="YYYY-MM-DD"
                  placeholderTextColor={colors.textMuted}
                  className="bg-fixme-bg border border-fixme-border rounded-xl px-3 py-3 text-sm text-fixme-text-primary"
                />
              </View>
              <View className="flex-row gap-3">
                <View className="flex-1">
                  <Text className="text-[11px] text-fixme-text-muted mb-1">Start</Text>
                  <TextInput
                    value={rescheduleStartTime}
                    onChangeText={setRescheduleStartTime}
                    placeholder="14:00"
                    placeholderTextColor={colors.textMuted}
                    className="bg-fixme-bg border border-fixme-border rounded-xl px-3 py-3 text-sm text-fixme-text-primary"
                  />
                </View>
                <View className="flex-1">
                  <Text className="text-[11px] text-fixme-text-muted mb-1">End</Text>
                  <TextInput
                    value={rescheduleEndTime}
                    onChangeText={setRescheduleEndTime}
                    placeholder="15:00"
                    placeholderTextColor={colors.textMuted}
                    className="bg-fixme-bg border border-fixme-border rounded-xl px-3 py-3 text-sm text-fixme-text-primary"
                  />
                </View>
              </View>
            </View>

            <Text className="text-fixme-text-muted text-xs mt-3">
              Saving this will update the customer's booking view and send an email notification.
            </Text>

            <View className="flex-row gap-3 mt-5">
              <Button
                variant="ghost"
                onPress={() => setRescheduleBookingTarget(null)}
                className="flex-1"
                disabled={rescheduleMut.isPending}
              >
                Cancel
              </Button>
              <Button
                onPress={handleSubmitReschedule}
                className="flex-1"
                loading={rescheduleMut.isPending}
                disabled={rescheduleMut.isPending}
              >
                Save new time
              </Button>
            </View>
          </View>
        </View>
      </Modal>

      {bookingFlowService && providerId && (
        <BookingFlow
          visible={bookingFlowVisible}
          onClose={() => {
            setBookingFlowVisible(false);
            setBookingFlowService(null);
            setBookingFlowInitialDate(null);
          }}
          providerId={providerId}
          service={bookingFlowService}
          initialDate={bookingFlowInitialDate}
        />
      )}
    </SafeAreaView>
  );
}
