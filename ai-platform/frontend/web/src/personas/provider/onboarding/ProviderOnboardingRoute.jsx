import { useEffect } from 'react';
import ProviderFlow from './ProviderFlow';

export default function ProviderOnboardingRoute() {
  useEffect(() => {
    localStorage.setItem('fixme_provider_persona', 'provider');
    const url = new URL(window.location.href);
    if (url.searchParams.get('type') !== 'freelancer') {
      url.searchParams.set('type', 'freelancer');
      window.history.replaceState({}, '', `${url.pathname}?${url.searchParams.toString()}`);
    }
  }, []);

  return <ProviderFlow mode="onboarding" />;
}


