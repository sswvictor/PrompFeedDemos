export function Badge({
  children,
  variant = 'default',
  size = 'sm',
  dot = false,
  className = '',
}) {
  const variantStyles = {
    success: {
      container: 'bg-emerald-400/10 border border-emerald-400/20',
      text: 'text-emerald-300',
      dot: 'bg-emerald-300',
    },
    error: {
      container: 'bg-red-400/10 border border-red-400/20',
      text: 'text-red-300',
      dot: 'bg-red-300',
    },
    warning: {
      container: 'bg-amber-400/10 border border-amber-400/20',
      text: 'text-amber-300',
      dot: 'bg-amber-300',
    },
    neutral: {
      container: 'bg-white/5 border border-fixme-border',
      text: 'text-fixme-text-muted',
      dot: 'bg-fixme-text-muted',
    },
    default: {
      container: 'bg-fixme-card border border-fixme-border',
      text: 'text-fixme-text-secondary',
      dot: 'bg-fixme-text-secondary',
    },
  };

  const sizeStyles = {
    sm: { text: 'text-[11px]', space: 'px-2.5 py-[3px]', dot: 'w-[5px] h-[5px]' },
    md: { text: 'text-[13px]', space: 'px-3 py-1', dot: 'w-1.5 h-1.5' },
  };

  const style = variantStyles[variant];
  const sizeStyle = sizeStyles[size];

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full ${style.container} ${style.text} ${sizeStyle.space} ${className}`.trim()}
    >
      {dot && <span className={`${sizeStyle.dot} rounded-full ${style.dot}`} />}
      <span className={`${sizeStyle.text} font-semibold`}>{children}</span>
    </span>
  );
}
