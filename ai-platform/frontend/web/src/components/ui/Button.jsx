export function Button({
  children,
  onClick,
  onPress,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  fullWidth = false,
  className = '',
  type = 'button',
}) {
  const handleClick = onClick || onPress;
  const isDisabled = disabled || loading;

  const containerSize = {
    sm: 'px-4 py-2.5 rounded-2xl',
    md: 'px-6 py-3.5 rounded-full',
    lg: 'px-8 py-4 rounded-full',
  };

  const textSize = {
    sm: 'text-[13px]',
    md: 'text-[15px]',
    lg: 'text-base',
  };

  const variantContainer = {
    primary: 'bg-fixme-accent text-fixme-bg',
    ghost: 'border border-fixme-border bg-transparent text-fixme-text-primary',
    destructive: 'border border-red-400/50 bg-transparent text-red-300',
  };

  const variantText = {
    primary: 'font-bold',
    ghost: 'font-semibold',
    destructive: 'font-semibold',
  };

  return (
    <button
      type={type}
      onClick={isDisabled ? undefined : handleClick}
      disabled={isDisabled}
      className={`
        inline-flex items-center justify-center
        ${containerSize[size]}
        ${variantContainer[variant]}
        ${fullWidth ? 'w-full' : ''}
        ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'transition-opacity hover:opacity-90'}
        ${className}
      `.trim()}
    >
      {loading ? (
        <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : (
        <span className={`${textSize[size]} ${variantText[variant]}`}>{children}</span>
      )}
    </button>
  );
}
