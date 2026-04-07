import { useEffect, useState } from 'react';
import ProviderTabBar from '../navigation/ProviderTabBar';
import {
  getFinanceInsights,
  getFinanceRecent,
  getFinanceSummary,
  markBookingPaid,
} from '../../../api/bookingApi';
import FinanceDashboardView from '../finance/FinanceDashboardView';

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function firstDayOfYear() {
  return `${new Date().getFullYear()}-01-01`;
}

export default function ProviderFinancePage() {
  const token = localStorage.getItem('fixme_provider_token');
  const [period, setPeriod] = useState('this_month');
  const [insights, setInsights] = useState(null);
  const [recentBookings, setRecentBookings] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [recentLoading, setRecentLoading] = useState(true);
  const [error, setError] = useState(null);
  const [markingId, setMarkingId] = useState(null);
  const [startDate, setStartDate] = useState(firstDayOfYear());
  const [endDate, setEndDate] = useState(todayStr());

  async function loadFinance() {
    if (!token) return;
    try {
      setLoading(true);
      setRecentLoading(true);
      const [insightsResult, recentResult, summaryResult] = await Promise.all([
        getFinanceInsights(period, token),
        getFinanceRecent(token, 15),
        getFinanceSummary(token, startDate, endDate),
      ]);
      setInsights(insightsResult);
      setRecentBookings(recentResult || []);
      setSummary(summaryResult);
      setError(null);
    } catch (err) {
      setError(err.message || 'Could not load finance data.');
    } finally {
      setLoading(false);
      setRecentLoading(false);
    }
  }

  useEffect(() => {
    loadFinance();
  }, [period, startDate, endDate]);

  async function handleMarkPaid(bookingId) {
    if (!token) return;
    setMarkingId(bookingId);
    try {
      await markBookingPaid(token, bookingId);
      await loadFinance();
    } catch (err) {
      alert(err.message || 'Could not update payment status.');
    } finally {
      setMarkingId(null);
    }
  }

  if (!token) {
    window.location.replace('/provider/login');
    return null;
  }

  if (error && /token|401|unauthorized|expired/i.test(error)) {
    localStorage.removeItem('fixme_provider_token');
    window.location.replace('/provider/login');
    return null;
  }

  return (
    <div className="min-h-screen bg-fixme-bg pb-24 px-4 pt-8 max-w-md mx-auto space-y-5">
      <div>
        <p className="text-fixme-text-muted text-sm">Business performance</p>
        <h1 className="text-fixme-text-primary text-2xl font-bold mt-1">Finance</h1>
      </div>

      <FinanceDashboardView
        period={period}
        onPeriodChange={setPeriod}
        loading={loading}
        error={error}
        onRetry={loadFinance}
        insights={insights}
        summary={summary}
        startDate={startDate}
        endDate={endDate}
        onStartDateChange={setStartDate}
        onEndDateChange={setEndDate}
        recentBookings={recentBookings}
        recentLoading={recentLoading}
        onMarkPaid={handleMarkPaid}
        markingId={markingId}
      />

      <ProviderTabBar active="finance" />
    </div>
  );
}
