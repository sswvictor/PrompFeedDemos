import { useEffect } from 'react';
import ProviderFlow from '../onboarding/ProviderFlow';

export default function ProviderLoginRoute() {
  useEffect(() => {
    localStorage.setItem('fixme_provider_persona', 'provider');
    const url = new URL(window.location.href);
    if (url.searchParams.get('type') !== 'freelancer') {
      url.searchParams.set('type', 'freelancer');
      window.history.replaceState({}, '', `/provider/login?${url.searchParams.toString()}`);
    }
  }, []);

  return <ProviderFlow mode="login" />;
}


