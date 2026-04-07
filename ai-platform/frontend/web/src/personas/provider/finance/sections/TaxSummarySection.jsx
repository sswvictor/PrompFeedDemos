import { Caption, Card, SectionHeader } from '../../../../components/ui';
import { fmtSek } from '../financeUtils';

export default function TaxSummarySection({
  summary,
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
}) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <SectionHeader label="Tax summary" className="mt-0 mb-1 px-0" />
          <Caption>Set a date range for export checks.</Caption>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <label className="text-xs text-fixme-text-muted space-y-1">
          <span>Start</span>
          <input type="date" value={startDate} onChange={(e) => onStartDateChange(e.target.value)} className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2 text-fixme-text-primary" />
        </label>
        <label className="text-xs text-fixme-text-muted space-y-1">
          <span>End</span>
          <input type="date" value={endDate} onChange={(e) => onEndDateChange(e.target.value)} className="w-full bg-fixme-bg border border-fixme-border rounded-xl px-3 py-2 text-fixme-text-primary" />
        </label>
      </div>
      {summary && (
        <div className="grid grid-cols-2 gap-3">
          <Card variant="soft" padding="sm">
            <p className="text-fixme-text-muted text-[11px] uppercase">Revenue ex VAT</p>
            <p className="text-fixme-text-primary text-sm font-semibold mt-1">{fmtSek(summary.revenue_ex_vat)}</p>
          </Card>
          <Card variant="soft" padding="sm">
            <p className="text-fixme-text-muted text-[11px] uppercase">VAT collected</p>
            <p className="text-fixme-text-primary text-sm font-semibold mt-1">{fmtSek(summary.vat_collected)}</p>
          </Card>
          <Card variant="soft" padding="sm">
            <p className="text-fixme-text-muted text-[11px] uppercase">Revenue inc VAT</p>
            <p className="text-fixme-text-primary text-sm font-semibold mt-1">{fmtSek(summary.revenue_inc_vat)}</p>
          </Card>
          <Card variant="soft" padding="sm">
            <p className="text-fixme-text-muted text-[11px] uppercase">Unpaid</p>
            <p className="text-fixme-text-primary text-sm font-semibold mt-1">{summary.unpaid_count || 0}</p>
          </Card>
        </div>
      )}
    </Card>
  );
}
