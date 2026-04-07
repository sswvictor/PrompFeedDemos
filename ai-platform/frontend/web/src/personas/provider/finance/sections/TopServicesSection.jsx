import { Badge, Caption, Card, SectionHeader } from '../../../../components/ui';

export default function TopServicesSection({ services }) {
  if (!services?.length) return null;

  return (
    <Card className="space-y-3">
      <div>
        <SectionHeader label="Top services" className="mt-0 mb-1 px-0" />
        <Caption>What is repeatedly selling should influence pricing, bundling, and staffing.</Caption>
      </div>
      {services.map((service, index) => (
        <div
          key={service.name}
          className={`flex items-center justify-between ${index < services.length - 1 ? 'pb-3 border-b border-fixme-border/50' : ''}`}
        >
          <p className="text-fixme-text-primary text-sm">{service.name}</p>
          <Badge>{service.count}x</Badge>
        </div>
      ))}
    </Card>
  );
}
