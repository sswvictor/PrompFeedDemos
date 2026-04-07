import { useState } from 'react';
import {
  createAdminManualBooking,
  getAdminBookings,
  patchAdminBooking,
} from '../../api/bookingApi';
import AdminShell, { getAdminToken } from '../../features/admin/AdminShell';

export default function AdminBookingsPage() {
  const [filters, setFilters] = useState({ provider_id: '', user_id: '', status: '', limit: 100 });
  const [rows, setRows] = useState([]);
  const [message, setMessage] = useState('');
  const [manual, setManual] = useState({
    provider_id: '',
    customer_email: '',
    customer_name: '',
    scheduled_start: '',
    scheduled_end: '',
    service_name: '',
    unit_price_ex_vat: '0',
    status: 'confirmed',
  });

  async function loadBookings() {
    setMessage('');
    try {
      const token = getAdminToken();
      const data = await getAdminBookings(token, filters);
      setRows(data || []);
    } catch (err) {
      setMessage(err.message || 'Failed to load bookings');
    }
  }

  async function updateStatus(bookingId, status) {
    setMessage('');
    try {
      const token = getAdminToken();
      await patchAdminBooking(token, bookingId, { status, reason: 'admin_bookings_page' });
      await loadBookings();
      setMessage('Booking updated');
    } catch (err) {
      setMessage(err.message || 'Failed to update booking');
    }
  }

  async function createManual() {
    setMessage('');
    try {
      const token = getAdminToken();
      await createAdminManualBooking(token, {
        ...manual,
        unit_price_ex_vat: Number(manual.unit_price_ex_vat || 0),
        quantity: 1,
        reason: 'admin_manual_booking',
      });
      setMessage('Manual booking created');
      await loadBookings();
    } catch (err) {
      setMessage(err.message || 'Failed to create manual booking');
    }
  }

  return (
    <AdminShell title="Booking controls and manual creation" activeKey="bookings">
      <div className="grid lg:grid-cols-2 gap-4">
        <section className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4 space-y-3">
          <p className="text-sm font-semibold">Find bookings</p>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Provider ID" value={filters.provider_id} onChange={(v) => setFilters((p) => ({ ...p, provider_id: v }))} />
            <Field label="User ID" value={filters.user_id} onChange={(v) => setFilters((p) => ({ ...p, user_id: v }))} />
            <Field label="Status" value={filters.status} onChange={(v) => setFilters((p) => ({ ...p, status: v }))} />
            <Field label="Limit" value={String(filters.limit)} onChange={(v) => setFilters((p) => ({ ...p, limit: Number(v || 100) }))} />
          </div>
          <button type="button" onClick={loadBookings} className="px-3 py-2 bg-white text-black rounded-lg text-xs font-semibold">Load</button>
          {message && <p className="text-xs text-amber-300">{message}</p>}

          <div className="max-h-[440px] overflow-auto space-y-2">
            {rows.map((row) => (
              <div key={row.booking_id} className="border border-[#2A2A2A] rounded-xl p-3 text-xs space-y-2">
                <p className="text-white">{row.booking_id}</p>
                <p className="text-gray-400">{row.provider_name} - {row.customer_name}</p>
                <p className="text-gray-500">{new Date(row.scheduled_start).toLocaleString()}</p>
                <div className="flex gap-2">
                  {['pending', 'confirmed', 'completed', 'cancelled'].map((status) => (
                    <button
                      key={status}
                      type="button"
                      onClick={() => updateStatus(row.booking_id, status)}
                      className={[
                        'px-2 py-1 rounded border text-[11px]',
                        row.status === status ? 'border-[#F5F5F0]/50 text-white' : 'border-[#333333] text-gray-400',
                      ].join(' ')}
                    >
                      {status}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4 space-y-3">
          <p className="text-sm font-semibold">Create booking manually</p>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Provider ID" value={manual.provider_id} onChange={(v) => setManual((p) => ({ ...p, provider_id: v }))} />
            <Field label="Customer email" value={manual.customer_email} onChange={(v) => setManual((p) => ({ ...p, customer_email: v }))} />
            <Field label="Customer name" value={manual.customer_name} onChange={(v) => setManual((p) => ({ ...p, customer_name: v }))} />
            <Field label="Service" value={manual.service_name} onChange={(v) => setManual((p) => ({ ...p, service_name: v }))} />
            <Field label="Start (ISO)" value={manual.scheduled_start} onChange={(v) => setManual((p) => ({ ...p, scheduled_start: v }))} />
            <Field label="End (ISO)" value={manual.scheduled_end} onChange={(v) => setManual((p) => ({ ...p, scheduled_end: v }))} />
            <Field label="Price ex VAT" value={manual.unit_price_ex_vat} onChange={(v) => setManual((p) => ({ ...p, unit_price_ex_vat: v }))} />
            <Field label="Status" value={manual.status} onChange={(v) => setManual((p) => ({ ...p, status: v }))} />
          </div>
          <button type="button" onClick={createManual} className="px-3 py-2 bg-white text-black rounded-lg text-xs font-semibold">Create booking</button>
        </section>
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
