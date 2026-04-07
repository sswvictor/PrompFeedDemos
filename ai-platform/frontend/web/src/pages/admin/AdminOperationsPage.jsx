import { useState } from 'react';
import {
  getAdminProvider,
  getAdminSearch,
  getAdminUser,
  patchAdminProvider,
  patchAdminUser,
} from '../../api/bookingApi';
import AdminShell, { getAdminToken } from '../../features/admin/AdminShell';

export default function AdminOperationsPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [selectedUser, setSelectedUser] = useState(null);
  const [selectedProvider, setSelectedProvider] = useState(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  async function runSearch() {
    if (!query.trim()) return;
    setLoading(true);
    setMessage('');
    try {
      const token = getAdminToken();
      const data = await getAdminSearch(token, query.trim(), 20);
      setResults(data);
    } catch (err) {
      setMessage(err.message || 'Search failed');
    } finally {
      setLoading(false);
    }
  }

  async function openUser(userId) {
    setLoading(true);
    setMessage('');
    try {
      const token = getAdminToken();
      const data = await getAdminUser(token, userId);
      setSelectedUser(data);
      setSelectedProvider(null);
    } catch (err) {
      setMessage(err.message || 'Failed to load user');
    } finally {
      setLoading(false);
    }
  }

  async function openProvider(providerId) {
    setLoading(true);
    setMessage('');
    try {
      const token = getAdminToken();
      const data = await getAdminProvider(token, providerId);
      setSelectedProvider(data);
      setSelectedUser(null);
    } catch (err) {
      setMessage(err.message || 'Failed to load provider');
    } finally {
      setLoading(false);
    }
  }

  async function saveUser() {
    if (!selectedUser) return;
    setLoading(true);
    setMessage('');
    try {
      const token = getAdminToken();
      const payload = {
        status: selectedUser.status,
        display_name: selectedUser.display_name || null,
        is_profile_public: selectedUser.is_profile_public,
        is_customer: selectedUser.is_customer,
        is_provider: selectedUser.is_provider,
        reason: 'admin_operations_update',
      };
      const data = await patchAdminUser(token, selectedUser.user_id, payload);
      setSelectedUser(data.user);
      setMessage('User updated');
    } catch (err) {
      setMessage(err.message || 'Failed to save user');
    } finally {
      setLoading(false);
    }
  }

  async function saveProvider() {
    if (!selectedProvider) return;
    setLoading(true);
    setMessage('');
    try {
      const token = getAdminToken();
      const payload = {
        name: selectedProvider.name,
        phone: selectedProvider.phone,
        city: selectedProvider.city,
        location_salon: selectedProvider.location_salon,
        is_verified: selectedProvider.is_verified,
        linked_user_status: selectedProvider.user_status,
        reason: 'admin_operations_update',
      };
      const data = await patchAdminProvider(token, selectedProvider.provider_id, payload);
      setSelectedProvider(data.provider);
      setMessage('Provider updated');
    } catch (err) {
      setMessage(err.message || 'Failed to save provider');
    } finally {
      setLoading(false);
    }
  }

  return (
    <AdminShell title="Search, inspect and fix accounts" activeKey="operations">
      <div className="space-y-4">
        <div className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4 space-y-3">
          <p className="text-sm font-semibold">Global search</p>
          <div className="flex gap-2">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && runSearch()}
              placeholder="Search provider, user or booking id"
              className="flex-1 bg-[#0D0D0D] border border-[#2A2A2A] rounded-xl px-3 py-2 text-sm"
            />
            <button
              type="button"
              onClick={runSearch}
              disabled={loading || !query.trim()}
              className="px-4 py-2 rounded-xl bg-[#F5F5F0] text-[#0D0D0D] text-sm font-semibold disabled:opacity-40"
            >
              Search
            </button>
          </div>
          {message && <p className="text-xs text-amber-300">{message}</p>}

          {results && (
            <div className="grid md:grid-cols-3 gap-3">
              <ResultList title="Providers" rows={results.providers} onOpen={openProvider} />
              <ResultList title="Users" rows={results.users} onOpen={openUser} />
              <ResultList title="Bookings" rows={results.bookings} onOpen={null} />
            </div>
          )}
        </div>

        {selectedUser && (
          <div className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4 space-y-3">
            <p className="text-sm font-semibold">User edit</p>
            <p className="text-xs text-gray-400">{selectedUser.user_id}</p>
            <div className="grid md:grid-cols-2 gap-2">
              <label className="text-xs text-gray-300 space-y-1">
                <span>Status</span>
                <input
                  value={selectedUser.status || ''}
                  onChange={(e) => setSelectedUser((prev) => ({ ...prev, status: e.target.value }))}
                  className="w-full bg-[#0D0D0D] border border-[#2A2A2A] rounded-lg px-2 py-1.5"
                />
              </label>
              <label className="text-xs text-gray-300 space-y-1">
                <span>Display name</span>
                <input
                  value={selectedUser.display_name || ''}
                  onChange={(e) => setSelectedUser((prev) => ({ ...prev, display_name: e.target.value }))}
                  className="w-full bg-[#0D0D0D] border border-[#2A2A2A] rounded-lg px-2 py-1.5"
                />
              </label>
            </div>
            <div className="flex gap-3 text-xs">
              <Toggle label="Public profile" checked={!!selectedUser.is_profile_public} onToggle={() => setSelectedUser((prev) => ({ ...prev, is_profile_public: !prev.is_profile_public }))} />
              <Toggle label="Is customer" checked={!!selectedUser.is_customer} onToggle={() => setSelectedUser((prev) => ({ ...prev, is_customer: !prev.is_customer }))} />
              <Toggle label="Is provider" checked={!!selectedUser.is_provider} onToggle={() => setSelectedUser((prev) => ({ ...prev, is_provider: !prev.is_provider }))} />
            </div>
            <button type="button" onClick={saveUser} className="px-3 py-2 bg-white text-black rounded-lg text-xs font-semibold">Save user</button>
          </div>
        )}

        {selectedProvider && (
          <div className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4 space-y-3">
            <p className="text-sm font-semibold">Provider edit</p>
            <p className="text-xs text-gray-400">{selectedProvider.provider_id}</p>
            <div className="grid md:grid-cols-2 gap-2">
              <label className="text-xs text-gray-300 space-y-1">
                <span>Name</span>
                <input
                  value={selectedProvider.name || ''}
                  onChange={(e) => setSelectedProvider((prev) => ({ ...prev, name: e.target.value }))}
                  className="w-full bg-[#0D0D0D] border border-[#2A2A2A] rounded-lg px-2 py-1.5"
                />
              </label>
              <label className="text-xs text-gray-300 space-y-1">
                <span>City</span>
                <input
                  value={selectedProvider.city || ''}
                  onChange={(e) => setSelectedProvider((prev) => ({ ...prev, city: e.target.value }))}
                  className="w-full bg-[#0D0D0D] border border-[#2A2A2A] rounded-lg px-2 py-1.5"
                />
              </label>
            </div>
            <div className="flex gap-3 text-xs">
              <Toggle label="Verified" checked={!!selectedProvider.is_verified} onToggle={() => setSelectedProvider((prev) => ({ ...prev, is_verified: !prev.is_verified }))} />
            </div>
            <button type="button" onClick={saveProvider} className="px-3 py-2 bg-white text-black rounded-lg text-xs font-semibold">Save provider</button>
          </div>
        )}
      </div>
    </AdminShell>
  );
}

function ResultList({ title, rows, onOpen }) {
  return (
    <div className="bg-[#111111] border border-[#2A2A2A] rounded-xl p-3 space-y-2">
      <p className="text-xs uppercase tracking-wide text-gray-400">{title}</p>
      {rows?.length ? rows.map((row) => (
        <button
          key={row.id}
          type="button"
          disabled={!onOpen}
          onClick={() => onOpen && onOpen(row.id)}
          className="w-full text-left border border-[#2A2A2A] hover:border-[#555555] rounded-lg p-2 text-xs disabled:cursor-default"
        >
          <p className="text-white">{row.label}</p>
          <p className="text-gray-400 truncate">{row.subtitle || row.id}</p>
        </button>
      )) : <p className="text-xs text-gray-500">No results</p>}
    </div>
  );
}

function Toggle({ label, checked, onToggle }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={[
        'px-2 py-1 rounded-md border',
        checked ? 'bg-[#F5F5F0]/10 border-[#F5F5F0]/50 text-white' : 'border-[#333333] text-gray-400',
      ].join(' ')}
    >
      {label}
    </button>
  );
}
