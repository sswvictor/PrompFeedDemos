export function SectionHeader({
  label,
  count,
  actionLabel,
  onAction,
  className = '',
  labelClassName = '',
}) {
  return (
    <div className={`flex items-center mt-1 mb-3 px-1 ${className}`.trim()}>
      <p className={`flex-1 text-xs font-semibold uppercase tracking-widest text-fixme-text-muted ${labelClassName}`.trim()}>
        {label}
      </p>

      {count !== undefined && (
        <div className="bg-fixme-bg border border-fixme-border rounded-full px-2 py-0.5 mr-2">
          <span className="text-[11px] font-semibold text-fixme-text-muted">{count}</span>
        </div>
      )}

      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="text-xs font-medium text-fixme-text-secondary underline"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
