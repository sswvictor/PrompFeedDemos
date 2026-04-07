import { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  Share,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getFinanceInsights,
  getFinanceRecent,
  getFinanceSummary,
  markBookingPaid,
  type FinanceInsights,
  type FinanceSummary,
} from '@/lib/api';
import { colors } from '@/theme';

// ── Helpers ──────────────────────────────────────────────────────────────────

import { formatPrice } from '@/utils/currency';
function fmtSek(value: number, currency = 'SEK') {
  return formatPrice(value, currency);
}

function fmtShortDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

function changeLabel(current: number, prev: number): { text: string; positive: boolean } | null {
  if (prev <= 0) return null;
  const pct = ((current - prev) / prev) * 100;
  const sign = pct >= 0 ? '+' : '';
  return { text: `${sign}${Math.round(pct)}%`, positive: pct >= 0 };
}

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function firstDayOfYear() {
  return `${new Date().getFullYear()}-01-01`;
}

// ── Period picker ─────────────────────────────────────────────────────────────

const PERIODS = [
  { id: 'this_month',   label: 'This month' },
  { id: 'last_month',   label: 'Last month' },
  { id: 'this_quarter', label: 'Quarter' },
  { id: 'this_year',    label: 'This year' },
];

function PeriodPicker({ selected, onSelect }: { selected: string; onSelect: (id: string) => void }) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={{ gap: 8, marginBottom: 20 }}
    >
      {PERIODS.map((p) => (
        <Pressable
          key={p.id}
          onPress={() => onSelect(p.id)}
          className={`px-4 py-2 rounded-full border ${
            selected === p.id
              ? 'bg-fixme-accent border-fixme-accent'
              : 'bg-fixme-card border-fixme-border'
          }`}
        >
          <Text
            className={`text-sm font-medium ${
              selected === p.id ? 'text-fixme-bg' : 'text-fixme-text-secondary'
            }`}
          >
            {p.label}
          </Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}

// ── Revenue hero card ─────────────────────────────────────────────────────────

function RevenueCard({ data }: { data: FinanceInsights }) {
  const change = changeLabel(data.revenue_this_period, data.revenue_prev_period);
  return (
    <View className="bg-fixme-card border border-fixme-accent/30 rounded-2xl p-5 mb-4">
      <Text className="text-fixme-text-muted text-xs uppercase tracking-wider mb-1">Revenue</Text>
      <Text className="text-fixme-accent font-bold text-3xl">{fmtSek(data.revenue_this_period)}</Text>
      {change && (
        <Text className={`text-xs mt-2 ${change.positive ? 'text-emerald-400' : 'text-red-400'}`}>
          {change.text} vs last period{data.revenue_prev_period > 0 ? ` \u00B7 ${fmtSek(data.revenue_prev_period)}` : ''}
        </Text>
      )}
      {!change && data.revenue_prev_period > 0 && (
        <Text className="text-fixme-text-muted text-xs mt-2">
          vs {fmtSek(data.revenue_prev_period)} last period
        </Text>
      )}
    </View>
  );
}

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <View className="flex-1 bg-fixme-card border border-fixme-border rounded-2xl p-4">
      <Text className="text-fixme-text-muted text-xs mb-1">{label}</Text>
      <Text className="text-fixme-text-primary font-bold text-xl">{value}</Text>
      {sub ? <Text className="text-fixme-text-muted text-xs mt-1">{sub}</Text> : null}
    </View>
  );
}

// ── Top services ──────────────────────────────────────────────────────────────

function TopServices({ services }: { services: { name: string; count: number }[] }) {
  if (!services.length) return null;
  return (
    <View className="bg-fixme-card border border-fixme-border rounded-2xl p-5 mb-6">
      <Text className="text-fixme-text-secondary font-semibold text-sm mb-4">Top services</Text>
      {services.map((s, i) => (
        <View
          key={s.name}
          className={`flex-row items-center justify-between py-2 ${
            i < services.length - 1 ? 'border-b border-fixme-border/50' : ''
          }`}
        >
          <Text className="text-fixme-text-primary text-sm">{s.name}</Text>
          <View className="bg-fixme-accent/15 rounded-full px-2.5 py-1">
            <Text className="text-fixme-accent text-xs font-semibold">{s.count}\u00D7</Text>
          </View>
        </View>
      ))}
    </View>
  );
}

// ── Recent bookings ───────────────────────────────────────────────────────────

function RecentBookings() {
  const qc = useQueryClient();

  const { data: bookings, isLoading } = useQuery({
    queryKey: ['finance-recent'],
    queryFn: () => getFinanceRecent(15),
  });

  const markPaid = useMutation({
    mutationFn: (bookingId: string) => markBookingPaid(bookingId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['finance-recent'] });
      qc.invalidateQueries({ queryKey: ['finance-summary'] });
    },
  });

  if (isLoading) {
    return (
      <View className="items-center py-8">
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  if (!bookings?.length) return null;

  const unpaidCount = bookings.filter(
    (b) => b.status === 'completed' && b.payment_status !== 'paid',
  ).length;

  // Unpaid completed first, then the rest by date
  const sorted = [...bookings].sort((a, b) => {
    const aFlag = a.status === 'completed' && a.payment_status !== 'paid' ? 0 : 1;
    const bFlag = b.status === 'completed' && b.payment_status !== 'paid' ? 0 : 1;
    return aFlag - bFlag;
  });

  return (
    <View className="mb-6">
      <View className="flex-row items-center justify-between mb-3">
        <Text className="text-fixme-text-secondary font-semibold text-sm">Recent bookings</Text>
        {unpaidCount > 0 && (
          <View className="bg-amber-500/20 border border-amber-500/40 rounded-full px-2.5 py-0.5">
            <Text className="text-amber-400 text-xs font-semibold">{unpaidCount} unpaid</Text>
          </View>
        )}
      </View>

      <View className="bg-fixme-card border border-fixme-border rounded-2xl overflow-hidden">
        {sorted.map((b, i) => (
          <View
            key={b.booking_id}
            className={`flex-row items-center gap-3 px-4 py-3 ${
              i < sorted.length - 1 ? 'border-b border-fixme-border/40' : ''
            }`}
          >
            {/* Name + service */}
            <View className="flex-1 min-w-0">
              <Text className="text-fixme-text-primary text-sm font-medium" numberOfLines={1}>
                {b.customer_name || 'Guest'}
              </Text>
              <Text className="text-fixme-text-muted text-xs mt-0.5" numberOfLines={1}>
                {b.service_name || 'Appointment'} \u00B7 {fmtShortDate(b.scheduled_start)}
              </Text>
            </View>

            {/* Amount + payment badge */}
            <View className="items-end gap-1">
              <Text className="text-fixme-text-primary text-sm font-semibold">
                {fmtSek(b.amount_inc_vat)}
              </Text>
              {b.status === 'completed' ? (
                b.payment_status === 'paid' ? (
                  <Text className="text-emerald-400 text-xs font-semibold">{'\u2713'} Paid</Text>
                ) : (
                  <Pressable
                    onPress={() => markPaid.mutate(b.booking_id)}
                    disabled={markPaid.isPending}
                    className="bg-fixme-accent/15 border border-fixme-accent/40 rounded-full px-2.5 py-0.5"
                  >
                    <Text className="text-fixme-accent text-xs font-semibold">
                      {markPaid.isPending ? '\u2026' : 'Mark paid'}
                    </Text>
                  </Pressable>
                )
              ) : (
                <Text className="text-fixme-text-muted text-xs capitalize">{b.status}</Text>
              )}
            </View>
          </View>
        ))}
      </View>
    </View>
  );
}

// ── Tax summary ───────────────────────────────────────────────────────────────

function buildSummaryText(data: FinanceSummary, start: string, end: string, currency = 'SEK'): string {
  const fmt = (n: number) => formatPrice(n, currency);
  const lines: string[] = [
    'Fixmeapp Finance Summary',
    `Period: ${start} \u2013 ${end}`,
    '',
    `Revenue ex VAT:  ${fmt(data.revenue_ex_vat)}`,
    `VAT collected:   ${fmt(data.vat_collected)}`,
    `Revenue inc VAT: ${fmt(data.revenue_inc_vat)}`,
    '',
    `Total bookings: ${data.total_bookings}`,
    `Completed:      ${data.completed_bookings}`,
  ];
  if (data.unpaid_count > 0) {
    lines.push(`Unpaid (${data.unpaid_count}): ${fmt(data.unpaid_amount)}`);
  }
  if (data.top_services?.[0]) {
    lines.push(`Top service: ${data.top_services[0].name} (${data.top_services[0].count}\u00D7)`);
  }
  lines.push('', 'Generated by Fixmeapp');
  return lines.join('\n');
}

function SummaryRow({
  label,
  value,
  accent,
  warn,
}: {
  label: string;
  value: string;
  accent?: boolean;
  warn?: boolean;
}) {
  return (
    <View className="flex-row items-center justify-between py-0.5">
      <Text className="text-fixme-text-muted text-sm">{label}</Text>
      <Text
        className={`text-sm font-semibold ${
          accent ? 'text-fixme-accent' : warn ? 'text-amber-400' : 'text-fixme-text-primary'
        }`}
      >
        {value}
      </Text>
    </View>
  );
}

function TaxSummary() {
  const [startDate, setStartDate] = useState(firstDayOfYear());
  const [endDate, setEndDate] = useState(todayStr());
  const [triggered, setTriggered] = useState(false);

  const { data, isFetching, refetch } = useQuery({
    queryKey: ['finance-summary', startDate, endDate],
    queryFn: () => getFinanceSummary(startDate, endDate),
    enabled: triggered,
  });

  async function handleGenerate() {
    if (!triggered) {
      setTriggered(true);
    } else {
      await refetch();
    }
  }

  async function handleShare() {
    if (!data) return;
    await Share.share({ message: buildSummaryText(data, startDate, endDate) });
  }

  return (
    <View className="mb-10">
      <Text className="text-fixme-text-secondary font-semibold text-sm mb-3">
        Tax summary
      </Text>
      <View className="bg-fixme-card border border-fixme-border rounded-2xl p-4">
        <Text className="text-fixme-text-muted text-xs leading-relaxed mb-4">
          Pick a date range and generate a summary you can send to your accountant.
        </Text>

        {/* Date inputs */}
        <View className="flex-row gap-3 mb-4">
          <View className="flex-1">
            <Text className="text-fixme-text-muted text-[10px] uppercase tracking-wider mb-1.5">
              From
            </Text>
            <TextInput
              value={startDate}
              onChangeText={setStartDate}
              placeholder="YYYY-MM-DD"
              placeholderTextColor={colors.textMuted}
              className="bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2.5 text-fixme-text-primary text-sm"
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="numbers-and-punctuation"
            />
          </View>
          <View className="flex-1">
            <Text className="text-fixme-text-muted text-[10px] uppercase tracking-wider mb-1.5">
              To
            </Text>
            <TextInput
              value={endDate}
              onChangeText={setEndDate}
              placeholder="YYYY-MM-DD"
              placeholderTextColor={colors.textMuted}
              className="bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2.5 text-fixme-text-primary text-sm"
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="numbers-and-punctuation"
            />
          </View>
        </View>

        {/* Generate button */}
        <Pressable
          onPress={handleGenerate}
          disabled={isFetching}
          className={`rounded-xl py-3.5 items-center mb-4 ${
            isFetching ? 'bg-fixme-card border border-fixme-border' : 'bg-fixme-accent'
          }`}
        >
          <Text className={`font-bold text-sm ${isFetching ? 'text-fixme-text-muted' : 'text-fixme-bg'}`}>
            {isFetching ? 'Generating\u2026' : '\u2728 Generate summary'}
          </Text>
        </Pressable>

        {/* Results */}
        {data && !isFetching && (
          <View className="border-t border-fixme-border/50 pt-4 space-y-1.5">
            <SummaryRow label="Revenue ex VAT" value={fmtSek(data.revenue_ex_vat)} accent />
            <SummaryRow label="VAT collected" value={fmtSek(data.vat_collected)} />
            <SummaryRow label="Revenue inc VAT" value={fmtSek(data.revenue_inc_vat)} />
            <View className="border-t border-fixme-border/30 my-2" />
            <SummaryRow label="Total bookings" value={String(data.total_bookings)} />
            <SummaryRow label="Completed" value={String(data.completed_bookings)} />
            {data.unpaid_count > 0 && (
              <SummaryRow
                label={`Unpaid (${data.unpaid_count})`}
                value={fmtSek(data.unpaid_amount)}
                warn
              />
            )}
            {data.top_services?.[0] && (
              <SummaryRow
                label="Top service"
                value={`${data.top_services[0].name} (${data.top_services[0].count}\u00D7)`}
              />
            )}

            {/* Share / Copy */}
            <Pressable
              onPress={handleShare}
              className="mt-4 flex-row items-center justify-center gap-2 bg-fixme-bg border border-fixme-border rounded-xl py-3"
            >
              <Text className="text-fixme-text-secondary text-sm font-semibold">
                {'\u{1F4CB}'} Copy \u00B7 Share
              </Text>
            </Pressable>
          </View>
        )}
      </View>
    </View>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────

export default function FinanceScreen() {
  const [period, setPeriod] = useState('this_month');

  const { data, isLoading } = useQuery({
    queryKey: ['finance-insights', period],
    queryFn: () => getFinanceInsights(period),
  });

  const completionRate = data
    ? Math.round((data.completed / Math.max(data.total_bookings, 1)) * 100)
    : 0;

  return (
    <SafeAreaView className="flex-1 bg-fixme-bg" edges={['top']}>
      <ScrollView className="flex-1 px-5" showsVerticalScrollIndicator={false}>
        <Text className="text-fixme-text-primary font-bold text-2xl pt-6 mb-1">Finance</Text>
        <Text className="text-fixme-text-muted text-sm mb-5">Your money, clear.</Text>

        <PeriodPicker selected={period} onSelect={setPeriod} />

        {isLoading ? (
          <View className="items-center py-20">
            <ActivityIndicator color={colors.accent} />
          </View>
        ) : data ? (
          <>
            <RevenueCard data={data} />

            <View className="flex-row gap-3 mb-3">
              <StatCard label="Total bookings" value={String(data.total_bookings)} />
              <StatCard
                label="Completed"
                value={String(data.completed)}
                sub={`${completionRate}% rate`}
              />
            </View>
            <View className="flex-row gap-3 mb-6">
              <StatCard label="Cancelled" value={String(data.cancelled)} />
              <StatCard label="Completion rate" value={`${completionRate}%`} />
            </View>

            <TopServices services={data.top_services ?? []} />
          </>
        ) : null}

        {/* Recent bookings with payment status — always shown */}
        <RecentBookings />

        {/* Tax summary with date range + generate */}
        <TaxSummary />
      </ScrollView>
    </SafeAreaView>
  );
}
