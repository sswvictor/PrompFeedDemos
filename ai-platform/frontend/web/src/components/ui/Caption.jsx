export function Caption({
  children,
  variant = 'default',
  center = false,
  className = '',
}) {
  const variantClass = {
    default: 'text-fixme-text-muted',
    secondary: 'text-fixme-text-secondary',
    error: 'text-red-400',
    success: 'text-emerald-400',
  };

  return (
    <p
      className={`text-sm leading-[21px] ${variantClass[variant]} ${center ? 'text-center' : ''} ${className}`.trim()}
    >
      {children}
    </p>
  );
}
