export function Card({
  children,
  onClick,
  onPress,
  variant = 'default',
  padding = 'md',
  className = '',
  type = 'button',
}) {
  const handleClick = onClick || onPress;

  const variantClass = {
    default: 'bg-fixme-card border border-fixme-border',
    soft: 'bg-fixme-bg border border-fixme-border/70',
    ghost: 'bg-transparent border border-fixme-border',
  };

  const paddingClass = {
    none: '',
    sm: 'px-4 py-3.5',
    md: 'px-5 py-5',
    lg: 'px-6 py-6',
  };

  const classes = `rounded-2xl overflow-hidden ${variantClass[variant]} ${paddingClass[padding]} ${className}`.trim();

  if (handleClick) {
    return (
      <button
        type={type}
        onClick={handleClick}
        className={`${classes} text-left transition-opacity hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-fixme-accent/30`}
      >
        {children}
      </button>
    );
  }

  return <div className={classes}>{children}</div>;
}
