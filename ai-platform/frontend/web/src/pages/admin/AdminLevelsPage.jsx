import { useState } from 'react';
import { getAdminLevelInspector } from '../../api/bookingApi';
import AdminShell, { getAdminToken } from '../../features/admin/AdminShell';

export default function AdminLevelsPage() {
  const [actorType, setActorType] = useState('provider');
  const [actorId, setActorId] = useState('');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  async function load() {
    setError('');
    setData(null);
    try {
      const token = getAdminToken();
      const out = await getAdminLevelInspector(token, actorType, actorId.trim());
      setData(out);
    } catch (err) {
      setError(err.message || 'Failed to load level data');
    }
  }

  return (
    <AdminShell title="Level inspector" activeKey="levels">
      <div className="space-y-4">
        <div className="max-w-2xl bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4 space-y-3">
          <p className="text-sm font-semibold">Inspect loyalty level</p>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-gray-300 space-y-1">
              <span>Actor type</span>
              <input value={actorType} onChange={(e) => setActorType(e.target.value)} className="w-full bg-[#0D0D0D] border border-[#2A2A2A] rounded-lg px-2 py-1.5" />
            </label>
            <label className="text-xs text-gray-300 space-y-1">
              <span>Actor ID</span>
              <input value={actorId} onChange={(e) => setActorId(e.target.value)} className="w-full bg-[#0D0D0D] border border-[#2A2A2A] rounded-lg px-2 py-1.5" />
            </label>
          </div>
          <button type="button" onClick={load} className="px-3 py-2 bg-white text-black rounded-lg text-xs font-semibold">Load level</button>
          {error && <p className="text-xs text-red-400">{error}</p>}
        </div>

        {data?.snapshot && (
          <div className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4 space-y-2 text-sm">
            <p className="font-semibold">Snapshot</p>
            <p>Badge: <span className="text-emerald-300">{data.snapshot.level_badge}</span></p>
            <p>Tier: {data.snapshot.tier}</p>
            <p>Score (internal): {data.snapshot.score}</p>
            <p>Completed bookings: {data.snapshot.completed_bookings}</p>
            <p>Completed referrals: {data.snapshot.completed_referrals}</p>
          </div>
        )}

        {data?.events?.length > 0 && (
          <div className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4 space-y-2">
            <p className="text-sm font-semibold">Recent events</p>
            <div className="max-h-[380px] overflow-auto space-y-2">
              {data.events.map((event) => (
                <div key={event.event_id} className="border border-[#2A2A2A] rounded-lg p-2 text-xs">
                  <p className="text-white">{event.event_type} ({event.points}p)</p>
                  <p className="text-gray-400">{new Date(event.occurred_at).toLocaleString()}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </AdminShell>
  );
}
