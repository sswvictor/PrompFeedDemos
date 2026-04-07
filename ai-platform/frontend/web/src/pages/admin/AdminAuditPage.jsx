import { useState } from 'react';
import { getAdminAuditLogs } from '../../api/bookingApi';
import AdminShell, { getAdminToken } from '../../features/admin/AdminShell';

export default function AdminAuditPage() {
  const [filters, setFilters] = useState({ entity_type: '', entity_id: '', action: '', admin_actor: '', limit: 200 });
  const [rows, setRows] = useState([]);
  const [error, setError] = useState('');

  async function load() {
    setError('');
    try {
      const token = getAdminToken();
      const data = await getAdminAuditLogs(token, filters);
      setRows(data || []);
    } catch (err) {
      setError(err.message || 'Failed to load logs');
    }
  }

  return (
    <AdminShell title="Fixmeapp history log" activeKey="audit">
      <div className="space-y-4">
        <div className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4 space-y-3">
          <p className="text-sm font-semibold">Audit log filters</p>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
            <Field label="Entity type" value={filters.entity_type} onChange={(v) => setFilters((p) => ({ ...p, entity_type: v }))} />
            <Field label="Entity ID" value={filters.entity_id} onChange={(v) => setFilters((p) => ({ ...p, entity_id: v }))} />
            <Field label="Action" value={filters.action} onChange={(v) => setFilters((p) => ({ ...p, action: v }))} />
            <Field label="Admin actor" value={filters.admin_actor} onChange={(v) => setFilters((p) => ({ ...p, admin_actor: v }))} />
            <Field label="Limit" value={String(filters.limit)} onChange={(v) => setFilters((p) => ({ ...p, limit: Number(v || 200) }))} />
          </div>
          <button type="button" onClick={load} className="px-3 py-2 bg-white text-black rounded-lg text-xs font-semibold">Load logs</button>
          {error && <p className="text-xs text-red-400">{error}</p>}
        </div>

        <div className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4">
          <div className="max-h-[520px] overflow-auto space-y-2">
            {rows.map((row) => (
              <div key={row.log_id} className="border border-[#2A2A2A] rounded-lg p-3 text-xs space-y-1">
                <p className="text-white">{row.action} - {row.entity_type}:{row.entity_id || 'n/a'}</p>
                <p className="text-gray-400">{row.admin_actor || 'unknown'} - {new Date(row.created_at).toLocaleString()}</p>
                {row.reason && <p className="text-amber-300">Reason: {row.reason}</p>}
              </div>
            ))}
            {rows.length === 0 && <p className="text-xs text-gray-500">No logs loaded</p>}
          </div>
        </div>
      </div>
    </AdminShell>
  );
}

function Field({ label, value, onChange }) {
  return (
    <label className="text-xs text-gray-300 space-y-1">
      <span>{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-[#0D0D0D] border border-[#2A2A2A] rounded-lg px-2 py-1.5"
      />
    </label>
  );
}
