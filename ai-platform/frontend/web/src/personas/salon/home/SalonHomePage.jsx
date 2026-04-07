import { useEffect, useMemo, useState } from 'react';
import SalonTabBar from '../navigation/SalonTabBar';

const API_BASE = '/api/v1';

async function authRequest(endpoint, options = {}) {
  const token = localStorage.getItem('fixme_provider_token');
  if (!token) throw new Error('Not authenticated');

  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
    ...options,
  });

  if (res.status === 401 || res.status === 403) {
    throw new Error('Session expired. Please sign in again.');
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || 'Request failed');
  return data;
}

export default function SalonHomePage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyRequestId, setBusyRequestId] = useState(null);

  const loadDashboard = async () => {
    setLoading(true);
    setError('');
    try {
      const dashboard = await authRequest('/home/dashboard');
      setData(dashboard);
    } catch (e) {
      setError(e.message || 'Could not load salon home');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  const workerRequests = useMemo(
    () => (data?.requests || []).filter((r) => r.request_type === 'worker'),
    [data],
  );

  const handleReviewRequest = async (requestId, action) => {
    setBusyRequestId(requestId);
    try {
      await authRequest(`/salon-links/${requestId}/${action}`, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      await loadDashboard();
    } catch (e) {
      setError(e.message || `Could not ${action} request`);
    } finally {
      setBusyRequestId(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-fixme-bg px-4 pt-10 pb-24 max-w-md mx-auto">
        <div className="w-10 h-10 border-2 border-fixme-accent border-t-transparent rounded-full animate-spin mx-auto mt-16" />
        <SalonTabBar active="home" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="min-h-screen bg-fixme-bg px-4 pt-10 pb-24 max-w-md mx-auto">
        <h1 className="text-fixme-text-primary text-2xl font-bold">Salon Home</h1>
        <p className="text-fixme-error text-sm mt-4">{error}</p>
        <button
          onClick={() => { window.location.href = '/salon/login'; }}
          className="mt-4 bg-fixme-accent text-fixme-bg text-sm font-semibold px-4 py-2 rounded-xl"
        >
          Go to salon login
        </button>
        <SalonTabBar active="home" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-fixme-bg px-4 pt-8 pb-24 max-w-md mx-auto">
      <h1 className="text-fixme-text-primary text-2xl font-bold">{data?.provider_name || 'Salon Home'}</h1>
      <p className="text-fixme-text-secondary text-sm mt-1">{data?.today_label || 'Today'}</p>

      <div className="grid grid-cols-3 gap-2 mt-4">
        <StatCard label="Team" value={(data?.team || []).length} />
        <StatCard label="Requests" value={workerRequests.length} />
        <StatCard label="Upcoming" value={(data?.upcoming_bookings || []).length} />
      </div>

      {error && <p className="text-fixme-error text-xs mt-3">{error}</p>}

      <section className="mt-6">
        <h2 className="text-fixme-text-primary font-semibold text-base">Join Requests</h2>
        {workerRequests.length === 0 && (
          <p className="text-fixme-text-muted text-sm mt-2">No pending freelancer requests.</p>
        )}
        <div className="space-y-2 mt-2">
          {workerRequests.map((r) => (
            <div key={r.request_id} className="bg-fixme-card border border-fixme-border rounded-xl p-3">
              <p className="text-fixme-text-primary font-semibold text-sm">{r.person_name}</p>
              <p className="text-fixme-text-muted text-xs mt-1">
                {(r.business_type || 'freelancer').replace('_', ' ')}
                {r.worker_city ? ` � ${r.worker_city}` : ''}
              </p>
              {r.worker_message && (
                <p className="text-fixme-text-secondary text-xs mt-2">"{r.worker_message}"</p>
              )}
              <div className="flex gap-2 mt-3">
                <button
                  onClick={() => handleReviewRequest(r.request_id, 'approve')}
                  disabled={busyRequestId === r.request_id}
                  className="flex-1 bg-fixme-accent text-fixme-bg text-xs font-semibold py-2 rounded-lg disabled:opacity-60"
                >
                  Approve
                </button>
                <button
                  onClick={() => handleReviewRequest(r.request_id, 'reject')}
                  disabled={busyRequestId === r.request_id}
                  className="flex-1 bg-fixme-card border border-fixme-border text-fixme-text-secondary text-xs font-semibold py-2 rounded-lg disabled:opacity-60"
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-6">
        <h2 className="text-fixme-text-primary font-semibold text-base">Team</h2>
        <div className="space-y-2 mt-2">
          {(data?.team || []).map((member) => (
            <div key={member.id} className="bg-fixme-card border border-fixme-border rounded-xl p-3 flex items-center justify-between">
              <div>
                <p className="text-fixme-text-primary text-sm font-semibold">{member.display_name}</p>
                <p className="text-fixme-text-muted text-xs mt-0.5">{(member.member_type || 'worker').replace('_', ' ')}</p>
              </div>
              <span className={`text-xs ${member.is_working_today ? 'text-fixme-accent' : 'text-fixme-text-muted'}`}>
                {member.is_working_today ? 'Working today' : 'Off today'}
              </span>
            </div>
          ))}
          {(data?.team || []).length === 0 && (
            <p className="text-fixme-text-muted text-sm">No team members yet.</p>
          )}
        </div>
      </section>

      <SalonTabBar active="home" />
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="bg-fixme-card border border-fixme-border rounded-xl py-3 px-2 text-center">
      <p className="text-fixme-text-primary text-base font-bold">{value}</p>
      <p className="text-fixme-text-muted text-[11px] mt-0.5">{label}</p>
    </div>
  );
}
