/**
 * OrgNumberLookup — reusable business registration number input + auto-fill widget.
 *
 * Shows a text input for the org number, a country selector,
 * and a "Verify" button. On success it calls onVerified(result) so
 * the parent can auto-fill provider name, address etc.
 *
 * AGENTS.md §9: shared verification widget — never re-implemented per persona.
 */

import { useState } from 'react';

const COUNTRY_OPTIONS = [
  { code: 'SE', label: 'Sweden', placeholder: '556000-1111', hint: 'Swedish org number (10 digits)' },
  { code: 'US', label: 'United States', placeholder: 'My Business LLC', hint: 'Business name (name search)' },
  { code: 'IN', label: 'India', placeholder: '22AAAAA0000A1Z5', hint: 'GSTIN (15 characters)' },
];

export default function OrgNumberLookup({ token, onVerified, onError, className = '' }) {
  const [country, setCountry] = useState('SE');
  const [orgNumber, setOrgNumber] = useState('');
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');

  const selected = COUNTRY_OPTIONS.find((c) => c.code === country) || COUNTRY_OPTIONS[0];
  // For US, we need a name; for SE/IN we prefer org number
  const needsName = country === 'US';

  async function handleVerify() {
    if (!token) {
      setErrorMsg('You must be logged in to verify your business.');
      return;
    }
    if (needsName && !name.trim()) {
      setErrorMsg('Please enter your business name.');
      return;
    }
    if (!needsName && !orgNumber.trim()) {
      setErrorMsg(`Please enter your ${selected.hint}.`);
      return;
    }

    setLoading(true);
    setErrorMsg('');
    setResult(null);

    try {
      const resp = await fetch('/api/v1/onboarding/business/verify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          country,
          org_number: needsName ? null : orgNumber.trim() || null,
          name: needsName ? name.trim() : name.trim() || null,
        }),
      });

      const data = await resp.json();

      if (!resp.ok) {
        const msg = data?.detail || 'Verification failed.';
        setErrorMsg(msg);
        onError?.(msg);
        return;
      }

      setResult(data);
      if (data.success) {
        onVerified?.(data);
      } else {
        setErrorMsg(data.error || 'Business not found. Please check your details.');
        onError?.(data.error);
      }
    } catch (err) {
      const msg = err.message || 'Network error. Please try again.';
      setErrorMsg(msg);
      onError?.(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={`space-y-3 ${className}`}>
      {/* Country selector */}
      <div>
        <label className="block text-xs font-medium text-neutral-600 mb-1">Country</label>
        <select
          value={country}
          onChange={(e) => {
            setCountry(e.target.value);
            setOrgNumber('');
            setName('');
            setResult(null);
            setErrorMsg('');
          }}
          className="w-full border border-neutral-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
        >
          {COUNTRY_OPTIONS.map((c) => (
            <option key={c.code} value={c.code}>{c.label}</option>
          ))}
        </select>
      </div>

      {/* Org number / GSTIN (SE, IN) */}
      {!needsName && (
        <div>
          <label className="block text-xs font-medium text-neutral-600 mb-1">{selected.hint}</label>
          <input
            type="text"
            value={orgNumber}
            onChange={(e) => setOrgNumber(e.target.value)}
            placeholder={selected.placeholder}
            className="w-full border border-neutral-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
          />
        </div>
      )}

      {/* Business name (US) or optional name for SE/IN */}
      {(needsName || !needsName) && (
        <div>
          <label className="block text-xs font-medium text-neutral-600 mb-1">
            {needsName ? 'Business name' : 'Business name (optional)'}
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Scissors & Co"
            className="w-full border border-neutral-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
          />
        </div>
      )}

      {/* Verify button */}
      <button
        onClick={handleVerify}
        disabled={loading}
        className="w-full rounded-xl bg-black text-white text-sm font-semibold py-2.5 disabled:opacity-60"
      >
        {loading ? 'Verifying…' : 'Verify Business'}
      </button>

      {/* Error */}
      {errorMsg && (
        <p className="text-xs text-red-500">{errorMsg}</p>
      )}

      {/* Success card */}
      {result?.success && (
        <div className="rounded-xl border border-green-200 bg-green-50 p-3 space-y-1">
          <div className="flex items-center gap-1.5">
            <svg className="w-4 h-4 text-green-600" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
            <span className="text-sm font-semibold text-green-800">Business verified</span>
          </div>
          {result.legal_name && (
            <p className="text-sm text-green-900 font-medium">{result.legal_name}</p>
          )}
          {result.city && (
            <p className="text-xs text-green-700">{[result.address_line1, result.city, result.region].filter(Boolean).join(', ')}</p>
          )}
          {result.business_type && (
            <p className="text-xs text-green-600">{result.business_type} · {result.status}</p>
          )}
          <p className="text-xs text-green-600 font-medium">
            {result.provider_verified ? '✓ Verified badge added to your profile' : ''}
          </p>
        </div>
      )}
    </div>
  );
}
