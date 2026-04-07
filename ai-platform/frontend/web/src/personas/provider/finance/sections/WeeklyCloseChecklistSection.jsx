import { Caption, Card, SectionHeader } from '../../../../components/ui';

export default function WeeklyCloseChecklistSection({ items }) {
  return (
    <Card className="space-y-4">
      <div>
        <SectionHeader label="Accountant-style weekly close" className="mt-0 mb-1 px-0" />
        <Caption>This is the behavior we want from the AI, even before full filing automation exists.</Caption>
      </div>

      <div className="space-y-3">
        {items.map((item, index) => (
          <div key={item.title} className="flex gap-3 items-start">
            <div className="w-6 h-6 rounded-full bg-fixme-accent/12 border border-fixme-accent/20 flex items-center justify-center text-fixme-accent text-xs font-bold shrink-0">
              {index + 1}
            </div>
            <div>
              <p className="text-fixme-text-primary text-sm font-medium">{item.title}</p>
              <Caption className="text-xs mt-1 leading-5">{item.body}</Caption>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
