export function SegmentedControl({
  options,
  activeIndex,
  onChange,
  className = '',
}) {
  return (
    <div className={`grid bg-fixme-bg border border-fixme-border rounded-2xl p-1 gap-1 ${className}`.trim()} style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}>
      {options.map((option, index) => {
        const label = typeof option === 'string' ? option : option.label;
        const key = typeof option === 'string' ? option : option.id;
        const isActive = activeIndex === index;

        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(index)}
            className={`
              rounded-xl px-3 py-2.5 text-[13px] font-semibold tracking-tight transition-colors
              ${isActive
                ? 'bg-fixme-card border border-fixme-border text-fixme-text-primary'
                : 'text-fixme-text-muted hover:text-fixme-text-secondary'}
            `.trim()}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
