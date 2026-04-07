import { useEffect, useState } from 'react';
import {
  getAdminGdprRequests,
  getAdminGdprStats,
  updateAdminGdprRequest,
} from '../../api/bookingApi';
import AdminShell, { getAdminToken } from '../../features/admin/AdminShell';

export default function AdminGdprPage() {
  const [status, setStatus] = useState('');
  const [requestType, setRequestType] = useState('');
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState(null);
  const [message, setMessage] = useState('');

  async function load() {
    setMessage('');
    try {
      const token = getAdminToken();
      const [data, nextStats] = await Promise.all([
        getAdminGdprRequests(token, { status, requestType }),
        getAdminGdprStats(token),
      ]);
      setRows(data || []);
      setStats(nextStats || null);
    } catch (err) {
      setMessage(err.message || 'Failed to load GDPR requests');
    }
  }

  useEffect(() => {
    load();
  }, [status, requestType]);

  async function changeStatus(requestId, nextStatus) {
    setMessage('');
    try {
      await updateAdminGdprRequest(getAdminToken(), requestId, {
        status: nextStatus,
        adminNotes: 'updated_from_admin_menu',
      });
      await load();
    } catch (err) {
      setMessage(err.message || 'Failed to update request');
    }
  }

  return (
    <AdminShell title="GDPR requests" activeKey="gdpr">
      <div className="space-y-4">
        <div className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4 space-y-3">
          <p className="text-sm font-semibold">Data rights queue</p>
          <div className="flex flex-wrap gap-2 text-xs">
            <FilterPill active={!status} onClick={() => setStatus('')}>All statuses</FilterPill>
            <FilterPill active={status === 'pending'} onClick={() => setStatus('pending')}>Pending</FilterPill>
            <FilterPill active={status === 'in_progress'} onClick={() => setStatus('in_progress')}>In progress</FilterPill>
            <FilterPill active={status === 'completed'} onClick={() => setStatus('completed')}>Completed</FilterPill>
            <FilterPill active={status === 'rejected'} onClick={() => setStatus('rejected')}>Rejected</FilterPill>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <FilterPill active={!requestType} onClick={() => setRequestType('')}>All types</FilterPill>
            <FilterPill active={requestType === 'export'} onClick={() => setRequestType('export')}>Export</FilterPill>
            <FilterPill active={requestType === 'deletion'} onClick={() => setRequestType('deletion')}>Deletion</FilterPill>
          </div>
          {stats && <p className="text-xs text-gray-400">Need action: {stats.pending_attention || 0}</p>}
          {message && <p className="text-xs text-amber-300">{message}</p>}
        </div>

        <div className="space-y-2">
          {rows.map((row) => (
            <div key={row.request_id} className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-xl p-3 text-xs space-y-2">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-white">{row.user_email}</p>
                  <p className="text-gray-400">{row.request_type} / {row.status}</p>
                </div>
                <p className="text-gray-500">{new Date(row.requested_at).toLocaleDateString()}</p>
              </div>
              {row.notes && <p className="text-gray-300">{row.notes}</p>}
              <div className="flex gap-2 flex-wrap">
                {['pending', 'in_progress', 'completed', 'rejected'].map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => changeStatus(row.request_id, s)}
                    className={[
                      'px-2 py-1 rounded-md border',
                      row.status === s ? 'border-[#F5F5F0]/50 text-white' : 'border-[#333333] text-gray-400',
                    ].join(' ')}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ))}
          {rows.length === 0 && <p className="text-xs text-gray-500">No rows</p>}
        </div>
      </div>
    </AdminShell>
  );
}

function FilterPill({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'px-2.5 py-1 rounded-full border',
        active ? 'border-[#F5F5F0]/50 text-white' : 'border-[#333333] text-gray-400',
      ].join(' ')}
    >
      {children}
    </button>
  );
}
