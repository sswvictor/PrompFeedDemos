import { useBooking } from '../hooks/useBooking';

export default function ProviderHeader({ compact = false }) {
  const { provider } = useBooking();

  if (!provider) return null;

  return (
    <div className={`flex items-center gap-3 ${compact ? 'py-2' : 'py-4'}`}>
      {/* Provider avatar */}
      <div className="w-12 h-12 rounded-full bg-fixme-card border border-fixme-border overflow-hidden flex-shrink-0">
        {provider.image_url ? (
          <img
            src={provider.image_url}
            alt={provider.name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-fixme-accent text-lg font-semibold">
            {provider.name?.charAt(0)}
          </div>
        )}
      </div>

      <div className="flex-1 min-w-0">
        <h2 className="text-fixme-text-primary font-semibold text-base truncate">{provider.name}</h2>
        <div className="flex items-center gap-2 text-sm text-fixme-text-secondary">
          {provider.city && <span>{provider.city}</span>}
          {provider.rating && (
            <>
              <span>·</span>
              <span className="flex items-center gap-0.5">
                <svg className="w-3.5 h-3.5 text-fixme-accent" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                </svg>
                {provider.rating}
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
