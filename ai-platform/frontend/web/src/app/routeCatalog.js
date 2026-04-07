export const ROUTES = {
  auth: {
    start: '/auth',
  },
  customer: {
    welcome: '/customer/welcome',
    onboarding: '/customer/onboarding',
    login: '/customer/login',
    home: '/customer/home',
    search: '/customer/search',
    profile: '/customer/profile',
    settings: '/customer/settings',
    myData: '/customer/my-data',
  },
  provider: {
    welcome: '/provider/welcome',
    onboarding: '/provider/onboarding',
    login: '/provider/login',
    profile: '/provider/profile',
    home: '/provider/home',
    finance: '/provider/finance',
    settings: '/provider/settings',
    calendarCallback: '/provider/calendar/callback',
  },
  salon: {
    onboarding: '/salon/onboarding',
    login: '/salon/login',
    home: '/salon/home',
    profile: '/salon/profile',
    settings: '/salon/settings',
  },
  demo: {
    aiChat: '/demo/chat',
  },
  fixmeapp: {
    chat: '/fixmeapp/chat',
  },
  legacy: {
    onboardingRoot: '/onboard',
    customerOnboarding: '/onboard/customer',
    providerOnboarding: '/onboard/provider',
    providerSettings: '/settings',
    providerInsights: '/provider/insights',
  },
  admin: {
    home: '/admin',
    operations: '/admin/operations',
    bookings: '/admin/bookings',
    reports: '/admin/reports',
    accounts: '/admin/accounts',
    levels: '/admin/levels',
    audit: '/admin/audit',
    verifications: '/admin/verifications',
    gdprRequests: '/admin/gdpr-requests',
  },
};

export const CUSTOMER_PREFIXES = ['/customer/'];
export const PROVIDER_PREFIXES = ['/provider/'];
export const SALON_PREFIXES = ['/salon/'];

export function isCustomerRoute(path) {
  return CUSTOMER_PREFIXES.some((prefix) => path.startsWith(prefix));
}

export function isProviderRoute(path) {
  return PROVIDER_PREFIXES.some((prefix) => path.startsWith(prefix));
}

export function isSalonRoute(path) {
  return SALON_PREFIXES.some((prefix) => path.startsWith(prefix));
}
