import { useEffect, useState } from 'react';
import {
  approveVerification,
  getAdminVerificationStats,
  getAdminVerifications,
  rejectVerification,
} from '../../api/bookingApi';
import AdminShell, { getAdminToken } from '../../features/admin/AdminShell';

export default function AdminVerificationsPage() {
  const [status, setStatus] = useState('pending');
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState({});
  const [message, setMessage] = useState('');

  async function load() {
    setMessage('');
    try {
      const token = getAdminToken();
      const [items, nextStats] = await Promise.all([
        getAdminVerifications(token, status),
        getAdminVerificationStats(token),
      ]);
      setRows(items || []);
      setStats(nextStats || {});
    } catch (err) {
      setMessage(err.message || 'Failed to load verification queue');
    }
  }

  useEffect(() => {
    load();
  }, [status]);

  async function approve(id) {
    setMessage('');
    try {
      await approveVerification(getAdminToken(), id);
      await load();
    } catch (err) {
      setMessage(err.message || 'Approve failed');
    }
  }

  async function reject(id) {
    const reason = window.prompt('Reason for rejection (optional):') || '';
    setMessage('');
    try {
      await rejectVerification(getAdminToken(), id, reason);
      await load();
    } catch (err) {
      setMessage(err.message || 'Reject failed');
    }
  }

  return (
    <AdminShell title="Provider verification queue" activeKey="verifications">
      <div className="space-y-4">
        <div className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4 flex items-center justify-between gap-2">
          <p className="text-sm font-semibold">Verifications</p>
          <div className="flex gap-2">
            {['pending', 'approved', 'rejected'].map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setStatus(s)}
                className={[
                  'px-2.5 py-1 rounded-full text-xs border',
                  s === status ? 'border-[#F5F5F0]/50 text-white' : 'border-[#333333] text-gray-400',
                ].join(' ')}
              >
                {s} ({stats?.[s] || 0})
              </button>
            ))}
          </div>
        </div>

        {message && <p className="text-xs text-amber-300">{message}</p>}

        <div className="space-y-2">
          {rows.map((row) => (
            <div key={row.id} className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-xl p-3 text-xs space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-white">{row.provider_name}</p>
                  <p className="text-gray-400">{row.provider_email}</p>
                </div>
                <p className="text-gray-500">{row.status}</p>
              </div>
              <p className="text-gray-500">{row.country}{row.us_state ? ` / ${row.us_state}` : ''}</p>
              {row.status === 'pending' && (
                <div className="flex gap-2">
                  <button type="button" onClick={() => approve(row.id)} className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white">Approve</button>
                  <button type="button" onClick={() => reject(row.id)} className="px-3 py-1.5 rounded-lg bg-red-700 text-white">Reject</button>
                </div>
              )}
            </div>
          ))}
          {rows.length === 0 && <p className="text-xs text-gray-500">No rows</p>}
        </div>
      </div>
    </AdminShell>
  );
}
