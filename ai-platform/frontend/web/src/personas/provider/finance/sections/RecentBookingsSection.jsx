import { Badge, Button, Caption, Card, Divider, SectionHeader } from '../../../../components/ui';
import { fmtSek, fmtShortDate } from '../financeUtils';

export default function RecentBookingsSection({
  bookings,
  loading,
  onMarkPaid,
  markingId,
}) {
  return (
    <div className="space-y-3">
      <div>
        <SectionHeader label="Recent bookings" className="mt-0 mb-1 px-0" />
        <Caption>Recent booking-to-cash events for follow-up and reconciliation.</Caption>
      </div>

      {loading ? (
        <Card className="flex items-center gap-3" padding="lg">
          <div className="w-5 h-5 border-2 border-fixme-accent border-t-transparent rounded-full animate-spin" />
          <Caption variant="secondary">Loading recent bookings...</Caption>
        </Card>
      ) : !bookings?.length ? (
        <Card padding="sm">
          <Caption>No recent booking activity yet.</Caption>
        </Card>
      ) : (
        <Card padding="none">
          {bookings.map((booking, index) => {
            const canMarkPaid = booking.status === 'completed' && booking.payment_status !== 'paid';
            const paymentVariant = booking.payment_status === 'paid' ? 'success' : 'warning';

            return (
              <div key={booking.booking_id}>
                {index > 0 && <Divider />}
                <div className="px-4 py-3 flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-fixme-text-primary text-sm font-medium truncate">{booking.customer_name || 'Guest'}</p>
                    <Caption className="text-xs mt-0.5 truncate">
                      {booking.service_name || 'Appointment'} / {fmtShortDate(booking.scheduled_start)}
                    </Caption>
                  </div>
                  <div className="text-right">
                    <p className="text-fixme-text-primary text-sm font-semibold">{fmtSek(booking.amount_inc_vat)}</p>
                    <div className="mt-1">
                      <Badge variant={paymentVariant}>{booking.payment_status === 'paid' ? 'Paid' : booking.payment_status || 'Unpaid'}</Badge>
                    </div>
                  </div>
                  {canMarkPaid && (
                    <Button
                      onClick={() => onMarkPaid(booking.booking_id)}
                      disabled={markingId === booking.booking_id}
                      loading={markingId === booking.booking_id}
                      variant="ghost"
                      size="sm"
                    >
                      Mark paid
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </Card>
      )}
    </div>
  );
}
