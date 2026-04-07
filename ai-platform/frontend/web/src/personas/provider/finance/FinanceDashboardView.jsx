import { useMemo } from 'react';
import { Button, Caption, Card, StatCard } from '../../../components/ui';
import FinancePeriodPicker from './sections/FinancePeriodPicker';
import FinanceAgentBriefSection from './sections/FinanceAgentBriefSection';
import FinanceActionQueueSection from './sections/FinanceActionQueueSection';
import WeeklyCloseChecklistSection from './sections/WeeklyCloseChecklistSection';
import TaxSummarySection from './sections/TaxSummarySection';
import TopServicesSection from './sections/TopServicesSection';
import FinanceCapabilitySection from './sections/FinanceCapabilitySection';
import RecentBookingsSection from './sections/RecentBookingsSection';
import { buildCloseChecklist, buildFinanceActions, changeLabel, fmtSek } from './financeUtils';

export default function FinanceDashboardView({
  period,
  onPeriodChange,
  loading,
  error,
  onRetry,
  insights,
  summary,
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  recentBookings,
  recentLoading,
  onMarkPaid,
  markingId,
}) {
  const revenueChange = useMemo(() => {
    if (!insights) return null;
    return changeLabel(insights.revenue_this_period, insights.revenue_prev_period);
  }, [insights]);

  const financeActions = useMemo(
    () => buildFinanceActions({ summary, insights, revenueChange }),
    [summary, insights, revenueChange],
  );

  const closeChecklist = useMemo(
    () => buildCloseChecklist({ summary, insights }),
    [summary, insights],
  );

  return (
    <>
      <FinancePeriodPicker selected={period} onSelect={onPeriodChange} />

      {loading ? (
        <Card className="flex items-center gap-3" padding="lg">
          <div className="w-5 h-5 border-2 border-fixme-accent border-t-transparent rounded-full animate-spin" />
          <Caption variant="secondary">Loading finance...</Caption>
        </Card>
      ) : error ? (
        <Card padding="sm">
          <Caption>{error}</Caption>
          <Button onClick={onRetry} variant="ghost" size="sm" className="mt-3">Retry</Button>
        </Card>
      ) : (
        <>
          <FinanceAgentBriefSection
            summary={summary}
            insights={insights}
            period={period}
            revenueChange={revenueChange}
          />

          <FinanceActionQueueSection actions={financeActions} />

          <Card className="border-fixme-accent/30">
            <StatCard
              label="Revenue"
              value={fmtSek(insights?.revenue_this_period)}
              change={revenueChange?.text}
              positive={revenueChange?.positive}
              size="lg"
              hero
            />
          </Card>

          <div className="grid grid-cols-2 gap-3">
            <StatCard label="Bookings" value={String(insights?.total_bookings || 0)} size="sm" />
            <StatCard label="Completed" value={String(insights?.completed || 0)} size="sm" />
          </div>

          <WeeklyCloseChecklistSection items={closeChecklist} />

          <TaxSummarySection
            summary={summary}
            startDate={startDate}
            endDate={endDate}
            onStartDateChange={onStartDateChange}
            onEndDateChange={onEndDateChange}
          />

          <TopServicesSection services={insights?.top_services || summary?.top_services} />

          <FinanceCapabilitySection />

          <RecentBookingsSection
            bookings={recentBookings}
            loading={recentLoading}
            onMarkPaid={onMarkPaid}
            markingId={markingId}
          />
        </>
      )}
    </>
  );
}
