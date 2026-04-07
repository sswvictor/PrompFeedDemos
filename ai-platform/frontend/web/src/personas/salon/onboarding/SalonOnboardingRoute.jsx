import { useEffect } from 'react';
import ProviderFlow from '../../provider/onboarding/ProviderFlow';

export default function SalonOnboardingRoute() {
  useEffect(() => {
    localStorage.setItem('fixme_provider_persona', 'salon');
    const url = new URL(window.location.href);
    if (url.searchParams.get('type') !== 'salon') {
      url.searchParams.set('type', 'salon');
      window.history.replaceState({}, '', `${url.pathname}?${url.searchParams.toString()}`);
    }
  }, []);

  return <ProviderFlow mode="onboarding" />;
}


