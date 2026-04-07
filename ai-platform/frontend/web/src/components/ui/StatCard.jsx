export function StatCard({
  label,
  value,
  change,
  positive,
  size = 'md',
  hero = false,
  className = '',
}) {
  const valueSize = {
    sm: 'text-[22px] leading-[28px]',
    md: 'text-[28px] leading-[34px]',
    lg: 'text-[38px] leading-[44px]',
  };

  const labelSize = {
    sm: 'text-xs',
    md: 'text-[13px]',
    lg: 'text-sm',
  };

  const changeColor =
    positive === true
      ? 'text-emerald-300'
      : positive === false
        ? 'text-red-300'
        : 'text-fixme-text-muted';

  const wrapper = hero
    ? `px-1 py-1 ${className}`
    : `bg-fixme-card border border-fixme-border rounded-2xl px-5 py-5 ${className}`;

  return (
    <div className={wrapper}>
      <p className={`${labelSize[size]} font-medium mb-2 uppercase tracking-wider text-fixme-text-muted`}>
        {label}
      </p>

      <div className="flex items-end gap-2">
        <p className={`${valueSize[size]} font-bold tracking-tight text-fixme-text-primary`}>
          {value}
        </p>
        {change && (
          <p className={`text-sm font-semibold mb-1 ${changeColor}`}>{change}</p>
        )}
      </div>
    </div>
  );
}
