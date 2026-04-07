import { Badge, Caption, Card, InfoCard, SectionHeader } from '../../../../components/ui';
import { fmtSek, periodLabel } from '../financeUtils';

export default function FinanceAgentBriefSection({ summary, insights, period, revenueChange }) {
  const topService = summary?.top_services?.[0] || insights?.top_services?.[0];

  return (
    <Card variant="soft" className="space-y-4 border-fixme-accent/20">
      <div className="flex items-start justify-between gap-3">
        <div>
          <SectionHeader label="AI finance department" className="mt-0 mb-2 px-0" labelClassName="text-fixme-accent" />
          <h2 className="text-fixme-text-primary text-xl font-bold mt-2">Run bookkeeping, tax prep, and cash follow-up from one place.</h2>
        </div>
        <Badge size="md">MVP</Badge>
      </div>

      <Caption variant="secondary" className="leading-6">
        The AI can already act like a finance ops agent for {periodLabel(period).toLowerCase()}: it watches revenue,
        flags unpaid work, and estimates what should be reserved for VAT before the provider pays themselves.
      </Caption>

      <div className="grid grid-cols-3 gap-3">
        <Card variant="default" padding="sm">
          <p className="text-fixme-text-muted text-[11px] uppercase">VAT reserve</p>
          <p className="text-fixme-text-primary text-sm font-semibold mt-1">{fmtSek(summary?.vat_collected)}</p>
        </Card>
        <Card variant="default" padding="sm">
          <p className="text-fixme-text-muted text-[11px] uppercase">Cash at risk</p>
          <p className="text-fixme-text-primary text-sm font-semibold mt-1">{fmtSek(summary?.unpaid_amount)}</p>
        </Card>
        <Card variant="default" padding="sm">
          <p className="text-fixme-text-muted text-[11px] uppercase">Best seller</p>
          <p className="text-fixme-text-primary text-sm font-semibold mt-1 truncate">{topService?.name || 'No data yet'}</p>
        </Card>
      </div>

      {revenueChange && (
        <InfoCard
          icon={revenueChange.positive ? 'Up' : 'Down'}
          variant={revenueChange.positive ? 'success' : 'error'}
          title={`Revenue is ${revenueChange.positive ? 'up' : 'down'} ${revenueChange.text.replace('+', '')} vs the previous period.`}
          description="This is where the AI should explain what changed, not just show a chart."
        />
      )}
    </Card>
  );
}
