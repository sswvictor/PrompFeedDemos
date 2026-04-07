import { useEffect, useRef } from 'react';
import { BookingProvider, useBooking } from './hooks/useBooking';
import { getProvider, getProviderBySlug } from './api/bookingApi';
import ErrorBoundary from './components/ErrorBoundary';
import LoadingScreen from './components/LoadingScreen';
import StepProgress from './components/StepProgress';
import BookingEntry from './features/booking/flow/BookingEntry';
import LocationStep from './features/booking/flow/LocationStep';
import ServicesStep from './features/booking/flow/ServicesStep';
import DateTimeStep from './features/booking/flow/DateTimeStep';
import ConfirmStep from './features/booking/flow/ConfirmStep';
import BookingConfirmed from './features/booking/flow/BookingConfirmed';
import WaitlistStep from './features/booking/flow/WaitlistStep';
import ProviderSettingsPage from './personas/provider/profile/ProviderSettingsPage';
import DemoAiChat from './features/chat/provider/DemoAiChatPage';
import FixmeappChat from './features/chat/discovery/FixmeappChatPage';
import ProviderWelcomePage from './personas/provider/onboarding/ProviderWelcomePage';
import ProviderOnboardingRoute from './personas/provider/onboarding/ProviderOnboardingRoute';
import ProviderLoginRoute from './personas/provider/auth/ProviderLoginRoute';
import ProviderProfilePage from './personas/provider/profile/ProviderProfilePage';
import ProviderHomePage from './personas/provider/home/ProviderHomePage';
import ProviderFinancePage from './personas/provider/home/ProviderFinancePage';
import CustomerWelcomePage from './personas/customer/onboarding/CustomerWelcomePage';
import CustomerOnboardingRoute from './personas/customer/onboarding/CustomerOnboardingRoute';
import CustomerLoginRoute from './personas/customer/auth/CustomerLoginRoute';
import CustomerHomePage from './personas/customer/home/CustomerHomePage';
import CustomerSearchPage from './personas/customer/search/CustomerSearchPage';
import CustomerProfilePage from './personas/customer/profile/CustomerProfilePage';
import CustomerSettingsPage from './personas/customer/settings/CustomerSettingsPage';
import CustomerDataPage from './personas/customer/data/CustomerDataPage';
import SalonOnboardingRoute from './personas/salon/onboarding/SalonOnboardingRoute';
import SalonLoginRoute from './personas/salon/auth/SalonLoginRoute';
import SalonHomePage from './personas/salon/home/SalonHomePage';
import SalonProfilePage from './personas/salon/profile/SalonProfilePage';
import SalonSettingsPage from './personas/salon/profile/SalonSettingsPage';
import { ROUTES, isProviderRoute, isSalonRoute } from './app/routeCatalog';
import { captureReferralFromSearch, normalizeReferralSource } from './utils/referralTracking';
import CalendarCallbackPage from './personas/provider/calendar/CalendarCallbackPage';
import AdminHomePage from './pages/admin/AdminHomePage';
import AdminOperationsPage from './pages/admin/AdminOperationsPage';
import AdminBookingsPage from './pages/admin/AdminBookingsPage';
import AdminReportsPage from './pages/admin/AdminReportsPage';
import AdminAccountsPage from './pages/admin/AdminAccountsPage';
import AdminLevelsPage from './pages/admin/AdminLevelsPage';
import AdminAuditPage from './pages/admin/AdminAuditPage';
import AdminVerificationsPage from './pages/admin/AdminVerificationsPage';
import AdminGdprPage from './pages/admin/AdminGdprPage';

function BookingFlow() {
  const { currentStep, provider, dispatch } = useBooking();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const path = window.location.pathname;
    const referralFromUrl = normalizeReferralSource(params.get('ref'));

    if (referralFromUrl) {
      dispatch({ type: 'SET_REFERRAL_SOURCE', payload: referralFromUrl });
    }

    const slugMatch = path.match(/^\/b\/([a-z0-9-]+)/);
    if (slugMatch) {
      const slug = slugMatch[1];
      const ref = referralFromUrl || 'provider_link';
      dispatch({ type: 'SET_REFERRAL_SOURCE', payload: ref });
      captureReferralFromSearch(window.location.search, { slug });

      getProviderBySlug(slug)
        .then((data) => getProvider(data.provider_id))
        .then((data) => dispatch({ type: 'SET_PROVIDER', payload: data }))
        .catch((err) => dispatch({ type: 'SET_ERROR', payload: err.message }));
      return;
    }

    const providerId = params.get('provider') || params.get('provider_id');
    const pathMatch = path.match(/\/book\/([a-f0-9-]+)/i);
    const id = providerId || (pathMatch && pathMatch[1]);

    if (id && !provider) {
      captureReferralFromSearch(window.location.search, { providerId: id });
      getProvider(id)
        .then((data) => dispatch({ type: 'SET_PROVIDER', payload: data }))
        .catch((err) => dispatch({ type: 'SET_ERROR', payload: err.message }));
    }
  }, []);

  // Rebook shortcut: ?rebook=1
  // Runs once provider is loaded --- pre-fills service and jumps to Confirm step
  useEffect(() => {
    if (!provider) return;
    const params = new URLSearchParams(window.location.search);
    if (params.get('rebook') !== '1') return;

    const rebookKey = `fixme_rebook_${provider.provider_id}`;
    let rebookData = null;
    try { rebookData = JSON.parse(localStorage.getItem(rebookKey) || 'null'); } catch {}
    if (!rebookData) return;

    dispatch({ type: 'SET_SERVICES', payload: [{
      service_id: rebookData.service_id,
      name: rebookData.service_name,
      duration_minutes: rebookData.duration_minutes,
      price_ex_vat: rebookData.price_ex_vat,
    }]});
    dispatch({ type: 'SET_LOCATION_TYPE', payload: 'salon' });
    dispatch({ type: 'SET_BOOKING_PATH', payload: 'rebook' });
    dispatch({ type: 'SET_STEP', payload: 3 });
  }, [provider]);

  if (!provider) {
    return <LoadingScreen message={"Preparing your booking\u2026"} />;
  }

  const renderStep = () => {
    switch (currentStep) {
      case 0: return <BookingEntry />;
      case 1: return <LocationStep />;
      case 2: return <ServicesStep />;
      case 3: return <DateTimeStep />;
      case 4: return <ConfirmStep />;
      case 5: return <BookingConfirmed />;
      case 6: return <WaitlistStep />;
      default: return <BookingEntry />;
    }
  };

  const showHeader = currentStep < 5 || currentStep === 6;
  const showProgress = currentStep > 0 && currentStep < 5;

  return (
    <div className="flex flex-col min-h-screen">
      {showHeader && (
        <div className="sticky top-0 z-10 bg-fixme-bg/95 backdrop-blur-sm border-b border-fixme-border/50 px-4 pb-1">
          <div className="flex items-center justify-center pt-3 pb-1">
            <span className="text-fixme-text-primary font-bold text-lg tracking-tight">Fixmeapp</span>
          </div>
          {showProgress && <StepProgress />}
        </div>
      )}
      <div className="flex-1 px-4 pt-2 pb-6">
        {renderStep()}
      </div>
    </div>
  );
}

function AppWithErrorBoundary() {
  const resetKey = useRef(0);

  const handleReset = () => {
    resetKey.current += 1;
    window.dispatchEvent(new CustomEvent('booking-reset', { detail: resetKey.current }));
  };

  return (
    <ErrorBoundary onReset={handleReset}>
      <BookingProvider key={resetKey.current}>
        <BookingFlow />
      </BookingProvider>
    </ErrorBoundary>
  );
}

function redirectTo(path) {
  window.location.replace(path);
  return null;
}

export default function App() {
  const path = window.location.pathname;
  const searchParams = new URLSearchParams(window.location.search);
  const hasBookingEntryParams = Boolean(searchParams.get('provider') || searchParams.get('provider_id'));
  const hasProviderSession = Boolean(localStorage.getItem('fixme_provider_token'));
  const providerPersona = localStorage.getItem('fixme_provider_persona') === 'salon' ? 'salon' : 'provider';
  const providerLanding = providerPersona === 'salon' ? ROUTES.salon.home : ROUTES.provider.home;

  if (path === '/' && !hasBookingEntryParams) {
    if (hasProviderSession) return redirectTo(providerLanding);
    return redirectTo(ROUTES.provider.welcome);
  }

  // Legacy URL redirects
  if (path === ROUTES.legacy.onboardingRoot) return redirectTo(ROUTES.provider.welcome);
  if (path === ROUTES.legacy.customerOnboarding) return redirectTo(ROUTES.customer.welcome);
  if (path.startsWith(ROUTES.legacy.providerOnboarding)) {
    const type = new URLSearchParams(window.location.search).get('type');
    return type === 'salon' ? redirectTo(ROUTES.salon.onboarding) : redirectTo(ROUTES.provider.onboarding);
  }
  if (path.startsWith(ROUTES.legacy.providerSettings)) return redirectTo(providerLanding);

  // Google OAuth callback — must be matched BEFORE the cross-persona guardrail so
  // the browser isn't redirected away while exchanging the OAuth code.
  if (path === ROUTES.provider.calendarCallback) {
    return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><CalendarCallbackPage /></div>;
  }

  // Cross-persona guardrails: logged-in provider stays in their persona
  if (
    hasProviderSession
    && (
      (providerPersona === 'salon' ? isProviderRoute(path) : isSalonRoute(path))
      || path === ROUTES.legacy.onboardingRoot
      || path === (providerPersona === 'salon' ? ROUTES.salon.login : ROUTES.provider.login)
      || path === (providerPersona === 'salon' ? ROUTES.salon.onboarding : ROUTES.provider.onboarding)
      || path.startsWith('/b/')
      || path.startsWith('/book')
      || path === '/'
    )
  ) {
    return redirectTo(providerLanding);
  }

  // /auth is archived --- redirect to /provider/welcome
  if (path === ROUTES.auth.start) return redirectTo(ROUTES.provider.welcome);

  // Provider welcome (cinematic splash + auth entry)
  if (path === ROUTES.provider.welcome) return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><ProviderWelcomePage /></div>;

  // Provider POV
  if (path === ROUTES.provider.onboarding) return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><ProviderOnboardingRoute /></div>;
  if (path === ROUTES.provider.login) return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><ProviderLoginRoute /></div>;
  if (path === ROUTES.provider.profile) return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><ProviderProfilePage /></div>;
  if (path === ROUTES.provider.home) return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><ProviderHomePage /></div>;
  if (path === ROUTES.provider.finance) return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><ProviderFinancePage /></div>;
  if (path === ROUTES.legacy.providerInsights) return redirectTo(`${ROUTES.provider.home}?view=inbox`);
  if (path === ROUTES.provider.settings) return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><ProviderSettingsPage /></div>;

  // Customer POV
  if (path === ROUTES.customer.welcome) return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><CustomerWelcomePage /></div>;
  if (path === ROUTES.customer.onboarding) return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><CustomerOnboardingRoute /></div>;
  if (path === ROUTES.customer.login) return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><CustomerLoginRoute /></div>;
  if (path === ROUTES.customer.home) return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><CustomerHomePage /></div>;
  if (path === ROUTES.customer.search) return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><CustomerSearchPage /></div>;
  if (path === ROUTES.customer.profile) return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><CustomerProfilePage /></div>;
  if (path === ROUTES.customer.settings) return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><CustomerSettingsPage /></div>;
  if (path === ROUTES.customer.myData) return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><CustomerDataPage /></div>;

  // Salon POV
  if (path === ROUTES.salon.onboarding) return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><SalonOnboardingRoute /></div>;
  if (path === ROUTES.salon.login) return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><SalonLoginRoute /></div>;
  if (path === ROUTES.salon.home) return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><SalonHomePage /></div>;
  if (path === ROUTES.salon.profile) return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><SalonProfilePage /></div>;
  if (path === ROUTES.salon.settings) return <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen"><SalonSettingsPage /></div>;

  // Internal ops
  if (path === ROUTES.admin.home) return <AdminHomePage />;
  if (path === ROUTES.admin.operations) return <AdminOperationsPage />;
  if (path === ROUTES.admin.bookings) return <AdminBookingsPage />;
  if (path === ROUTES.admin.reports) return <AdminReportsPage />;
  if (path === ROUTES.admin.accounts) return <AdminAccountsPage />;
  if (path === ROUTES.admin.levels) return <AdminLevelsPage />;
  if (path === ROUTES.admin.audit) return <AdminAuditPage />;
  if (path === ROUTES.admin.verifications) return <AdminVerificationsPage />;
  if (path === ROUTES.admin.gdprRequests) return <AdminGdprPage />;

  if (path === ROUTES.demo.aiChat) return <DemoAiChat />;
  if (path === ROUTES.fixmeapp.chat) return <FixmeappChat />;

  // Public provider profile --- /p/{slug} (SEO links) or /pid/{provider_id} (from search results)
  if (path.startsWith('/p/') || path.startsWith('/pid/')) {
    return (
      <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen">
        <ProviderProfilePage />
      </div>
    );
  }

  // Default: booking flow (public-facing widget for booking via provider link)
  return (
    <div className="w-full max-w-md mx-auto bg-fixme-bg min-h-screen">
      <AppWithErrorBoundary />
    </div>
  );
}
