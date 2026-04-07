import { useEffect, useMemo, useState } from 'react';
import {
  getAdminReports,
  getAdminReportStats,
  patchAdminReport,
} from '../../api/bookingApi';
import AdminShell, { getAdminToken } from '../../features/admin/AdminShell';

const STATUS_OPTIONS = ['open', 'reviewing', 'resolved', 'dismissed'];
const ACTION_OPTIONS = ['none', 'warned', 'blocked', 'dismissed'];

function fmtDateTime(iso) {
  if (!iso) return '-';
  return new Date(iso).toLocaleString('en-GB', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function ScopeBadge({ scope }) {
  const label = scope === 'provider_to_customer' ? 'Provider ? Customer' : 'Customer ? Provider';
  return (
    <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#222] border border-[#333] text-gray-300">
      {label}
    </span>
  );
}

export default function AdminReportsPage() {
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState({ open_total: 0, open_provider_to_customer: 0, open_customer_to_provider: 0 });
  const [scope, setScope] = useState('all');
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [updatingId, setUpdatingId] = useState('');
  const [drafts, setDrafts] = useState({});

  async function loadData() {
    setLoading(true);
    setMessage('');
    try {
      const token = getAdminToken();
      const [reportRows, reportStats] = await Promise.all([
        getAdminReports(token, {
          scope,
          ...(status ? { status } : {}),
          limit: 300,
        }),
        getAdminReportStats(token),
      ]);
      setRows(Array.isArray(reportRows) ? reportRows : []);
      setStats(reportStats || { open_total: 0, open_provider_to_customer: 0, open_customer_to_provider: 0 });
    } catch (err) {
      setMessage(err.message || 'Failed to load reports');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, [scope, status]);

  const groupedOpen = useMemo(() => {
    return {
      total: Number(stats.open_total || 0),
      providerToCustomer: Number(stats.open_provider_to_customer || 0),
      customerToProvider: Number(stats.open_customer_to_provider || 0),
    };
  }, [stats]);

  function draftFor(row) {
    return drafts[row.report_id] || {
      status: row.status || 'open',
      action_taken: row.action_taken || 'none',
      admin_notes: row.admin_notes || '',
      reason: '',
    };
  }

  async function applyRowUpdate(row) {
    const token = getAdminToken();
    const draft = draftFor(row);
    setUpdatingId(row.report_id);
    setMessage('');
    try {
      await patchAdminReport(token, row.report_scope, row.report_id, {
        status: draft.status,
        action_taken: draft.action_taken,
        admin_notes: draft.admin_notes || null,
        reason: draft.reason || 'admin_reports_update',
      });
      await loadData();
      setMessage('Report updated');
    } catch (err) {
      setMessage(err.message || 'Failed to update report');
    } finally {
      setUpdatingId('');
    }
  }

  return (
    <AdminShell title="Incident reports from booking cards" activeKey="reports">
      <div className="space-y-4">
        <div className="grid md:grid-cols-4 gap-3">
          <div className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4">
            <p className="text-xs text-gray-400">Open total</p>
            <p className="text-xl font-semibold mt-1">{groupedOpen.total}</p>
          </div>
          <div className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4">
            <p className="text-xs text-gray-400">Provider ? Customer</p>
            <p className="text-xl font-semibold mt-1">{groupedOpen.providerToCustomer}</p>
          </div>
          <div className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4">
            <p className="text-xs text-gray-400">Customer ? Provider</p>
            <p className="text-xl font-semibold mt-1">{groupedOpen.customerToProvider}</p>
          </div>
          <div className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4">
            <p className="text-xs text-gray-400">Loaded rows</p>
            <p className="text-xl font-semibold mt-1">{rows.length}</p>
          </div>
        </div>

        <div className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4 space-y-3">
          <div className="grid md:grid-cols-4 gap-2">
            <label className="text-xs text-gray-300 space-y-1">
              <span>Scope</span>
              <select
                value={scope}
                onChange={(e) => setScope(e.target.value)}
                className="w-full bg-[#0D0D0D] border border-[#2A2A2A] rounded-lg px-2 py-1.5"
              >
                <option value="all">All</option>
                <option value="provider_to_customer">Provider ? Customer</option>
                <option value="customer_to_provider">Customer ? Provider</option>
              </select>
            </label>
            <label className="text-xs text-gray-300 space-y-1">
              <span>Status</span>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full bg-[#0D0D0D] border border-[#2A2A2A] rounded-lg px-2 py-1.5"
              >
                <option value="">All</option>
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </label>
            <div className="flex items-end">
              <button
                type="button"
                onClick={loadData}
                disabled={loading}
                className="px-4 py-2 rounded-xl bg-[#F5F5F0] text-[#0D0D0D] text-sm font-semibold disabled:opacity-40"
              >
                {loading ? 'Loading...' : 'Refresh'}
              </button>
            </div>
          </div>
          {message && <p className="text-xs text-amber-300">{message}</p>}
        </div>

        <div className="space-y-3">
          {rows.length === 0 && !loading && (
            <div className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4 text-sm text-gray-400">
              No reports found for this filter.
            </div>
          )}

          {rows.map((row) => {
            const draft = draftFor(row);
            return (
              <div key={`${row.report_scope}:${row.report_id}`} className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4 space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <ScopeBadge scope={row.report_scope} />
                      <span className="text-xs text-gray-400">{row.report_type}</span>
                      <span className="text-xs text-gray-500">Severity {row.severity}</span>
                    </div>
                    <p className="text-sm text-white mt-1">{row.provider_name} - {row.customer_name}</p>
                    <p className="text-xs text-gray-400 mt-1">Created {fmtDateTime(row.created_at)} | Booking {fmtDateTime(row.booking_start)}</p>
                  </div>
                  <span className="text-[11px] px-2 py-1 rounded-full border border-[#333] text-gray-300">{row.status}</span>
                </div>

                {row.details && <p className="text-xs text-gray-300 bg-[#111] border border-[#2A2A2A] rounded-xl p-2">{row.details}</p>}

                <div className="grid md:grid-cols-4 gap-2">
                  <label className="text-xs text-gray-300 space-y-1">
                    <span>Status</span>
                    <select
                      value={draft.status}
                      onChange={(e) => setDrafts((prev) => ({ ...prev, [row.report_id]: { ...draft, status: e.target.value } }))}
                      className="w-full bg-[#0D0D0D] border border-[#2A2A2A] rounded-lg px-2 py-1.5"
                    >
                      {STATUS_OPTIONS.map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </label>

                  <label className="text-xs text-gray-300 space-y-1">
                    <span>Action</span>
                    <select
                      value={draft.action_taken}
                      onChange={(e) => setDrafts((prev) => ({ ...prev, [row.report_id]: { ...draft, action_taken: e.target.value } }))}
                      className="w-full bg-[#0D0D0D] border border-[#2A2A2A] rounded-lg px-2 py-1.5"
                    >
                      {ACTION_OPTIONS.map((a) => (
                        <option key={a} value={a}>{a}</option>
                      ))}
                    </select>
                  </label>

                  <label className="text-xs text-gray-300 space-y-1 md:col-span-2">
                    <span>Admin notes</span>
                    <input
                      value={draft.admin_notes}
                      onChange={(e) => setDrafts((prev) => ({ ...prev, [row.report_id]: { ...draft, admin_notes: e.target.value } }))}
                      className="w-full bg-[#0D0D0D] border border-[#2A2A2A] rounded-lg px-2 py-1.5"
                    />
                  </label>
                </div>

                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => applyRowUpdate(row)}
                    disabled={updatingId === row.report_id}
                    className="px-4 py-2 rounded-xl bg-[#F5F5F0] text-[#0D0D0D] text-xs font-semibold disabled:opacity-40"
                  >
                    {updatingId === row.report_id ? 'Saving...' : 'Apply'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </AdminShell>
  );
}

