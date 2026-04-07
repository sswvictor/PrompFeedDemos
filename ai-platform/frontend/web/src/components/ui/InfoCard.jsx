export function InfoCard({
  title,
  description,
  icon,
  variant = 'info',
  className = '',
}) {
  const variantStyles = {
    info: {
      container: 'bg-fixme-card border border-fixme-border',
      title: 'text-fixme-text-primary',
      body: 'text-fixme-text-muted',
    },
    success: {
      container: 'bg-emerald-400/8 border border-emerald-400/25',
      title: 'text-emerald-300',
      body: 'text-fixme-text-secondary',
    },
    warning: {
      container: 'bg-amber-400/8 border border-amber-400/25',
      title: 'text-amber-300',
      body: 'text-fixme-text-secondary',
    },
    error: {
      container: 'bg-red-400/8 border border-red-400/25',
      title: 'text-red-300',
      body: 'text-fixme-text-secondary',
    },
  };

  const style = variantStyles[variant];

  return (
    <div className={`flex items-start rounded-2xl px-5 py-5 gap-4 ${style.container} ${className}`.trim()}>
      {icon && (
        <span className="text-2xl leading-7 mt-[1px]">{icon}</span>
      )}

      <div className="flex-1">
        <p className={`text-[15px] font-semibold leading-snug ${style.title}`}>{title}</p>
        {description && (
          <p className={`text-[13px] leading-[19px] mt-1.5 ${style.body}`}>{description}</p>
        )}
      </div>
    </div>
  );
}
