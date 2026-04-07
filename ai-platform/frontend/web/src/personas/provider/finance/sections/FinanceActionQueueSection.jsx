import { Badge, Caption, Card, SectionHeader } from '../../../../components/ui';

export default function FinanceActionQueueSection({ actions }) {
  if (!actions.length) return null;

  return (
    <Card className="space-y-4">
      <div>
        <SectionHeader label="This week your agent would" className="mt-0 mb-1 px-0" />
        <Caption>A provider should feel like someone in finance is actively moving the numbers forward.</Caption>
      </div>

      <div className="space-y-3">
        {actions.map((action) => (
          <Card key={action.title} variant="soft" padding="sm">
            <div className="flex items-center justify-between gap-3">
              <p className="text-fixme-text-primary text-sm font-semibold">{action.title}</p>
              <Badge>{action.badge}</Badge>
            </div>
            <Caption variant="secondary" className="text-xs leading-5 mt-2">{action.body}</Caption>
          </Card>
        ))}
      </div>
    </Card>
  );
}
