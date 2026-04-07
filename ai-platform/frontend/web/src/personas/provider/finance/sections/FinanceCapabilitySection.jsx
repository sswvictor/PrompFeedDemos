import { Badge, Caption, Card, InfoCard, SectionHeader } from '../../../../components/ui';
import { FINANCE_CAPABILITIES } from '../financeConfig';

export default function FinanceCapabilitySection() {
  return (
    <div className="space-y-3">
      <div>
        <SectionHeader label="What the AI can own" className="mt-0 mb-1 px-0" />
        <Caption>Position it as a finance department agent first, and a licensed-accountant replacement only where regulation allows.</Caption>
      </div>

      <div className="grid gap-3">
        {FINANCE_CAPABILITIES.map((capability) => (
          <Card key={capability.title} padding="sm">
            <div className="flex items-center justify-between gap-3">
              <p className="text-fixme-text-primary text-sm font-semibold">{capability.title}</p>
              <Badge variant={capability.status === 'Ready now' ? 'success' : 'default'}>{capability.status}</Badge>
            </div>
            <Caption variant="secondary" className="text-xs leading-5 mt-2">{capability.body}</Caption>
          </Card>
        ))}
      </div>

      <InfoCard
        icon="AI"
        title="Can we help like an accountant?"
        description="Yes for bookkeeping support, VAT prep, payment reconciliation, and clean handoff exports. For legal tax advice, payroll filings, and country-specific compliance, the safer product stance is AI plus accountant review until those workflows are built and localized."
      />
    </div>
  );
}
