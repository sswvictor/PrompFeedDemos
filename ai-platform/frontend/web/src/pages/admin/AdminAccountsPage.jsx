import { useState } from 'react';
import { createAdminManualAccount } from '../../api/bookingApi';
import AdminShell, { getAdminToken } from '../../features/admin/AdminShell';

export default function AdminAccountsPage() {
  const [form, setForm] = useState({
    account_type: 'customer',
    email: '',
    display_name: '',
    provider_name: '',
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  async function submit() {
    setError('');
    setResult(null);
    try {
      const token = getAdminToken();
      const data = await createAdminManualAccount(token, {
        ...form,
        reason: 'admin_manual_account',
      });
      setResult(data);
    } catch (err) {
      setError(err.message || 'Failed to create account');
    }
  }

  return (
    <AdminShell title="Manual account creation" activeKey="accounts">
      <div className="max-w-2xl bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4 space-y-3">
        <p className="text-sm font-semibold">Create account manually</p>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Account type" value={form.account_type} onChange={(v) => setForm((p) => ({ ...p, account_type: v }))} />
          <Field label="Email" value={form.email} onChange={(v) => setForm((p) => ({ ...p, email: v }))} />
          <Field label="Display name" value={form.display_name} onChange={(v) => setForm((p) => ({ ...p, display_name: v }))} />
          <Field label="Provider name" value={form.provider_name} onChange={(v) => setForm((p) => ({ ...p, provider_name: v }))} />
        </div>

        <p className="text-xs text-gray-400">
          Flow: admin creates user/provider shell account, user then logs in with email OTP.
        </p>

        <button type="button" onClick={submit} className="px-3 py-2 bg-white text-black rounded-lg text-xs font-semibold">
          Create account
        </button>

        {error && <p className="text-xs text-red-400">{error}</p>}
        {result && (
          <div className="text-xs text-emerald-300 bg-[#0D0D0D] border border-[#2A2A2A] rounded-lg p-3">
            <p>User ID: {result.user_id}</p>
            {result.provider_id && <p>Provider ID: {result.provider_id}</p>}
            <p>Created user: {String(result.created_user)}</p>
            <p>Created provider: {String(result.created_provider)}</p>
          </div>
        )}
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
